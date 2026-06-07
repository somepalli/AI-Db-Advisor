"""
Gated context builder for the AI chat.

Builds the database context block injected into the chat prompt, honouring the
provider-trust data boundary:

  * schema is always names-only;
  * sample rows are included ONLY for local-trust models;
  * metadata tools run through Postgres MCP Pro (restricted driver when hosted) and
    their outputs are sanitized before they enter the prompt;
  * the user's question is scrubbed of literals when hosted.

PostgreSQL and MySQL/MariaDB use this gated path; callers fall back to the legacy
``build_ai_context`` for other engines.
"""
from __future__ import annotations

import json
import logging
from typing import Any, List, Optional, Tuple

from ..config import settings
from ..deps import resolve_agent
from .tool_registry import (
    active_tools,
    run_metadata_tool,
    names_only,
    scrub_literals,
)
from .postgres_mcp_executor import PostgresMcpExecutor
from .mysql_mcp_executor import MySqlMcpExecutor
from .mssql_mcp_executor import MsSqlMcpExecutor

logger = logging.getLogger(__name__)

# Engines that route through the provider-trust gated path (vs. legacy build_ai_context).
GATED_ENGINES = ("postgres", "mysql", "sqlserver")

# Metadata ops auto-run into the prompt each turn (bounded latency), per engine. Other
# registered metadata tools stay available but aren't auto-run. ``explain`` is appended
# on demand when the editor has SQL.
_CONTEXT_OPS = {
    "postgres": ("index_inventory", "index_usage", "top_queries", "table_bloat", "lock_waits", "health"),
    "mysql": ("index_inventory", "index_usage", "top_queries", "table_stats", "config_audit"),
    "sqlserver": ("missing_indexes", "index_usage", "index_fragmentation", "top_queries"),
}
_MAX_ROWS = 40          # cap rows shown per tool
_MAX_TEXT = 4000        # cap length of text-returning tools (health/explain)


# The on-demand "plan" op (run when the editor has SQL) is named per engine.
_PLAN_OP = {"postgres": "explain", "mysql": "explain", "sqlserver": "estimated_plan"}


def _make_executor(engine: str, dsn: str, trust: str):
    if engine == "postgres":
        return PostgresMcpExecutor(dsn, trust)
    if engine == "mysql":
        return MySqlMcpExecutor(dsn, trust)
    if engine == "sqlserver":
        return MsSqlMcpExecutor(dsn, trust)
    raise ValueError(f"No gated executor for engine {engine!r}")


def _fmt(name: str, out: Any) -> str:
    if isinstance(out, str):
        text = out.strip()
        if len(text) > _MAX_TEXT:
            text = text[:_MAX_TEXT] + "\n…(truncated)"
        return f"### {name}\n{text}"
    if isinstance(out, list):
        rows = out[:_MAX_ROWS]
        body = json.dumps(rows, default=str, indent=2)
        more = "" if len(out) <= _MAX_ROWS else f"\n…(+{len(out) - _MAX_ROWS} more rows)"
        return f"### {name} ({len(out)} rows)\n{body}{more}"
    return f"### {name}\n{out}"


async def build_gated_context(
    ds_id: str,
    engine: str,
    trust: str,
    user_message: str,
    current_sql: Optional[str] = None,
) -> Tuple[str, str]:
    """Return (context_str, safe_user_message). PostgreSQL and MySQL."""
    agent = resolve_agent(ds_id)
    cfg = settings.DATASOURCES.get(ds_id) or {}
    dsn = cfg.get("dsn", "")

    parts: List[str] = []

    # Schema — names only (never sample values in the prompt schema block).
    try:
        schema = names_only(agent.get_schema())
        parts.append("## Schema (names only)\n" + json.dumps(schema["tables"], default=str, indent=2)[:6000])
    except Exception as e:
        logger.warning("schema fetch failed: %s", e)

    # Sample rows — local trust only.
    if trust == "local":
        try:
            from .context_builder import build_ai_context
            sample = build_ai_context(ds_id=ds_id, user_message=user_message,
                                      current_sql=current_sql, max_tables=3, include_sample_data=True)
            parts.append("## Sample data (local model only)\n" + str(sample)[:4000])
        except Exception as e:
            logger.info("sample data unavailable: %s", e)

    # Gated metadata tools.
    tools = {t.mcp_op: t for t in active_tools(engine, trust) if t.tier == "metadata"}
    ops = list(_CONTEXT_OPS.get(engine, ()))
    plan_op = _PLAN_OP.get(engine, "explain")
    if current_sql and plan_op not in ops:
        ops.append(plan_op)

    executor = _make_executor(engine, dsn, trust)
    try:
        tool_parts: List[str] = []
        for op in ops:
            tool = tools.get(op)
            if not tool:
                continue
            args = {"sql": current_sql} if op == plan_op else {}
            try:
                out = await run_metadata_tool(tool, executor, args)
                tool_parts.append(_fmt(tool.name, out))
            except Exception as e:
                logger.info("tool %s failed: %s", op, e)
        if tool_parts:
            parts.append("## Live metadata (driver=%s)\n%s" % (executor.driver_kind, "\n\n".join(tool_parts)))
    finally:
        await executor.aclose()

    safe_message = scrub_literals(user_message) if trust == "hosted" else user_message
    return "\n\n".join(parts), safe_message
