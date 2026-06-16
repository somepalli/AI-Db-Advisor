# tests/test_mcp_execute_apply.py
"""
Stage 3 tests: approved execution is routed through the dry-run-validated apply path.

  - An APPROVED CREATE INDEX runs apply.py with dry_run=True (is_agentic=True)
    first, then dry_run=False — in that order.
  - A failed dry-run blocks the real run and marks the approval FAILED.
"""
import uuid
from unittest.mock import MagicMock

import pytest

from backend.schemas import ApplyResult


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    db = tmp_path / f"approvals-{uuid.uuid4().hex}.db"
    monkeypatch.setenv("APPROVALS_DB_FILE", str(db))
    from backend.services import approval_store, approval_workflow
    approval_workflow._workflows.clear()
    approval_store.init_db()
    return approval_store, approval_workflow


class FakeAgent:
    """Non-Postgres agent so the orchestrator uses the open/close branch."""
    def get_db_type(self):
        return "postgres"

    def _conn(self):
        return MagicMock()


def _approved(wf_mod, ds_id):
    wf = wf_mod.get_workflow(ds_id)
    approval_id = wf.submit_for_approval({
        "id": "sug-1",
        "sql": "CREATE INDEX idx_email ON students(email);",
        "category": "index",
        "risk_level": "low",
    })
    wf.approve(approval_id, user_id="bob")
    return approval_id


@pytest.mark.asyncio
async def test_dry_run_then_real(isolated_store, monkeypatch):
    store, wf_mod = isolated_store
    from backend.services import mcp_orchestrator
    import backend.services.apply as apply_mod

    monkeypatch.setattr(mcp_orchestrator, "resolve_agent", lambda ds_id: FakeAgent())
    calls = MagicMock(side_effect=[
        [ApplyResult(id="sug-1", status="success", message="dry ok", rollback_sql="DROP INDEX IF EXISTS idx_email;")],
        [ApplyResult(id="sug-1", status="success", message="applied", rollback_sql="DROP INDEX IF EXISTS idx_email;")],
    ])
    monkeypatch.setattr(apply_mod, "apply_suggestions", calls)

    approval_id = _approved(wf_mod, "pg-1")
    orch = mcp_orchestrator.MCPOrchestrator("pg-1")
    result = await orch.execute_approved_suggestion(approval_id, user_id="bob")

    assert result["success"] is True
    # Called twice, dry-run first (positional dry_run arg), then real.
    assert calls.call_count == 2
    assert calls.call_args_list[0].args[2] is True   # dry_run=True
    assert calls.call_args_list[1].args[2] is False  # dry_run=False
    assert all(c.kwargs.get("is_agentic") is True for c in calls.call_args_list)

    rec = store.get_approval(approval_id)
    assert rec["status"] == "executed"
    assert rec["rollback_sql"] == "DROP INDEX IF EXISTS idx_email;"


@pytest.mark.asyncio
async def test_failed_dry_run_blocks_real(isolated_store, monkeypatch):
    store, wf_mod = isolated_store
    from backend.services import mcp_orchestrator
    import backend.services.apply as apply_mod

    monkeypatch.setattr(mcp_orchestrator, "resolve_agent", lambda ds_id: FakeAgent())
    calls = MagicMock(side_effect=[
        [ApplyResult(id="sug-1", status="error", message="syntax error at end of input")],
    ])
    monkeypatch.setattr(apply_mod, "apply_suggestions", calls)

    approval_id = _approved(wf_mod, "pg-2")
    orch = mcp_orchestrator.MCPOrchestrator("pg-2")

    with pytest.raises(ValueError, match="Dry-run validation failed"):
        await orch.execute_approved_suggestion(approval_id, user_id="bob")

    # Real run never happened; record marked FAILED.
    assert calls.call_count == 1
    rec = store.get_approval(approval_id)
    assert rec["status"] == "failed"


@pytest.mark.asyncio
async def test_execute_requires_approved_status(isolated_store, monkeypatch):
    store, wf_mod = isolated_store
    from backend.services import mcp_orchestrator
    monkeypatch.setattr(mcp_orchestrator, "resolve_agent", lambda ds_id: FakeAgent())

    wf = wf_mod.get_workflow("pg-3")
    approval_id = wf.submit_for_approval({"id": "s", "sql": "ANALYZE students;", "category": "config"})
    # still PENDING, not approved
    orch = mcp_orchestrator.MCPOrchestrator("pg-3")
    with pytest.raises(ValueError, match="not approved"):
        await orch.execute_approved_suggestion(approval_id, user_id="bob")
