"""
Postgres MCP Pro executor — access-mode-aware tool execution.

Every gated PostgreSQL tool runs through Postgres MCP Pro's in-process driver
(``postgres_mcp``). The driver is chosen by ``provider_trust``:

    local  -> SqlDriver        (unrestricted)
    hosted -> SafeSqlDriver    (RESTRICTED: read-only + timeout-capped)

This mirrors postgres-mcp's own ``server.py:get_sql_driver``. Metadata tools are
either Postgres MCP Pro's high-level tool classes (health / explain / index advice,
which return formatted text) or read-only catalog SQL run through the same
access-mode driver (so hosted mode is structurally read-only). Data tools run on the
unrestricted base driver and are only reachable when the selector admits them (local).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .dsn_utils import maybe_rewrite_localhost_dsn

logger = logging.getLogger(__name__)

# Read-only catalog queries (psycopg %s params). Kept here so the access-mode driver
# — not a raw psycopg connection — executes them, giving hosted mode read-only enforcement.
_LIST_SCHEMA_SQL = """
select table_schema, table_name, column_name, data_type, is_nullable
from information_schema.columns
where table_schema not in ('pg_catalog', 'information_schema')
order by table_schema, table_name, ordinal_position
"""

_INDEX_INVENTORY_SQL = """
select schemaname, tablename, indexname, indexdef
from pg_indexes
where schemaname not in ('pg_catalog', 'information_schema')
"""

_INDEX_USAGE_SQL = """
select schemaname, relname as table_name, indexrelname as index_name,
       idx_scan, idx_tup_read, idx_tup_fetch,
       pg_size_pretty(pg_relation_size(indexrelid)) as index_size
from pg_stat_user_indexes
order by idx_scan asc, pg_relation_size(indexrelid) desc
limit {limit}
"""

# Approximate bloat signal from dead-tuple accounting (reliable + read-only),
# instead of the fragile classic bloat-estimate math.
_TABLE_BLOAT_SQL = """
select schemaname, relname as table_name, n_live_tup, n_dead_tup,
       round(n_dead_tup * 100.0 / nullif(n_live_tup + n_dead_tup, 0), 2) as dead_pct,
       last_autovacuum
from pg_stat_user_tables
order by n_dead_tup desc
limit {limit}
"""

_LOCK_WAITS_SQL = """
select l.locktype, l.mode, l.granted, l.pid,
       (now() - a.query_start)::text as age, a.query
from pg_locks l
join pg_stat_activity a on a.pid = l.pid
order by l.granted asc, age desc
limit {limit}
"""

# pg_stats keeps the value arrays (most_common_vals / histogram_bounds / most_common_elems);
# the drop_value_arrays sanitizer strips them before anything reaches a hosted model.
_COLUMN_STATS_SQL = """
select schemaname, tablename, attname, n_distinct, null_frac, correlation,
       most_common_vals, histogram_bounds, most_common_elems
from pg_stats
where schemaname not in ('pg_catalog', 'information_schema')
"""

# Top queries by total execution time (mirrors PostgresAgent). Needs pg_stat_statements.
_TOP_QUERIES_SQL = """
select query, calls,
       total_exec_time / nullif(calls, 0) as mean_time_ms,
       rows
