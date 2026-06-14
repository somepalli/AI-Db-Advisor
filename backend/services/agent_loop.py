"""
agent_loop.py — Bounded, metadata-only DBA investigation loop.

Guarantees enforced here (in addition to the guardrail wall):
  * METADATA-ONLY: the toolset comes from agent_tool_policy.build_agent_toolset()
    which contains zero row-reading tools and zero arbitrary-SQL tools. EXPLAIN is
    always run WITHOUT ANALYZE.
  * include_sample_data forced OFF via agent_tool_policy.agent_context_kwargs().
  * The loop NEVER executes a write/DDL statement. When the model proposes a
    remediation it is screened by the guardrail wall; queueable actions are
    submitted for HITL approval (and the loop stops proposing). Destructive /
    unknown proposals are dropped and raise a destructive-blocked alert.

The LLM is driven with a small JSON action protocol rather than a provider-native
tool-calling API (LLMClient has no tool-calling surface). Each turn the model
returns one of:
    {"action": "tool", "tool": "<read-tool>", "input": {...}}
    {"action": "propose", "sql": "<remediation SQL>", "rationale": "..."}
    {"action": "finish", "summary": "..."}
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from .agent_tool_policy import (
    build_agent_toolset,
    agent_context_kwargs,
    screen_proposed_action,
)
from .agent_guardrails import evaluate as guardrail_evaluate, GuardrailDecision
from .approval_workflow import get_workflow

logger = logging.getLogger(__name__)


# Map a read tool's handler_key to a metadata-only agent call. None of these
# return application row data; explain() is always called with analyze=False.
def _dispatch_read(handler_key: str, agent: Any, inp: Dict[str, Any]) -> Any:
    inp = inp or {}
    if handler_key == "schema":
        return agent.get_schema()
    if handler_key == "explain":
        return agent.explain(inp.get("sql", ""), analyze=False)  # NEVER analyze=True
    if handler_key == "index_usage":
        return agent.get_existing_indexes(inp.get("table"))
    if handler_key in ("table_stats", "cache_ratios"):
        return agent.stats()
    if handler_key == "wait_events":
        return agent.locks()
    if handler_key == "slow_queries":
        return agent.get_top_queries(limit=inp.get("limit", 10))
    raise ValueError(f"Unknown read handler: {handler_key}")


def _summarize(obj: Any, limit: int = 600) -> str:
    try:
        text = json.dumps(obj, default=str)
    except Exception:
        text = str(obj)
    return text[:limit] + ("…" if len(text) > limit else "")


def _system_prompt(goal: str, read_names: List[str]) -> str:
    return (
        "You are a cautious, metadata-only database performance investigator.\n"
        "You may ONLY read metadata (schema, EXPLAIN estimates, stats, indexes, "
        "slow-query digests). You CANNOT read table rows and CANNOT execute SQL.\n"
        f"Available read tools: {', '.join(read_names)}.\n"
        "When you have enough evidence you may propose ONE remediation (CREATE INDEX, "
        "ANALYZE, or SET) — it will be screened and queued for human approval, never "
        "auto-executed. Destructive statements are rejected.\n"
        "Respond with a SINGLE JSON object, one of:\n"
        '  {"action":"tool","tool":"<read-tool>","input":{...}}\n'
        '  {"action":"propose","sql":"<remediation SQL>","rationale":"..."}\n'
        '  {"action":"finish","summary":"..."}\n'
        f"Investigation goal: {goal}"
    )


async def run_investigation(
    ds_id: str,
    goal: str,
    *,
    max_iters: int = 6,
    token_budget: int = 8000,
    llm: Any = None,
    agent: Any = None,
    submitted_by: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run a bounded metadata-only investigation. Returns a structured trace plus the
    list of created approval_ids and any blocked (destructive) proposals.
    """
    # --- toolset + context invariants ---------------------------------------
    tools = build_agent_toolset()  # asserts: no row-readers, no arbitrary-SQL tool
    read_tools = {t.name: t for t in tools if not t.is_write}
    assert all(not t.reads_row_data for t in tools), "Row-data tool leaked into agent loop"

    ctx_kwargs = agent_context_kwargs()
    assert ctx_kwargs.get("include_sample_data") is False, "Agent loop must not include sample data"

    # Resolve dependencies lazily so tests can inject fakes.
    if agent is None:
        from ..deps import resolve_agent
        agent = resolve_agent(ds_id)
    if llm is None:
        from .ai_client import LLMClient
        llm = LLMClient()

    workflow = get_workflow(ds_id)

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": _system_prompt(goal, list(read_tools.keys()))},
        {"role": "user", "content": f"Begin investigating: {goal}"},
    ]

    trace: List[Dict[str, Any]] = []
    approval_ids: List[str] = []
    blocked: List[Dict[str, Any]] = []
    tokens_used = 0

    for step in range(1, max_iters + 1):
        if tokens_used >= token_budget:
            trace.append({"step": step, "action": "halt", "detail": "token budget exhausted"})
            break

        try:
            reply = llm.chat(messages, json_response=True)
        except Exception as e:
            trace.append({"step": step, "action": "error", "detail": f"LLM call failed: {e}"})
            break

        # Rough token accounting for the budget guard.
        tokens_used += len(_summarize(reply, 10_000)) // 4

        action = reply.get("action") if isinstance(reply, dict) else None

        if action == "finish" or action is None:
            trace.append({"step": step, "action": "finish",
                          "summary": (reply.get("summary") if isinstance(reply, dict) else str(reply))})
            break

        if action == "tool":
            tool_name = reply.get("tool", "")
            tool = read_tools.get(tool_name)
            if tool is None:
                # Either an unknown tool, or a write/propose tool used illegally.
                obs = {"error": f"'{tool_name}' is not an available read tool."}
                trace.append({"step": step, "action": "tool", "tool": tool_name,
                              "input": reply.get("input"), "observation": _summarize(obs)})
                messages.append({"role": "assistant", "content": json.dumps(reply)})
                messages.append({"role": "user", "content": f"Observation: {_summarize(obs)}"})
                continue
            try:
                result = _dispatch_read(tool.handler_key, agent, reply.get("input") or {})
                obs_summary = _summarize(result)
            except Exception as e:
                obs_summary = _summarize({"error": str(e)})
            trace.append({"step": step, "action": "tool", "tool": tool_name,
                          "input": reply.get("input"), "observation": obs_summary})
            messages.append({"role": "assistant", "content": json.dumps(reply)})
            messages.append({"role": "user", "content": f"Observation: {obs_summary}"})
            continue

        if action == "propose":
            sql = (reply.get("sql") or "").strip()
            decision = guardrail_evaluate(sql, agentic=True)
            queueable, reason = screen_proposed_action(sql)
            if not queueable:
                # Drop + raise a destructive-blocked alert. NEVER queued.
                _raise_destructive_blocked(ds_id, sql, decision, actor=submitted_by)
                blocked.append({"sql": sql, "reason": reason, "rule": decision.matched_rule,
                                "alert": decision.alert})
                trace.append({"step": step, "action": "propose_blocked", "sql": sql[:200],
                              "reason": reason, "alert": decision.alert})
                # Tell the model and let it continue investigating.
                messages.append({"role": "assistant", "content": json.dumps(reply)})
                messages.append({"role": "user",
                                 "content": f"That proposal was rejected: {reason}. Do not repeat it."})
                continue

            # Queueable: submit for HITL approval and STOP proposing.
            suggestion = {
                "id": f"agent-{uuid.uuid4().hex[:8]}",
                "sql": sql,
                "category": "index" if sql.upper().lstrip().startswith(("CREATE INDEX", "CREATE UNIQUE INDEX")) else "config",
                "risk_level": decision.risk_class.value,
                "risk_class": decision.risk_class.value,
                "rationale": reply.get("rationale") or goal,
                "source": "agent_loop",
            }
            approval_id = workflow.submit_for_approval(suggestion, submitted_by=submitted_by)
            approval_ids.append(approval_id)
            trace.append({"step": step, "action": "propose_queued", "sql": sql[:200],
                          "approval_id": approval_id, "risk_class": decision.risk_class.value})
            break  # stop proposing after the first queued remediation

        # Unrecognized action — record and stop to stay bounded.
        trace.append({"step": step, "action": "unknown", "detail": _summarize(reply)})
        break

    return {
        "ds_id": ds_id,
        "goal": goal,
        "iterations": len(trace),
        "trace": trace,
        "approval_ids": approval_ids,
        "blocked": blocked,
    }


def _raise_destructive_blocked(ds_id: str, sql: str, decision, actor: Optional[str]) -> None:
    """
    Raise a DESTRUCTIVE_BLOCKED alarm via the single alert funnel. This is an
    informational alarm, NOT an approvable item.
    """
    from .destructive_alerts import raise_destructive_blocked
    raise_destructive_blocked(
        ds_id, sql,
        matched_rule=decision.matched_rule,
        risk_class=decision.risk_class.value,
        reason=decision.reason,
        actor=actor,
        source="agent_loop",
    )
