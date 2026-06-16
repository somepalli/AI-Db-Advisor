# tests/test_approval_workflow.py
"""
Stage 2 tests: persisted approval lifecycle + append-only audit + demo gating.

Covers:
  - submit -> approve -> execute happy path, persisted in SQLite
  - an audit row written on every state transition
  - guardrail screening drops destructive suggestions before they are queued
    (and records a destructive_blocked audit event)
  - cleanup_old_records never deletes audit rows
  - DEMO MODE off + no MCP client -> request-suggestions returns 503
"""
import importlib
import uuid

import pytest

from backend.config import settings


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Point the approval store at a throwaway SQLite file and reset workflow handles."""
    db = tmp_path / f"approvals-{uuid.uuid4().hex}.db"
    monkeypatch.setenv("APPROVALS_DB_FILE", str(db))
    from backend.services import approval_store, approval_workflow
    approval_workflow._workflows.clear()
    approval_store.init_db()
    return approval_store, approval_workflow


def _index_suggestion():
    return {
        "id": "sug-1",
        "sql": "CREATE INDEX CONCURRENTLY idx_email ON students(email);",
        "risk_level": "low",
        "category": "index",
    }


class TestLifecycleAndAudit:
    def test_submit_approve_execute_happy_path(self, isolated_store):
        store, wf_mod = isolated_store
        wf = wf_mod.get_workflow("pg-1")

        approval_id = wf.submit_for_approval(_index_suggestion(), submitted_by="alice")
        assert store.get_approval(approval_id)["status"] == "pending"

        wf.approve(approval_id, user_id="bob", notes="lgtm")
        assert store.get_approval(approval_id)["status"] == "approved"

        wf.mark_executing(approval_id)
        wf.mark_executed(approval_id, execution_result={"rows_affected": 0}, rollback_available=True,
                         rollback_sql="DROP INDEX IF EXISTS idx_email;")

        rec = store.get_approval(approval_id)
        assert rec["status"] == "executed"
        assert rec["rollback_sql"] == "DROP INDEX IF EXISTS idx_email;"
        assert rec["execution_result"] == {"rows_affected": 0}

    def test_audit_row_per_transition(self, isolated_store):
        store, wf_mod = isolated_store
        wf = wf_mod.get_workflow("pg-1")
        approval_id = wf.submit_for_approval(_index_suggestion(), submitted_by="alice")
        wf.approve(approval_id, user_id="bob")
        wf.mark_executing(approval_id)
        wf.mark_executed(approval_id, execution_result={})

        actions = [a["action"] for a in store.get_audit(approval_id)]
        assert {"submit", "approve", "execute", "executed"} <= set(actions)

    def test_persists_across_new_workflow_handle(self, isolated_store):
        store, wf_mod = isolated_store
        approval_id = wf_mod.get_workflow("pg-1").submit_for_approval(_index_suggestion())
        # Simulate a fresh process: drop in-memory handles, reload from SQLite.
        wf_mod._workflows.clear()
        rec = wf_mod.get_workflow("pg-1").get_approval_by_id(approval_id)
        assert rec is not None and rec["status"] == "pending"

    def test_statistics(self, isolated_store):
        store, wf_mod = isolated_store
        wf = wf_mod.get_workflow("pg-2")
        a = wf.submit_for_approval(_index_suggestion())
        wf.submit_for_approval(_index_suggestion())
        wf.approve(a, user_id="bob")
        stats = wf.get_statistics()
        assert stats["total_submitted"] == 2
        assert stats["currently_pending"] == 1
        assert stats["awaiting_execution"] == 1


class TestScreeningDropsDestructive:
    def test_destructive_dropped_and_alerted(self, isolated_store, monkeypatch):
        store, wf_mod = isolated_store
        from backend.routers import mcp as mcp_router
        suggestions = [
            {"id": "good", "sql": "CREATE INDEX idx ON students(email);", "risk_level": "low"},
            {"id": "bad", "sql": "DROP TABLE students;", "risk_level": "high"},
        ]
        kept = mcp_router._screen_and_register("pg-3", suggestions)
        assert [s["id"] for s in kept] == ["good"]
        assert kept[0]["approval_id"].startswith("approval-")
        # The kept one is persisted as PENDING; the destructive one never was.
        pending = store.list_by_status("pg-3", "pending")
        assert len(pending) == 1
        # risk_class must be PERSISTED (not just on the HTTP response) so the UI
        # badge + typed-confirmation gate work off /pending.
        assert pending[0]["suggestion"]["risk_class"] == "impactful_write"
        # A destructive_blocked audit event was recorded.
        actions = [a["action"] for a in store.get_audit()]
        assert "destructive_blocked" in actions


class TestCleanupNeverTouchesAudit:
    def test_cleanup_keeps_audit(self, isolated_store):
        store, wf_mod = isolated_store
        wf = wf_mod.get_workflow("pg-4")
        approval_id = wf.submit_for_approval(_index_suggestion())
        wf.approve(approval_id, user_id="bob")
        wf.mark_executing(approval_id)
        wf.mark_executed(approval_id, execution_result={})

        # Backdate the executed row well past the TTL so cleanup removes it.
        import sqlite3
        conn = sqlite3.connect(store._db_path())
        conn.execute("UPDATE approvals SET executed_at = '2000-01-01T00:00:00' WHERE approval_id = ?",
                     (approval_id,))
        conn.commit()
        conn.close()

        audit_before = len(store.get_audit())
        removed = wf.cleanup_old_records(days=30)
        assert removed == 1
        assert store.get_approval(approval_id) is None          # approval row gone
        assert len(store.get_audit()) >= audit_before           # audit rows preserved (+cleanup event)


class TestDemoGating:
    def test_request_suggestions_503_when_no_client_and_demo_off(self, client, monkeypatch, isolated_store):
        monkeypatch.setattr(settings, "DEMO_MODE", False)
        from backend.services import mcp_client as mcp_client_mod
        monkeypatch.setattr(mcp_client_mod, "get_mcp_client", lambda: None)
        # mcp router imported get_mcp_client by reference — patch there too.
        from backend.routers import mcp as mcp_router
        monkeypatch.setattr(mcp_router, "get_mcp_client", lambda: None)

        resp = client.post("/mcp/pg-x/request-suggestions", json={"optimization_type": "performance"})
        assert resp.status_code == 503

    def test_request_suggestions_demo_on_creates_real_approvals(self, client, monkeypatch, isolated_store):
        monkeypatch.setattr(settings, "DEMO_MODE", True)
        from backend.routers import mcp as mcp_router
        monkeypatch.setattr(mcp_router, "get_mcp_client", lambda: None)

        resp = client.post("/mcp/pg-y/request-suggestions", json={"optimization_type": "performance"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 1
        for s in body["suggestions"]:
            assert s["approval_id"].startswith("approval-")
        # Approvals are really persisted and resolvable.
        store, wf_mod = isolated_store
        assert len(store.list_by_status("pg-y", "pending")) == body["count"]
