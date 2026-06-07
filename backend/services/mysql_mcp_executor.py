"""
MySQL / MariaDB gated executor — access-mode-aware tool execution.

The MySQL analogue of ``PostgresMcpExecutor``. There is no in-process "mysql-mcp"
driver, so gated tools run directly through pymysql. The data boundary is still
enforced two ways:

  * the selector in ``tool_registry.active_tools`` decides which ops exist for the
    session (data tools are absent in hosted mode), and
  * in hosted mode this executor opens the session ``READ ONLY``, so even the
    metadata tools cannot mutate, mirroring postgres-mcp's SafeSqlDriver.

Metadata tools run fixed read-only catalog SQL we author (information_schema /
performance_schema / sys). The single user-supplied statement (``explain``) is
wrapped in ``EXPLAIN FORMAT=JSON``, which is plan-only and never executes the query.
Data tools run on the read-write session and are only reachable when the selector
admits them (local trust).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .dsn_utils import maybe_rewrite_localhost_dsn

logger = logging.getLogger(__name__)

# Curated tuning variables surfaced by config_audit (avoids dumping all ~600 vars).
_CONFIG_VARS = (
    "version", "max_connections", "innodb_buffer_pool_size", "innodb_buffer_pool_instances",
    "innodb_log_file_size", "innodb_flush_log_at_trx_commit", "innodb_flush_method",
    "innodb_io_capacity", "innodb_read_io_threads", "innodb_write_io_threads",
    "query_cache_type", "query_cache_size", "tmp_table_size", "max_heap_table_size",
    "table_open_cache", "thread_cache_size", "join_buffer_size", "sort_buffer_size",
    "slow_query_log", "long_query_time",
)

# Scoped to the connected database via DATABASE(); never crosses into system schemas.
_LIST_SCHEMA_SQL = """
select table_schema, table_name, column_name, data_type, is_nullable
from information_schema.columns
where table_schema = database()
order by table_name, ordinal_position
"""

_INDEX_INVENTORY_SQL = """
select table_schema, table_name, index_name,
       group_concat(column_name order by seq_in_index) as columns,
       (non_unique = 0) as is_unique, index_type
from information_schema.statistics
where table_schema = database()
{table_filter}
group by table_schema, table_name, index_name, non_unique, index_type
order by table_name, index_name
"""

# sys.schema_unused_indexes lists indexes never hit since the last server restart.
_INDEX_USAGE_SQL = """
select object_schema, object_name as table_name, index_name
from sys.schema_unused_indexes
where object_schema = database()
limit {limit}
"""

# Digest text already has literals folded to '?'; the normalize_sql sanitizer is a
# second belt-and-braces pass before anything reaches a hosted model.
_TOP_QUERIES_SQL = """
select digest_text as query, count_star as calls,
       round(avg_timer_wait / 1000000000, 3) as mean_time_ms,
       sum_rows_examined as `rows`
from performance_schema.events_statements_summary_by_digest
where digest_text is not null and schema_name = database()
order by sum_timer_wait desc
limit {limit}
"""

_TABLE_STATS_SQL = """
select table_name, table_rows, data_length, index_length,
       data_length + index_length as total_bytes, auto_increment, engine
from information_schema.tables
where table_schema = database() and table_type = 'BASE TABLE'
order by (data_length + index_length) desc
limit {limit}
"""

# Identifiers passed to data tools must be plain identifiers — no injection.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)?$")
_READ_RE = re.compile(r"^\s*(select|with|show|describe|desc|explain)\b", re.IGNORECASE)


def _safe_ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return name


class MySqlMcpExecutor:
    """Owns a pymysql connection for one chat turn; one coroutine per tool op."""

    def __init__(self, dsn: str, trust: str):
        self.dsn = maybe_rewrite_localhost_dsn(dsn)
        self.trust = trust
        self._conn = None

    @property
    def driver_kind(self) -> str:
        return "ReadOnly" if self.trust == "hosted" else "ReadWrite"

    def _connect(self):
        import pymysql
        import pymysql.cursors

        parsed = urlparse(self.dsn)
        conn = pymysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip("/") if parsed.path else None,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=10,
            read_timeout=30,
        )
        if self.trust == "hosted":
            # Structural read-only enforcement for the whole session (hosted models).
            with conn.cursor() as cur:
                cur.execute("SET SESSION TRANSACTION READ ONLY")
        return conn

    async def _ensure(self):
        if self._conn is None:
            self._conn = await asyncio.to_thread(self._connect)
            logger.info("MySqlMcpExecutor ready: trust=%s driver=%s", self.trust, self.driver_kind)

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
        with self._conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall() or [])

    async def _rows(self, sql: str) -> List[Dict[str, Any]]:
        await self._ensure()
        return await asyncio.to_thread(self._query_sync, sql)

    # -- metadata tools (read-only catalog SQL) ----------------------------
    async def list_schema(self, **_) -> List[Dict[str, Any]]:
        return await self._rows(_LIST_SCHEMA_SQL)

    async def index_inventory(self, table: Optional[str] = None, **_) -> List[Dict[str, Any]]:
        flt = f"and table_name = '{_safe_ident(table).split('.')[-1]}'" if table else ""
        rows = await self._rows(_INDEX_INVENTORY_SQL.format(table_filter=flt))
        for r in rows:
            if isinstance(r.get("columns"), str):
                r["columns"] = r["columns"].split(",")
        return rows

    async def index_usage(self, limit: int = 50, **_) -> List[Dict[str, Any]]:
        try:
            return await self._rows(_INDEX_USAGE_SQL.format(limit=int(limit)))
        except Exception as e:
            logger.info("index_usage unavailable (sys schema?): %s", e)
            return [{"note": "sys.schema_unused_indexes not available"}]

    async def top_queries(self, limit: int = 10, **_) -> List[Dict[str, Any]]:
        try:
            return await self._rows(_TOP_QUERIES_SQL.format(limit=int(limit)))
        except Exception as e:
            logger.info("top_queries unavailable (performance_schema?): %s", e)
            return [{"note": "performance_schema digest not available", "query": None, "calls": 0}]

    async def table_stats(self, limit: int = 50, **_) -> List[Dict[str, Any]]:
        return await self._rows(_TABLE_STATS_SQL.format(limit=int(limit)))

    async def config_audit(self, **_) -> List[Dict[str, Any]]:
        await self._ensure()
        names = "','".join(_CONFIG_VARS)
        return await self._rows(
            f"show variables where variable_name in ('{names}')"
        )

    async def explain(self, sql: str, **_) -> Any:
        if not sql:
            return {"note": "no SQL supplied"}
        # EXPLAIN FORMAT=JSON is plan-only (never executes); still require a read shape.
        if not _READ_RE.match(sql):
            return {"note": "explain only supports read statements"}
        await self._ensure()
        rows = await self._rows(f"EXPLAIN FORMAT=JSON {sql}")
        if rows:
            raw = rows[0].get("EXPLAIN") or next(iter(rows[0].values()), None)
            try:
                return json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                return raw
        return {"note": "no plan returned"}

    # -- data tools (read-write session; selector admits only when local) --
    async def run_query(self, sql: str, **_) -> List[Dict[str, Any]]:
        return await self._rows(sql)

    async def sample_rows(self, table: str, limit: int = 20, **_) -> List[Dict[str, Any]]:
        return await self._rows(f"SELECT * FROM {_safe_ident(table)} LIMIT {int(limit)}")
