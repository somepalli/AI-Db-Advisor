"""
Oracle Database Agent
Supports Oracle Database with AI-powered optimization
"""
from .base_agent import BaseAgent
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class OracleAgent(BaseAgent):
    """
    Oracle Database agent.
    Connection string format: oracle://user:password@host:port/service_name
    or: oracle+cx_oracle://user:password@host:port/?service_name=SERVICE
    """

    def get_db_type(self) -> str:
        return "oracle"

    def _conn(self):
        """Create Oracle connection using cx_Oracle"""
        try:
            import cx_Oracle
            from urllib.parse import urlparse

            parsed = urlparse(self.dsn)

            # Build connection string
            dsn = cx_Oracle.makedsn(
                parsed.hostname or 'localhost',
                parsed.port or 1521,
                service_name=parsed.path.lstrip('/') if parsed.path else 'ORCL'
            )

            conn = cx_Oracle.connect(
                user=parsed.username,
                password=parsed.password,
                dsn=dsn
            )
            return conn
        except ImportError:
            raise Exception("cx_Oracle not installed. Run: pip install cx_Oracle")

    def _fetch_dict(self, cursor):
        """Convert Oracle cursor to list of dicts"""
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_schema(self) -> Dict[str, Any]:
        """Get Oracle schema from ALL_TAB_COLUMNS"""
        query = """
        SELECT
            t.owner || '.' || t.table_name as table_name,
            c.column_name,
            c.data_type,
            CASE WHEN c.nullable = 'Y' THEN 'YES' ELSE 'NO' END as is_nullable
        FROM all_tables t
        JOIN all_tab_columns c ON t.owner = c.owner AND t.table_name = c.table_name
        WHERE t.owner NOT IN ('SYS', 'SYSTEM', 'OUTLN', 'DBSNMP', 'APPQOSSYS', 'WMSYS', 'EXFSYS', 'CTXSYS', 'XDB', 'ANONYMOUS', 'ORDSYS', 'MDSYS', 'ORDDATA', 'OLAPSYS', 'FLOWS_FILES', 'APEX_PUBLIC_USER')
        ORDER BY t.owner, t.table_name, c.column_id
        """

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            cols = self._fetch_dict(cursor)

            schema: Dict[str, Any] = {}
            for r in cols:
                key = r['TABLE_NAME']
                schema.setdefault(key, []).append({
                    "column": r["COLUMN_NAME"],
                    "type": r["DATA_TYPE"],
                    "nullable": r["IS_NULLABLE"]
                })

            return {"tables": schema}
        finally:
            conn.close()

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get top queries from V$SQL"""
        query = f"""
        SELECT * FROM (
            SELECT
                sql_text as query,
                executions as calls,
                elapsed_time / GREATEST(executions, 1) / 1000 as mean_time_ms,
                rows_processed / GREATEST(executions, 1) as rows
            FROM v$sql
            WHERE sql_text IS NOT NULL
                AND sql_text NOT LIKE '%v$sql%'
                AND command_type IN (2, 3, 6, 7)
            ORDER BY elapsed_time DESC
        ) WHERE ROWNUM <= {limit}
        """

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = self._fetch_dict(cursor)
            for r in rows:
                r["source"] = "v$sql"
            return rows
        except Exception as e:
            logger.warning(f"v$sql unavailable: {e}")
            return []
        finally:
            conn.close()

    def explain(self, sql: str, analyze: bool = False) -> Dict[str, Any]:
        """Get Oracle execution plan"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Set statement ID
            statement_id = 'EXPLAIN_PLAN_' + str(hash(sql))[:10]

            # Generate explain plan
            cursor.execute(f"EXPLAIN PLAN SET STATEMENT_ID = '{statement_id}' FOR {sql}")

            # Retrieve plan
            plan_query = f"""
            SELECT
                id,
                parent_id,
                operation,
                options,
                object_name,
                cost,
                cardinality as rows,
                bytes,
                access_predicates,
                filter_predicates
            FROM plan_table
            WHERE statement_id = '{statement_id}'
            ORDER BY id
            """
            cursor.execute(plan_query)
            plan_rows = self._fetch_dict(cursor)

            # Clean up
            cursor.execute(f"DELETE FROM plan_table WHERE statement_id = '{statement_id}'")
            conn.commit()

            return {"plan": plan_rows, "format": "oracle"}
        except Exception as e:
            logger.error(f"EXPLAIN failed: {e}")
            return {"plan": None, "error": str(e)}
        finally:
            conn.close()

    def locks(self) -> List[Dict[str, Any]]:
        """Get Oracle locks from V$LOCK"""
        query = """
        SELECT
            l.type as locktype,
            DECODE(l.lmode,
                0, 'None',
                1, 'Null',
                2, 'Row-S',
                3, 'Row-X',
                4, 'Share',
                5, 'S/Row-X',
                6, 'Exclusive') as mode,
            CASE WHEN l.request = 0 THEN 1 ELSE 0 END as granted,
            s.sid as pid,
            s.username as database_name
        FROM v$lock l
        JOIN v$session s ON l.sid = s.sid
        WHERE l.type IN ('TM', 'TX')
        """

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            return self._fetch_dict(cursor)
        except Exception as e:
            logger.warning(f"v$lock unavailable: {e}")
            return []
        finally:
            conn.close()

    def stats(self) -> Dict[str, Any]:
        """Get Oracle database statistics"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Get database size from DBA_SEGMENTS
            cursor.execute("""
                SELECT SUM(bytes) as total_bytes
                FROM dba_segments
            """)
            size_result = cursor.fetchone()

            # Get session count
            cursor.execute("""
                SELECT COUNT(*) as session_count
                FROM v$session
                WHERE username IS NOT NULL
            """)
            session_result = cursor.fetchone()

            return {
                "total_db_size": int(size_result[0] if size_result and size_result[0] else 0),
                "active_backends": int(session_result[0] if session_result else 0)
            }
        except Exception as e:
            logger.error(f"Stats query failed: {e}")
            return {"total_db_size": 0, "active_backends": 0}
        finally:
            conn.close()

    def get_existing_indexes(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get existing Oracle indexes"""
        query = """
        SELECT
            i.owner || '.' || i.table_name as table_name,
            i.table_name as table_name_short,
            i.index_name,
            LISTAGG(c.column_name, ',') WITHIN GROUP (ORDER BY c.column_position) as columns_str,
            CASE WHEN i.uniqueness = 'UNIQUE' THEN 1 ELSE 0 END as is_unique,
            i.index_type
        FROM all_indexes i
        JOIN all_ind_columns c ON i.owner = c.index_owner AND i.index_name = c.index_name
        WHERE i.owner NOT IN ('SYS', 'SYSTEM')
        """

        params = []
        if table_name:
            query += " AND i.table_name = :1"
            params = [table_name.upper()]

        query += " GROUP BY i.owner, i.table_name, i.index_name, i.uniqueness, i.index_type"

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = self._fetch_dict(cursor)

            # Convert columns_str to list
            for row in rows:
                row['columns'] = row['COLUMNS_STR'].split(',') if row.get('COLUMNS_STR') else []
                # Normalize keys
                row['table_name'] = row.get('TABLE_NAME', '')
                row['table_name_short'] = row.get('TABLE_NAME_SHORT', '')
                row['index_name'] = row.get('INDEX_NAME', '')
                row['is_unique'] = row.get('IS_UNIQUE', 0)
                row['index_type'] = row.get('INDEX_TYPE', '')

            return rows
        finally:
            conn.close()

    def index_exists(self, table_name: str, columns: List[str]) -> bool:
        """Check if Oracle index exists"""
        existing = self.get_existing_indexes(table_name)
        columns_normalized = [c.upper().strip() for c in columns]

        for idx in existing:
            idx_columns = [c.upper().strip() for c in idx['columns']]
            if columns_normalized == idx_columns[:len(columns_normalized)]:
                logger.info(f"Index already exists: {idx['index_name']} on {idx['table_name_short']}")
                return True

        return False

    def get_optimization_context(self) -> Dict[str, Any]:
        """Get Oracle-specific optimization context"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Get Oracle version
            cursor.execute("SELECT * FROM v$version WHERE ROWNUM = 1")
            version = cursor.fetchone()[0]

            # Get table count
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM all_tables
                WHERE owner NOT IN ('SYS', 'SYSTEM')
            """)
            table_count = cursor.fetchone()[0]

            # Get index count
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM all_indexes
                WHERE owner NOT IN ('SYS', 'SYSTEM')
            """)
            index_count = cursor.fetchone()[0]

            stats = self.stats()

            return {
                "db_type": "oracle",
                "version": version.split('\n')[0] if version else "unknown",
                "total_size": stats.get("total_db_size", 0),
                "table_count": table_count,
                "index_count": index_count
            }
        finally:
            conn.close()
