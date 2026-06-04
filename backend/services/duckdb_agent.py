"""
DuckDB Agent for AI DB Advisor
DuckDB is an embedded analytical database - no server installation required!
"""
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import duckdb
import os

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DuckDBAgent(BaseAgent):
    """
    DuckDB agent for analytics database operations.
    DuckDB is an embedded OLAP database optimized for analytical queries.
    No server installation required - stores data in a local file.
    """

    def get_db_type(self) -> str:
        return "duckdb"

    def _parse_dsn(self, dsn: str) -> str:
        """
        Parse DuckDB DSN into database file path.
        DSN formats:
        - duckdb:///path/to/database.db
        - duckdb:///:memory: (in-memory database)
        """
        if dsn.startswith("duckdb:///"):
            return dsn.replace("duckdb:///", "")
        elif dsn.startswith("duckdb://"):
            return dsn.replace("duckdb://", "")
        return dsn

    def _conn(self):
        """Create DuckDB connection"""
        db_path = self._parse_dsn(self.dsn)

        # Create directory if it doesn't exist
        if db_path != ":memory:" and db_path:
            os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

        return duckdb.connect(database=db_path, read_only=False)

    def get_schema(self) -> Dict[str, Any]:
        """Get DuckDB database schema"""
        conn = self._conn()
        try:
            # Query information_schema for tables and columns
            result = conn.execute("""
                SELECT
                    table_schema || '.' || table_name as full_table_name,
                    column_name,
                    data_type,
                    is_nullable
                FROM information_schema.columns
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_schema, table_name, ordinal_position
            """).fetchall()

            tables = {}
            for row in result:
                table_name = row[0]
                if table_name not in tables:
                    tables[table_name] = []

                tables[table_name].append({
                    "column": row[1],
                    "type": row[2],
                    "nullable": row[3]
                })

            return {"tables": tables}
        except Exception as e:
            logger.error(f"DuckDB schema error: {e}")
            return {"tables": {}, "error": str(e)}
        finally:
            conn.close()

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        DuckDB doesn't have built-in query logging like PostgreSQL.
        Returns empty list.
        """
        return [{
            "info": "DuckDB doesn't track query history",
            "message": "Query logging not available for embedded databases"
        }]

    def explain(self, sql: str, analyze: bool = False) -> Dict[str, Any]:
        """Get DuckDB query execution plan"""
        conn = self._conn()
        try:
            explain_sql = f"EXPLAIN {'ANALYZE ' if analyze else ''}{sql}"
            result = conn.execute(explain_sql).fetchall()

            # Parse the explain output
            plan = []
            for row in result:
                plan.append({"step": row[0] if isinstance(row, tuple) else str(row)})

            return {"plan": plan}
        except Exception as e:
            logger.error(f"DuckDB EXPLAIN error: {e}")
            return {"plan": [], "error": f"DuckDB could not EXPLAIN the query: {e}"}
        finally:
            conn.close()

    def locks(self) -> List[Dict[str, Any]]:
        """Get current locks (DuckDB has minimal locking as embedded DB)"""
        return [{
            "info": "DuckDB uses MVCC (Multi-Version Concurrency Control)",
            "message": "Lock-free reads, single writer at a time"
        }]

    def stats(self) -> Dict[str, Any]:
        """Get DuckDB database statistics"""
        conn = self._conn()
        try:
            db_path = self._parse_dsn(self.dsn)

            # Get database file size
            if db_path and db_path != ":memory:" and os.path.exists(db_path):
                file_size = os.path.getsize(db_path)
                readable_size = self._format_bytes(file_size)
            else:
                readable_size = "In-memory" if db_path == ":memory:" else "0 B"

            # Get table count
            table_result = conn.execute("""
                SELECT COUNT(*) as table_count
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            """).fetchone()

            return {
                "total_db_size": readable_size,
                "table_count": table_result[0] if table_result else 0,
                "database_path": db_path,
                "database_type": "DuckDB (Embedded Analytics)"
            }
        except Exception as e:
            logger.error(f"DuckDB stats error: {e}")
            return {"error": str(e)}
        finally:
            conn.close()

    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} PB"

    def get_existing_indexes(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get existing indexes in DuckDB"""
        conn = self._conn()
        try:
            # DuckDB stores index information differently
            # Query duckdb_indexes() table function
            query = "SELECT * FROM duckdb_indexes()"
            if table_name:
                query += f" WHERE table_name = '{table_name}'"

            result = conn.execute(query).fetchall()

            indexes = []
            for row in result:
                indexes.append({
                    "schema": row[0] if len(row) > 0 else None,
                    "table": row[1] if len(row) > 1 else None,
                    "index_name": row[2] if len(row) > 2 else None,
                    "is_unique": row[3] if len(row) > 3 else False,
                    "is_primary": row[4] if len(row) > 4 else False,
                    "sql": row[5] if len(row) > 5 else None
                })

            return indexes
        except Exception as e:
            logger.error(f"DuckDB get_existing_indexes error: {e}")
            return []
        finally:
            conn.close()

    def index_exists(self, table_name: str, columns: List[str]) -> bool:
        """Check if an index exists on given columns"""
        indexes = self.get_existing_indexes(table_name)
        column_set = set(c.lower().strip() for c in columns)

        for idx in indexes:
            # Parse the SQL to check columns (simplified check)
            idx_sql = idx.get("sql", "").lower()
            if all(col in idx_sql for col in column_set):
                return True

        return False

    def get_optimization_context(self) -> Dict[str, Any]:
        """Get DuckDB-specific optimization context"""
        conn = self._conn()
        try:
            # Get version
            version_result = conn.execute("SELECT version()").fetchone()

            stats = self.stats()

            return {
                "db_type": "duckdb",
                "version": version_result[0] if version_result else "unknown",
                "total_size": stats.get("total_db_size", "0 B"),
                "table_count": stats.get("table_count", 0),
                "database_path": stats.get("database_path", ""),
                "index_count": len(self.get_existing_indexes())
            }
        except Exception as e:
            logger.error(f"DuckDB optimization context error: {e}")
            return {
                "db_type": "duckdb",
                "version": "unknown",
                "error": str(e)
            }
        finally:
            conn.close()

    def execute_query(self, sql: str) -> Dict[str, Any]:
        """Execute a query and return results"""
        conn = self._conn()
        try:
            result = conn.execute(sql).fetchall()

            # Get column names
            columns = [desc[0] for desc in conn.description] if conn.description else []

            # Convert to list of dictionaries
            rows = []
            for row in result:
                rows.append(dict(zip(columns, row)))

            return {
                "success": True,
                "rows": rows,
                "row_count": len(rows)
            }
        except Exception as e:
            logger.error(f"DuckDB execute error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            conn.close()

    def create_table_from_schema(self, table_name: str, schema: List[Dict[str, str]],
                                  engine: Optional[str] = None, order_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a DuckDB table from schema definition.

        Args:
            table_name: Name of the table to create
            schema: List of column definitions
            engine: Ignored (for ClickHouse compatibility)
            order_by: Ignored (for ClickHouse compatibility)
        """
        conn = self._conn()
        try:
            # Build CREATE TABLE statement
            columns = []
            for col in schema:
                col_name = col["column"]
                col_type = self._map_type_to_duckdb(col["type"])
                nullable = "NULL" if col.get("nullable", "YES") == "YES" else "NOT NULL"
                columns.append(f'"{col_name}" {col_type} {nullable}')

            columns_str = ",\n    ".join(columns)

            create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {columns_str}
            )
            """

            conn.execute(create_sql)

            logger.info(f"DuckDB table {table_name} created successfully")

            return {
                "success": True,
                "message": f"Table {table_name} created successfully"
            }
        except Exception as e:
            logger.error(f"DuckDB create table error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            conn.close()

    def _map_type_to_duckdb(self, pg_type: str) -> str:
        """Map PostgreSQL types to DuckDB types"""
        type_mapping = {
            "integer": "INTEGER",
            "bigint": "BIGINT",
            "smallint": "SMALLINT",
            "numeric": "DECIMAL(18, 2)",
            "real": "REAL",
            "double precision": "DOUBLE",
            "character varying": "VARCHAR",
            "varchar": "VARCHAR",
            "text": "VARCHAR",
            "boolean": "BOOLEAN",
            "date": "DATE",
            "timestamp without time zone": "TIMESTAMP",
            "timestamp with time zone": "TIMESTAMPTZ",
            "timestamp": "TIMESTAMP",
            "json": "JSON",
            "jsonb": "JSON",
        }

        # Remove size constraints like varchar(255)
        base_type = pg_type.split("(")[0].strip().lower()
        return type_mapping.get(base_type, "VARCHAR")

    def insert_batch(self, table_name: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert batch data into DuckDB table"""
        conn = self._conn()
        try:
            if not data:
                logger.debug(f"No data to insert into {table_name}")
                return {"success": True, "rows_inserted": 0}

            logger.debug(f"Inserting {len(data)} rows into {table_name}")

            # Use DuckDB's efficient batch insert via DataFrame
            import pandas as pd

            # Convert data to DataFrame
            df = pd.DataFrame(data)

            logger.debug(f"DataFrame created with columns: {list(df.columns)}")
            logger.debug(f"DataFrame shape: {df.shape}")

            # Register the DataFrame as a temporary view
            conn.register("temp_df", df)

            # Insert using DuckDB's DataFrame integration
            insert_sql = f"INSERT INTO {table_name} SELECT * FROM temp_df"
            logger.debug(f"Executing: {insert_sql}")

            conn.execute(insert_sql)

            # Unregister the temporary view
            conn.unregister("temp_df")

            logger.debug(f"Successfully inserted {len(data)} rows into {table_name}")

            return {
                "success": True,
                "rows_inserted": len(data)
            }
        except Exception as e:
            logger.error(f"DuckDB batch insert error for {table_name}: {e}", exc_info=True)
            logger.error(f"Sample data (first row): {data[0] if data else 'No data'}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        finally:
            conn.close()