from pg_stat_statements
order by total_exec_time desc
limit {limit}
"""

# Identifiers passed to data tools (table/column) must be plain identifiers — no
# injection through the unrestricted driver.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def _safe_ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return name


class PostgresMcpExecutor:
    """Owns the access-mode driver for one chat turn; one coroutine per tool op."""

    def __init__(self, dsn: str, trust: str):
        self.dsn = maybe_rewrite_localhost_dsn(dsn)
        self.trust = trust
        self._pool = None
        self._base = None     # unrestricted SqlDriver
        self._driver = None   # access-mode driver (Safe in hosted)

    @property
    def driver_kind(self) -> str:
        return "SafeSqlDriver" if self.trust == "hosted" else "SqlDriver"

    async def _ensure(self):
        if self._driver is not None:
            return
        from postgres_mcp.sql import DbConnPool, SqlDriver, SafeSqlDriver

        self._pool = DbConnPool(self.dsn)
        await self._pool.pool_connect()
        self._base = SqlDriver(conn=self._pool)
        self._driver = (
            SafeSqlDriver(sql_driver=self._base, timeout=30)
            if self.trust == "hosted" else self._base
        )
        logger.info("PostgresMcpExecutor ready: trust=%s driver=%s", self.trust, self.driver_kind)

    async def aclose(self):
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:
                pass
            self._pool = self._base = self._driver = None

    async def __aenter__(self):
        await self._ensure()
        return self

    async def __aexit__(self, *exc):
        await self.aclose()

    # -- helpers ------------------------------------------------------------
    async def _rows(self, sql: str) -> List[Dict[str, Any]]:
        # No psycopg %s params: SafeSqlDriver validates fully-formed SQL with a parser
        # that rejects placeholders. Limits are int()-cast and identifiers are validated
        # by _safe_ident, so inlining them is injection-safe.
        await self._ensure()
        res = await self._driver.execute_query(sql)
        return [r.cells for r in (res or [])]

    # -- metadata tools (read-only) ----------------------------------------
    async def list_schema(self, **_) -> List[Dict[str, Any]]:
        return await self._rows(_LIST_SCHEMA_SQL)

    async def index_inventory(self, table: Optional[str] = None, **_) -> List[Dict[str, Any]]:
        sql = _INDEX_INVENTORY_SQL
        if table:
            sql += f" and tablename = '{_safe_ident(table).split('.')[-1]}'"
        return await self._rows(sql + " order by schemaname, tablename, indexname")

    async def index_usage(self, limit: int = 50, **_) -> List[Dict[str, Any]]:
        return await self._rows(_INDEX_USAGE_SQL.format(limit=int(limit)))

    async def top_queries(self, limit: int = 10, **_) -> List[Dict[str, Any]]:
        try:
            return await self._rows(_TOP_QUERIES_SQL.format(limit=int(limit)))
        except Exception as e:
            logger.info("top_queries unavailable (pg_stat_statements?): %s", e)
            return [{"note": "pg_stat_statements not available", "query": None, "calls": 0}]

    async def table_bloat(self, limit: int = 25, **_) -> List[Dict[str, Any]]:
        return await self._rows(_TABLE_BLOAT_SQL.format(limit=int(limit)))

    async def lock_waits(self, limit: int = 50, **_) -> List[Dict[str, Any]]:
        return await self._rows(_LOCK_WAITS_SQL.format(limit=int(limit)))

    async def column_stats(self, table: Optional[str] = None, **_) -> List[Dict[str, Any]]:
        sql = _COLUMN_STATS_SQL
        if table:
            sql += f" and tablename = '{_safe_ident(table).split('.')[-1]}'"
        return await self._rows(sql + " order by schemaname, tablename, attname")

    async def explain(self, sql: str, **_) -> str:
        await self._ensure()
        from postgres_mcp.explain import ExplainPlanTool
        res = await ExplainPlanTool(sql_driver=self._driver).explain(sql, do_analyze=False)
        return getattr(res, "value", None) or str(res)

    async def health(self, health_type: str = "all", **_) -> str:
        await self._ensure()
        from postgres_mcp.database_health import DatabaseHealthTool
        return await DatabaseHealthTool(self._driver).health(health_type=health_type)

    async def index_advice(self, max_index_size_mb: int = 10000, **_) -> str:
        await self._ensure()
        from postgres_mcp.index.dta_calc import DatabaseTuningAdvisor
        res = await DatabaseTuningAdvisor(self._driver).analyze_workload(max_index_size_mb=max_index_size_mb)
        return getattr(res, "value", None) or str(res)

    # -- data tools (unrestricted base driver; selector admits only when local) ----
    async def run_query(self, sql: str, **_) -> List[Dict[str, Any]]:
        await self._ensure()
        res = await self._base.execute_query(sql)
        return [r.cells for r in (res or [])]

    async def sample_rows(self, table: str, limit: int = 20, **_) -> List[Dict[str, Any]]:
        return await self.run_query(f"SELECT * FROM {_safe_ident(table)} LIMIT {int(limit)}")

    async def profile_values(self, table: str, column: str, limit: int = 20, **_) -> List[Dict[str, Any]]:
        t, col = _safe_ident(table), _safe_ident(column)
        return await self.run_query(
            f"SELECT {col} AS value, count(*) AS freq FROM {t} "
            f"GROUP BY {col} ORDER BY freq DESC LIMIT {int(limit)}"
        )
