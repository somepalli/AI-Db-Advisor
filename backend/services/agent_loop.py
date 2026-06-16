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

Key behaviours:
  * Warm-start: schema, indexes, top-slow queries, and table stats are pre-fetched
    and injected into the first user message so the agent doesn't waste iterations
    on basic reads.
  * Tool-call deduplication: results are cached by (tool, input); repeat calls
    return the cached value and nudge the agent toward a decision.
  * Propose pressure: after PROPOSE_PRESSURE_AT tool reads with no proposal, a
    strong "decide now" message is injected to prevent infinite read loops.
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


def build_proactive_goal(engine_type: str) -> str:
    """Return a multi-concern proactive DBA audit goal tailored to the engine type."""
    base = (
        "Proactive DBA health audit: investigate (1) missing or unused indexes on slow "
        "queries, (2) stale optimizer statistics, (3) high wait events or blocking locks, "
        "(4) cache hit ratio below threshold, (5) unusually expensive queries. "
        "Identify the single highest-priority issue and propose one targeted remediation."
    )
    extras: Dict[str, str] = {
        "postgres":   " Also check pg_stat_statements for query regressions and autovacuum lag.",
        "postgresql": " Also check pg_stat_statements for query regressions and autovacuum lag.",
        "pg":         " Also check pg_stat_statements for query regressions and autovacuum lag.",
        "mysql":      " Also check InnoDB buffer pool efficiency and slow query log patterns.",
        "mariadb":    " Also check InnoDB buffer pool efficiency and slow query log patterns.",
        "mongodb":    " Check for collection scan queries and missing compound indexes.",
        "mongo":      " Check for collection scan queries and missing compound indexes.",
        "redis":      " Check keyspace hit ratio and memory fragmentation.",
        "sqlserver":  " Check sys.dm_exec_query_stats for top CPU consumers and missing index DMVs.",
        "mssql":      " Check sys.dm_exec_query_stats for top CPU consumers and missing index DMVs.",
        "sqlite":     " Check for full table scans using EXPLAIN QUERY PLAN.",
        "cassandra":  " Check for full partition reads and missing secondary indexes.",
    }
    return base + extras.get((engine_type or "").lower(), "")


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


def _summarize(obj: Any, limit: int = 2000) -> str:
    try:
        text = json.dumps(obj, default=str)
    except Exception:
        text = str(obj)
    return text[:limit] + ("…" if len(text) > limit else "")


def _system_prompt(goal: str, read_names: List[str]) -> str:
    tools_list = ", ".join(read_names)
    return (
        "You are a proactive database performance investigator. "
        "Your job is to FIND issues and PROPOSE a concrete fix — not to keep reading indefinitely.\n\n"
        "== WHAT YOU CAN DO ==\n"
        "Read metadata only (no row data, no query execution).\n"
        f"Available read tools: {tools_list}.\n"
        "Propose ONE of: CREATE INDEX [CONCURRENTLY], ANALYZE <table>, or SET <param>.\n\n"
        "== INVESTIGATION PROTOCOL ==\n"
        "The FIRST USER MESSAGE already contains pre-fetched schema, existing indexes, slow queries, and stats.\n"
        "Step 1 — Analyse that pre-fetched data immediately. Look for:\n"
        "   • Tables in slow queries that lack indexes on their WHERE/JOIN/ORDER BY columns\n"
        "   • Large tables (>10k rows) with no useful indexes\n"
        "   • Cache hit ratio below 0.95 (shared_buffers too small)\n"
        "   • Sequential scans on large tables\n"
        "   • Tables with 0 slow-query rows but significant size (potential stale stats)\n"
        "Step 2 — If you need ONE more data point, call at most 2 extra tools "
        "(e.g. explain_plan on a specific slow query, get_index_usage for one table).\n"
        "   Do NOT call a tool you have already called — you will get a cached result and "
        "a reminder to decide.\n"
        "Step 3 — After analysing the pre-fetched data (± 2 extra reads), you MUST "
        "output a propose or finish action. Do NOT continue reading.\n\n"
        "== RESPONSE FORMAT (single JSON object, nothing else) ==\n"
        '{"action":"tool","tool":"<name>","input":{...}}\n'
        '{"action":"propose","sql":"CREATE INDEX CONCURRENTLY idx_name ON tbl(col)","rationale":"why this fixes the top issue"}\n'
        '{"action":"finish","summary":"No actionable issue found: <specific reason>"}\n\n'
        "== EXAMPLE OF A GOOD FINDING ==\n"
        "If slow queries scan the orders table filtering on customer_id with no index:\n"
        '{"action":"propose","sql":"CREATE INDEX CONCURRENTLY idx_orders_customer ON orders(customer_id)","rationale":"orders has 250k rows; slow queries filter on customer_id with no covering index, causing full seq scans estimated at cost 4800."}\n\n"'
        "== RULES ==\n"
        "• Prefer CREATE INDEX CONCURRENTLY (non-blocking) over plain CREATE INDEX.\n"
        "• Propose ANALYZE only if you see evidence of stale statistics (large row count delta or planner underestimates).\n"
        "• When in doubt between two issues, pick the one affecting the largest table or the slowest query.\n"
        "• If genuinely nothing actionable is found, call finish with a specific explanation.\n\n"
        f"Investigation goal: {goal}"
    )


