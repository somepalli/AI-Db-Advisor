from .base_agent import BaseAgent
from typing import List, Dict, Any
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import ObjectNotInPrerequisiteState
import logging

logger = logging.getLogger(__name__)  

PG_TOP_SQL = """
select query,
       calls,
       total_exec_time / nullif(calls,0) as mean_time_ms,
       rows
from pg_stat_statements
order by total_exec_time desc
limit %s;
"""
# Fallback: shows currently running longest queries (no history)
PG_ACTIVITY_FALLBACK = """
select
  query,
  1 as calls,
  extract(milliseconds from (now() - query_start))::bigint as mean_time_ms,
  0 as rows
from pg_stat_activity
where state <> 'idle'
  and query not ilike '%pg_stat_activity%'
order by mean_time_ms desc
limit %s;
"""

class PostgresAgent(BaseAgent):
    def get_db_type(self) -> str:
        return "postgres"

    def _conn(self):
        return psycopg.connect(self.dsn, autocommit=True, row_factory=dict_row)

    def get_schema(self) -> Dict[str, Any]:
        sql = """
        select table_schema, table_name, column_name, data_type, is_nullable
        from information_schema.columns
        where table_schema not in ('pg_catalog','information_schema')
        order by table_schema, table_name, ordinal_position;
        """
        with self._conn() as c, c.cursor() as cur:
            cur.execute(sql)
            cols = cur.fetchall()
        # group by table
        schema: Dict[str, Any] = {}
        for r in cols:
            key = f"{r['table_schema']}.{r['table_name']}"
            schema.setdefault(key, []).append(
                {"column": r["column_name"], "type": r["data_type"], "nullable": r["is_nullable"]}
            )
        return {"tables": schema}

    def get_database_objects(self) -> Dict[str, Any]:
        """pgAdmin-style object inventory: tables/views (with columns + PK flag),
        sequences, functions/procedures, and triggers — grouped as schema.name."""
        cols_sql = """
        select t.table_schema, t.table_name, t.table_type,
               c.column_name, c.data_type, c.is_nullable,
               (pk.column_name is not null) as is_pk
        from information_schema.tables t
        join information_schema.columns c
          on c.table_schema = t.table_schema and c.table_name = t.table_name
        left join (
            select kcu.table_schema, kcu.table_name, kcu.column_name
            from information_schema.table_constraints tc
            join information_schema.key_column_usage kcu
              on tc.constraint_name = kcu.constraint_name
             and tc.table_schema = kcu.table_schema
            where tc.constraint_type = 'PRIMARY KEY'
        ) pk on pk.table_schema = c.table_schema
            and pk.table_name = c.table_name
            and pk.column_name = c.column_name
        where t.table_schema not in ('pg_catalog','information_schema')
        order by t.table_schema, t.table_name, c.ordinal_position;
        """
        seq_sql = """
        select sequence_schema, sequence_name
        from information_schema.sequences
        where sequence_schema not in ('pg_catalog','information_schema')
        order by sequence_schema, sequence_name;
        """
        fn_sql = """
        select n.nspname as schema, p.proname as name,
               case p.prokind when 'p' then 'procedure'
                              when 'a' then 'aggregate'
                              when 'w' then 'window'
                              else 'function' end as kind,
               pg_catalog.pg_get_function_result(p.oid) as returns,
               pg_catalog.pg_get_function_arguments(p.oid) as arguments
        from pg_catalog.pg_proc p
        join pg_catalog.pg_namespace n on n.oid = p.pronamespace
        where n.nspname not in ('pg_catalog','information_schema')
        order by n.nspname, p.proname;
        """
        trg_sql = """
        select trigger_schema, trigger_name, event_object_table,
               action_timing,
               string_agg(event_manipulation, ', ' order by event_manipulation) as events
        from information_schema.triggers
        where trigger_schema not in ('pg_catalog','information_schema')
        group by trigger_schema, trigger_name, event_object_table, action_timing
        order by trigger_schema, trigger_name;
        """

        tables: Dict[str, Any] = {}
        views: Dict[str, Any] = {}
        sequences: List[str] = []
        functions: List[Dict[str, Any]] = []
        triggers: List[Dict[str, Any]] = []

        with self._conn() as c, c.cursor() as cur:
            cur.execute("select current_database() as db;")
            db_name = cur.fetchone()["db"]

            cur.execute(cols_sql)
            for r in cur.fetchall():
                key = f"{r['table_schema']}.{r['table_name']}"
                target = views if r["table_type"] == "VIEW" else tables
                target.setdefault(key, []).append({
                    "column": r["column_name"],
                    "type": r["data_type"],
                    "nullable": r["is_nullable"],
                    "pk": r["is_pk"],
                })

            # Secondary catalogs are best-effort; never fail the whole tree.
            try:
                cur.execute(seq_sql)
                sequences = [f"{r['sequence_schema']}.{r['sequence_name']}" for r in cur.fetchall()]
            except Exception as e:
                logger.warning("Failed to list sequences: %s", e)

            try:
                cur.execute(fn_sql)
                functions = [{
                    "name": f"{r['schema']}.{r['name']}",
                    "kind": r["kind"],
                    "returns": r["returns"],
                    "arguments": r["arguments"],
                } for r in cur.fetchall()]
            except Exception as e:
                logger.warning("Failed to list functions: %s", e)

            try:
                cur.execute(trg_sql)
                triggers = [{
                    "name": f"{r['trigger_schema']}.{r['trigger_name']}",
                    "table": r["event_object_table"],
                    "timing": r["action_timing"],
                    "events": r["events"],
                } for r in cur.fetchall()]
            except Exception as e:
                logger.warning("Failed to list triggers: %s", e)

        return {
            "database": db_name,
            "tables": tables,
            "views": views,
            "sequences": sequences,
            "functions": functions,
            "triggers": triggers,
        }

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        with self._conn() as c, c.cursor() as cur:
            try:
                # try pg_stat_statements first
                cur.execute("create extension if not exists pg_stat_statements;")
                cur.execute(PG_TOP_SQL, (limit,))
                rows = cur.fetchall()
                for r in rows:
                    r["source"] = "pg_stat_statements"
                return rows
            except ObjectNotInPrerequisiteState:
                # extension not preloaded -> fallback to activity
                cur.execute(PG_ACTIVITY_FALLBACK, (limit,))
                rows = cur.fetchall()
                for r in rows:
                    r["source"] = "pg_stat_activity"
                    r["note"] = "pg_stat_statements unavailable; showing longest currently running queries"
                return rows

    def explain(self, sql: str, analyze: bool = False) -> Dict[str, Any]:
        with self._conn() as c, c.cursor() as cur:
            fmt = "EXPLAIN (FORMAT JSON{}) ".format(", ANALYZE, BUFFERS" if analyze else "")
            cur.execute(fmt + sql)
            plan = cur.fetchone()
        return {"plan": plan["QUERY PLAN"] if "QUERY PLAN" in plan else list(plan.values())[0]}

    def locks(self) -> List[Dict[str, Any]]:
        q = """
        select locktype, mode, granted, l.pid, now()-query_start as age, query
        from pg_locks l
        join pg_stat_activity a on a.pid = l.pid
        order by granted asc, age desc;
        """
        with self._conn() as c, c.cursor() as cur:
            cur.execute(q)
            return cur.fetchall()

    def stats(self) -> Dict[str, Any]:
        q = """
        select
          (select sum(pg_database_size(datname)) from pg_database)::bigint as total_db_size,
          (select numbackends from pg_stat_database where datname = current_database() limit 1) as active_backends;
        """
        with self._conn() as c, c.cursor() as cur:
            cur.execute(q)
            return cur.fetchone()

    def _ensure_hypopg(self, cur) -> bool:
        try:
            cur.execute("create extension if not exists hypopg;")
            return True
        except Exception:
            return False  # not installed

    def hypothetical_index(self, table, columns, include=None, method=None):
        with self._conn() as c, c.cursor() as cur:
            if not self._ensure_hypopg(cur):
                return {"hypo_stmt": None, "hypopg_available": False}
            meth = method or "btree"
            cols = ", ".join(columns)
            inc  = f" INCLUDE ({', '.join(include)})" if include else ""
            stmt = f"CREATE INDEX ON {table} USING {meth} ({cols}){inc};"
            cur.execute("select * from hypopg_create_index(%s);", (stmt,))
            return {"hypo_stmt": stmt, "hypopg_available": True}

    def plan_with_hypo(self, sql: str, idx_stmt: str):
        with self._conn() as c, c.cursor() as cur:
            if not self._ensure_hypopg(cur) or not idx_stmt:
                # Fallback: plain plan only
                cur.execute("EXPLAIN (FORMAT JSON) " + sql)
                return {"plan": cur.fetchone()["QUERY PLAN"], "validated": False}
            cur.execute("select * from hypopg_reset();")
            cur.execute("select * from hypopg_create_index(%s);", (idx_stmt,))
            cur.execute("EXPLAIN (FORMAT JSON) " + sql)
            return {"plan": cur.fetchone()["QUERY PLAN"], "validated": True}

    def get_existing_indexes(self, table_name: str = None) -> List[Dict[str, Any]]:
        """
        Get all existing indexes, optionally filtered by table.

        Returns list of indexes with:
        - table_name: Full qualified table name
        - index_name: Name of the index
        - columns: List of column names in index order
        - is_unique: Whether index is unique
        - index_type: btree, gin, gist, etc.
        """
        # Query to get all indexes with their columns
        query = """
        SELECT
            n.nspname || '.' || t.relname AS table_name,
            t.relname AS table_name_short,
            i.relname AS index_name,
            array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS columns,
            ix.indisunique AS is_unique,
            am.amname AS index_type
        FROM pg_class t
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN pg_index ix ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_am am ON i.relam = am.oid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
        WHERE t.relkind = 'r'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND a.attnum > 0
        """

        params = []
        if table_name:
            # Support both "table" and "schema.table" formats
            query += " AND (t.relname = %s OR n.nspname || '.' || t.relname = %s)"
            params = [table_name, table_name]

        query += """
        GROUP BY n.nspname, t.relname, i.relname, ix.indisunique, am.amname
        ORDER BY table_name, index_name;
        """

        with self._conn() as c, c.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return rows

    def index_exists(self, table_name: str, columns: List[str]) -> bool:
        """
        Check if an index already exists on the given table with the exact column set.

        Args:
            table_name: Table name (with or without schema)
            columns: List of column names (order matters for composite indexes)

        Returns:
            True if an index with matching columns exists
        """
        existing = self.get_existing_indexes(table_name)

        # Normalize columns for comparison (lowercase)
        columns_normalized = [c.lower().strip() for c in columns]

        logger.debug(f"Checking if index exists on {table_name}({', '.join(columns_normalized)})")
        logger.debug(f"Found {len(existing)} existing indexes on {table_name}")

        for idx in existing:
            idx_columns = [c.lower().strip() for c in idx['columns']]
            logger.debug(f"  Comparing with {idx['index_name']}: ({', '.join(idx_columns)})")

            # Check if columns match (exact order or subset)
            # An index on (a, b, c) can serve queries on (a), (a, b), or (a, b, c)
            if columns_normalized == idx_columns[:len(columns_normalized)]:
                logger.info(f"✓ Index match found: {idx['index_name']} on {table_name}({', '.join(idx['columns'])}) - suggestion will be skipped")
                return True

        logger.debug(f"✗ No matching index found on {table_name}({', '.join(columns_normalized)})")
        return False

    def execute_query(self, sql: str) -> Dict[str, Any]:
        """Execute a query and return results (for data sync and analytics)"""
        try:
            with self._conn() as c, c.cursor() as cur:
                cur.execute(sql)

                # Check if there are results to fetch
                if cur.description:
                    rows = cur.fetchall()
                    return {
                        "success": True,
                        "rows": rows,
                        "row_count": len(rows)
                    }
                else:
                    # For queries that don't return rows (INSERT, UPDATE, etc.)
                    return {
                        "success": True,
                        "rows": [],
                        "row_count": cur.rowcount
                    }
        except Exception as e:
            logger.error(f"PostgreSQL execute error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
