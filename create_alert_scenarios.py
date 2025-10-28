"""
Create real database scenarios to trigger all 16 alert types.

This script generates actual PostgreSQL load and database conditions that will
trigger each of the 16 alert rules.
"""

import sys
import os
import time
import psycopg
from psycopg.rows import dict_row

# Add .venv/app to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.venv', 'app'))

# Database connection
DSN = "postgresql://postgres:postgres@localhost:5432/UniversityDB"

def get_conn():
    """Get database connection"""
    return psycopg.connect(DSN, autocommit=True, row_factory=dict_row)

def print_section(title):
    """Print section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def scenario_1_stop_database():
    """P1-01: Database Down (db_down)"""
    print_section("Scenario 1: Database Down")
    print("Action: Stop PostgreSQL service to trigger db_down alert")
    print("")
    print("Manual steps:")
    print("  1. Open Services (services.msc)")
    print("  2. Find 'postgresql-x64-15' service")
    print("  3. Click 'Stop'")
    print("  4. Wait 30 seconds")
    print("  5. Check alerts in Tauri app or http://127.0.0.1:8000/alerts/active")
    print("")
    input("Press ENTER after stopping PostgreSQL to continue...")

def scenario_2_cpu_high():
    """P2-01: High CPU (cpu_high)"""
    print_section("Scenario 2: High CPU Usage")
    print("Action: Generate CPU-intensive queries to trigger cpu_high alert")
    print("")

    try:
        with get_conn() as conn, conn.cursor() as cur:
            print("Executing CPU-intensive query (factorial calculation)...")
            # Create a CPU-intensive function
            cur.execute("""
            CREATE OR REPLACE FUNCTION factorial(n integer) RETURNS numeric AS $$
            BEGIN
                IF n <= 1 THEN
                    RETURN 1;
                ELSE
                    RETURN n * factorial(n-1);
                END IF;
            END;
            $$ LANGUAGE plpgsql;
            """)

            # Run multiple CPU-intensive queries in parallel
            print("Running 10 parallel factorial calculations of 5000...")
            for i in range(10):
                print(f"  Query {i+1}/10...")
                try:
                    cur.execute("SELECT factorial(5000);")
                except Exception as e:
                    print(f"    Error: {e}")

            print("\nCPU stress complete. Check system CPU usage and wait for alert.")
            print("Expected: cpu_high alert will trigger if CPU > 85% for 10 minutes")

    except Exception as e:
        print(f"Error: {e}")

def scenario_3_memory_pressure():
    """P2-02: Memory Pressure (memory_pressure)"""
    print_section("Scenario 3: Memory Pressure")
    print("Action: Create large temporary tables to consume memory")
    print("")

    try:
        with get_conn() as conn, conn.cursor() as cur:
            print("Creating large temporary table (10 million rows)...")
            cur.execute("""
            CREATE TEMP TABLE large_temp_table AS
            SELECT
                i AS id,
                md5(random()::text) AS data1,
                md5(random()::text) AS data2,
                md5(random()::text) AS data3,
                md5(random()::text) AS data4
            FROM generate_series(1, 10000000) AS i;
            """)

            print("\nLarge table created. Check system memory usage.")
            print("Expected: memory_pressure alert will trigger if memory > 90% for 10 minutes")

    except Exception as e:
        print(f"Error: {e}")

def scenario_4_long_transaction():
    """P2-03: Long Running Transaction (long_running_transaction)"""
    print_section("Scenario 4: Long Running Transaction")
    print("Action: Start a transaction and keep it open for 31+ minutes")
    print("")

    try:
        conn = get_conn()
        conn.autocommit = False  # Start transaction mode

        with conn.cursor() as cur:
            print("Starting long transaction...")
            cur.execute("BEGIN;")
            cur.execute("SELECT 1;")

            print("\nTransaction started. Keeping it open...")
            print("Expected: long_running_transaction alert after 30 minutes")
            print("")
            print("Leave this terminal open for 31 minutes, then press ENTER")
            input()

            cur.execute("ROLLBACK;")
            print("Transaction rolled back.")

        conn.close()

    except Exception as e:
        print(f"Error: {e}")

def scenario_5_table_bloat():
    """P2-04: Table Bloat (table_bloat_high)"""
    print_section("Scenario 5: Table Bloat")
    print("Action: Create bloat by excessive UPDATE operations without VACUUM")
    print("")

    try:
        with get_conn() as conn, conn.cursor() as cur:
            print("Creating test table with 100,000 rows...")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS bloat_test (
                id serial PRIMARY KEY,
                data text,
                counter int DEFAULT 0
            );
            """)

            cur.execute("TRUNCATE bloat_test;")
            cur.execute("""
            INSERT INTO bloat_test (data)
            SELECT md5(random()::text)
            FROM generate_series(1, 100000);
            """)

            print("Running 50 UPDATE passes to create bloat...")
            for i in range(50):
                print(f"  Update pass {i+1}/50...")
                cur.execute("UPDATE bloat_test SET counter = counter + 1;")

            print("\nBloat created. Table now has significant dead tuples.")
            print("Expected: table_bloat_high alert if bloat > 30%")

    except Exception as e:
        print(f"Error: {e}")

