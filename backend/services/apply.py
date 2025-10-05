"""
Apply optimization suggestions to the database.
Handles dry-run mode, rollback generation, and safe execution.
"""
from __future__ import annotations
from typing import List, Dict, Any
import logging
import re
from psycopg import Connection
from ..schemas import Suggestion, ApplyResult
from .guardrails import validate_suggestion_for_apply

logger = logging.getLogger(__name__)


def generate_rollback_sql(suggestion: Suggestion) -> str | None:
    """
    Generate SQL to rollback/undo a suggestion.

    Args:
        suggestion: The suggestion that was applied

    Returns:
        SQL to undo the change, or None if not applicable
    """
    if not suggestion.sql_fix:
        return None

    sql_upper = suggestion.sql_fix.upper().strip()

    # For index creation, generate DROP INDEX
    if suggestion.category == "index" and sql_upper.startswith('CREATE'):
        # Extract index name from CREATE INDEX statement
        # Pattern: CREATE [UNIQUE] INDEX [CONCURRENTLY] [IF NOT EXISTS] index_name
        match = re.search(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?(\w+)',
                         suggestion.sql_fix, re.IGNORECASE)
        if match:
            index_name = match.group(1)
            return f"DROP INDEX IF EXISTS {index_name};"

    # For config changes, we can't always rollback (would need previous value)
    if suggestion.category == "config":
        if sql_upper.startswith('SET'):
            # Session-level SET can be reset
            match = re.search(r'SET\s+(\w+)', suggestion.sql_fix, re.IGNORECASE)
            if match:
                param_name = match.group(1)
                return f"RESET {param_name};"

    # For query rewrites, no rollback needed (it's a SELECT)
    # For other categories, we don't generate automatic rollback
    return None


def apply_suggestions(
    conn: Connection,
    suggestions: List[Suggestion],
    dry_run: bool,
    db_type: str = "postgres"
) -> List[ApplyResult]:
    """
    Apply a batch of suggestions to the database.

    Args:
        conn: Database connection
        suggestions: List of suggestions to apply
        dry_run: If True, wrap in BEGIN/ROLLBACK for validation
        db_type: Database type (postgres, mysql, sqlserver, oracle, sqlite)

    Returns:
        List of ApplyResult for each suggestion
    """
    results = []

    for suggestion in suggestions:
        result = _apply_single_suggestion(conn, suggestion, dry_run, db_type)
        results.append(result)

    return results


