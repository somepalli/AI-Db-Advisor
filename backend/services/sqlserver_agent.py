"""
Microsoft SQL Server Agent
Supports SQL Server with AI-powered optimization
"""
from .base_agent import BaseAgent
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SQLServerAgent(BaseAgent):
    """
    Microsoft SQL Server database agent.
    Connection string format: mssql+pyodbc://user:password@host:port/database?driver=ODBC+Driver+17+for+SQL+Server
    or: mssql://user:password@host:port/database
    """

    def get_db_type(self) -> str:
        return "sqlserver"

    def _conn(self):
        """Create SQL Server connection using pyodbc"""
        try:
            import pyodbc
            from urllib.parse import urlparse

            parsed = urlparse(self.dsn)

            # Build connection string
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={parsed.hostname or 'localhost'},{parsed.port or 1433};"
                f"DATABASE={parsed.path.lstrip('/') if parsed.path else 'master'};"
                f"UID={parsed.username};"
                f"PWD={parsed.password}"
            )

            conn = pyodbc.connect(conn_str, autocommit=True)
            return conn
        except ImportError:
            raise Exception("pyodbc not installed. Run: pip install pyodbc")

    def _fetch_dict(self, cursor):
        """Convert SQL Server cursor to list of dicts"""
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_schema(self) -> Dict[str, Any]:
        """Get SQL Server schema from sys.columns"""
        query = """
        SELECT
            s.name as table_schema,
            t.name as table_name,
            c.name as column_name,
            ty.name as data_type,
            CASE WHEN c.is_nullable = 1 THEN 'YES' ELSE 'NO' END as is_nullable
        FROM sys.columns c
        JOIN sys.tables t ON c.object_id = t.object_id
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        JOIN sys.types ty ON c.user_type_id = ty.user_type_id
        WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
        ORDER BY s.name, t.name, c.column_id
        """

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            cols = self._fetch_dict(cursor)

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
        """Get top queries from sys.dm_exec_query_stats"""
        query = f"""
        SELECT TOP {limit}
            SUBSTRING(qt.text, (qs.statement_start_offset/2)+1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(qt.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset)/2) + 1) as query,
            qs.execution_count as calls,
            qs.total_elapsed_time / qs.execution_count / 1000 as mean_time_ms,
            qs.total_rows / NULLIF(qs.execution_count, 0) as rows
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
        WHERE qt.text IS NOT NULL
        ORDER BY qs.total_elapsed_time DESC
        """

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = self._fetch_dict(cursor)
            for r in rows:
                r["source"] = "dm_exec_query_stats"
            return rows
        except Exception as e:
            logger.warning(f"dm_exec_query_stats unavailable: {e}")
            return []
        finally:
            conn.close()

    def explain(self, sql: str, analyze: bool = False) -> Dict[str, Any]:
        """Get SQL Server execution plan"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Enable SHOWPLAN_XML
            cursor.execute("SET SHOWPLAN_XML ON")
            cursor.execute(sql)
            plan_xml = cursor.fetchone()[0]
            cursor.execute("SET SHOWPLAN_XML OFF")

            return {"plan": plan_xml, "format": "xml"}
        except Exception as e:
            logger.error(f"EXPLAIN failed: {e}")
            return {"plan": None, "error": str(e)}
        finally:
            conn.close()

    def locks(self) -> List[Dict[str, Any]]:
        """Get SQL Server locks from sys.dm_tran_locks"""
        query = """
        SELECT
            tl.resource_type as locktype,
            tl.request_mode as mode,
            CASE WHEN tl.request_status = 'GRANT' THEN 1 ELSE 0 END as granted,
            tl.request_session_id as pid,
            DB_NAME(tl.resource_database_id) as database_name
        FROM sys.dm_tran_locks tl
        WHERE tl.resource_type IN ('DATABASE', 'TABLE', 'PAGE', 'ROW')
        """

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            return self._fetch_dict(cursor)
        except Exception as e:
            logger.warning(f"dm_tran_locks unavailable: {e}")
            return []
        finally:
            conn.close()

    def stats(self) -> Dict[str, Any]:
        """Get SQL Server database statistics"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Get database size
            cursor.execute("""
                SELECT SUM(size) * 8 / 1024 as total_db_size_mb
                FROM sys.master_files
                WHERE database_id = DB_ID()
            """)
            size_result = cursor.fetchone()

            # Get connection count
            cursor.execute("""
                SELECT COUNT(*) as connection_count
                FROM sys.dm_exec_sessions
                WHERE is_user_process = 1
            """)
            conn_result = cursor.fetchone()

            return {
                "total_db_size": int((size_result[0] or 0) * 1024 * 1024),  # Convert MB to bytes
                "active_backends": int(conn_result[0] if conn_result else 0)
            }
        finally:
            conn.close()

    def get_existing_indexes(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get existing SQL Server indexes"""
        query = """
        SELECT
            SCHEMA_NAME(t.schema_id) as table_schema,
            t.name as table_name_short,
            SCHEMA_NAME(t.schema_id) + '.' + t.name as table_name,
            i.name as index_name,
            STRING_AGG(c.name, ',') WITHIN GROUP (ORDER BY ic.key_ordinal) as columns_str,
            CASE WHEN i.is_unique = 1 THEN 1 ELSE 0 END as is_unique,
            i.type_desc as index_type
        FROM sys.indexes i
        JOIN sys.tables t ON i.object_id = t.object_id
        JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        WHERE i.name IS NOT NULL
        """

        params = []
        if table_name:
            query += " AND t.name = ?"
            params = [table_name]

        query += " GROUP BY SCHEMA_NAME(t.schema_id), t.name, i.name, i.is_unique, i.type_desc"

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = self._fetch_dict(cursor)

            # Convert columns_str to list
            for row in rows:
                row['columns'] = row['columns_str'].split(',') if row['columns_str'] else []
                del row['columns_str']

            return rows
        finally:
            conn.close()

    def index_exists(self, table_name: str, columns: List[str]) -> bool:
        """Check if SQL Server index exists"""
        existing = self.get_existing_indexes(table_name)
        columns_normalized = [c.lower().strip() for c in columns]

        for idx in existing:
            idx_columns = [c.lower().strip() for c in idx['columns']]
            if columns_normalized == idx_columns[:len(columns_normalized)]:
                logger.info(f"Index already exists: {idx['index_name']} on {idx['table_name_short']}")
                return True

        return False

    def get_optimization_context(self) -> Dict[str, Any]:
        """Get SQL Server-specific optimization context"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Get SQL Server version
            cursor.execute("SELECT @@VERSION as version")
            version = cursor.fetchone()[0]

            # Get table count
            cursor.execute("SELECT COUNT(*) as count FROM sys.tables")
            table_count = cursor.fetchone()[0]

            # Get index count
            cursor.execute("SELECT COUNT(*) as count FROM sys.indexes WHERE name IS NOT NULL")
            index_count = cursor.fetchone()[0]

            stats = self.stats()

            return {
                "db_type": "sqlserver",
                "version": version.split('\n')[0] if version else "unknown",
                "total_size": stats.get("total_db_size", 0),
                "table_count": table_count,
                "index_count": index_count
            }
        finally:
            conn.close()
