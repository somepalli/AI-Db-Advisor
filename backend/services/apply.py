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
from .agent_guardrails import evaluate as guardrail_evaluate, GuardrailDecision

logger = logging.getLogger(__name__)

# A pure read-only statement (SELECT / WITH ... SELECT / SHOW / EXPLAIN-no-ANALYZE).
# Destructive verbs are already hard-DENIED by the wall before this is consulted,
# so this only governs the benign UNKNOWN-but-read case on the human apply path.
_READ_ONLY_PREFIX = re.compile(r"^\s*(WITH\b.*\bSELECT\b|SELECT\b|SHOW\b|EXPLAIN\b)",
                               re.IGNORECASE | re.DOTALL)


def _is_read_only(sql: str) -> bool:
    return bool(_READ_ONLY_PREFIX.match(sql or ""))


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
    db_type: str = "postgres",
    is_agentic: bool = False,
    elevated_confirmation: bool = False,
    elevated_object_name: str | None = None,
    ds_id: str | None = None,
) -> List[ApplyResult]:
    """
    Apply a batch of suggestions to the database.

    Args:
        conn: Database connection
        suggestions: List of suggestions to apply
        dry_run: If True, wrap in BEGIN/ROLLBACK for validation
        db_type: Database type (postgres, mysql, sqlserver, oracle, sqlite)
        is_agentic: True when invoked by the autonomous agent loop (stricter wall)
        elevated_confirmation: Caller explicitly confirmed an elevated-risk action
        elevated_object_name: Typed object name accompanying the elevated confirmation

    Returns:
        List of ApplyResult for each suggestion
    """
    results = []

    for suggestion in suggestions:
        result = _apply_single_suggestion(
            conn, suggestion, dry_run, db_type,
            is_agentic=is_agentic,
            elevated_confirmation=elevated_confirmation,
            elevated_object_name=elevated_object_name,
            ds_id=ds_id,
        )
        results.append(result)

    return results


def _apply_single_suggestion(
    conn: Connection,
    suggestion: Suggestion,
    dry_run: bool,
    db_type: str = "postgres",
    is_agentic: bool = False,
    elevated_confirmation: bool = False,
    elevated_object_name: str | None = None,
    ds_id: str | None = None,
) -> ApplyResult:
    """
    Apply a single suggestion.

    Args:
        conn: Database connection
        suggestion: Suggestion to apply
        dry_run: If True, rollback after execution
        db_type: Database type (postgres, mysql, sqlserver, oracle, sqlite)
        is_agentic: True when invoked by the autonomous agent loop (stricter wall)
        elevated_confirmation: Caller explicitly confirmed an elevated-risk action
        elevated_object_name: Typed object name accompanying the elevated confirmation

    Returns:
        ApplyResult with status and details
    """
    # --- THE WALL (agent_guardrails) -------------------------------------
    # Single hard gate, evaluated BEFORE any dry-run or real execution and
    # BEFORE the legacy category-based safety check. Destructive/unknown
    # statements never reach cursor.execute from any path.
    wall_sql = (suggestion.sql_fix or "").strip()
    if wall_sql:
        wall = guardrail_evaluate(wall_sql, agentic=is_agentic)
        if wall.decision is GuardrailDecision.DENY:
            logger.warning(
                f"Guardrail wall DENY for suggestion {suggestion.id}: "
                f"{wall.matched_rule or wall.risk_class.value} :: {wall.reason}"
            )
            if wall.alert:
                from .destructive_alerts import raise_destructive_blocked
                raise_destructive_blocked(
                    ds_id, wall_sql,
                    matched_rule=wall.matched_rule,
                    risk_class=wall.risk_class.value,
                    reason=wall.reason,
                    source="apply" + ("/agentic" if is_agentic else ""),
                )
            return ApplyResult(
                id=suggestion.id,
                status="error",
                message=f"Blocked at guardrail wall: {wall.reason}",
                rollback_sql=None,
                alert=wall.alert,
            )
        if wall.decision is GuardrailDecision.REQUIRE_ELEVATED and not _is_read_only(wall_sql):
            # Unclassified write (e.g. GRANT/DCL): only proceed with an explicit
            # elevated confirmation AND a typed object name from the caller.
            # Pure read-only SELECTs (rewrite suggestions) are not destructive
            # and fall through to the legacy validator on the human path; on the
            # agentic path they are already hard-DENIED above.
            if not (elevated_confirmation and elevated_object_name
                    and elevated_object_name.strip()):
                logger.warning(
                    f"Refusing elevated suggestion {suggestion.id} without "
                    f"explicit confirmation + typed object name: {wall.reason}"
                )
                return ApplyResult(
                    id=suggestion.id,
                    status="error",
                    message=(
                        "Elevated review required: this statement could not be "
                        "positively classified and needs explicit confirmation "
                        "with a typed object name before it can be applied."
                    ),
                    rollback_sql=None,
                    alert=wall.alert,
                )

    # Validate suggestion is safe to apply (legacy category-based check)
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
    db_type: str = "postgres",
    is_agentic: bool = False,
    elevated_confirmation: bool = False,
    elevated_object_name: str | None = None,
    ds_id: str | None = None,
) -> List[ApplyResult]:
    """
    Apply multiple suggestions with optional error handling.

    Args:
        conn: Database connection
        suggestions: List of suggestions to apply
        dry_run: If True, validate but don't commit
        stop_on_error: If True, stop on first error
        db_type: Database type (postgres, mysql, sqlserver, oracle, sqlite)
        is_agentic: True when invoked by the autonomous agent loop (stricter wall)
        elevated_confirmation: Caller explicitly confirmed an elevated-risk action
        elevated_object_name: Typed object name accompanying the elevated confirmation

    Returns:
        List of ApplyResult for each suggestion
    """
    results = []

    for suggestion in suggestions:
        result = _apply_single_suggestion(
            conn, suggestion, dry_run, db_type,
            is_agentic=is_agentic,
            elevated_confirmation=elevated_confirmation,
            elevated_object_name=elevated_object_name,
            ds_id=ds_id,
        )
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
