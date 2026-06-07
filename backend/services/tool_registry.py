"""
Tool-enforcement map — provider-trust gated access.

The data boundary is enforced at *tool selection*, not by instructing the model.
``active_tools()`` filters the registry by the connected ``engine`` and the model's
``provider_trust``:

    local  -> metadata tools + data tools
    hosted -> metadata tools only      (data tools are structurally absent)

Metadata tool outputs always pass through their declared sanitizers before they can
reach a hosted model. ``scrub_literals`` / ``names_only`` handle the separate egress
channel (the NL question + schema) that the tool gate does not cover.

Covers PostgreSQL, MySQL/MariaDB and SQL Server; the descriptor format is engine-generic
so other engines slot in later.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Tool:
    name: str                       # stable id, e.g. "pg.top_queries"
    engine: str                     # which engine it belongs to
    tier: str                       # "metadata" (always on) | "data" (local-only)
    mcp_op: str                     # executor coroutine name (Postgres/MySQL executor)
    sanitize: tuple = ()            # ordered sanitizer ids applied to the output
    description: str = ""


# ---------------------------------------------------------------- PostgreSQL
REGISTRY: List[Tool] = [
    # metadata — always available
    Tool("pg.list_schema",     "postgres", "metadata", "list_schema",    description="Tables and columns"),
    Tool("pg.index_inventory", "postgres", "metadata", "index_inventory", description="Existing indexes (pg_indexes)"),
    Tool("pg.index_usage",     "postgres", "metadata", "index_usage",    description="Index scan counts / unused indexes"),
    Tool("pg.top_queries",     "postgres", "metadata", "top_queries",    sanitize=("normalize_sql",), description="Slowest queries"),
    Tool("pg.explain",         "postgres", "metadata", "explain",        description="EXPLAIN plan (no ANALYZE)"),
    Tool("pg.table_bloat",     "postgres", "metadata", "table_bloat",    description="Dead-tuple / bloat signal"),
    Tool("pg.lock_waits",      "postgres", "metadata", "lock_waits",     sanitize=("strip_query_text",), description="Lock waits"),
    Tool("pg.column_stats",    "postgres", "metadata", "column_stats",   sanitize=("drop_value_arrays",), description="Column statistics (pg_stats)"),
    Tool("pg.health",          "postgres", "metadata", "health",         description="DB health: cache, vacuum, replication, indexes"),
    Tool("pg.index_advice",    "postgres", "metadata", "index_advice",   description="Index tuning recommendations"),
    # data — local-trust only
    Tool("pg.sample_rows",     "postgres", "data", "sample_rows",    description="Sample rows from a table"),
    Tool("pg.run_query",       "postgres", "data", "run_query",      description="Run a read query"),
    Tool("pg.profile_values",  "postgres", "data", "profile_values", description="Value frequency profile of a column"),

    # ------------------------------------------------------------ MySQL / MariaDB
    # metadata — always available
    Tool("my.list_schema",     "mysql", "metadata", "list_schema",     description="Tables and columns"),
    Tool("my.index_inventory", "mysql", "metadata", "index_inventory", description="Existing indexes (information_schema.statistics)"),
    Tool("my.index_usage",     "mysql", "metadata", "index_usage",     description="Unused indexes (sys.schema_unused_indexes)"),
    Tool("my.top_queries",     "mysql", "metadata", "top_queries",     sanitize=("normalize_sql",), description="Slowest queries (performance_schema digest)"),
    Tool("my.explain",         "mysql", "metadata", "explain",         description="EXPLAIN FORMAT=JSON plan"),
    Tool("my.table_stats",     "mysql", "metadata", "table_stats",     description="Table sizes / row estimates"),
    Tool("my.config_audit",    "mysql", "metadata", "config_audit",    description="Server tuning variables"),
    # data — local-trust only
    Tool("my.sample_rows",     "mysql", "data", "sample_rows", description="Sample rows from a table"),
    Tool("my.run_query",       "mysql", "data", "run_query",   description="Run a read query"),

    # ------------------------------------------------------------ SQL Server
    # metadata — always available
    Tool("mssql.list_schema",         "sqlserver", "metadata", "list_schema",         description="Tables and columns"),
    Tool("mssql.missing_indexes",     "sqlserver", "metadata", "missing_indexes",     description="Engine missing-index recommendations (dm_db_missing_index_*)"),
    Tool("mssql.index_usage",         "sqlserver", "metadata", "index_usage",         description="Index seeks/scans/updates (dm_db_index_usage_stats)"),
    Tool("mssql.index_fragmentation", "sqlserver", "metadata", "index_fragmentation", description="Index fragmentation (dm_db_index_physical_stats)"),
    Tool("mssql.top_queries",         "sqlserver", "metadata", "top_queries",         sanitize=("strip_plan_params",), description="Slowest queries (dm_exec_query_stats)"),
    Tool("mssql.estimated_plan",      "sqlserver", "metadata", "estimated_plan",      description="Estimated plan (SHOWPLAN_XML, no execution)"),
    Tool("mssql.query_store_regress", "sqlserver", "metadata", "query_store_regress", description="Query Store regressed queries"),
    # data — local-trust only
    Tool("mssql.sample_rows",         "sqlserver", "data", "sample_rows", description="Sample rows from a table"),
    Tool("mssql.run_query",           "sqlserver", "data", "run_query",   description="Run a read query"),
]


def active_tools(engine: str, provider_trust: str, registry: List[Tool] = REGISTRY) -> List[Tool]:
    """The entire enforcement: data tools exist only when provider_trust == 'local'."""
    return [
        t for t in registry
        if t.engine == engine and (t.tier == "metadata" or provider_trust == "local")
    ]


# ---------------------------------------------------------------- sanitizers
def normalize_sql(value: Any) -> Any:
    """Replace literals with $1, $2 … in any 'query' field (list of rows or a string)."""
    def _sub(sql: str) -> str:
        if not isinstance(sql, str):
            return sql
        counter = {"i": 0}
        def repl(_m):
            counter["i"] += 1
            return f"${counter['i']}"
        # single pass over quoted strings OR bare numbers so inserted "$1" placeholders
        # are never re-scanned (running the two patterns separately double-counts digits).
        return re.sub(r"'(?:[^']|'')*'|\b\d+\b", repl, sql)
    if isinstance(value, str):
        return _sub(value)
    if isinstance(value, list):
        for row in value:
            if isinstance(row, dict) and isinstance(row.get("query"), str):
                row["query"] = _sub(row["query"])
    return value


_VALUE_ARRAY_KEYS = ("most_common_vals", "histogram_bounds", "most_common_elems",
                     "most_common_freqs", "elem_count_histogram")


def drop_value_arrays(value: Any) -> Any:
    """Strip pg_stats MCV / histogram value arrays, keep the shape stats."""
    if isinstance(value, list):
        for row in value:
            if isinstance(row, dict):
                for k in _VALUE_ARRAY_KEYS:
                    row.pop(k, None)
    return value


def strip_query_text(value: Any) -> Any:
    """Remove embedded statement text (e.g. pg_locks join query column)."""
    if isinstance(value, list):
        for row in value:
            if isinstance(row, dict):
                row.pop("query", None)
    return value


_HANDLE_KEYS = ("plan_handle", "sql_handle", "query_hash", "query_plan_hash", "query_plan")


def strip_plan_params(value: Any) -> Any:
    """SQL Server cached-plan rows: normalize literals in the statement text and drop
    binary handles / raw plan blobs so no parameter values reach a hosted model."""
    if isinstance(value, list):
        for row in value:
            if isinstance(row, dict):
                for k in _HANDLE_KEYS:
                    row.pop(k, None)
        normalize_sql(value)  # parameterizes the 'query' field in place
    return value


SANITIZERS: Dict[str, Callable[[Any], Any]] = {
    "normalize_sql": normalize_sql,
    "drop_value_arrays": drop_value_arrays,
    "strip_query_text": strip_query_text,
    "strip_plan_params": strip_plan_params,
}


async def run_metadata_tool(tool: Tool, executor, args: Dict[str, Any] | None = None) -> Any:
    """Execute a metadata tool via the executor, then apply its sanitizers in order."""
    op = getattr(executor, tool.mcp_op)
    raw = await op(**(args or {}))
    for s in tool.sanitize:
        raw = SANITIZERS[s](raw)
    return raw


# ------------------------------------------------ hosted egress (spec §5; not the gate)
def scrub_literals(nl: str) -> str:
    """Mask numbers and quoted strings in the user's question before it reaches a hosted model."""
    if not nl:
        return nl
    nl = re.sub(r"'[^']*'|\"[^\"]*\"", "'<redacted>'", nl)
    nl = re.sub(r"\b\d[\d,_.]*\b", "<n>", nl)
    return nl


def names_only(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Return DDL names/types only — never sample values. Accepts {'tables': {...}}."""
    tables = schema.get("tables", schema) if isinstance(schema, dict) else {}
    out: Dict[str, Any] = {}
    for table, cols in (tables or {}).items():
        out[table] = [
            {"column": c.get("column"), "type": c.get("type")}
            for c in cols if isinstance(c, dict)
        ]
    return {"tables": out}
