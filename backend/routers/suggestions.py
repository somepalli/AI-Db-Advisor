"""
Suggestions workflow API endpoints.
Provides headless approval workflow for optimization suggestions.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Tuple, Optional
from ..schemas import (
    AnalyzeSuggestionsRequest,
    AnalyzeSuggestionsResponse,
    ApplySuggestionsRequest,
    ApplySuggestionsResponse,
    ApplySuggestionsDirectRequest,
    Suggestion,
    ApplyResult
)
from ..deps import resolve_agent
from ..services.super_agent import analyze_query_suggestions
from ..services.apply import apply_suggestions
from ..services.history import record_analyze, record_apply
from ..services.suggestion_store import suggestion_store
from ..services.postgres_agent import PostgresAgent
import logging
import time

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/suggestions", tags=["suggestions"])

SUPPORTED_SQL_ENGINES = {"postgres"}
SUPPORTED_SQL_NAMES = {"postgres": "PostgreSQL"}
SUPPORTED_SQL_DISPLAY = "PostgreSQL"


def _resolve_db_type(agent) -> Tuple[str, str]:
    """
    Attempt to determine the database type for the provided agent.

    Returns:
        Tuple[db_type_normalized, agent_class_name]
    """
    agent_class = getattr(agent.__class__, "__name__", "") or "UnknownAgent"

    db_type: Optional[str] = None
    if hasattr(agent, "get_db_type"):
        try:
            value = agent.get_db_type()
            if isinstance(value, str) and value:
                db_type = value.lower()
        except Exception as exc:
            logger.debug(f"get_db_type() failed for {agent_class}: {exc}")

    if not db_type and agent_class:
        db_type = agent_class.replace("Agent", "").lower()

    return db_type or "unknown", agent_class


def _ensure_supported(agent) -> str:
    """
    Ensure that the provided agent corresponds to a supported SQL database.
    Raises HTTPException if not supported.

    Returns:
        Normalized database type string.
    """
    db_type, agent_class = _resolve_db_type(agent)

    if db_type not in SUPPORTED_SQL_ENGINES:
        raise HTTPException(
            400,
            (
                f"Suggestions workflow currently supports {SUPPORTED_SQL_DISPLAY}. "
                f"Received: {agent_class}."
            ),
        )

    return db_type


@router.post("/analyze", response_model=AnalyzeSuggestionsResponse)
def analyze_suggestions(body: AnalyzeSuggestionsRequest):
    """
    Analyze a SQL query and generate consolidated optimization suggestions.

    This endpoint combines:
    - Rule-based index advisor
    - Rule-based query rewrite advisor
    - AI-powered suggestions (optional)
    - Transactional validation (Windows-safe, uses BEGIN/ROLLBACK)

    Returns:
        Structured suggestions ready for approval/application
    """
    start_time = time.time()

    logger.info(f"\n{'#'*80}")
    logger.info(f"POST /suggestions/analyze")
    logger.info(f"{'#'*80}")
    logger.info(f"Data Source: {body.ds_id}")
    logger.info(f"SQL Length: {len(body.sql)} chars")
    logger.info(f"Include AI: {body.include_ai}")
    logger.info(f"Top K: {body.top_k}")

    try:
        # Resolve agent
        agent = resolve_agent(body.ds_id)
        logger.info(f"Agent: {agent.__class__.__name__}")

        # Support SQL databases only
        db_type = _ensure_supported(agent)

        # Generate suggestions
        suggestions, notes = analyze_query_suggestions(
            agent,
            body.sql,
            include_ai=body.include_ai,
            top_k=body.top_k
        )

        duration_ms = (time.time() - start_time) * 1000

        if suggestions:
            # Store suggestions for future /suggestions/apply calls
            suggestion_store.add_all(body.ds_id, suggestions)

        # Record in audit log
        suggestions_dict = [s.model_dump() for s in suggestions]
        record_analyze(
            ds_id=body.ds_id,
            sql=body.sql,
            suggestions=suggestions_dict,
            include_ai=body.include_ai,
            duration_ms=duration_ms,
            notes=notes
        )

        logger.info(f"\n{'#'*80}")
        logger.info(f"Analysis complete: {len(suggestions)} suggestions in {duration_ms:.0f}ms")
        logger.info(f"{'#'*80}\n")

        return AnalyzeSuggestionsResponse(
            notes=notes,
            suggestions=suggestions
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"analyze_suggestions error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@router.post("/apply", response_model=ApplySuggestionsResponse)
def apply_suggestions_endpoint(body: ApplySuggestionsRequest):
    """
    Apply one or more optimization suggestions to the database.

    Supports:
    - Dry-run mode: Validates with BEGIN/ROLLBACK (no actual changes)
    - Real mode: Applies changes and generates rollback SQL
    - Batch application: Apply multiple suggestions at once
    - Safety checks: Guardrails prevent dangerous operations

    Returns:
        Results for each suggestion with status and rollback SQL
    """
    start_time = time.time()

    logger.info(f"\n{'#'*80}")
    logger.info(f"POST /suggestions/apply")
    logger.info(f"{'#'*80}")
    logger.info(f"Data Source: {body.ds_id}")
    logger.info(f"Suggestion IDs: {body.suggestion_ids}")
    logger.info(f"Dry Run: {body.dry_run}")

    try:
        # Resolve agent
        agent = resolve_agent(body.ds_id)
        logger.info(f"Agent: {agent.__class__.__name__}")

        # Support SQL databases only
        db_type = _ensure_supported(agent)

        # We need to reconstruct Suggestion objects from IDs
        # In a real system, you'd store suggestions in a cache/database
        # For now, we'll return a helpful error
        # TODO: Implement suggestion caching/storage

        notes = []

        # Retrieve stored suggestions by ID
        stored_suggestions, missing_ids = suggestion_store.get_many(
            body.suggestion_ids, datasource_id=body.ds_id
        )

        if missing_ids:
            notes.append(
                "Some suggestion IDs were not found or have expired. "
                "Regenerate analysis if you need fresh recommendations."
            )

        apply_results: List[ApplyResult] = []

        if stored_suggestions:
            logger.info(f"Applying {len(stored_suggestions)} stored suggestion(s)")

            # Apply the stored suggestions
            try:
                if isinstance(agent, PostgresAgent):
                    with agent._conn() as conn:
                        apply_results = apply_suggestions(conn, stored_suggestions, body.dry_run, db_type)
                else:
                    conn = agent._conn()
                    try:
                        apply_results = apply_suggestions(conn, stored_suggestions, body.dry_run, db_type)
                    finally:
                        conn.close()
            except Exception as e:
                logger.error(f"Failed to apply stored suggestions: {e}", exc_info=True)
                raise
        else:
            notes.append("No stored suggestions available to apply.")

        # Any missing IDs should return skipped ApplyResult entries. Clients may then
        # retry those via /suggestions/apply_direct with the full suggestion payload.
        if missing_ids:
            missing_results = [
                ApplyResult(
                    id=sug_id,
                    status="skipped",
                    message="Suggestion not found or expired. Please re-run analysis to obtain a fresh recommendation.",
                    rollback_sql=None
                )
                for sug_id in missing_ids
            ]

            apply_results.extend(missing_results)

        # Preserve original ordering of request IDs in response
        results_by_id = {result.id: result for result in apply_results}
        ordered_results = [
            results_by_id.get(
                sug_id,
                ApplyResult(
                    id=sug_id,
                    status="skipped",
                    message="Suggestion not found or expired. Please re-run analysis to obtain a fresh recommendation.",
                    rollback_sql=None
                )
            )
            for sug_id in body.suggestion_ids
        ]

        duration_ms = (time.time() - start_time) * 1000

        # Record in audit log
        results_dict = [r.model_dump() for r in ordered_results]
        record_apply(
            ds_id=body.ds_id,
            suggestion_ids=body.suggestion_ids,
            results=results_dict,
            dry_run=body.dry_run,
            duration_ms=duration_ms,
            notes=notes
        )

        logger.info(f"\n{'#'*80}")
        logger.info(f"Apply complete in {duration_ms:.0f}ms")
        logger.info(f"{'#'*80}\n")

        return ApplySuggestionsResponse(
            notes=notes,
            results=ordered_results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"apply_suggestions error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Application failed: {str(e)}")


@router.post("/apply_direct", response_model=ApplySuggestionsResponse)
def apply_suggestions_direct(body: ApplySuggestionsDirectRequest):
    """
    Apply suggestions directly (for demonstration/testing).
    Client provides full Suggestion objects.

    This endpoint:
    - Takes full Suggestion objects (not just IDs)
    - Applies them using the apply service
    - Returns detailed results with rollback SQL

    Args:
        body: Request containing ds_id, suggestions, and dry_run flag
    """
    start_time = time.time()

    logger.info(f"\n{'#'*80}")
    logger.info(f"POST /suggestions/apply_direct")
    logger.info(f"{'#'*80}")
    logger.info(f"Data Source: {body.ds_id}")
    logger.info(f"Suggestions: {len(body.suggestions)}")
    logger.info(f"Dry Run: {body.dry_run}")

    try:
        # Resolve agent
        agent = resolve_agent(body.ds_id)
        logger.info(f"Agent: {agent.__class__.__name__}")

        notes = []

        # Apply suggestions using the apply service
        # PostgreSQL uses context manager, others need explicit close
        db_type = _ensure_supported(agent)
        logger.info(f"Database type: {db_type}")

        if isinstance(agent, PostgresAgent):
            with agent._conn() as conn:
                results = apply_suggestions(conn, body.suggestions, body.dry_run, db_type)
        else:
            conn = agent._conn()
            try:
                results = apply_suggestions(conn, body.suggestions, body.dry_run, db_type)
            finally:
                conn.close()

        # Convert to ApplyResult models
        apply_results = [
            ApplyResult(
                id=r.id,
                status=r.status,
                message=r.message,
                rollback_sql=r.rollback_sql
            ) for r in results
        ]

        duration_ms = (time.time() - start_time) * 1000

        # Record in audit log
        suggestion_ids = [s.id for s in body.suggestions]
        results_dict = [r.model_dump() for r in apply_results]
        record_apply(
            ds_id=body.ds_id,
            suggestion_ids=suggestion_ids,
            results=results_dict,
            dry_run=body.dry_run,
            duration_ms=duration_ms,
            notes=notes
        )

        # Count outcomes
        success_count = sum(1 for r in apply_results if r.status == "success")
        error_count = sum(1 for r in apply_results if r.status == "error")
        skipped_count = sum(1 for r in apply_results if r.status == "skipped")

        notes.append(f"Applied {success_count}/{len(body.suggestions)} suggestions successfully")
        if error_count > 0:
            notes.append(f"{error_count} suggestions failed")
        if skipped_count > 0:
            notes.append(f"{skipped_count} suggestions skipped")

        logger.info(f"\n{'#'*80}")
        logger.info(f"Apply complete: {success_count} success, {error_count} error, {skipped_count} skipped")
        logger.info(f"Duration: {duration_ms:.0f}ms")
        logger.info(f"{'#'*80}\n")

        return ApplySuggestionsResponse(
            notes=notes,
            results=apply_results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"apply_suggestions_direct error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Application failed: {str(e)}")
