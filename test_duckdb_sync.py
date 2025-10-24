"""
Test script for DuckDB sync functionality
Run this to verify the sync is working correctly
"""
import sys
import os
import logging

# Add .venv to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".venv"))

from app.services.postgres_agent import PostgresAgent
from app.services.duckdb_agent import DuckDBAgent
from app.services.data_sync import DataSyncService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_sync():
    """Test syncing a single table from PostgreSQL to DuckDB"""

    # Configuration
    PG_DSN = "postgresql://postgres:postgres@localhost:5432/UniversityDB"
    DUCKDB_DSN = "duckdb:///university_analytics.db"

    logger.info("=" * 80)
    logger.info("DuckDB Sync Test")
    logger.info("=" * 80)
    logger.info(f"PostgreSQL DSN: {PG_DSN}")
    logger.info(f"DuckDB DSN: {DUCKDB_DSN}")
    logger.info("")

    try:
        # Create agents
        logger.info("Creating database agents...")
        pg_agent = PostgresAgent(PG_DSN)
        duckdb_agent = DuckDBAgent(DUCKDB_DSN)

        # Test PostgreSQL connection
        logger.info("Testing PostgreSQL connection...")
        pg_schema = pg_agent.get_schema()
        pg_tables = list(pg_schema.get("tables", {}).keys())
        logger.info(f"✓ PostgreSQL connected. Found {len(pg_tables)} tables")
        logger.info(f"  Tables: {pg_tables[:5]}..." if len(pg_tables) > 5 else f"  Tables: {pg_tables}")

        # Test DuckDB connection
        logger.info("Testing DuckDB connection...")
        duckdb_stats = duckdb_agent.stats()
        logger.info(f"✓ DuckDB connected. Database: {duckdb_stats.get('database_path')}")

        # Create sync service
        logger.info("Creating sync service...")
        sync_service = DataSyncService(pg_agent, duckdb_agent)

        # Test 1: Sync a single small table
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST 1: Sync single table (departments)")
        logger.info("=" * 80)

        result = sync_service.sync_table(
            table_name="public.departments",
            batch_size=100
        )

        if result.get("success"):
            logger.info(f"✓ Single table sync SUCCESS")
            logger.info(f"  Rows synced: {result.get('rows_synced')}")
            logger.info(f"  DuckDB table: {result.get('duckdb_table')}")
        else:
            logger.error(f"✗ Single table sync FAILED: {result.get('error')}")
            return False

        # Test 2: Verify data was inserted
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST 2: Verify data in DuckDB")
        logger.info("=" * 80)

        duckdb_table = result.get('duckdb_table', 'public_departments')
        verify_result = duckdb_agent.execute_query(f"SELECT COUNT(*) as count FROM {duckdb_table}")

        if verify_result.get("success"):
            count = verify_result.get("rows", [{}])[0].get("count", 0)
            logger.info(f"✓ Data verification SUCCESS")
            logger.info(f"  Rows in DuckDB: {count}")
        else:
            logger.error(f"✗ Data verification FAILED: {verify_result.get('error')}")
            return False

        # Test 3: Sync all tables (limited batch for testing)
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST 3: Sync all tables")
        logger.info("=" * 80)

        sync_all_result = sync_service.sync_all_tables(
            batch_size=100,
            exclude_tables=[]  # Sync all tables
        )

        if sync_all_result.get("success"):
            logger.info(f"✓ Sync all tables SUCCESS")
            logger.info(f"  Total tables: {sync_all_result.get('total_tables')}")
            logger.info(f"  Successfully synced: {sync_all_result.get('tables_synced')}")
            logger.info(f"  Failed: {sync_all_result.get('tables_failed')}")
            logger.info(f"  Total rows: {sync_all_result.get('total_rows')}")

            if sync_all_result.get('failed_tables'):
                logger.warning("Failed tables:")
                for failed in sync_all_result.get('failed_tables', []):
                    logger.warning(f"  - {failed.get('table')}: {failed.get('error')}")
        else:
            logger.error(f"✗ Sync all tables FAILED: {sync_all_result.get('error')}")
            return False

        # Test 4: Get sync status
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST 4: Get sync status")
        logger.info("=" * 80)

        status_result = sync_service.get_sync_status()

        if status_result.get("success"):
            logger.info(f"✓ Sync status SUCCESS")
            logger.info(f"  Synced tables: {len(status_result.get('synced_tables', []))}")
            logger.info(f"  Unsynced tables: {len(status_result.get('unsynced_tables', []))}")

            # Show table stats
            for stat in status_result.get('table_stats', [])[:5]:
                in_sync = "✓" if stat.get('in_sync') else "✗"
                logger.info(f"    {in_sync} {stat.get('table')}: PG={stat.get('pg_rows')}, DuckDB={stat.get('ch_rows')}")
        else:
            logger.error(f"✗ Get sync status FAILED: {status_result.get('error')}")
            return False

        logger.info("")
        logger.info("=" * 80)
        logger.info("ALL TESTS PASSED ✓")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_sync()
    sys.exit(0 if success else 1)
