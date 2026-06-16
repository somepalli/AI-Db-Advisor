# tests/test_agent_loop.py
"""
Stage 4 tests: the bounded, metadata-only agent investigation loop.

  - toolset is metadata-only (no row-readers, no arbitrary SQL) and
    include_sample_data is forced OFF.
  - a CREATE INDEX proposal is screened, queued for approval, and NOTHING is executed.
  - a DROP TABLE proposal is screened out, dropped, raises a destructive_blocked
    alert (audit event), and is NEVER queued.
"""
import uuid

import pytest

from backend.services.agent_loop import run_investigation
from backend.services.agent_tool_policy import build_agent_toolset, agent_context_kwargs


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    db = tmp_path / f"approvals-{uuid.uuid4().hex}.db"
    monkeypatch.setenv("APPROVALS_DB_FILE", str(db))
    from backend.services import approval_store, approval_workflow
    approval_workflow._workflows.clear()
    approval_store.init_db()
    return approval_store, approval_workflow


class FakeLLM:
    """Returns a scripted sequence of JSON action replies."""
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = 0

    def chat(self, messages, json_response=False, **kwargs):
        self.calls += 1
        return self._scripted.pop(0) if self._scripted else {"action": "finish", "summary": "done"}


class FakeAgent:
    def get_db_type(self):
        return "postgres"

    def get_schema(self):
        return {"tables": {"students": [{"column": "email", "type": "varchar"}]}}

    def explain(self, sql, analyze=False):
        assert analyze is False, "agent loop must never run EXPLAIN ANALYZE"
        return {"plan": [{"Node Type": "Seq Scan", "Total Cost": 1234.0}]}

    def get_existing_indexes(self, table=None):
        return []

    def get_top_queries(self, limit=10):
        return []

    def stats(self):
        return {}

    def locks(self):
        return []


class TestInvariants:
    def test_toolset_metadata_only(self):
        tools = build_agent_toolset()
        assert tools and not any(t.reads_row_data for t in tools)
        assert not any(t.name in {"execute_sql", "run_query", "raw_sql"} for t in tools)

    def test_context_forces_no_sample_data(self):
        assert agent_context_kwargs()["include_sample_data"] is False
        assert agent_context_kwargs()["max_sample_rows"] == 0


@pytest.mark.asyncio
async def test_create_index_proposal_is_queued_not_executed(isolated_store):
    store, wf_mod = isolated_store
    llm = FakeLLM([
        {"action": "tool", "tool": "explain", "input": {"sql": "SELECT * FROM students WHERE email='x'"}},
        {"action": "tool", "tool": "get_schema", "input": {}},
        {"action": "propose", "sql": "CREATE INDEX idx_email ON students(email);",
         "rationale": "Seq scan on email filter"},
    ])
    result = await run_investigation("pg-1", "slow email lookups", llm=llm, agent=FakeAgent())

    assert len(result["approval_ids"]) == 1
    approval_id = result["approval_ids"][0]
    rec = store.get_approval(approval_id)
    assert rec is not None and rec["status"] == "pending"   # queued, NOT executed
    assert any(s["action"] == "propose_queued" for s in result["trace"])
    # No execution occurred and no destructive alert was raised.
    assert result["blocked"] == []
    assert "destructive_blocked" not in [a["action"] for a in store.get_audit()]


@pytest.mark.asyncio
async def test_drop_table_proposal_is_blocked_and_alerted(isolated_store):
    store, wf_mod = isolated_store
    llm = FakeLLM([
        {"action": "tool", "tool": "get_schema", "input": {}},
        {"action": "propose", "sql": "DROP TABLE students;", "rationale": "cleanup"},
        {"action": "finish", "summary": "stopped"},
    ])
    result = await run_investigation("pg-2", "tidy up", llm=llm, agent=FakeAgent())

    assert result["approval_ids"] == []                     # never queued
    assert len(result["blocked"]) == 1
    assert result["blocked"][0]["alert"] is True
    # Exactly one destructive_blocked audit event was recorded.
    actions = [a["action"] for a in store.get_audit()]
    assert actions.count("destructive_blocked") == 1
    # Nothing persisted as an approval.
    assert store.list_by_status("pg-2", "pending") == []


@pytest.mark.asyncio
async def test_loop_is_bounded_by_max_iters(isolated_store):
    # Model keeps asking for tools forever; loop must stop at max_iters.
    llm = FakeLLM([{"action": "tool", "tool": "get_schema", "input": {}}] * 50)
    result = await run_investigation("pg-3", "endless", max_iters=4, llm=llm, agent=FakeAgent())
    assert llm.calls <= 4
    assert result["approval_ids"] == []
