"""
Super Agent: Orchestrates end-to-end suggestion analysis.
Combines rule-based advisors, AI suggestions, and validation.
"""
from __future__ import annotations
from typing import List, Dict, Any
import logging
from ..schemas import Suggestion
from .base_agent import BaseAgent
from .postgres_agent import PostgresAgent
from .advisor import index_advice_pg, rewrite_advice
from .ai_client import LLMClient
from .validate import validate_index_in_tx, validate_rewrite, can_validate_suggestion
from .guardrails import check_risk_level
import re

logger = logging.getLogger(__name__)


def _extract_table_from_sql(sql: str) -> str | None:
    """Extract primary table name from SQL query."""
    # Simple pattern: FROM table_name
    match = re.search(r'\bFROM\s+(\w+\.)?(\w+)', sql, re.IGNORECASE)
    if match:
        return match.group(2)
    return None


def _extract_table_from_index_sql(create_index_sql: str) -> str | None:
    """Extract table name from CREATE INDEX statement."""
    # Pattern: CREATE INDEX ... ON table_name
    match = re.search(r'\bON\s+(\w+\.)?(\w+)', create_index_sql, re.IGNORECASE)
    if match:
        return match.group(2)
    return None


def _extract_columns_from_index_sql(create_index_sql: str) -> List[str]:
    """
    Extract column list from CREATE INDEX statement.

    Examples:
        "CREATE INDEX idx ON Fees (student_id, due_date)" -> ["student_id", "due_date"]
        "CREATE INDEX idx ON Fees (student_id, due_date) INCLUDE (...)" -> ["student_id", "due_date"]
        "CREATE INDEX CONCURRENTLY idx ON Fees (student_id)" -> ["student_id"]
    """
    # Pattern: ... ON table_name (col1, col2, ...)
    # Stop at first closing paren to avoid INCLUDE clause
    match = re.search(r'\bON\s+[\w.]+\s*\(([^)]+)\)', create_index_sql, re.IGNORECASE)
    if match:
        columns_str = match.group(1)
        # Split by comma and clean whitespace/quotes
        columns = [col.strip().strip('"').strip("'") for col in columns_str.split(',')]
        return [c for c in columns if c]  # Filter empty strings
    return []


def _deduplicate_suggestions(suggestions: List[Suggestion], agent: BaseAgent = None) -> List[Suggestion]:
    """
    Remove duplicate suggestions based on ID.
    Also filter out index suggestions for indexes that already exist (safety net).
    """
    seen = set()
    unique = []

    for suggestion in suggestions:
        # Check for ID duplicates
        if suggestion.id in seen:
            logger.debug(f"Deduplicating suggestion by ID: {suggestion.id}")
            continue

        # Safety net: Double-check index existence for index suggestions
        if agent and suggestion.category == "index" and suggestion.sql_fix:
            table = _extract_table_from_index_sql(suggestion.sql_fix)
            columns = _extract_columns_from_index_sql(suggestion.sql_fix)

            logger.debug(f"Deduplication check: sql_fix='{suggestion.sql_fix}' -> table='{table}', columns={columns}")

            if table and columns:
                if agent.index_exists(table, columns):
                    logger.info(f"[FILTERED] Index suggestion removed - already exists: {table}({', '.join(columns)})")
                    continue
                else:
                    logger.debug(f"[KEPT] Index suggestion - does not exist: {table}({', '.join(columns)})")
            else:
                logger.warning(f"[WARNING] Could not parse CREATE INDEX: {suggestion.sql_fix}")

        seen.add(suggestion.id)
        unique.append(suggestion)

    return unique


