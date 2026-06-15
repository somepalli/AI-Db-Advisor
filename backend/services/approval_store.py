"""
approval_store.py — Durable persistence for the approval lifecycle.

Backs ApprovalWorkflow with SQLite so PENDING/APPROVED/EXECUTED records survive
restarts, and records an append-only `audit_log` of every state transition.

Why SQLite + CREATE TABLE IF NOT EXISTS rather than a migration tool:
    This repo has no migration framework and no application database — it persists
    via JSON files, in-memory TTL stores, and ChromaDB. A self-initialising SQLite
    store is the lightweight, codebase-consistent way to get durable approvals and
    an immutable audit trail without introducing alembic + a DB engine.

Two tables:
  approvals  — current state of each approval (mutable rows, keyed by approval_id)
  audit_log  — append-only history; rows are NEVER updated or deleted by cleanup
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_DEFAULT_PATH = Path(__file__).parent.parent / "approvals.db"


def _db_path() -> Path:
    """Resolved at call time so tests can override APPROVALS_DB_FILE."""
    configured = os.getenv("APPROVALS_DB_FILE", "")
    if configured:
        return Path(configured)
    # Allow the settings object to provide it too, but env wins for test isolation.
    try:
        from ..config import settings
        if getattr(settings, "APPROVALS_DB_FILE", ""):
            return Path(settings.APPROVALS_DB_FILE)
    except Exception:
        pass
    return _DEFAULT_PATH


_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    approval_id     TEXT PRIMARY KEY,
    ds_id           TEXT NOT NULL,
    suggestion_json TEXT NOT NULL,
    status          TEXT NOT NULL,
    submitted_at    TEXT NOT NULL,
    submitted_by    TEXT,
    approved_by     TEXT,
    approved_at     TEXT,
    rejected_by     TEXT,
    rejected_at     TEXT,
    rejection_reason TEXT,
    executed_at     TEXT,
    result_json     TEXT,
    rollback_sql    TEXT,
    rollback_available INTEGER DEFAULT 0,
    error           TEXT,
    notes_json      TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    ds_id       TEXT,
    approval_id TEXT,
    actor       TEXT,
    action      TEXT NOT NULL,
    detail_json TEXT
);
CREATE TABLE IF NOT EXISTS scan_findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    ds_id       TEXT NOT NULL,
    scan_id     TEXT,
    status      TEXT NOT NULL,
    top_finding TEXT,
    approval_ids_json TEXT,
    blocked_count INTEGER DEFAULT 0,
    trace_length  INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_approvals_ds_status ON approvals(ds_id, status);
CREATE INDEX IF NOT EXISTS idx_audit_approval ON audit_log(approval_id);
CREATE INDEX IF NOT EXISTS idx_scan_findings_ds ON scan_findings(ds_id, ts DESC);
"""


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def init_db() -> None:
    """Idempotently create the schema (called lazily by _connect too)."""
    with _LOCK:
        conn = _connect()
        conn.commit()
        conn.close()


# --- record (de)serialization ------------------------------------------------

def _row_to_record(row: sqlite3.Row) -> Dict[str, Any]:
    """Reconstruct the dict shape ApprovalWorkflow/UI expect from a DB row."""
    return {
        "approval_id": row["approval_id"],
        "ds_id": row["ds_id"],
        "suggestion": json.loads(row["suggestion_json"]),
        "status": row["status"],
        "submitted_at": row["submitted_at"],
        "submitted_by": row["submitted_by"],
        "approved_at": row["approved_at"],
        "approved_by": row["approved_by"],
        "rejected_at": row["rejected_at"],
        "rejected_by": row["rejected_by"],
        "rejection_reason": row["rejection_reason"],
        "executed_at": row["executed_at"],
        "execution_result": json.loads(row["result_json"]) if row["result_json"] else None,
        "execution_error": row["error"],
        "rollback_sql": row["rollback_sql"],
        "rollback_available": bool(row["rollback_available"]),
        "notes": json.loads(row["notes_json"]) if row["notes_json"] else [],
    }


# --- approval CRUD -----------------------------------------------------------

def insert_approval(
    approval_id: str,
    ds_id: str,
    suggestion: Dict[str, Any],
    status: str,
    submitted_by: Optional[str] = None,
) -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO approvals
                   (approval_id, ds_id, suggestion_json, status, submitted_at, submitted_by, notes_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    approval_id, ds_id, json.dumps(suggestion), status,
                    datetime.utcnow().isoformat(), submitted_by, json.dumps([]),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def update_approval(approval_id: str, **fields: Any) -> None:
    """Update mutable columns. JSON fields (result/notes) are encoded automatically."""
    if not fields:
        return
    if "execution_result" in fields:
        fields["result_json"] = json.dumps(fields.pop("execution_result"))
    if "notes" in fields:
        fields["notes_json"] = json.dumps(fields.pop("notes"))
    if "rollback_available" in fields:
        fields["rollback_available"] = 1 if fields["rollback_available"] else 0
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                f"UPDATE approvals SET {cols} WHERE approval_id = ?",
                (*fields.values(), approval_id),
            )
            conn.commit()
        finally:
            conn.close()


