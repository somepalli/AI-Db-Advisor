"""
SQLite Agent
Supports SQLite with AI-powered optimization
"""
from .base_agent import BaseAgent
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SQLiteAgent(BaseAgent):
    """
    SQLite database agent.
    Connection string format: sqlite:///path/to/database.db
    or: sqlite:///C:/path/to/database.db (Windows absolute path)
    """

    def get_db_type(self) -> str:
        return "sqlite"

    def _conn(self):
        """Create SQLite connection"""
        try:
            import sqlite3
            from urllib.parse import urlparse

            parsed = urlparse(self.dsn)

            # Extract path from DSN
            # For sqlite:///path/to/db.db, path will be /path/to/db.db
            # For sqlite:///C:/path/to/db.db, path will be /C:/path/to/db.db
            db_path = parsed.path

            # Handle Windows paths (remove leading slash if drive letter follows)
            if db_path.startswith('/') and len(db_path) > 2 and db_path[2] == ':':
                db_path = db_path[1:]

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            return conn
        except ImportError:
            raise Exception("sqlite3 not available (should be part of Python stdlib)")

    def _fetch_dict(self, cursor):
        """Convert SQLite cursor to list of dicts"""
        return [dict(row) for row in cursor.fetchall()]

    def get_schema(self) -> Dict[str, Any]:
        """Get SQLite schema from sqlite_master and pragma"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]

            schema: Dict[str, Any] = {}

            # Get columns for each table
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()

                schema[table] = [
                    {
                        "column": col[1],  # name
                        "type": col[2],    # type
                        "nullable": "NO" if col[3] else "YES"  # notnull
                    }
                    for col in columns
                ]

            return {"tables": schema}
        finally:
            conn.close()

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        """SQLite doesn't track query stats - return empty list"""
        logger.info("SQLite doesn't track query statistics")
        return []

    def explain(self, sql: str, analyze: bool = False) -> Dict[str, Any]:
        """Get SQLite query plan"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Use EXPLAIN QUERY PLAN
            explain_cmd = "EXPLAIN QUERY PLAN" if not analyze else "EXPLAIN QUERY PLAN"
            cursor.execute(f"{explain_cmd} {sql}")
            plan_rows = self._fetch_dict(cursor)

            return {"plan": plan_rows, "format": "sqlite"}
        except Exception as e:
            logger.error(f"EXPLAIN failed: {e}")
            return {"plan": None, "error": str(e)}
        finally:
            conn.close()

    def locks(self) -> List[Dict[str, Any]]:
        """SQLite uses file-level locking - not queryable"""
        logger.info("SQLite uses file-level locking (not queryable)")
        return []

    def stats(self) -> Dict[str, Any]:
        """Get SQLite database statistics"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Get page count and page size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]

            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            total_size = page_count * page_size

            # SQLite is single-connection for writes, so active backends is always 1
            return {
                "total_db_size": total_size,
                "active_backends": 1
            }
        except Exception as e:
            logger.error(f"Stats query failed: {e}")
            return {"total_db_size": 0, "active_backends": 0}
        finally:
            conn.close()

    def get_existing_indexes(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get existing SQLite indexes"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            if table_name:
                # Get indexes for specific table
                cursor.execute(f"PRAGMA index_list({table_name})")
                indexes = self._fetch_dict(cursor)

                results = []
                for idx in indexes:
                    idx_name = idx['name']

                    # Get columns for this index
                    cursor.execute(f"PRAGMA index_info({idx_name})")
                    columns = [col[2] for col in cursor.fetchall()]  # col[2] is column name

                    results.append({
                        "table_schema": "main",
                        "table_name_short": table_name,
                        "table_name": table_name,
                        "index_name": idx_name,
                        "columns": columns,
                        "is_unique": idx['unique'],
                        "index_type": "btree"  # SQLite uses B-tree for all indexes
                    })

                return results
            else:
                # Get indexes for all tables
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = [row[0] for row in cursor.fetchall()]

                all_indexes = []
                for table in tables:
                    all_indexes.extend(self.get_existing_indexes(table))

                return all_indexes
        finally:
            conn.close()

    def index_exists(self, table_name: str, columns: List[str]) -> bool:
        """Check if SQLite index exists"""
        existing = self.get_existing_indexes(table_name)
        columns_normalized = [c.lower().strip() for c in columns]

        for idx in existing:
            idx_columns = [c.lower().strip() for c in idx['columns']]
            if columns_normalized == idx_columns[:len(columns_normalized)]:
                logger.info(f"Index already exists: {idx['index_name']} on {idx['table_name_short']}")
                return True

        return False

    def get_optimization_context(self) -> Dict[str, Any]:
        """Get SQLite-specific optimization context"""
        conn = self._conn()
        try:
            cursor = conn.cursor()

            # Get SQLite version
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]

            # Get table count
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            table_count = cursor.fetchone()[0]

            # Get index count
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM sqlite_master
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
            """)
            index_count = cursor.fetchone()[0]

            stats = self.stats()

            return {
                "db_type": "sqlite",
                "version": version,
                "total_size": stats.get("total_db_size", 0),
                "table_count": table_count,
                "index_count": index_count
            }
        finally:
            conn.close()
