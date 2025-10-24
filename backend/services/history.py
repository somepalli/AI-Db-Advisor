"""
Audit logging for suggestion analysis and application.
Maintains an append-only log of all operations for traceability.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

# Log file location
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
AUDIT_LOG_FILE = LOG_DIR / "suggestions_audit.jsonl"


def _get_query_fingerprint(sql: str) -> str:
    """Generate a stable fingerprint for a query (normalized hash)."""
    # Normalize: lowercase, remove extra whitespace
    normalized = ' '.join(sql.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def record_analyze(
    ds_id: str,
    sql: str,
    suggestions: List[Dict[str, Any]],
    include_ai: bool,
    duration_ms: float,
    notes: List[str]
) -> None:
    """
    Record a suggestion analysis operation.

    Args:
        ds_id: Data source ID
        sql: Query analyzed
        suggestions: List of suggestions generated
        include_ai: Whether AI was included
        duration_ms: Analysis duration
        notes: System notes
    """
    try:
        record = {
            "event": "analyze",
            "timestamp": datetime.utcnow().isoformat(),
            "ds_id": ds_id,
            "query_fingerprint": _get_query_fingerprint(sql),
            "query_length": len(sql),
            "include_ai": include_ai,
            "suggestion_count": len(suggestions),
            "suggestion_ids": [s.get("id") for s in suggestions],
            "categories": list(set(s.get("category") for s in suggestions)),
            "validated_count": sum(1 for s in suggestions if s.get("validated")),
            "duration_ms": duration_ms,
            "notes": notes
        }

        _append_to_log(record)
        logger.info(f"Recorded analyze event: {ds_id}, {len(suggestions)} suggestions")

    except Exception as e:
        logger.error(f"Failed to record analyze event: {e}")


def record_apply(
    ds_id: str,
    suggestion_ids: List[str],
    results: List[Dict[str, Any]],
    dry_run: bool,
    duration_ms: float,
    notes: List[str]
) -> None:
    """
    Record a suggestion application operation.

    Args:
        ds_id: Data source ID
        suggestion_ids: IDs of suggestions applied
        results: Application results
        dry_run: Whether this was a dry run
        duration_ms: Application duration
        notes: System notes
    """
    try:
        # Count outcomes
        success_count = sum(1 for r in results if r.get("status") == "success")
        error_count = sum(1 for r in results if r.get("status") == "error")
        skipped_count = sum(1 for r in results if r.get("status") == "skipped")

        record = {
            "event": "apply",
            "timestamp": datetime.utcnow().isoformat(),
            "ds_id": ds_id,
            "suggestion_ids": suggestion_ids,
            "dry_run": dry_run,
            "total_count": len(results),
            "success_count": success_count,
            "error_count": error_count,
            "skipped_count": skipped_count,
            "duration_ms": duration_ms,
            "notes": notes,
            "results": results  # Full results for audit trail
        }

        _append_to_log(record)
        logger.info(f"Recorded apply event: {ds_id}, {success_count}/{len(results)} successful, dry_run={dry_run}")

    except Exception as e:
        logger.error(f"Failed to record apply event: {e}")


def _append_to_log(record: Dict[str, Any]) -> None:
    """Append a record to the JSONL audit log."""
    try:
        with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
    except Exception as e:
        logger.error(f"Failed to write to audit log: {e}")


def get_recent_analyses(ds_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Retrieve recent analysis events from the audit log.

    Args:
        ds_id: Filter by data source ID (optional)
        limit: Maximum number of records to return

    Returns:
        List of analysis events
    """
    results = []

    try:
        if not AUDIT_LOG_FILE.exists():
            return results

        with open(AUDIT_LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Process most recent first
        for line in reversed(lines):
            if len(results) >= limit:
                break

            try:
                record = json.loads(line.strip())
                if record.get("event") == "analyze":
                    if ds_id is None or record.get("ds_id") == ds_id:
                        results.append(record)
            except json.JSONDecodeError:
                continue

    except Exception as e:
        logger.error(f"Failed to read audit log: {e}")

    return results


def get_recent_applications(ds_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Retrieve recent application events from the audit log.

    Args:
        ds_id: Filter by data source ID (optional)
        limit: Maximum number of records to return

    Returns:
        List of application events
    """
    results = []

    try:
        if not AUDIT_LOG_FILE.exists():
            return results

        with open(AUDIT_LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Process most recent first
        for line in reversed(lines):
            if len(results) >= limit:
                break

            try:
                record = json.loads(line.strip())
                if record.get("event") == "apply":
                    if ds_id is None or record.get("ds_id") == ds_id:
                        results.append(record)
            except json.JSONDecodeError:
                continue

    except Exception as e:
        logger.error(f"Failed to read audit log: {e}")

    return results


def get_suggestion_history(suggestion_id: str) -> List[Dict[str, Any]]:
    """
    Get the history of a specific suggestion (when it was generated, applied, etc.).

    Args:
        suggestion_id: Suggestion ID

    Returns:
        List of events involving this suggestion
    """
    results = []

    try:
        if not AUDIT_LOG_FILE.exists():
            return results

        with open(AUDIT_LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line.strip())

                    # Check if this record involves the suggestion
                    if suggestion_id in record.get("suggestion_ids", []):
                        results.append(record)

                except json.JSONDecodeError:
                    continue

    except Exception as e:
        logger.error(f"Failed to read audit log: {e}")

    return results
