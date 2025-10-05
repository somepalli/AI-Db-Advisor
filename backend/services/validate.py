"""
Transactional validation for optimization suggestions.
Uses BEGIN/ROLLBACK to safely test index creation and measure impact.
"""
from __future__ import annotations
from typing import Dict, Any, Optional
import logging
import json
from psycopg import Connection

logger = logging.getLogger(__name__)

# Safety thresholds
MAX_TABLE_ROWS_FOR_VALIDATION = 1_000_000  # Don't validate on huge tables
VALIDATION_STATEMENT_TIMEOUT = '10s'  # Max time for validation
VALIDATION_LOCK_TIMEOUT = '2s'  # Max time waiting for locks


def explain_cost(conn: Connection, sql: str) -> Dict[str, Any]:
    """
    Get EXPLAIN plan cost for a query.

    Args:
        conn: Database connection
        sql: SQL query to explain

    Returns:
        Dict with:
            - total_cost: Total cost estimate
            - plan_rows: Estimated rows
            - node_type: Top-level node type
            - plan: Full plan JSON
    """
    try:
        with conn.cursor() as cur:
            cur.execute(f"EXPLAIN (FORMAT JSON) {sql}")
            result = cur.fetchone()
            if not result:
                return {}

            plan_json = result[0] if isinstance(result[0], list) else json.loads(result[0])
            plan = plan_json[0]["Plan"]

            return {
                "total_cost": plan.get("Total Cost", 0),
                "plan_rows": plan.get("Plan Rows", 0),
                "node_type": plan.get("Node Type", "Unknown"),
                "plan": plan_json
            }
    except Exception as e:
        logger.error(f"EXPLAIN failed: {e}")
        return {}


def validate_index_in_tx(
    conn: Connection,
    create_index_sql: str,
    target_sql: str,
    table_name: str
) -> Dict[str, Any]:
    """
    Validate index creation using transactional rollback.
    On Windows (no HypoPG), we:
    1. BEGIN transaction
    2. CREATE INDEX
    3. EXPLAIN target query
    4. ROLLBACK (no actual index created)

    Args:
        conn: Database connection
        create_index_sql: CREATE INDEX statement
        target_sql: Query to test with the index
        table_name: Table being indexed (for safety checks)

    Returns:
        Dict with:
            - validated: True if validation succeeded
            - before_cost: Cost without index
            - after_cost: Cost with index (in transaction)
            - cost_delta_pct: Percentage improvement
            - note: Explanation
    """
    result = {
        "validated": False,
        "before_cost": 0,
        "after_cost": 0,
        "cost_delta_pct": 0,
        "note": ""
    }

    try:
        # Safety check: Get table size
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT
                    pg_total_relation_size('{table_name}'::regclass) as size_bytes,
                    (SELECT COUNT(*) FROM {table_name}) as row_count
            """)
            size_check = cur.fetchone()

            if not size_check:
                result["note"] = "Could not determine table size"
                return result

            row_count = size_check[1]
            if row_count > MAX_TABLE_ROWS_FOR_VALIDATION:
                result["note"] = f"Table too large for validation ({row_count:,} rows > {MAX_TABLE_ROWS_FOR_VALIDATION:,})"
                return result

        # Get baseline cost (before index)
        baseline = explain_cost(conn, target_sql)
        if not baseline:
            result["note"] = "Failed to get baseline EXPLAIN"
            return result

        result["before_cost"] = baseline["total_cost"]

        # Now validate in transaction
        with conn.cursor() as cur:
            # Start transaction
            cur.execute("BEGIN")

            try:
                # Set safety timeouts
                cur.execute(f"SET LOCAL statement_timeout = '{VALIDATION_STATEMENT_TIMEOUT}'")
                cur.execute(f"SET LOCAL lock_timeout = '{VALIDATION_LOCK_TIMEOUT}'")

                # Create index in transaction
                logger.info(f"Creating index in transaction: {create_index_sql}")
                cur.execute(create_index_sql)

                # Get cost with index
                cur.execute(f"EXPLAIN (FORMAT JSON) {target_sql}")
                result_row = cur.fetchone()
                if result_row:
                    plan_json = result_row[0] if isinstance(result_row[0], list) else json.loads(result_row[0])
                    plan = plan_json[0]["Plan"]
                    result["after_cost"] = plan.get("Total Cost", 0)

                # Rollback transaction (index never actually created)
                cur.execute("ROLLBACK")
                logger.info("Transaction rolled back - no index created")

                # Calculate improvement
                if result["before_cost"] > 0 and result["after_cost"] > 0:
                    delta = result["before_cost"] - result["after_cost"]
                    result["cost_delta_pct"] = round((delta / result["before_cost"]) * 100, 2)

                    if result["cost_delta_pct"] > 1:  # At least 1% improvement
                        result["validated"] = True
                        result["note"] = f"Validated: {result['cost_delta_pct']}% cost reduction"
                    else:
                        result["note"] = f"Minimal improvement: {result['cost_delta_pct']}%"
                else:
                    result["note"] = "Could not measure cost delta"

            except Exception as e:
                # Ensure rollback on error
                try:
                    cur.execute("ROLLBACK")
                except:
                    pass
                result["note"] = f"Validation error: {str(e)}"
                logger.error(f"Validation error: {e}")

    except Exception as e:
        result["note"] = f"Failed to validate: {str(e)}"
        logger.error(f"validate_index_in_tx error: {e}")

    return result


def validate_rewrite(conn: Connection, original_sql: str, rewritten_sql: str) -> Dict[str, Any]:
    """
    Validate query rewrite by comparing EXPLAIN costs.
    No transaction needed - EXPLAIN is read-only.

    Args:
        conn: Database connection
        original_sql: Original query
        rewritten_sql: Rewritten query

    Returns:
        Dict with validation results
    """
    result = {
        "validated": False,
        "before_cost": 0,
        "after_cost": 0,
        "cost_delta_pct": 0,
        "note": ""
    }

    try:
        # Get cost for original query
        before = explain_cost(conn, original_sql)
        if not before:
            result["note"] = "Failed to EXPLAIN original query"
            return result

        # Get cost for rewritten query
        after = explain_cost(conn, rewritten_sql)
        if not after:
            result["note"] = "Failed to EXPLAIN rewritten query"
            return result

        result["before_cost"] = before["total_cost"]
        result["after_cost"] = after["total_cost"]

        # Calculate improvement
        if result["before_cost"] > 0:
            delta = result["before_cost"] - result["after_cost"]
            result["cost_delta_pct"] = round((delta / result["before_cost"]) * 100, 2)

            if result["cost_delta_pct"] > 1:
                result["validated"] = True
                result["note"] = f"Validated: {result['cost_delta_pct']}% cost reduction"
            else:
                result["note"] = f"Minimal or negative improvement: {result['cost_delta_pct']}%"
        else:
            result["note"] = "Could not measure cost delta"

    except Exception as e:
        result["note"] = f"Validation error: {str(e)}"
        logger.error(f"validate_rewrite error: {e}")

    return result


def can_validate_suggestion(category: str, sql_fix: Optional[str]) -> bool:
    """
    Check if a suggestion can be validated.

    Args:
        category: Suggestion category
        sql_fix: SQL to apply

    Returns:
        True if validation is possible
    """
    if not sql_fix:
        return False

    if category in ("index", "rewrite"):
        return True

    # Config, partition, cleanup typically can't be validated via EXPLAIN
    return False