def _normalize_rewrite_recommendation(rec: Dict[str, Any], original_sql: str) -> Suggestion:
    """Convert rewrite advice recommendation to Suggestion format."""
    category = rec.get("category", "")
    summary = rec.get("summary", "")
    sql_fix = rec.get("sql_fix")

    # Determine title from category
    title_map = {
        "SELECT *": "Avoid SELECT * - Specify columns explicitly",
        "OFFSET/LIMIT": "Use keyset pagination instead of OFFSET",
        "Redundant": "Remove redundant SQL clauses",
    }
    title = title_map.get(category, category)

    # Extract affected table
    table = _extract_table_from_sql(original_sql)
    related_objects = [table] if table else []

    suggestion_id = Suggestion.generate_id(
        level="query",
        category="rewrite",
        sql_fix=sql_fix,
        related_objects=related_objects
    )

    return Suggestion(
        id=suggestion_id,
        level="query",
        category="rewrite",
        title=title,
        summary=summary,
        sql_fix=sql_fix,
        validated=False,
        confidence="rule-based",
        risk="low",  # Rewrites (SELECT) are low risk
        estimated_gain=rec.get("expected_gain"),
        related_objects=related_objects,
        metadata={"source": "rewrite_advisor"}
    )


def _normalize_index_recommendation(rec: Dict[str, Any], original_sql: str) -> Suggestion:
    """Convert index advice recommendation to Suggestion format."""
    category = rec.get("category", "")
    summary = rec.get("summary", "")
    sql_fix = rec.get("sql_fix")

    # Determine title
    title = f"Create index: {category}"

    # Extract affected table from CREATE INDEX statement
    table = _extract_table_from_index_sql(sql_fix) if sql_fix else None
    related_objects = [table] if table else []

    suggestion_id = Suggestion.generate_id(
        level="table",
        category="index",
        sql_fix=sql_fix,
        related_objects=related_objects
    )

    return Suggestion(
        id=suggestion_id,
        level="table",
        category="index",
        title=title,
        summary=summary,
        sql_fix=sql_fix,
        validated=False,
        confidence="rule-based",
        risk="medium",  # Unvalidated indexes are medium risk
        estimated_gain=rec.get("expected_gain"),
        related_objects=related_objects,
        metadata={"source": "index_advisor"}
    )


def _normalize_ai_suggestion(ai_sug: Dict[str, Any], original_sql: str) -> Suggestion:
    """Convert AI suggestion to Suggestion format."""
    sug_type = ai_sug.get("type", "note")
    summary = ai_sug.get("summary", "")
    rationale = ai_sug.get("rationale", "")

    # Combine summary and rationale
    full_summary = f"{summary}. {rationale}" if rationale else summary

    if sug_type == "index":
        # AI index suggestion
        index_def = ai_sug.get("index", {})
        table = index_def.get("table", "")
        columns = index_def.get("columns", [])
        include = index_def.get("include", [])

        sql_fix = ai_sug.get("sql_fix")
        related_objects = [table] if table else []

        suggestion_id = Suggestion.generate_id(
            level="table",
            category="index",
            sql_fix=sql_fix,
            related_objects=related_objects
        )

        return Suggestion(
            id=suggestion_id,
            level="table",
            category="index",
            title=f"AI: Create index on {table}({', '.join(columns)})",
            summary=full_summary,
            sql_fix=sql_fix,
            validated=ai_sug.get("validated", False),
            confidence="ai-heuristic",
            risk=ai_sug.get("risk", "medium"),
            estimated_gain=ai_sug.get("expected_gain"),
            related_objects=related_objects,
            metadata={"source": "ai_advisor", "ai_details": ai_sug}
        )

    elif sug_type == "rewrite":
        # AI rewrite suggestion
        new_sql = ai_sug.get("new_sql") or ai_sug.get("sql_fix")
        table = _extract_table_from_sql(original_sql)
        related_objects = [table] if table else []

        suggestion_id = Suggestion.generate_id(
            level="query",
            category="rewrite",
            sql_fix=new_sql,
            related_objects=related_objects
        )

        return Suggestion(
            id=suggestion_id,
            level="query",
            category="rewrite",
            title="AI: Optimized query rewrite",
            summary=full_summary,
            sql_fix=new_sql,
            validated=ai_sug.get("validated", False),
            confidence="ai-heuristic",
            risk=ai_sug.get("risk", "low"),
            estimated_gain=ai_sug.get("expected_gain"),
            related_objects=related_objects,
            metadata={"source": "ai_advisor", "original_sql": original_sql}
        )

    else:
        # General note
        suggestion_id = Suggestion.generate_id(
            level="query",
            category="note",
            sql_fix=None,
            related_objects=[]
        )

        return Suggestion(
            id=suggestion_id,
            level="query",
            category="note",
            title="AI: Performance note",
            summary=full_summary,
            sql_fix=None,
            validated=False,
            confidence="ai-heuristic",
            risk="low",
            estimated_gain=None,
            related_objects=[],
            metadata={"source": "ai_advisor"}
        )


