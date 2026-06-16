"""
agent_scan_store.py — In-memory store for autonomous scan state.

Tracks one active scan at a time (ScanState) and the latest per-datasource
result (PerDsResult). Thread-safe via RLock so the background asyncio task
and the status/results endpoints never race.

step_info tracks real-time per-DS agent progress so the UI can show which
tool the agent is currently calling inside each database.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class PerDsResult:
    ds_id: str
    status: str          # "ok" | "approved" | "blocked" | "error" | "no_finding"
    trace: list
    approval_ids: list
    blocked: list
    error: Optional[str]
    scanned_at: str      # ISO datetime UTC
    top_finding: Optional[str]


@dataclass
class ScanState:
    scan_id: str
    in_progress: List[str]
    completed: List[str]
    failed: List[str]
    started_at: str
    finished_at: Optional[str]
    scanning: bool
    step_info: Dict[str, str] = field(default_factory=dict)
    # step_info: ds_id → human-readable current step, e.g. "step 3: get_index_usage"


_LOCK = threading.RLock()
_latest: Dict[str, PerDsResult] = {}
_active: Optional[ScanState] = None


def start_scan(scan_id: str, ds_ids: List[str]) -> ScanState:
    global _active
    with _LOCK:
        _active = ScanState(
            scan_id=scan_id,
            in_progress=list(ds_ids),
            completed=[],
            failed=[],
            started_at=datetime.utcnow().isoformat(),
            finished_at=None,
            scanning=True,
            step_info={ds_id: "starting…" for ds_id in ds_ids},
        )
        return _active


def update_step_info(scan_id: str, ds_id: str, info: str) -> None:
    """Update the live step description for a datasource during an active scan."""
    with _LOCK:
        if _active and _active.scan_id == scan_id:
            _active.step_info[ds_id] = info


def mark_done(scan_id: str, ds_id: str, result: PerDsResult) -> None:
    global _active
    with _LOCK:
        _latest[ds_id] = result
        if _active and _active.scan_id == scan_id:
            if ds_id in _active.in_progress:
                _active.in_progress.remove(ds_id)
            if ds_id not in _active.completed:
                _active.completed.append(ds_id)
            _active.step_info[ds_id] = "done"
            if not _active.in_progress:
                _active.scanning = False
                _active.finished_at = datetime.utcnow().isoformat()


def mark_failed(scan_id: str, ds_id: str, error: str) -> None:
    global _active
    with _LOCK:
        _latest[ds_id] = PerDsResult(
            ds_id=ds_id, status="error", trace=[], approval_ids=[], blocked=[],
            error=error, scanned_at=datetime.utcnow().isoformat(), top_finding=None,
        )
        if _active and _active.scan_id == scan_id:
            if ds_id in _active.in_progress:
                _active.in_progress.remove(ds_id)
            if ds_id not in _active.failed:
                _active.failed.append(ds_id)
            _active.step_info[ds_id] = f"error: {error[:60]}"
            if not _active.in_progress:
                _active.scanning = False
                _active.finished_at = datetime.utcnow().isoformat()


def get_status() -> Optional[ScanState]:
    with _LOCK:
        return _active


def get_all_latest() -> Dict[str, PerDsResult]:
    with _LOCK:
        return dict(_latest)


def get_latest(ds_id: str) -> Optional[PerDsResult]:
    with _LOCK:
        return _latest.get(ds_id)
