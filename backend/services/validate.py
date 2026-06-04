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
REWRITE_MIN_IMPROVEMENT_PCT = 5.0  # Min cost reduction to consider a rewrite validated


def _plan_from_row(row) -> Dict[str, Any]:
    """Extract the top-level Plan dict from an EXPLAIN (FORMAT JSON) result row."""
    raw = row[0]
    plan_json = raw if isinstance(raw, list) else json.loads(raw)
    return plan_json[0]["Plan"]


def explain_cost(conn: Connection, sql: str) -> float:
    """
    Get the estimated total cost of a query via EXPLAIN (FORMAT JSON).

    A statement timeout is applied to keep validation bounded. Any database error
    propagates to the caller (it is not swallowed).

    Args:
        conn: Database connection
        sql: SQL query to explain

    Returns:
        The estimated total cost (float).
    """
    with conn.cursor() as cur:
        # Bound the EXPLAIN with a statement timeout in a single round-trip.
        cur.execute(
            f"SET statement_timeout = '{VALIDATION_STATEMENT_TIMEOUT}'; "
            f"EXPLAIN (FORMAT JSON) {sql}"
        )
        result = cur.fetchone()
        if not result:
            raise ValueError("EXPLAIN returned no result")
        plan = _plan_from_row(result)
        return float(plan.get("Total Cost", 0))


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
            - validated: True if the index reduced the estimated cost
            - cost_before: Cost without index
            - cost_after: Cost with index (in transaction)
            - cost_delta_pct: Percentage improvement
            - table: The table being indexed
            - note: Explanation

    Raises:
        Exception: If the index creation or EXPLAIN fails (after rolling back).
    """
    result = {
        "validated": False,
        "cost_before": 0,
        "cost_after": 0,
        "cost_delta_pct": 0,
        "table": table_name,
        "note": ""
    }

    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            cur.execute(f"SET LOCAL statement_timeout = '{VALIDATION_STATEMENT_TIMEOUT}'")
            cur.execute(f"SET LOCAL lock_timeout = '{VALIDATION_LOCK_TIMEOUT}'")

            # Baseline EXPLAIN — also gives us the estimated row count for a safety check.
            cur.execute(f"EXPLAIN (FORMAT JSON) {target_sql}")
            baseline_plan = _plan_from_row(cur.fetchone())
            result["cost_before"] = float(baseline_plan.get("Total Cost", 0))

            plan_rows = baseline_plan.get("Plan Rows", 0)
            if plan_rows > MAX_TABLE_ROWS_FOR_VALIDATION:
                cur.execute("ROLLBACK")
                result["note"] = (
                    f"Skipped: too many rows ({plan_rows:,} > "
                    f"{MAX_TABLE_ROWS_FOR_VALIDATION:,})"
                )
                return result

            # Create the index inside the transaction, then re-plan.
            logger.info(f"Creating index in transaction: {create_index_sql}")
            cur.execute(create_index_sql)

            cur.execute(f"EXPLAIN (FORMAT JSON) {target_sql}")
            after_plan = _plan_from_row(cur.fetchone())
            result["cost_after"] = float(after_plan.get("Total Cost", 0))

            # Roll back so the index is never actually persisted.
            cur.execute("ROLLBACK")
            logger.info("Transaction rolled back - no index created")

            if result["cost_before"] > 0:
                delta = result["cost_before"] - result["cost_after"]
                result["cost_delta_pct"] = round((delta / result["cost_before"]) * 100, 2)
                if result["cost_delta_pct"] > 0:
                    result["validated"] = True
                    result["note"] = f"Validated: {result['cost_delta_pct']}% cost reduction"
                else:
                    result["note"] = f"No improvement: {result['cost_delta_pct']}%"
            else:
                result["note"] = "Could not measure cost delta"

        return result

    except Exception as e:
        # Best-effort rollback, then propagate so callers know validation failed.
        try:
            with conn.cursor() as cur:
                cur.execute("ROLLBACK")
        except Exception:
            pass
        logger.error(f"validate_index_in_tx error: {e}")
        raise


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
        "cost_before": 0,
        "cost_after": 0,
        "cost_delta_pct": 0,
        "note": ""
    }

    # EXPLAIN both queries (errors propagate to the caller).
    result["cost_before"] = explain_cost(conn, original_sql)
    result["cost_after"] = explain_cost(conn, rewritten_sql)

    if result["cost_before"] > 0:
        delta = result["cost_before"] - result["cost_after"]
        result["cost_delta_pct"] = round((delta / result["cost_before"]) * 100, 2)

        # Require a meaningful improvement to consider the rewrite validated.
        if result["cost_delta_pct"] > REWRITE_MIN_IMPROVEMENT_PCT:
            result["validated"] = True
            result["note"] = f"Validated: {result['cost_delta_pct']}% cost reduction"
        else:
            result["note"] = f"Minimal or negative improvement: {result['cost_delta_pct']}%"
    else:
        result["note"] = "Could not measure cost delta"

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