def analyze_query_suggestions(
    agent: BaseAgent,
    sql: str,
    include_ai: bool = True,
    top_k: int = 12
) -> tuple[List[Suggestion], List[str]]:
    """
    Generate comprehensive optimization suggestions for a query.
    Supports all SQL databases (PostgreSQL, MySQL, SQL Server, Oracle, SQLite).

    Args:
        agent: Database agent for database interaction
        sql: SQL query to analyze
        include_ai: Whether to include AI suggestions
        top_k: Maximum number of suggestions to return

    Returns:
        Tuple of (suggestions, notes)
        - suggestions: List of Suggestion objects
        - notes: System notes about the analysis
    """
    suggestions = []
    notes = []

    logger.info(f"Analyzing query for suggestions (include_ai={include_ai}, top_k={top_k})")

    try:
        # 1. Get rule-based index advice (PostgreSQL only for now)
        logger.info("Fetching index advice...")
        try:
            # Rule-based index advisor currently only supports PostgreSQL
            if isinstance(agent, PostgresAgent):
                index_recs = index_advice_pg(agent, sql)
                for rec in index_recs:
                    suggestion = _normalize_index_recommendation(rec, sql)
                    suggestions.append(suggestion)
                logger.info(f"Generated {len(index_recs)} index suggestions")
            else:
                logger.info(f"Rule-based index advisor not available for {agent.get_db_type()}")
        except Exception as e:
            logger.error(f"Index advice failed: {e}")
            notes.append(f"Index advisor error: {str(e)}")

        # 2. Get rule-based rewrite advice
        logger.info("Fetching rewrite advice...")
        try:
            rewrite_recs = rewrite_advice(sql)
            for rec in rewrite_recs:
                suggestion = _normalize_rewrite_recommendation(rec, sql)
                suggestions.append(suggestion)
            logger.info(f"Generated {len(rewrite_recs)} rewrite suggestions")
        except Exception as e:
            logger.error(f"Rewrite advice failed: {e}")
            notes.append(f"Rewrite advisor error: {str(e)}")

        # 3. Get AI suggestions (if enabled)
        if include_ai:
            logger.info("Fetching AI suggestions...")
            try:
                # Use generic AI suggestions for all databases
                from .ai_suggest import ai_suggestions_for_sql_generic
                llm = LLMClient()
                ai_suggestions = ai_suggestions_for_sql_generic(agent, sql, llm)

                for ai_sug in ai_suggestions:
                    # ✅ Filter AI index suggestions if they already exist
                    if ai_sug.get("type") == "index":
                        index_def = ai_sug.get("index", {})
                        table = index_def.get("table", "")
                        columns = index_def.get("columns", [])

                        if table and columns and agent.index_exists(table, columns):
                            logger.info(f"Skipping AI index suggestion for {table}({', '.join(columns)}) - already exists")
                            continue

                    suggestion = _normalize_ai_suggestion(ai_sug, sql)
                    suggestions.append(suggestion)
                logger.info(f"Generated {len(ai_suggestions)} AI suggestions")
            except Exception as e:
                logger.error(f"AI suggestions failed: {e}")
                notes.append(f"AI advisor error: {str(e)}")
        else:
            notes.append("AI suggestions disabled")

        # 4. Deduplicate (with index existence check as safety net)
        suggestions = _deduplicate_suggestions(suggestions, agent)

        # 5. Validate suggestions (PostgreSQL only - transactional EXPLAIN)
        logger.info("Validating suggestions...")
        if isinstance(agent, PostgresAgent):
            validated_count = _validate_suggestions(agent, sql, suggestions, notes)
            notes.append(f"Validated {validated_count}/{len(suggestions)} suggestions")
        else:
            # Skip validation for non-PostgreSQL databases
            logger.info(f"Validation skipped for {agent.get_db_type()} (not supported)")
            # Don't add this to notes - it's not an error, just a feature limitation
            validated_count = 0

        # 6. Update risk levels based on validation
        for suggestion in suggestions:
            if not suggestion.risk or suggestion.risk == "low":
                suggestion.risk = check_risk_level(
                    suggestion.sql_fix or "",
                    suggestion.category,
                    suggestion.validated
                )
                if suggestion.validated:
                    suggestion.confidence = "validated"

        # 7. Sort by priority (validated + high gain first)
        suggestions = _prioritize_suggestions(suggestions)

        # 8. Limit to top_k
        if len(suggestions) > top_k:
            suggestions = suggestions[:top_k]
            notes.append(f"Limited to top {top_k} suggestions")

        logger.info(f"Analysis complete: {len(suggestions)} total suggestions")

    except Exception as e:
        logger.error(f"analyze_query_suggestions failed: {e}")
        notes.append(f"Critical error: {str(e)}")

    return suggestions, notes


