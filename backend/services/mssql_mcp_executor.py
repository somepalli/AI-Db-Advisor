"""
SQL Server gated executor — access-mode-aware tool execution.

The SQL Server analogue of ``PostgresMcpExecutor`` / ``MySqlMcpExecutor``. Gated tools
run through pyodbc (the project's standard SQL Server driver). The data boundary holds:

  * the selector in ``tool_registry.active_tools`` decides which ops exist for the
    session (data tools are absent in hosted mode), and
  * the only user-supplied statement (``estimated_plan``) runs under
    ``SET SHOWPLAN_XML ON``, which *compiles* the batch and returns the plan without
    ever executing it — so even a DML passed in hosted mode cannot mutate.

Metadata tools run fixed read-only catalog/DMV SQL we author (sys.* / dm_*). Data tools
run normal statements and are only reachable when the selector admits them (local trust).
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from .dsn_utils import build_mssql_odbc_connstr

logger = logging.getLogger(__name__)

# Tables/columns excluded from user-facing schema/index listings.
_SCHEMA_FILTER = "s.name NOT IN ('sys', 'INFORMATION_SCHEMA')"

_LIST_SCHEMA_SQL = """
select s.name as table_schema, t.name as table_name, c.name as column_name,
       ty.name as data_type,
       case when c.is_nullable = 1 then 'YES' else 'NO' end as is_nullable
from sys.columns c
join sys.tables t on c.object_id = t.object_id
join sys.schemas s on t.schema_id = s.schema_id
join sys.types ty on c.user_type_id = ty.user_type_id
where {filter}
order by s.name, t.name, c.column_id
""".format(filter=_SCHEMA_FILTER)

# Engine's own missing-index recommendations with a rough "improvement measure".
_MISSING_INDEXES_SQL = """
select top {limit}
       db_name(mid.database_id) as database_name,
       object_name(mid.object_id) as table_name,
       mid.equality_columns, mid.inequality_columns, mid.included_columns,
       migs.user_seeks, migs.user_scans, migs.avg_user_impact,
       cast(migs.avg_total_user_cost * migs.avg_user_impact * (migs.user_seeks + migs.user_scans) as bigint)
           as improvement_measure
from sys.dm_db_missing_index_details mid
join sys.dm_db_missing_index_groups mig on mid.index_handle = mig.index_handle
join sys.dm_db_missing_index_group_stats migs on mig.index_group_handle = migs.group_handle
where mid.database_id = db_id()
order by improvement_measure desc
"""

_INDEX_USAGE_SQL = """
select top {limit}
       schema_name(t.schema_id) as table_schema, t.name as table_name, i.name as index_name,
       isnull(us.user_seeks, 0) as user_seeks, isnull(us.user_scans, 0) as user_scans,
       isnull(us.user_lookups, 0) as user_lookups, isnull(us.user_updates, 0) as user_updates
from sys.indexes i
join sys.tables t on i.object_id = t.object_id
left join sys.dm_db_index_usage_stats us
       on us.object_id = i.object_id and us.index_id = i.index_id and us.database_id = db_id()
where i.name is not null
order by isnull(us.user_seeks, 0) + isnull(us.user_scans, 0) asc, user_updates desc
"""

_INDEX_FRAGMENTATION_SQL = """
select top {limit}
       schema_name(t.schema_id) as table_schema, t.name as table_name, i.name as index_name,
       round(ps.avg_fragmentation_in_percent, 2) as avg_fragmentation_pct, ps.page_count
from sys.dm_db_index_physical_stats(db_id(), null, null, null, 'LIMITED') ps
join sys.indexes i on ps.object_id = i.object_id and ps.index_id = i.index_id
join sys.tables t on i.object_id = t.object_id
where i.name is not null and ps.page_count > 100
order by ps.avg_fragmentation_in_percent desc
"""

# Slowest statements from the plan cache. strip_plan_params sanitizes the text + drops
# binary handles before this can reach a hosted model.
_TOP_QUERIES_SQL = """
select top {limit}
       substring(qt.text, (qs.statement_start_offset/2)+1,
            ((case qs.statement_end_offset when -1 then datalength(qt.text)
              else qs.statement_end_offset end - qs.statement_start_offset)/2) + 1) as query,
       qs.execution_count as calls,
       qs.total_elapsed_time / nullif(qs.execution_count, 0) / 1000 as mean_time_ms,
       qs.total_rows / nullif(qs.execution_count, 0) as [rows]
from sys.dm_exec_query_stats qs
cross apply sys.dm_exec_sql_text(qs.sql_handle) qt
where qt.text is not null
order by qs.total_elapsed_time desc
"""

# Query Store regressed queries (requires Query Store enabled on the database).
_QUERY_STORE_REGRESS_SQL = """
select top {limit}
       q.query_id, rs.avg_duration / 1000.0 as avg_duration_ms, rs.count_executions,
       rs.last_execution_time
