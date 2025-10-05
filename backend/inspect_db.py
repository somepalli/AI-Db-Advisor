#!/usr/bin/env python3
"""
Script to inspect the UniversityDB database and show table structures
"""

import psycopg
from psycopg.rows import dict_row

# Database connection
DSN = "postgresql://postgres:postgres@localhost:5432/UniversityDB"

def list_tables(conn):
    """List all tables in the database"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        tables = [row['table_name'] for row in cur.fetchall()]
        return tables

def get_table_structure(conn, table_name):
    """Get the structure of a specific table"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))
        return cur.fetchall()

def get_row_count(conn, table_name):
    """Get current row count for a table"""
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) as count FROM {table_name}")
        return cur.fetchone()['count']

def main():
    """Main inspection function"""
    print("Inspecting UniversityDB database...")
    print(f"Connecting to: {DSN}\n")

    try:
        with psycopg.connect(DSN, row_factory=dict_row) as conn:
            tables = list_tables(conn)

            if not tables:
                print("No tables found in the database!")
                return

            print(f"Found {len(tables)} tables:\n")

            for table_name in tables:
                row_count = get_row_count(conn, table_name)
                print(f"\n{'='*80}")
                print(f"Table: {table_name} (Current rows: {row_count})")
                print('='*80)

                columns = get_table_structure(conn, table_name)
                print(f"{'Column Name':<30} {'Type':<20} {'Nullable':<10} {'Default':<20}")
                print('-'*80)

                for col in columns:
                    col_type = col['data_type']
                    if col['character_maximum_length']:
                        col_type += f"({col['character_maximum_length']})"

                    default = col['column_default'] or ''
                    if len(default) > 18:
                        default = default[:15] + '...'

                    print(f"{col['column_name']:<30} {col_type:<20} {col['is_nullable']:<10} {default:<20}")

            print(f"\n{'='*80}")
            print("Inspection complete!")

    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure:")
        print("1. PostgreSQL is running")
        print("2. Database 'UniversityDB' exists")
        print("3. Username: postgres, Password: postgres")
        print("4. Install psycopg: pip install psycopg[binary]")

if __name__ == "__main__":
    main()