def _validate_suggestions(
    agent: PostgresAgent,
    original_sql: str,
    suggestions: List[Suggestion],
    notes: List[str]
) -> int:
    """
    Validate suggestions using transactional EXPLAIN.

    Args:
        agent: PostgresAgent
        original_sql: Original query
        suggestions: List of suggestions to validate
        notes: Notes list to append validation results

    Returns:
        Number of successfully validated suggestions
    """
    validated_count = 0

    with agent._conn() as conn:
        for suggestion in suggestions:
            # Check if validation is possible
            if not can_validate_suggestion(suggestion.category, suggestion.sql_fix):
                continue

            try:
                if suggestion.category == "index":
                    # Validate index using transactional rollback
                    table = suggestion.related_objects[0] if suggestion.related_objects else None
                    if not table:
                        continue

                    result = validate_index_in_tx(
                        conn,
                        suggestion.sql_fix,
                        original_sql,
                        table
                    )

                    if result.get("validated"):
                        suggestion.validated = True
                        suggestion.estimated_gain = f"Cost reduction: {result['cost_delta_pct']}%"
                        suggestion.metadata["validation"] = result
                        validated_count += 1
                        logger.info(f"Validated index suggestion {suggestion.id}: {result['cost_delta_pct']}% improvement")
                    else:
                        suggestion.metadata["validation_note"] = result.get("note", "Validation failed")

                elif suggestion.category == "rewrite":
                    # Validate rewrite by comparing EXPLAIN
                    result = validate_rewrite(conn, original_sql, suggestion.sql_fix)

                    if result.get("validated"):
                        suggestion.validated = True
                        suggestion.estimated_gain = f"Cost reduction: {result['cost_delta_pct']}%"
                        suggestion.metadata["validation"] = result
                        validated_count += 1
                        logger.info(f"Validated rewrite suggestion {suggestion.id}: {result['cost_delta_pct']}% improvement")
                    else:
                        suggestion.metadata["validation_note"] = result.get("note", "Validation failed")

            except Exception as e:
                logger.warning(f"Validation failed for {suggestion.id}: {e}")
                suggestion.metadata["validation_error"] = str(e)

    return validated_count


def _prioritize_suggestions(suggestions: List[Suggestion]) -> List[Suggestion]:
    """
    Sort suggestions by priority.
    Priority: validated > high gain > low risk > category (index > rewrite > note)

    Args:
        suggestions: List of suggestions

    Returns:
        Sorted list
    """
    def priority_key(s: Suggestion):
        # Validated suggestions first
        validated_score = 100 if s.validated else 0

        # Extract numeric gain if available
        gain_score = 0
        if s.estimated_gain and "%" in s.estimated_gain:
            try:
                # Extract percentage value
                pct_match = re.search(r'(\d+(\.\d+)?)', s.estimated_gain)
                if pct_match:
                    gain_score = float(pct_match.group(1))
            except:
                pass

        # Risk score (lower is better)
        risk_score = {"low": 10, "medium": 5, "high": 0}.get(s.risk, 5)

        # Category score
        category_score = {"index": 30, "rewrite": 20, "config": 15, "note": 5}.get(s.category, 0)

        # Combined score (higher is better)
        return -(validated_score + gain_score + risk_score + category_score)

    return sorted(suggestions, key=priority_key)
