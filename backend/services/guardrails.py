"""
Guardrails for safe SQL execution.
Prevents destructive operations and enforces safety constraints.
"""
from __future__ import annotations
import re
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# Always-destructive patterns (regardless of WHERE clause)
DESTRUCTIVE_PATTERNS = [
    (r'\bDROP\s+TABLE\b', "DROP TABLE"),
    (r'\bDROP\s+DATABASE\b', "DROP DATABASE"),
    (r'\bTRUNCATE\b', "TRUNCATE"),
]

# Patterns for mass DELETE/UPDATE without a WHERE clause (a trailing ';' is allowed).
# These only fire when no WHERE clause is present (verified separately below).
MASS_OPERATION_PATTERNS = [
    (r'\bDELETE\s+FROM\s+(\w+)\s*;?\s*$', "DELETE without WHERE"),
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

    # ALTER TABLE is a structural change. Allow index/key additions (MySQL expresses
    # index creation as `ALTER TABLE ... ADD [UNIQUE] INDEX/KEY`) and partition ops;
    # block everything else (ADD/DROP COLUMN, type changes, etc.).
    if sql_upper.startswith('ALTER TABLE'):
        if re.search(r'\bADD\s+(UNIQUE\s+)?(INDEX|KEY)\b', sql_upper):
            return True, ""
        if category == "partition":
            return True, ""
        return False, "Blocked: ALTER TABLE operation detected"

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

    # Notes are advisory only — always low risk.
    if category == "note":
        return "low"

    sql_upper = sql.upper().strip()

    # High risk: Unvalidated structural changes
    if category == "partition" and not validated:
        return "high"

    # Medium risk: unvalidated indexes; DROP INDEX is high risk (drops an object).
    if category == "index":
        if sql_upper.startswith('DROP INDEX'):
            return "high"
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
    # Both high- and medium-risk operations should be dry-run first.
    if risk in ("high", "medium"):
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
    # An empty/None SQL cannot be applied (e.g. a "note" suggestion).
    if not sql or not sql.strip():
        return False, "Cannot apply suggestion with empty SQL (no SQL to execute)"

    # Check SQL safety
    is_safe, reason = check_sql_safety(sql, category)
    if not is_safe:
        return False, reason

    # Check if dry_run is required
    if should_require_dry_run(risk, category) and not dry_run:
        return False, f"This {risk}-risk operation requires dry-run mode first for safety"

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

    # Collapse repeated semicolons into a single one
    sql = re.sub(r';+', ';', sql)

    # Normalize whitespace
    sql = ' '.join(sql.split())

    return sql.strip()
