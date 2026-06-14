# tests/test_destructive_alerts.py
"""
Stage 5 tests: the DESTRUCTIVE_BLOCKED out-of-band alert.

  - a blocked DROP produces exactly ONE DESTRUCTIVE_BLOCKED alert
    (via apply.py, the agent loop, and the MCP router funnel)
  - the alert fires the out-of-band notifier exactly once
  - destructive alerts are informational only (recorded + notified, never queued)
"""
import uuid
from unittest.mock import MagicMock

import pytest

from backend.schemas import Suggestion


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    db = tmp_path / f"approvals-{uuid.uuid4().hex}.db"
    monkeypatch.setenv("APPROVALS_DB_FILE", str(db))
    from backend.services import approval_store, approval_workflow, destructive_alerts
    approval_workflow._workflows.clear()
    approval_store.init_db()
    destructive_alerts.clear()
    notifier = MagicMock()
    destructive_alerts.set_notifier(notifier)
    yield approval_store, destructive_alerts, notifier
    destructive_alerts.set_notifier(None)
    destructive_alerts.clear()


def _sug(sql):
    return Suggestion(
        id="s1", level="table", category="cleanup", title="t", summary="s",
        sql_fix=sql, validated=True, confidence="validated", risk="low",
        related_objects=["students"], metadata={},
    )


class TestApplyEmitsExactlyOneAlert:
    def test_blocked_drop_raises_one_alert(self, isolated):
        store, alerts, notifier = isolated
        from backend.services.apply import _apply_single_suggestion
        conn = MagicMock()

        result = _apply_single_suggestion(conn, _sug("DROP TABLE students;"),
                                          dry_run=True, db_type="postgres", is_agentic=True)
        assert result.status == "error" and result.alert is True

        recent = alerts.get_recent()
        assert len(recent) == 1
        assert recent[0]["alert_class"] == "DESTRUCTIVE_BLOCKED"
        assert recent[0]["matched_rule"] == "DROP TABLE"
        # Fired the out-of-band notifier exactly once.
        assert notifier.call_count == 1
        # Exactly one immutable audit event too.
        assert [a["action"] for a in store.get_audit()].count("destructive_blocked") == 1


@pytest.mark.asyncio
class TestAgentLoopEmitsExactlyOneAlert:
    async def test_drop_proposal_one_alert(self, isolated):
        store, alerts, notifier = isolated
        from backend.services.agent_loop import run_investigation

        class FakeLLM:
            def __init__(self):
                self._s = [
                    {"action": "propose", "sql": "DROP TABLE students;", "rationale": "x"},
                    {"action": "finish", "summary": "done"},
                ]
            def chat(self, messages, json_response=False, **kw):
                return self._s.pop(0) if self._s else {"action": "finish", "summary": "done"}

        class FakeAgent:
            def get_db_type(self): return "postgres"
            def get_schema(self): return {}

        result = await run_investigation("pg-a", "tidy", llm=FakeLLM(), agent=FakeAgent())
        assert result["approval_ids"] == []
        assert len(alerts.get_recent("pg-a")) == 1
        assert notifier.call_count == 1


class TestMcpRouterFunnel:
    def test_screen_and_register_alerts_once(self, isolated):
        store, alerts, notifier = isolated
        from backend.routers import mcp as mcp_router
        kept = mcp_router._screen_and_register("pg-b", [
            {"id": "bad", "sql": "TRUNCATE enrollments;"},
            {"id": "ok", "sql": "CREATE INDEX i ON students(email);"},
        ])
        assert [s["id"] for s in kept] == ["ok"]
        assert len(alerts.get_recent("pg-b")) == 1
        assert notifier.call_count == 1


class TestNotInApprovalQueue:
    def test_alert_never_creates_approval(self, isolated):
        store, alerts, notifier = isolated
        alerts.raise_destructive_blocked("pg-c", "DROP TABLE x;", matched_rule="DROP TABLE",
                                         risk_class="destructive", reason="blocked")
        # Recorded + notified, but nothing queued for approval.
        assert len(alerts.get_recent("pg-c")) == 1
        assert store.list_by_status("pg-c", "pending") == []