def _build_warm_start(agent: Any, ds_id: str = "") -> str:
    """Pre-fetch core metadata and format it as the first user message.

    Also injects the last few scan findings so the agent builds on past analysis
    rather than starting cold on each scan (institutional memory).
    """
    sections: List[str] = []

    def _fetch(label: str, fn: Any, limit: int) -> None:
        try:
            data = fn()
            sections.append(f"=== {label} ===\n{_summarize(data, limit)}")
        except Exception as e:
            sections.append(f"=== {label} ===\n(unavailable: {e})")

    # Inject institutional memory from past scans so the agent can avoid
    # re-proposing already-approved fixes or spot recurring issues.
    if ds_id:
        try:
            from .approval_store import get_scan_findings
            past = get_scan_findings(ds_id, limit=4)
            if past:
                mem_lines = []
                for p in past:
                    finding = p.get("top_finding") or "(no finding)"
                    n_approved = len(p.get("approval_ids") or [])
                    n_blocked = p.get("blocked_count", 0)
                    mem_lines.append(
                        f"  [{p['ts'][:16]}] status={p['status']}  "
                        f"approved={n_approved}  blocked={n_blocked}  "
                        f"finding: {finding[:120]}"
                    )
                sections.append(
                    "=== PAST SCAN FINDINGS (institutional memory) ===\n"
                    "Use this context to avoid re-proposing already approved changes\n"
                    "and to escalate if the same issue recurs:\n"
                    + "\n".join(mem_lines)
                )
        except Exception:
            pass

    _fetch("SCHEMA (tables and columns)", agent.get_schema, 4000)
    _fetch("EXISTING INDEXES", lambda: agent.get_existing_indexes(), 3000)
    _fetch("TOP SLOW QUERIES (last hour)", lambda: agent.get_top_queries(limit=15), 2500)
    _fetch("TABLE STATS (size, row counts)", agent.stats, 1500)

    return (
        "\n\n".join(sections)
        + "\n\n--- End of pre-fetched metadata ---\n"
        "Analyse the above data now and decide: what is the single highest-priority "
        "performance issue? Respond with a propose, tool, or finish action."
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
    progress_callback: Optional[Callable[[int, str, str], None]] = None,
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

    # --- warm-start: pre-fetch core metadata --------------------------------
    # This gives the agent schema + indexes + slow queries + stats on its very
    # first turn, so it doesn't waste iterations on basic reads.
    warm_start = _build_warm_start(agent, ds_id=ds_id)

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": _system_prompt(goal, list(read_tools.keys()))},
        {"role": "user", "content": warm_start},
    ]

    trace: List[Dict[str, Any]] = []
    approval_ids: List[str] = []
    blocked: List[Dict[str, Any]] = []
    tokens_used = 0

    # --- deduplication + propose-pressure state ----------------------------
    tool_call_cache: Dict[str, str] = {}   # key: "tool::json_input" → observation
    reads_count = 0
    propose_pressure_sent = False
    # Send "decide now" pressure after this many tool reads (50% through budget).
    PROPOSE_PRESSURE_AT = max(2, min(max_iters // 2, 4))

    for step in range(1, max_iters + 1):
        if tokens_used >= token_budget:
            trace.append({"step": step, "action": "halt", "detail": "token budget exhausted"})
            break

        # Inject propose-pressure message once the agent has read enough data.
        if reads_count >= PROPOSE_PRESSURE_AT and not propose_pressure_sent:
            propose_pressure_sent = True
            pressure = (
                f"You have now read {reads_count} pieces of metadata. "
                "Based on everything you have observed, respond NOW with EITHER:\n"
                '  {"action":"propose","sql":"CREATE INDEX CONCURRENTLY ...","rationale":"..."}\n'
                '  {"action":"finish","summary":"No actionable issue because ..."}\n'
                "DO NOT call any more tools. Make your recommendation now."
            )
            messages.append({"role": "user", "content": pressure})

        try:
            reply = llm.chat(messages, json_response=True)
        except Exception as e:
            trace.append({"step": step, "action": "error", "detail": f"LLM call failed: {e}"})
            break

        # Rough token accounting for the budget guard.
        tokens_used += len(_summarize(reply, 10_000)) // 4

        action = reply.get("action") if isinstance(reply, dict) else None
        tool_name_hint = reply.get("tool", "") if isinstance(reply, dict) else ""

        if progress_callback:
            progress_callback(step, action or "finish", tool_name_hint)

        if action == "finish" or action is None:
            trace.append({"step": step, "action": "finish",
                          "summary": (reply.get("summary") if isinstance(reply, dict) else str(reply))})
            break

        if action == "tool":
            tool_name = reply.get("tool", "")
            tool = read_tools.get(tool_name)
            if tool is None:
                obs = {"error": f"'{tool_name}' is not an available read tool. Choose from: {list(read_tools.keys())}"}
                obs_summary = _summarize(obs)
                trace.append({"step": step, "action": "tool", "tool": tool_name,
                              "input": reply.get("input"), "observation": obs_summary})
                messages.append({"role": "assistant", "content": json.dumps(reply)})
                messages.append({"role": "user", "content": f"Observation: {obs_summary}"})
                continue

            # --- deduplication cache ---
            cache_key = f"{tool_name}::{json.dumps(reply.get('input') or {}, sort_keys=True)}"
            if cache_key in tool_call_cache:
                cached_obs = tool_call_cache[cache_key]
                trace.append({"step": step, "action": "tool", "tool": tool_name,
                              "input": reply.get("input"), "observation": f"(cached) {cached_obs}"})
                messages.append({"role": "assistant", "content": json.dumps(reply)})
                messages.append({
                    "role": "user",
                    "content": (
                        f"(Cached result — you already called this tool): {cached_obs}\n"
                        "You have sufficient data. Please respond with a propose or finish action now."
                    ),
                })
                reads_count += 1
                continue

            # --- normal dispatch ---
            try:
                result = _dispatch_read(tool.handler_key, agent, reply.get("input") or {})
                obs_summary = _summarize(result)
            except Exception as e:
                obs_summary = _summarize({"error": str(e)})

            tool_call_cache[cache_key] = obs_summary
            reads_count += 1

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
                                 "content": f"That proposal was rejected: {reason}. Do not repeat it. Propose a different safe remediation or call finish."})
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
