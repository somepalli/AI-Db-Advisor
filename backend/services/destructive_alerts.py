"""
destructive_alerts.py — Out-of-band alarm for blocked destructive statements.

A DESTRUCTIVE_BLOCKED alert fires whenever the guardrail wall rejects a
destructive/unknown statement with alert=True (in apply.py, mcp_orchestrator.py,
the MCP router, and the agent loop).

These are INFORMATIONAL ALARMS, not approvable items:
  * they can never be approved away — there is no approve/execute path for them;
  * each is persisted as a distinct, immutable audit event (action="destructive_blocked");
  * each fires the existing out-of-band notification channel (Slack webhook), best-effort.

This is the single funnel for raising the alert, so one blocked statement produces
exactly one DESTRUCTIVE_BLOCKED alert.
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from . import approval_store

logger = logging.getLogger(__name__)

ALERT_CLASS = "DESTRUCTIVE_BLOCKED"
_MAX_KEEP = 500
_LOCK = threading.RLock()
_RECENT: List["DestructiveBlockedAlert"] = []

# Injectable notifier hook (set in tests / wired to a real channel). Receives the
# alert dict. Must never be relied upon for safety — it is an alarm, not a gate.
_notifier: Optional[Callable[[Dict[str, Any]], None]] = None


@dataclass
class DestructiveBlockedAlert:
    id: str
    alert_class: str
    ts: str
    ds_id: Optional[str]
    matched_rule: Optional[str]
    risk_class: Optional[str]
    statement: str           # truncated
    reason: str
    actor: Optional[str]
    source: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def set_notifier(fn: Optional[Callable[[Dict[str, Any]], None]]) -> None:
    """Override the out-of-band notifier (used by tests / channel wiring)."""
    global _notifier
    _notifier = fn


def raise_destructive_blocked(
    ds_id: Optional[str],
    statement: str,
    *,
    matched_rule: Optional[str] = None,
    risk_class: Optional[str] = None,
    reason: str = "",
    actor: Optional[str] = None,
    source: Optional[str] = None,
) -> DestructiveBlockedAlert:
    """
    Raise exactly one DESTRUCTIVE_BLOCKED alert: persist an immutable audit event,
    record it in the recent ring buffer, and fire the out-of-band notification.
    Never raises — alerting must not crash the caller.
    """
    alert = DestructiveBlockedAlert(
        id=f"destructive-{uuid.uuid4().hex[:12]}",
        alert_class=ALERT_CLASS,
        ts=datetime.utcnow().isoformat(),
        ds_id=ds_id,
        matched_rule=matched_rule,
        risk_class=risk_class,
        statement=(statement or "")[:200],
        reason=reason,
        actor=actor,
        source=source,
    )

    logger.warning(
        f"[{ALERT_CLASS}] ds={ds_id} rule={matched_rule} source={source} "
        f"stmt={alert.statement!r}"
    )

    # 1. Immutable audit event (distinct class). Never deleted by cleanup.
    try:
        approval_store.append_audit(
            "destructive_blocked", ds_id=ds_id, actor=actor,
            detail={
                "alert_id": alert.id, "alert_class": ALERT_CLASS,
                "rule": matched_rule, "risk_class": risk_class,
                "statement": alert.statement, "reason": reason, "source": source,
            },
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Failed to persist destructive_blocked audit event: {e}")

    # 2. Recent ring buffer (for the UI banner).
    with _LOCK:
        _RECENT.append(alert)
        if len(_RECENT) > _MAX_KEEP:
            del _RECENT[: len(_RECENT) - _MAX_KEEP]

    # 3. Out-of-band notification (best-effort).
    _fire_notification(alert)

    return alert


def _fire_notification(alert: DestructiveBlockedAlert) -> None:
    payload = alert.to_dict()
    if _notifier is not None:
        try:
            _notifier(payload)
        except Exception as e:  # pragma: no cover
            logger.error(f"Destructive-blocked notifier failed: {e}")
        return
    _default_notify(payload)


def _default_notify(payload: Dict[str, Any]) -> None:
    """Best-effort Slack webhook post; no-op when no webhook is configured."""
    try:
        from ..config import settings
        url = getattr(settings, "SLACK_WEBHOOK_URL", "")
        if not url:
            return
        import httpx
        text = (
            f":no_entry: *DESTRUCTIVE BLOCKED* (ds={payload.get('ds_id')})\n"
            f"rule: {payload.get('matched_rule')} · source: {payload.get('source')}\n"
            f"`{payload.get('statement')}`\n"
            "This statement was rejected at the guardrail wall and cannot be approved."
        )
        with httpx.Client(timeout=5) as client:
            client.post(url, json={"text": text})
    except Exception as e:  # pragma: no cover - notification must never raise
        logger.error(f"Default destructive-blocked notification failed: {e}")


def get_recent(ds_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Most-recent-first list of DESTRUCTIVE_BLOCKED alerts (optionally per datasource)."""
    with _LOCK:
        items = [a for a in _RECENT if ds_id is None or a.ds_id == ds_id]
        return [a.to_dict() for a in reversed(items[-limit:])]


def clear() -> None:
    """Clear the in-memory ring buffer (test helper). Audit rows are unaffected."""
    with _LOCK:
        _RECENT.clear()
