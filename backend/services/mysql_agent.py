"""
MySQL/MariaDB Agent
Supports both MySQL and MariaDB databases with AI-powered optimization
"""
from .base_agent import BaseAgent
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class MySQLAgent(BaseAgent):
    """
    MySQL/MariaDB database agent.
    Connection string format: mysql://user:password@host:port/database
    or: mysql+pymysql://user:password@host:port/database
    """

    def get_db_type(self) -> str:
        return "mysql"

    def _conn(self):
        """Create MySQL connection using pymysql"""
        try:
            import pymysql
            import pymysql.cursors
            from urllib.parse import urlparse

            parsed = urlparse(self.dsn)
            return pymysql.connect(
                host=parsed.hostname or 'localhost',
                port=parsed.port or 3306,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path.lstrip('/') if parsed.path else None,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True
            )
        except ImportError:
            raise Exception("pymysql not installed. Run: pip install pymysql")

    def get_schema(self) -> Dict[str, Any]:
        """Get MySQL schema from INFORMATION_SCHEMA"""
        query = """
        SELECT
            TABLE_SCHEMA as table_schema,
            TABLE_NAME as table_name,
            COLUMN_NAME as column_name,
            DATA_TYPE as data_type,
            IS_NULLABLE as is_nullable
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
        ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
        """

        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                cols = cur.fetchall()

            schema: Dict[str, Any] = {}
            for r in cols:
                key = f"{r['table_schema']}.{r['table_name']}"
                schema.setdefault(key, []).append({
                    "column": r["column_name"],
                    "type": r["data_type"],
                    "nullable": r["is_nullable"]
                })

            return {"tables": schema}
        finally:
            conn.close()

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get top queries from performance_schema.events_statements_summary_by_digest"""
        query = f"""
        SELECT
            DIGEST_TEXT as query,
            COUNT_STAR as calls,
            AVG_TIMER_WAIT / 1000000000 as mean_time_ms,
            SUM_ROWS_EXAMINED as rows
        FROM performance_schema.events_statements_summary_by_digest
        WHERE DIGEST_TEXT IS NOT NULL
        ORDER BY SUM_TIMER_WAIT DESC
        LIMIT {limit}
        """

        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                for r in rows:
                    r["source"] = "performance_schema"
                return rows
        except Exception as e:
            logger.warning(f"performance_schema unavailable: {e}")
            return [{"query": "Performance schema not available", "calls": 0, "mean_time_ms": 0, "rows": 0, "source": "none"}]
        finally:
            conn.close()

    def explain(self, sql: str, analyze: bool = False) -> Dict[str, Any]:
        """Get MySQL EXPLAIN plan"""
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                # MySQL EXPLAIN FORMAT=JSON
                explain_sql = f"EXPLAIN FORMAT=JSON {sql}" if not analyze else f"EXPLAIN ANALYZE {sql}"
                cur.execute(explain_sql)
                result = cur.fetchone()

                # MySQL returns JSON in 'EXPLAIN' column
                if result and 'EXPLAIN' in result:
                    import json
                    return {"plan": json.loads(result['EXPLAIN'])}
                return {"plan": result}
        finally:
            conn.close()

    def locks(self) -> List[Dict[str, Any]]:
        """Get MySQL locks from performance_schema"""
        query = """
        SELECT
            OBJECT_SCHEMA as schema_name,
            OBJECT_NAME as table_name,
            LOCK_TYPE as locktype,
            LOCK_MODE as mode,
            LOCK_STATUS as status,
            PROCESSLIST_ID as pid
        FROM performance_schema.metadata_locks
        WHERE OBJECT_TYPE = 'TABLE'
        LIMIT 50
        """

        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchall()
        except Exception as e:
            logger.warning(f"metadata_locks unavailable: {e}")
            return []
        finally:
            conn.close()

    def stats(self) -> Dict[str, Any]:
        """Get MySQL database statistics"""
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                # Get database size
                cur.execute("""
                    SELECT SUM(data_length + index_length) as total_db_size
                    FROM information_schema.TABLES
                    WHERE table_schema NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
                """)
                size_result = cur.fetchone()

                # Get connection count
                cur.execute("SHOW STATUS LIKE 'Threads_connected'")
                conn_result = cur.fetchone()

                return {
                    "total_db_size": int(size_result['total_db_size'] or 0),
                    "active_backends": int(conn_result['Value'] if conn_result else 0)
                }
        finally:
            conn.close()

    def get_existing_indexes(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get existing MySQL indexes"""
        query = """
        SELECT
            TABLE_SCHEMA as table_schema,
            TABLE_NAME as table_name_short,
            CONCAT(TABLE_SCHEMA, '.', TABLE_NAME) as table_name,
            INDEX_NAME as index_name,
            GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) as columns_str,
            NON_UNIQUE = 0 as is_unique,
            INDEX_TYPE as index_type
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
        """

        params = []
        if table_name:
            query += " AND TABLE_NAME = %s"
            params = [table_name]

        query += " GROUP BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, NON_UNIQUE, INDEX_TYPE"

        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

                # Convert columns_str to list
                for row in rows:
                    row['columns'] = row['columns_str'].split(',') if row['columns_str'] else []
                    del row['columns_str']

                return rows
        finally:
            conn.close()

    def index_exists(self, table_name: str, columns: List[str]) -> bool:
        """Check if MySQL index exists"""
        existing = self.get_existing_indexes(table_name)
        columns_normalized = [c.lower().strip() for c in columns]

        for idx in existing:
            idx_columns = [c.lower().strip() for c in idx['columns']]
            if columns_normalized == idx_columns[:len(columns_normalized)]:
                logger.info(f"Index already exists: {idx['index_name']} on {idx['table_name_short']}")
                return True

        return False

    def get_optimization_context(self) -> Dict[str, Any]:
        """Get MySQL-specific optimization context"""
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                # Get MySQL version
                cur.execute("SELECT VERSION() as version")
                version = cur.fetchone()['version']

                # Get table count
                cur.execute("""
                    SELECT COUNT(*) as count FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
                """)
                table_count = cur.fetchone()['count']

                # Get index count
                cur.execute("""
                    SELECT COUNT(DISTINCT CONCAT(TABLE_SCHEMA, '.', TABLE_NAME, '.', INDEX_NAME)) as count
                    FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
                """)
                index_count = cur.fetchone()['count']

                stats = self.stats()

                return {
                    "db_type": "mysql",
                    "version": version,
                    "total_size": stats.get("total_db_size", 0),
                    "table_count": table_count,
                    "index_count": index_count
                }
        finally:
            conn.close()
