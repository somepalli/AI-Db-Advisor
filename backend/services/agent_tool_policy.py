"""
agent_tool_policy.py — Tool registry policy for the autonomous agent loop.

Two structural guarantees enforced here:

  1. The agentic loop is METADATA-ONLY regardless of LLM provider.
     Autonomy + row access is the dangerous combination, so the agent never
     gets row-reading tools even when a local (trusted) model is in use.

  2. The agent has NO arbitrary-SQL tool. It can read metadata and propose a
     narrow, fixed set of remediation actions. Every proposed remediation is
     re-checked by agent_guardrails.evaluate(agentic=True) before it can be
     queued.

This sits ON TOP OF the existing two-tier provider-trust model. The existing
model already restricts hosted providers to metadata; this restricts the
*agent* to metadata for ALL providers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent_guardrails import evaluate, GuardrailDecision, RiskClass


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    reads_row_data: bool          # if True, NEVER registered for the agent loop
    is_write: bool
    handler_key: str              # maps to the concrete implementation in the agent


# Metadata-only read tools the agent MAY call autonomously.
# None of these return application row data.
AGENT_READ_TOOLS: list[Tool] = [
    Tool("get_schema",        "Column names/types only, no values.",            False, False, "schema"),
    Tool("explain_plan",      "EXPLAIN without ANALYZE; planner estimates.",    False, False, "explain"),
    Tool("get_index_usage",   "pg_stat_user_indexes / equivalents.",            False, False, "index_usage"),
    Tool("get_table_stats",   "row-count estimates, bloat, size; aggregates.",  False, False, "table_stats"),
    Tool("get_wait_events",   "pg_stat_activity wait events (no query params).", False, False, "wait_events"),
    Tool("get_cache_ratios",  "buffer cache hit ratios.",                       False, False, "cache_ratios"),
    Tool("get_slow_queries",  "slow-query digests (statements, not bound row values).", False, False, "slow_queries"),
]

# The ONLY write actions the agent may PROPOSE (never auto-execute).
# Each is still routed through guardrails + HITL + dry-run before execution.
AGENT_PROPOSABLE_WRITES: list[Tool] = [
    Tool("propose_create_index", "Propose CREATE INDEX [CONCURRENTLY].", False, True, "propose_index"),
    Tool("propose_analyze",      "Propose ANALYZE <table>.",            False, True, "propose_analyze"),
    Tool("propose_set_config",   "Propose SET <param> for the session.", False, True, "propose_set"),
]

# Explicitly NOT available to the agent under any provider:
#   - any row-reading / SELECT-of-application-data tool
#   - any execute_arbitrary_sql / run_query tool
#   - any DROP/TRUNCATE/DELETE tool


def build_agent_toolset() -> list[Tool]:
    """
    Returns the agent's permitted tools. Filters out anything that reads row
    data as a hard invariant — independent of provider trust level.
    """
    tools = [t for t in AGENT_READ_TOOLS if not t.reads_row_data]
    tools += AGENT_PROPOSABLE_WRITES
    # Invariant check: no row-data tool may ever slip in.
    assert all(not t.reads_row_data for t in tools), "Row-data tool leaked into agent toolset"
    assert not any(t.name in {"execute_sql", "run_query", "raw_sql"} for t in tools), \
        "Arbitrary-SQL tool must never be in the agent toolset"
    return tools


def screen_proposed_action(sql: str) -> tuple[bool, str]:
    """
    Final structural screen before a proposed remediation is queued for approval.
    Returns (queueable, reason). Destructive/unknown => not queueable.
    """
    result = evaluate(sql, agentic=True)
    if result.decision is GuardrailDecision.DENY:
        return False, result.reason
    if result.risk_class in {RiskClass.METADATA_READ, RiskClass.SAFE_WRITE, RiskClass.IMPACTFUL_WRITE}:
        return True, result.reason
    return False, "Action not in the agent's permitted remediation set."


# Context-building invariant for the agentic path.
def agent_context_kwargs() -> dict[str, Any]:
    """
    Forces include_sample_data OFF for the agent loop. ai_chat.build_ai_context
    must consume these kwargs on the agentic path so no row data enters context.
    """
    return {"include_sample_data": False, "max_sample_rows": 0}
