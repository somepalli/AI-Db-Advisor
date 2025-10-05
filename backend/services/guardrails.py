"""
Guardrails for safe SQL execution.
Prevents destructive operations and enforces safety constraints.
"""
from __future__ import annotations
import re
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# Dangerous patterns that require extra scrutiny
DESTRUCTIVE_PATTERNS = [
    (r'\bDROP\s+TABLE\b', "DROP TABLE"),
    (r'\bDROP\s+DATABASE\b', "DROP DATABASE"),
    (r'\bTRUNCATE\b', "TRUNCATE"),
    (r'\bDELETE\s+FROM\s+\w+\s*;', "DELETE without WHERE"),  # DELETE FROM table;
    (r'\bUPDATE\s+\w+\s+SET\s+.+?;', "UPDATE without WHERE"),  # Basic check
]

# Patterns for mass operations without WHERE clause
MASS_OPERATION_PATTERNS = [
    (r'\bDELETE\s+FROM\s+(\w+)\s*$', "DELETE without WHERE"),
    (r'\bUPDATE\s+(\w+)\s+SET\b(?:(?!\bWHERE\b).)*$', "UPDATE without WHERE"),
]


def check_sql_safety(sql: str, category: str) -> Tuple[bool, str]:
    """
    Check if SQL is safe to execute.

    Args:
        sql: SQL statement to check
        category: Category of suggestion (index, rewrite, config, etc.)

    Returns:
        Tuple of (is_safe, reason)
        - is_safe: True if SQL is safe to execute
        - reason: Explanation if not safe
    """
    if not sql:
        return True, ""

    sql_upper = sql.upper().strip()

    # Allow standard operations for specific categories
    if category == "index":
        # Index operations are generally safe
        if sql_upper.startswith(('CREATE INDEX', 'CREATE UNIQUE INDEX')):
            return True, ""
        if sql_upper.startswith('DROP INDEX'):
            # DROP INDEX is safe (non-destructive to data)
            return True, ""

    if category == "config":
        # Config changes (SET statements) are session-scoped and safe
        if sql_upper.startswith('SET '):
            return True, ""
        if sql_upper.startswith('ALTER SYSTEM SET'):
            return False, "ALTER SYSTEM SET requires database restart - use dry_run mode"

    # Check for destructive patterns
    for pattern, name in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            return False, f"Blocked: {name} operation detected"

    # Check for mass operations without WHERE
    for pattern, name in MASS_OPERATION_PATTERNS:
        match = re.search(pattern, sql, re.IGNORECASE | re.DOTALL)
        if match:
            # For DELETE/UPDATE, ensure WHERE clause exists
            if 'WHERE' not in sql_upper:
                return False, f"Blocked: {name} - mass operation detected"

    # Check for cross-database operations (dblink, foreign data wrappers)
    if re.search(r'\bdblink\b|\bpostgres_fdw\b', sql, re.IGNORECASE):
        return False, "Blocked: cross-database operation detected"

    # Rewrite suggestions should only be SELECT queries
    if category == "rewrite":
        if not sql_upper.startswith('SELECT'):
            return False, "Blocked: rewrite suggestions must be SELECT queries"

    return True, ""


def check_risk_level(sql: str, category: str, validated: bool) -> str:
    """
    Determine risk level for a suggestion.

    Args:
        sql: SQL to execute
        category: Suggestion category
        validated: Whether suggestion was validated

    Returns:
        Risk level: "low", "medium", or "high"
    """
    if not sql:
        return "low"  # Notes without SQL are low risk

    sql_upper = sql.upper().strip()

    # High risk: Unvalidated structural changes
    if category == "partition" and not validated:
        return "high"

    # Medium risk: Index drops, unvalidated indexes
    if category == "index":
        if sql_upper.startswith('DROP INDEX'):
            return "medium"
        if not validated and 'CREATE' in sql_upper:
            return "medium"

    # Medium risk: Config changes
    if category == "config":
        if 'ALTER SYSTEM' in sql_upper:
            return "high"
        return "medium"

    # Low risk: Validated changes, SELECT rewrites
    if validated:
        return "low"

    if category == "rewrite":
        return "low"  # SELECT queries are safe

    return "medium"  # Default to medium for unvalidated changes


def should_require_dry_run(risk: str, category: str) -> bool:
    """
    Determine if suggestion should require dry_run=True.

    Args:
        risk: Risk level
        category: Suggestion category

    Returns:
        True if dry_run should be required
    """
    if risk == "high":
        return True

    # Medium-risk config changes should use dry_run
    if risk == "medium" and category == "config":
        return True

    return False


def validate_suggestion_for_apply(
    suggestion_id: str,
    sql: str,
    category: str,
    risk: str,
    dry_run: bool
) -> Tuple[bool, str]:
    """
    Validate that a suggestion is safe to apply.

    Args:
        suggestion_id: Suggestion ID
        sql: SQL to execute
        category: Suggestion category
        risk: Risk level
        dry_run: Whether this is a dry run

    Returns:
        Tuple of (can_apply, reason)
    """
    # Check SQL safety
    is_safe, reason = check_sql_safety(sql, category)
    if not is_safe:
        return False, reason

    # Check if dry_run is required
    if should_require_dry_run(risk, category) and not dry_run:
        return False, f"High-risk operation requires dry_run=True for safety"

    logger.info(f"Validated suggestion {suggestion_id} for apply: category={category}, risk={risk}, dry_run={dry_run}")
    return True, ""


def sanitize_sql(sql: str) -> str:
    """
    Basic SQL sanitization (removes comments, normalizes whitespace).

    Args:
        sql: Raw SQL

    Returns:
        Sanitized SQL
    """
    # Remove SQL comments
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

    # Normalize whitespace
    sql = ' '.join(sql.split())

    return sql.strip()