from sys.query_store_runtime_stats rs
join sys.query_store_plan p on rs.plan_id = p.plan_id
join sys.query_store_query q on p.query_id = q.query_id
order by rs.avg_duration desc
"""

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")
_READ_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def _safe_ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return name


def _bracket(table: str) -> str:
    """Quote a (schema.)table as [schema].[table] after identifier validation."""
    return ".".join(f"[{part}]" for part in _safe_ident(table).split("."))


class MsSqlMcpExecutor:
    """Owns a pyodbc connection for one chat turn; one coroutine per tool op."""

    def __init__(self, dsn: str, trust: str):
        self.dsn = dsn
        self.trust = trust
        self._conn = None

    @property
    def driver_kind(self) -> str:
        # No server-side read-only session in SQL Server; the boundary is the selector
        # (no data tools when hosted) plus SHOWPLAN compile-only for estimated_plan.
        return "ReadOnly" if self.trust == "hosted" else "ReadWrite"

    def _connect(self):
        import pyodbc
        return pyodbc.connect(build_mssql_odbc_connstr(self.dsn), autocommit=True, timeout=15)

    async def _ensure(self):
        if self._conn is None:
            self._conn = await asyncio.to_thread(self._connect)
            logger.info("MsSqlMcpExecutor ready: trust=%s driver=%s", self.trust, self.driver_kind)

    async def aclose(self):
        if self._conn is not None:
            conn, self._conn = self._conn, None
            try:
                await asyncio.to_thread(conn.close)
            except Exception:
                pass

    async def __aenter__(self):
        await self._ensure()
        return self

    async def __aexit__(self, *exc):
        await self.aclose()

    # -- helpers ------------------------------------------------------------
    def _query_sync(self, sql: str) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(sql)
        if cur.description is None:
            return []
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    async def _rows(self, sql: str) -> List[Dict[str, Any]]:
        await self._ensure()
        return await asyncio.to_thread(self._query_sync, sql)

    # -- metadata tools (read-only catalog / DMV SQL) ----------------------
    async def list_schema(self, **_) -> List[Dict[str, Any]]:
        return await self._rows(_LIST_SCHEMA_SQL)

    async def missing_indexes(self, limit: int = 25, **_) -> List[Dict[str, Any]]:
        return await self._rows(_MISSING_INDEXES_SQL.format(limit=int(limit)))

    async def index_usage(self, limit: int = 50, **_) -> List[Dict[str, Any]]:
        return await self._rows(_INDEX_USAGE_SQL.format(limit=int(limit)))

    async def index_fragmentation(self, limit: int = 25, **_) -> List[Dict[str, Any]]:
        try:
            return await self._rows(_INDEX_FRAGMENTATION_SQL.format(limit=int(limit)))
        except Exception as e:
            logger.info("index_fragmentation unavailable: %s", e)
            return [{"note": "index physical stats unavailable"}]

    async def top_queries(self, limit: int = 10, **_) -> List[Dict[str, Any]]:
        try:
            return await self._rows(_TOP_QUERIES_SQL.format(limit=int(limit)))
        except Exception as e:
            logger.info("top_queries unavailable (dm_exec_query_stats?): %s", e)
            return [{"note": "dm_exec_query_stats not available", "query": None, "calls": 0}]

    async def query_store_regress(self, limit: int = 15, **_) -> List[Dict[str, Any]]:
        try:
            return await self._rows(_QUERY_STORE_REGRESS_SQL.format(limit=int(limit)))
        except Exception as e:
            logger.info("query_store_regress unavailable (Query Store off?): %s", e)
            return [{"note": "Query Store not enabled on this database"}]

    async def estimated_plan(self, sql: str, **_) -> Any:
        """SHOWPLAN_XML compiles the batch and returns the plan WITHOUT executing it."""
        if not sql:
            return {"note": "no SQL supplied"}
        if not _READ_RE.match(sql):
            return {"note": "estimated_plan only supports read statements"}
        await self._ensure()

        def _plan() -> Any:
            cur = self._conn.cursor()
            cur.execute("SET SHOWPLAN_XML ON")
            try:
                cur.execute(sql)
                row = cur.fetchone()
                return row[0] if row else None
            finally:
                cur.execute("SET SHOWPLAN_XML OFF")

        try:
            xml = await asyncio.to_thread(_plan)
            return {"plan": xml, "format": "xml"}
        except Exception as e:
            return {"note": f"estimated_plan failed: {e}"}

    # -- data tools (selector admits only when local) ----------------------
    async def run_query(self, sql: str, **_) -> List[Dict[str, Any]]:
        return await self._rows(sql)

    async def sample_rows(self, table: str, limit: int = 20, **_) -> List[Dict[str, Any]]:
        return await self._rows(f"SELECT TOP {int(limit)} * FROM {_bracket(table)}")