def _apply_single_suggestion(
    conn: Connection,
    suggestion: Suggestion,
    dry_run: bool,
    db_type: str = "postgres"
) -> ApplyResult:
    """
    Apply a single suggestion.

    Args:
        conn: Database connection
        suggestion: Suggestion to apply
        dry_run: If True, rollback after execution
        db_type: Database type (postgres, mysql, sqlserver, oracle, sqlite)

    Returns:
        ApplyResult with status and details
    """
    # Validate suggestion is safe to apply
    can_apply, reason = validate_suggestion_for_apply(
        suggestion.id,
        suggestion.sql_fix or "",
        suggestion.category,
        suggestion.risk,
        dry_run
    )

    if not can_apply:
        logger.warning(f"Skipping suggestion {suggestion.id}: {reason}")
        return ApplyResult(
            id=suggestion.id,
            status="skipped",
            message=reason,
            rollback_sql=None
        )

    # Handle suggestions without SQL (notes)
    if not suggestion.sql_fix:
        return ApplyResult(
            id=suggestion.id,
            status="skipped",
            message="No SQL to execute (note/advisory suggestion)",
            rollback_sql=None
        )

    # Apply the suggestion
    try:
        with conn.cursor() as cur:
            if dry_run:
                # Dry run: wrap in transaction and rollback
                logger.info(f"Dry-run: executing {suggestion.id} on {db_type}")

                # Start transaction (database-specific)
                if db_type == "postgres":
                    cur.execute("BEGIN")
                elif db_type == "mysql":
                    cur.execute("START TRANSACTION")
                elif db_type in ["sqlserver", "oracle", "sqlite"]:
                    cur.execute("BEGIN TRANSACTION")

                try:
                    # Set safety timeouts (PostgreSQL only)
                    if db_type == "postgres":
                        cur.execute("SET LOCAL statement_timeout = '30s'")
                        cur.execute("SET LOCAL lock_timeout = '5s'")
                    elif db_type == "mysql":
                        # MySQL uses different syntax
                        cur.execute("SET SESSION max_execution_time = 30000")  # 30 seconds in milliseconds

                    # Execute the SQL
                    cur.execute(suggestion.sql_fix)

                    # Rollback (don't actually apply)
                    cur.execute("ROLLBACK")

                    rollback_sql = generate_rollback_sql(suggestion)

                    logger.info(f"Dry-run successful for {suggestion.id}")
                    return ApplyResult(
                        id=suggestion.id,
                        status="success",
                        message=f"Dry-run validated successfully (changes rolled back)",
                        rollback_sql=rollback_sql
                    )

                except Exception as e:
                    # Ensure rollback on error
                    try:
                        cur.execute("ROLLBACK")
                    except:
                        pass
                    raise e

            else:
                # Real execution: commit the change
                logger.info(f"Applying suggestion {suggestion.id} on {db_type}")

                # Start transaction (database-specific)
                if db_type == "postgres":
                    cur.execute("BEGIN")
                elif db_type == "mysql":
                    cur.execute("START TRANSACTION")
                elif db_type in ["sqlserver", "oracle", "sqlite"]:
                    cur.execute("BEGIN TRANSACTION")

                try:
                    # Set safety timeouts (database-specific)
                    if db_type == "postgres":
                        cur.execute("SET LOCAL statement_timeout = '60s'")
                        cur.execute("SET LOCAL lock_timeout = '10s'")
                    elif db_type == "mysql":
                        cur.execute("SET SESSION max_execution_time = 60000")  # 60 seconds

                    # Execute the SQL
                    cur.execute(suggestion.sql_fix)

                    # Commit the change
                    cur.execute("COMMIT")

                    rollback_sql = generate_rollback_sql(suggestion)

                    logger.info(f"Successfully applied {suggestion.id}")
                    return ApplyResult(
                        id=suggestion.id,
                        status="success",
                        message=f"Applied successfully",
                        rollback_sql=rollback_sql
                    )

                except Exception as e:
                    # Rollback on error
                    try:
                        cur.execute("ROLLBACK")
                    except:
                        pass
                    raise e

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error applying suggestion {suggestion.id}: {error_msg}")
        return ApplyResult(
            id=suggestion.id,
            status="error",
            message=f"Execution failed: {error_msg}",
            rollback_sql=None
        )


def apply_suggestion_batch(
    conn: Connection,
    suggestions: List[Suggestion],
    dry_run: bool,
    stop_on_error: bool = False,
    db_type: str = "postgres"
) -> List[ApplyResult]:
    """
    Apply multiple suggestions with optional error handling.

    Args:
        conn: Database connection
        suggestions: List of suggestions to apply
        dry_run: If True, validate but don't commit
        stop_on_error: If True, stop on first error
        db_type: Database type (postgres, mysql, sqlserver, oracle, sqlite)

    Returns:
        List of ApplyResult for each suggestion
    """
    results = []

    for suggestion in suggestions:
        result = _apply_single_suggestion(conn, suggestion, dry_run, db_type)
        results.append(result)

        # Stop on first error if requested
        if stop_on_error and result.status == "error":
            logger.warning(f"Stopping batch due to error on {suggestion.id}")
            # Mark remaining as skipped
            remaining_ids = [s.id for s in suggestions if s.id not in [r.id for r in results]]
            for remaining_id in remaining_ids:
                results.append(ApplyResult(
                    id=remaining_id,
                    status="skipped",
                    message="Skipped due to previous error in batch",
                    rollback_sql=None
                ))
            break

    return results
