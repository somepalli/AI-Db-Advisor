"""
Data Sync Service: PostgreSQL to DuckDB
Synchronizes data from PostgreSQL (OLTP) to DuckDB (OLAP) for analytics
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .postgres_agent import PostgresAgent
from .duckdb_agent import DuckDBAgent

logger = logging.getLogger(__name__)


class DataSyncService:
    """
    Synchronizes data between PostgreSQL and DuckDB for analytics.
    Supports full sync and incremental sync based on timestamps.
    """

    def __init__(self, pg_agent: PostgresAgent, analytics_agent: DuckDBAgent):
        self.pg_agent = pg_agent
        self.analytics_agent = analytics_agent

    def sync_table(self, table_name: str, batch_size: int = 1000,
                   incremental: bool = False,
                   timestamp_column: Optional[str] = None) -> Dict[str, Any]:
        """
        Sync a table from PostgreSQL to DuckDB.

        Args:
            table_name: Name of the table to sync (can include schema: public.students)
            batch_size: Number of rows per batch
            incremental: If True, only sync new/updated records
            timestamp_column: Column to use for incremental sync (e.g., 'updated_at')

        Returns:
            Dict with sync results
        """
        try:
            logger.info(f"Starting sync for table: {table_name}")

            # Step 1: Get table schema from PostgreSQL
            pg_schema = self.pg_agent.get_schema()

            # Handle schema.table format
            if table_name not in pg_schema.get("tables", {}):
                # Try without schema prefix
                simple_name = table_name.split(".")[-1] if "." in table_name else table_name
                found = False
                for tbl_key in pg_schema.get("tables", {}).keys():
                    if tbl_key.endswith(f".{simple_name}") or tbl_key == simple_name:
                        table_name = tbl_key
                        found = True
                        break

                if not found:
                    return {
                        "success": False,
                        "error": f"Table {table_name} not found in PostgreSQL. Available tables: {list(pg_schema.get('tables', {}).keys())}"
                    }

            table_columns = pg_schema["tables"][table_name]

            if not table_columns:
                return {
                    "success": False,
                    "error": f"No columns found for table {table_name}"
                }

            logger.info(f"Found {len(table_columns)} columns for table {table_name}")

            # Step 2: Create table in DuckDB if not exists
            # Get simple table name for DuckDB (without schema prefix)
            duckdb_table_name = table_name.replace(".", "_") if "." in table_name else table_name

            # Get first column for ordering
            first_column = table_columns[0]['column']
            order_by = timestamp_column if timestamp_column else first_column

            logger.info(f"Creating DuckDB table: {duckdb_table_name} (order by: {order_by})")

            create_result = self.analytics_agent.create_table_from_schema(
                table_name=duckdb_table_name,
                schema=table_columns,
                engine="MergeTree",  # Ignored by DuckDB
                order_by=order_by    # Ignored by DuckDB
            )

            if not create_result.get("success", False):
                logger.error(f"Failed to create table: {create_result.get('error')}")
                return create_result

            logger.info(f"Table {duckdb_table_name} created/verified successfully")

            # Step 3: Determine which rows to sync
            where_clause = ""
            if incremental and timestamp_column:
                # Get max timestamp from DuckDB
                last_sync = self._get_last_sync_timestamp(duckdb_table_name, timestamp_column)
                if last_sync:
                    where_clause = f" WHERE \"{timestamp_column}\" > '{last_sync}'"
                    logger.info(f"Incremental sync from: {last_sync}")

            # Step 4: Read data from PostgreSQL in batches
            total_rows = 0
            offset = 0
            errors = []

            logger.info(f"Starting batch sync (batch_size={batch_size})")

            while True:
                # Fetch batch from PostgreSQL
                # Quote the first column name to handle special characters
                query = f"""
                    SELECT * FROM {table_name}
                    {where_clause}
                    ORDER BY \"{first_column}\"
                    LIMIT {batch_size} OFFSET {offset}
                """

                logger.info(f"Fetching batch {offset//batch_size + 1} (offset={offset})")
                result = self.pg_agent.execute_query(query)

                if not result.get("success", False):
                    error_msg = f"Failed to read from PostgreSQL at offset {offset}: {result.get('error')}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "rows_synced": total_rows
                    }

                rows = result.get("rows", [])
                if not rows:
                    logger.info("No more rows to sync")
                    break  # No more data

                logger.info(f"Fetched {len(rows)} rows, inserting into DuckDB...")

                # Step 5: Insert batch into DuckDB
                insert_result = self.analytics_agent.insert_batch(duckdb_table_name, rows)

                if not insert_result.get("success", False):
                    error_msg = f"Failed to insert batch into DuckDB: {insert_result.get('error')}"
                    logger.error(error_msg)
                    errors.append(f"Batch at offset {offset}: {error_msg}")

                    # Continue with next batch instead of failing completely
                    offset += batch_size
                    continue

                batch_inserted = insert_result.get("rows_inserted", len(rows))
                total_rows += batch_inserted
                offset += batch_size

                logger.info(f"✓ Batch inserted: {batch_inserted} rows (total: {total_rows})")

                # If we got fewer rows than batch_size, we're done
                if len(rows) < batch_size:
                    logger.info(f"Last batch received ({len(rows)} < {batch_size}), sync complete")
                    break

            result = {
                "success": True,
                "table": table_name,
                "duckdb_table": duckdb_table_name,
                "rows_synced": total_rows,
                "sync_type": "incremental" if incremental else "full"
            }

            if errors:
                result["warnings"] = errors
                result["partial_success"] = True

            logger.info(f"✓ Sync complete for {table_name}: {total_rows} rows synced")
            return result

        except Exception as e:
            logger.error(f"Sync error for {table_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def sync_all_tables(self, exclude_tables: List[str] = None,
                        batch_size: int = 1000) -> Dict[str, Any]:
        """
        Sync all tables from PostgreSQL to DuckDB.

        Args:
            exclude_tables: List of table names to exclude
            batch_size: Number of rows per batch

        Returns:
            Dict with sync results for all tables
        """
        exclude_tables = exclude_tables or []

        try:
            logger.info("=" * 80)
            logger.info("Starting sync_all_tables operation")
            logger.info("=" * 80)

            # Get all tables from PostgreSQL
            pg_schema = self.pg_agent.get_schema()
            tables = list(pg_schema.get("tables", {}).keys())

            logger.info(f"Found {len(tables)} tables in PostgreSQL")
            logger.info(f"Tables: {tables}")

            if exclude_tables:
                logger.info(f"Excluding tables: {exclude_tables}")

            results = []
            total_synced = 0
            successful_tables = []
            failed_tables = []

            for idx, table_name in enumerate(tables, 1):
                # Check exclusions (match both simple name and full schema.table name)
                simple_name = table_name.split(".")[-1] if "." in table_name else table_name
                if table_name in exclude_tables or simple_name in exclude_tables:
                    logger.info(f"[{idx}/{len(tables)}] Skipping excluded table: {table_name}")
                    continue

                logger.info("")
                logger.info("-" * 80)
                logger.info(f"[{idx}/{len(tables)}] Syncing table: {table_name}")
                logger.info("-" * 80)

                result = self.sync_table(table_name, batch_size=batch_size)
                results.append(result)

                if result.get("success", False):
                    rows_synced = result.get("rows_synced", 0)
                    total_synced += rows_synced
                    successful_tables.append(table_name)
                    logger.info(f"✓ [{idx}/{len(tables)}] SUCCESS: {table_name} - {rows_synced} rows")
                else:
                    failed_tables.append({
                        "table": table_name,
                        "error": result.get("error", "Unknown error")
                    })
                    logger.error(f"✗ [{idx}/{len(tables)}] FAILED: {table_name} - {result.get('error')}")

            logger.info("")
            logger.info("=" * 80)
            logger.info("Sync All Tables - Summary")
            logger.info("=" * 80)
            logger.info(f"Total tables: {len(tables)}")
            logger.info(f"Successful: {len(successful_tables)}")
            logger.info(f"Failed: {len(failed_tables)}")
            logger.info(f"Total rows synced: {total_synced}")
            logger.info("=" * 80)

            return {
                "success": True,
                "total_tables": len(tables),
                "tables_synced": len(successful_tables),
                "tables_failed": len(failed_tables),
                "total_rows": total_synced,
                "successful_tables": successful_tables,
                "failed_tables": failed_tables,
                "details": results
            }

        except Exception as e:
            logger.error(f"Sync all tables error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def _get_last_sync_timestamp(self, table_name: str, timestamp_column: str) -> Optional[str]:
        """Get the last synced timestamp from DuckDB"""
        try:
            query = f"SELECT max({timestamp_column}) as last_sync FROM {table_name}"
            result = self.analytics_agent.execute_query(query)

            if result.get("success", False) and result.get("rows"):
                last_sync = result["rows"][0].get("last_sync")
                return str(last_sync) if last_sync else None

            return None
        except Exception as e:
            logger.error(f"Error getting last sync timestamp: {e}")
            return None

    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status comparing PostgreSQL and DuckDB"""
        try:
            # Get schemas from both databases
            pg_schema = self.pg_agent.get_schema()
            ch_schema = self.analytics_agent.get_schema()

            pg_tables = set(pg_schema.get("tables", {}).keys())
            ch_tables = set(ch_schema.get("tables", {}).keys())

            # Find synced and unsynced tables
            synced_tables = pg_tables.intersection(ch_tables)
            unsynced_tables = pg_tables.difference(ch_tables)

            # Get row counts for synced tables
            table_stats = []
            for table in synced_tables:
                pg_count_result = self.pg_agent.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                ch_count_result = self.analytics_agent.execute_query(f"SELECT COUNT(*) as count FROM {table}")

                pg_count = pg_count_result.get("rows", [{}])[0].get("count", 0) if pg_count_result.get("success") else 0
                ch_count = ch_count_result.get("rows", [{}])[0].get("count", 0) if ch_count_result.get("success") else 0

                table_stats.append({
                    "table": table,
                    "pg_rows": pg_count,
                    "duckdb_rows": ch_count,
                    "in_sync": pg_count == ch_count
                })

            return {
                "success": True,
                "synced_tables": list(synced_tables),
                "unsynced_tables": list(unsynced_tables),
                "table_stats": table_stats
            }

        except Exception as e:
            logger.error(f"Get sync status error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def create_sync_service(pg_dsn: str, duckdb_dsn: str) -> DataSyncService:
    """
    Factory function to create a DataSyncService.

    Args:
        pg_dsn: PostgreSQL connection string
        duckdb_dsn: DuckDB connection string

    Returns:
        DataSyncService instance
    """
    pg_agent = PostgresAgent(pg_dsn)
    analytics_agent = DuckDBAgent(duckdb_dsn)
    return DataSyncService(pg_agent, analytics_agent)
