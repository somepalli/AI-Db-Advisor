"""
Suggestions workflow API endpoints.
Provides headless approval workflow for optimization suggestions.
"""
from fastapi import APIRouter, HTTPException
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
import logging
import time

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/suggestions", tags=["suggestions"])


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

        # Support all SQL databases (NoSQL databases have different query structures)
        db_type = agent.get_db_type()
        if db_type not in ["postgres", "mysql", "sqlserver", "oracle", "sqlite"]:
            raise HTTPException(400, f"Suggestions workflow not supported for {db_type} (SQL databases only)")

        # Generate suggestions
        suggestions, notes = analyze_query_suggestions(
            agent,
            body.sql,
            include_ai=body.include_ai,
            top_k=body.top_k
        )

        duration_ms = (time.time() - start_time) * 1000

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

        # Support all SQL databases
        db_type = agent.get_db_type()
        if db_type not in ["postgres", "mysql", "sqlserver", "oracle", "sqlite"]:
            raise HTTPException(400, f"Suggestions workflow not supported for {db_type} (SQL databases only)")

        # We need to reconstruct Suggestion objects from IDs
        # In a real system, you'd store suggestions in a cache/database
        # For now, we'll return a helpful error
        # TODO: Implement suggestion caching/storage

        notes = []
        notes.append("Note: Suggestion application requires client to provide full Suggestion objects")
        notes.append("Current implementation: demonstration only")

        # For demonstration, return empty results
        # In production, you'd:
        # 1. Retrieve suggestions from cache by ID
        # 2. Apply them using services.apply.apply_suggestions()
        # 3. Record results in audit log

        results = []
        for sug_id in body.suggestion_ids:
            results.append(ApplyResult(
                id=sug_id,
                status="skipped",
                message="Suggestion storage not yet implemented - please use /apply_direct endpoint",
                rollback_sql=None
            ))

        duration_ms = (time.time() - start_time) * 1000

        # Record in audit log
        results_dict = [r.model_dump() for r in results]
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
            results=results
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

        # Support all SQL databases
        db_type = agent.get_db_type()
        if db_type not in ["postgres", "mysql", "sqlserver", "oracle", "sqlite"]:
            raise HTTPException(400, f"Suggestions workflow not supported for {db_type} (SQL databases only)")

        notes = []

        # Apply suggestions using the apply service
        # PostgreSQL uses context manager, others need explicit close
        from ..services.postgres_agent import PostgresAgent

        db_type = agent.get_db_type()
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