def get_approval(approval_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
            return _row_to_record(row) if row else None
        finally:
            conn.close()


def list_by_status(ds_id: str, status: str) -> List[Dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE ds_id = ? AND status = ? ORDER BY submitted_at",
                (ds_id, status),
            ).fetchall()
            return [_row_to_record(r) for r in rows]
        finally:
            conn.close()


def list_history(ds_id: str, limit: int = 50, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Executed/failed/rolled-back records, newest first."""
    terminal = ("executed", "failed", "rolled_back")
    with _LOCK:
        conn = _connect()
        try:
            if status_filter:
                rows = conn.execute(
                    "SELECT * FROM approvals WHERE ds_id = ? AND status = ? "
                    "ORDER BY COALESCE(executed_at, submitted_at) DESC LIMIT ?",
                    (ds_id, status_filter, limit),
                ).fetchall()
            else:
                placeholders = ",".join("?" for _ in terminal)
                rows = conn.execute(
                    f"SELECT * FROM approvals WHERE ds_id = ? AND status IN ({placeholders}) "
                    "ORDER BY COALESCE(executed_at, submitted_at) DESC LIMIT ?",
                    (ds_id, *terminal, limit),
                ).fetchall()
            return [_row_to_record(r) for r in rows]
        finally:
            conn.close()


def counts_by_status(ds_id: str) -> Dict[str, int]:
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM approvals WHERE ds_id = ? GROUP BY status",
                (ds_id,),
            ).fetchall()
            return {r["status"]: r["n"] for r in rows}
        finally:
            conn.close()


# --- append-only audit -------------------------------------------------------

def append_audit(
    action: str,
    *,
    ds_id: Optional[str] = None,
    approval_id: Optional[str] = None,
    actor: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO audit_log (ts, ds_id, approval_id, actor, action, detail_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    datetime.utcnow().isoformat(), ds_id, approval_id, actor, action,
                    json.dumps(detail) if detail is not None else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def get_audit(approval_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            if approval_id:
                rows = conn.execute(
                    "SELECT * FROM audit_log WHERE approval_id = ? ORDER BY id DESC LIMIT ?",
                    (approval_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [
                {
                    "id": r["id"], "ts": r["ts"], "ds_id": r["ds_id"],
                    "approval_id": r["approval_id"], "actor": r["actor"],
                    "action": r["action"],
                    "detail": json.loads(r["detail_json"]) if r["detail_json"] else None,
                }
                for r in rows
            ]
        finally:
            conn.close()


# --- retention ---------------------------------------------------------------

def record_scan_finding(
    ds_id: str,
    scan_id: str,
    status: str,
    top_finding: Optional[str],
    approval_ids: list,
    blocked_count: int = 0,
    trace_length: int = 0,
) -> None:
    """Append one row to scan_findings; used by the agent for institutional memory."""
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO scan_findings
                   (ts, ds_id, scan_id, status, top_finding, approval_ids_json, blocked_count, trace_length)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.utcnow().isoformat(), ds_id, scan_id, status,
                    top_finding, json.dumps(approval_ids), blocked_count, trace_length,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def get_scan_findings(ds_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Return the most recent scan findings for a datasource (agent memory)."""
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM scan_findings WHERE ds_id = ? ORDER BY ts DESC LIMIT ?",
                (ds_id, limit),
            ).fetchall()
            return [
                {
                    "ts": r["ts"],
                    "ds_id": r["ds_id"],
                    "scan_id": r["scan_id"],
                    "status": r["status"],
                    "top_finding": r["top_finding"],
                    "approval_ids": json.loads(r["approval_ids_json"]) if r["approval_ids_json"] else [],
                    "blocked_count": r["blocked_count"],
                    "trace_length": r["trace_length"],
                }
                for r in rows
            ]
        finally:
            conn.close()


def get_audit_log(ds_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    """Return audit entries across all DSes or filtered to one DS, newest first."""
    with _LOCK:
        conn = _connect()
        try:
            if ds_id:
                rows = conn.execute(
                    "SELECT * FROM audit_log WHERE ds_id = ? ORDER BY id DESC LIMIT ?",
                    (ds_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [
                {
                    "id": r["id"], "ts": r["ts"], "ds_id": r["ds_id"],
                    "approval_id": r["approval_id"], "actor": r["actor"],
                    "action": r["action"],
                    "detail": json.loads(r["detail_json"]) if r["detail_json"] else None,
                }
                for r in rows
            ]
        finally:
            conn.close()


def cleanup_old_records(days: int = 30) -> int:
    """
    Delete terminal approval rows (EXPIRED / EXECUTED / REJECTED / FAILED /
    ROLLED_BACK) older than `days`. NEVER deletes audit_log rows — the audit
    trail is immutable. Returns the number of approval rows removed.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    terminal = ("expired", "executed", "rejected", "failed", "rolled_back")
    placeholders = ",".join("?" for _ in terminal)
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                f"DELETE FROM approvals WHERE status IN ({placeholders}) "
                "AND COALESCE(executed_at, rejected_at, submitted_at) < ?",
                (*terminal, cutoff),
            )
            conn.commit()
            removed = cur.rowcount
            logger.info(f"cleanup_old_records: removed {removed} terminal approval rows older than {days}d")
            return removed
        finally:
            conn.close()