def scenario_6_cache_hit_degradation():
    """P3-02: Cache Hit Degradation (cache_hit_degradation)"""
    print_section("Scenario 6: Cache Hit Degradation")
    print("Action: Query tables larger than shared_buffers to degrade cache hits")
    print("")

    try:
        with get_conn() as conn, conn.cursor() as cur:
            print("Creating large table to evict cache...")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS cache_test AS
            SELECT
                i AS id,
                md5(random()::text) AS data
            FROM generate_series(1, 5000000) AS i;
            """)

            print("Running sequential scans to degrade cache...")
            for i in range(20):
                print(f"  Scan {i+1}/20...")
                cur.execute("SELECT COUNT(*) FROM cache_test WHERE data LIKE 'a%';")

            print("\nCache degradation complete.")
            print("Expected: cache_hit_degradation alert if cache < 95% for 30 minutes")

    except Exception as e:
        print(f"Error: {e}")

def scenario_7_unused_indexes():
    """P3-03: Unused Indexes (unused_index)"""
    print_section("Scenario 7: Unused Indexes")
    print("Action: Create indexes that are never used")
    print("")

    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Reset pg_stat_user_indexes
            cur.execute("SELECT pg_stat_reset();")

            # Create unused indexes
            print("Creating unused indexes...")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS index_test (
                id serial PRIMARY KEY,
                col1 int,
                col2 text,
                col3 timestamp
            );
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_unused_1 ON index_test(col1);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_unused_2 ON index_test(col2);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_unused_3 ON index_test(col3);")

            print("\nUnused indexes created. They will never be scanned.")
            print("Expected: unused_index alert immediately (unused_index_count > 0)")

    except Exception as e:
        print(f"Error: {e}")

def scenario_8_connection_exhaustion():
    """P1-07: Connection Pool Exhaustion (connection_exhaustion)"""
    print_section("Scenario 8: Connection Pool Exhaustion")
    print("Action: Open many idle connections to exhaust pool")
    print("")

    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Get max_connections
            cur.execute("SHOW max_connections;")
            result = cur.fetchone()
            max_conn = int(result['max_connections'])

            print(f"Max connections: {max_conn}")
            print(f"Target: Open {int(max_conn * 0.98)} connections (98% utilization)")
            print("")

            connections = []
            target = int(max_conn * 0.98)

            print("Opening connections...")
            for i in range(target - 10):  # Leave room for monitoring connection
                try:
                    c = psycopg.connect(DSN, autocommit=True)
                    connections.append(c)
                    if (i + 1) % 10 == 0:
                        print(f"  Opened {i+1} connections...")
                except Exception as e:
                    print(f"  Failed at {i+1} connections: {e}")
                    break

            print(f"\nOpened {len(connections)} connections")
            print("Keeping connections open for 5 minutes...")
            print("Expected: connection_exhaustion alert after 3 minutes")
            time.sleep(300)

            print("Closing connections...")
            for c in connections:
                c.close()

    except Exception as e:
        print(f"Error: {e}")

def main():
    """Main test orchestration"""
    print("\n" + "="*80)
    print("  DATABASE ALERT SCENARIOS CREATOR")
    print("  Create real database conditions to trigger all 16 alert types")
    print("="*80)

    scenarios = [
        ("1", "Database Down (P1-01)", scenario_1_stop_database),
        ("2", "High CPU (P2-01)", scenario_2_cpu_high),
        ("3", "Memory Pressure (P2-02)", scenario_3_memory_pressure),
        ("4", "Long Transaction (P2-03)", scenario_4_long_transaction),
        ("5", "Table Bloat (P2-04)", scenario_5_table_bloat),
        ("6", "Cache Hit Degradation (P3-02)", scenario_6_cache_hit_degradation),
        ("7", "Unused Indexes (P3-03)", scenario_7_unused_indexes),
        ("8", "Connection Exhaustion (P1-07)", scenario_8_connection_exhaustion),
    ]

    print("\nAvailable scenarios:")
    print("")
    for code, name, _ in scenarios:
        print(f"  {code}. {name}")
    print("  0. Run all scenarios sequentially")
    print("  q. Quit")
    print("")

    choice = input("Select scenario (0-8, q): ").strip()

    if choice == 'q':
        print("Exiting.")
        return

    if choice == '0':
        print("\nRunning all scenarios sequentially...")
        for code, name, func in scenarios:
            try:
                func()
            except Exception as e:
                print(f"Scenario {code} failed: {e}")
            input("\nPress ENTER to continue to next scenario...")
    else:
        # Find and run selected scenario
        for code, name, func in scenarios:
            if choice == code:
                func()
                return

        print(f"Invalid choice: {choice}")

if __name__ == "__main__":
    main()
