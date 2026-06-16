"""
MCP Router - API endpoints for Model Context Protocol integration

Provides endpoints for:
- Requesting MCP suggestions
- Approving/rejecting suggestions
- Executing approved suggestions
- Viewing pending approvals and history
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from ..services.mcp_orchestrator import MCPOrchestrator
from ..services.approval_workflow import get_workflow
from ..services.mcp_client import get_mcp_client
from ..services import approval_store
from ..services import destructive_alerts
from ..services.agent_guardrails import evaluate as guardrail_evaluate, GuardrailDecision
from ..deps import resolve_agent
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["mcp"])


def _screen_and_register(ds_id: str, suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Run every suggestion through the guardrail wall, drop+alert any DENY, and
    submit the survivors for approval so each carries a REAL persisted approval_id.
    """
    workflow = get_workflow(ds_id)
    kept: List[Dict[str, Any]] = []
    for s in suggestions:
        sql = (s.get("sql") or "")
        wall = guardrail_evaluate(sql, agentic=True)
        if wall.decision is GuardrailDecision.DENY:
            logger.warning(
                f"Guardrail wall DENY — dropping suggestion for {ds_id}: "
                f"{wall.matched_rule or wall.risk_class.value} :: {sql[:80]!r}"
            )
            if wall.alert:
                destructive_alerts.raise_destructive_blocked(
                    ds_id, sql,
                    matched_rule=wall.matched_rule,
                    risk_class=wall.risk_class.value,
                    reason=wall.reason,
                    source="mcp_router",
                )
            continue
        # Set risk_class BEFORE persisting so the stored record (returned by
        # /pending) carries it for the UI badge + typed-confirmation gate.
        s["risk_class"] = wall.risk_class.value
        # Submit for approval to obtain a real, persisted approval_id.
        approval_id = workflow.submit_for_approval(s)
        s["approval_id"] = approval_id
        s["status"] = "pending_approval"
        kept.append(s)
    return kept


# Request/Response Schemas
class MCPSuggestionRequest(BaseModel):
    """Request for MCP suggestions"""
    query: Optional[str] = None
    schema_context: Optional[Dict[str, Any]] = None
    optimization_type: str = "general"
    max_suggestions: int = 5


class MCPSuggestionResponse(BaseModel):
    """Response containing MCP suggestions"""
    suggestions: List[Dict[str, Any]]
    count: int
    datasource_id: str
    requested_at: str
    note: str = "These are suggestions only. Approve to execute."
    # True when MCP is not configured and the suggestions are illustrative samples.
    demo_mode: bool = False


class ApprovalRequest(BaseModel):
    """Request to approve a suggestion"""
    notes: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Response for approval action"""
    success: bool
    message: str
    approval: Dict[str, Any]


class RejectRequest(BaseModel):
    """Request to reject a suggestion"""
    reason: str


class ExecutionResponse(BaseModel):
    """Response for execution action"""
    success: bool
    message: str
    approval_id: str
    suggestion_id: str
    result: Dict[str, Any]
    executed_at: str


class PendingApprovalsResponse(BaseModel):
    """Response containing pending approvals"""
    pending: List[Dict[str, Any]]
    count: int
    datasource_id: str


class HistoryResponse(BaseModel):
    """Response containing execution history"""
    history: List[Dict[str, Any]]
    count: int
    datasource_id: str


class StatisticsResponse(BaseModel):
    """Response containing MCP statistics"""
    datasource_id: str
    mcp_enabled: bool
    total_submitted: int
    total_approved: int
    total_rejected: int
    total_executed: int
    total_failed: int
    currently_pending: int
    awaiting_execution: int


@router.post("/{ds_id}/request-suggestions", response_model=MCPSuggestionResponse)
async def request_mcp_suggestions(
    ds_id: str,
    request: MCPSuggestionRequest
):
    """
    Request suggestions from MCP tools.

    SAFETY: Only generates suggestions, never executes.

    Args:
        ds_id: Datasource ID
        request: Suggestion request parameters

    Returns:
        List of validated suggestions ready for user approval

    Example:
        POST /mcp/postgres-db/request-suggestions
        {
            "query": "SELECT * FROM students",
            "optimization_type": "performance",
            "max_suggestions": 5
        }
    """
    try:
        logger.info(f"MCP suggestion request for {ds_id}: type={request.optimization_type}")

        # Check if MCP is enabled - if not, only fall back to demo when explicitly enabled.
        mcp_client = get_mcp_client()
        use_demo_mode = mcp_client is None and settings.DEMO_MODE

        if mcp_client is None and not settings.DEMO_MODE:
            # No real MCP client and demo mode is off → refuse rather than fake success.
            raise HTTPException(
                status_code=503,
                detail="MCP is not configured and demo mode is disabled. "
                       "Set MCP_ENABLED + a bridge, or DEMO_MODE=true to use illustrative suggestions.",
            )

        # Generate suggestions (demo mode if MCP not configured but DEMO_MODE on)
        if use_demo_mode:
            logger.info(f"Using DEMO mode for MCP suggestions (MCP not configured, DEMO_MODE on)")
            # In demo mode, we don't need to verify datasource exists.
            # Screen + register so demo suggestions carry real persisted approval IDs.
            suggestions = _screen_and_register(ds_id, _generate_demo_suggestions(ds_id, request))
        else:
            # Verify datasource exists (only needed for real MCP mode)
            try:
                resolve_agent(ds_id)
            except Exception as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"Datasource not found: {ds_id}"
                )

            # Create orchestrator (screens + submits real, persisted approvals internally)
            orchestrator = MCPOrchestrator(ds_id)

            # Request suggestions
            suggestions = await orchestrator.request_database_suggestions(
                query=request.query,
                schema_context=request.schema_context,
                optimization_type=request.optimization_type,
                max_suggestions=request.max_suggestions
            )

        logger.info(f"Generated {len(suggestions)} MCP suggestions for {ds_id}")

        return MCPSuggestionResponse(
            suggestions=suggestions,
            count=len(suggestions),
            datasource_id=ds_id,
            requested_at=datetime.utcnow().isoformat(),
            note="These are suggestions only. Approve to execute." + (" [DEMO MODE]" if use_demo_mode else ""),
            demo_mode=use_demo_mode
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP suggestion request failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to request MCP suggestions: {str(e)}"
        )


@router.post("/{ds_id}/approve/{approval_id}", response_model=ApprovalResponse)
async def approve_mcp_suggestion(
    ds_id: str,
    approval_id: str,
    request: ApprovalRequest,
    user_id: str = Header(default="user", alias="X-User-ID")
):
    """
    User approves an MCP suggestion.

    Args:
        ds_id: Datasource ID
        approval_id: Approval identifier
        request: Approval request with optional notes
        user_id: User ID from header

    Returns:
        Approval confirmation

    Example:
        POST /mcp/postgres-db/approve/approval-abc123
        Headers: X-User-ID: john@example.com
        {
            "notes": "Looks good, will improve performance"
        }
    """
    try:
        logger.info(f"Approval request: {approval_id} by {user_id}")

        # DEMO MODE: only short-circuit when demo is explicitly enabled.
        mcp_client = get_mcp_client()
        if mcp_client is None and settings.DEMO_MODE:
            logger.info(f"DEMO MODE: Approving {approval_id}")
            return ApprovalResponse(
                success=True,
                message="Suggestion approved successfully (DEMO MODE). Ready for execution.",
                approval={
                    "approval_id": approval_id,
                    "status": "approved",
                    "approved_by": user_id,
                    "approved_at": datetime.utcnow().isoformat(),
                    "notes": request.notes
                }
            )

        # Get workflow
        workflow = get_workflow(ds_id)

        # Approve suggestion
        try:
            approval = workflow.approve(
                approval_id=approval_id,
                user_id=user_id,
                notes=request.notes
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

        logger.info(f"Suggestion approved: {approval_id}")

        return ApprovalResponse(
            success=True,
            message="Suggestion approved successfully. Ready for execution.",
            approval=approval
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve suggestion: {str(e)}"
        )


@router.post("/{ds_id}/reject/{approval_id}", response_model=ApprovalResponse)
async def reject_mcp_suggestion(
    ds_id: str,
    approval_id: str,
    request: RejectRequest,
    user_id: str = Header(default="user", alias="X-User-ID")
):
    """
    User rejects an MCP suggestion.

    Args:
        ds_id: Datasource ID
        approval_id: Approval identifier
        request: Rejection request with reason
        user_id: User ID from header

    Returns:
        Rejection confirmation
    """
    try:
        logger.info(f"Rejection request: {approval_id} by {user_id}")

        # Get workflow
        workflow = get_workflow(ds_id)

        # Reject suggestion
        try:
            approval = workflow.reject(
                approval_id=approval_id,
                user_id=user_id,
                reason=request.reason
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

        logger.info(f"Suggestion rejected: {approval_id}")

        return ApprovalResponse(
            success=True,
            message="Suggestion rejected.",
            approval=approval
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rejection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reject suggestion: {str(e)}"
        )


@router.post("/{ds_id}/execute/{approval_id}", response_model=ExecutionResponse)
async def execute_approved_suggestion(
    ds_id: str,
    approval_id: str,
    user_id: str = Header(default="user", alias="X-User-ID")
):
    """
    Execute an APPROVED MCP suggestion.

    CRITICAL SAFETY:
    Only executes suggestions that have been:
    1. Validated for safety
    2. Approved by a user
    3. Confirmed for execution

    Args:
        ds_id: Datasource ID
        approval_id: Approval identifier
        user_id: User ID from header

    Returns:
        Execution result

    Raises:
        403: If suggestion is not approved
        500: If execution fails
    """
    try:
        logger.info(f"Execution request: {approval_id} by {user_id}")

        # DEMO MODE: only simulate execution when demo is explicitly enabled.
        mcp_client = get_mcp_client()
        if mcp_client is None and settings.DEMO_MODE:
            logger.info(f"DEMO MODE: Simulating execution of {approval_id}")
            return ExecutionResponse(
                success=True,
                message="Suggestion executed successfully (DEMO MODE - no actual changes made)",
                approval_id=approval_id,
                suggestion_id=f"demo-{approval_id}",
                result={
                    "status": "success",
                    "message": "Demo execution completed",
                    "note": "This is a simulated execution. In production, the actual SQL would be executed.",
                    "rows_affected": 0
                },
                executed_at=datetime.utcnow().isoformat()
            )

        # Create orchestrator
        orchestrator = MCPOrchestrator(ds_id)

        # Execute approved suggestion
        result = await orchestrator.execute_approved_suggestion(
            approval_id=approval_id,
            user_id=user_id
        )

        logger.info(f"Execution successful: {approval_id}")

        return ExecutionResponse(
            success=result["success"],
            message="Suggestion executed successfully",
            approval_id=result["approval_id"],
            suggestion_id=result["suggestion_id"],
            result=result["result"],
            executed_at=result["executed_at"]
        )

    except ValueError as e:
        raise HTTPException(
            status_code=403,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Execution failed: {str(e)}"
        )


@router.get("/{ds_id}/pending", response_model=PendingApprovalsResponse)
async def get_pending_approvals(ds_id: str):
    """
    Get all pending approval requests for a datasource.

    Args:
        ds_id: Datasource ID

    Returns:
        List of pending suggestions awaiting user approval
    """
    try:
        workflow = get_workflow(ds_id)
        pending = workflow.get_pending_approvals()

        logger.info(f"Retrieved {len(pending)} pending approvals for {ds_id}")

        return PendingApprovalsResponse(
            pending=pending,
            count=len(pending),
            datasource_id=ds_id
        )

    except Exception as e:
        logger.error(f"Failed to get pending approvals: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve pending approvals: {str(e)}"
        )


@router.get("/{ds_id}/history", response_model=HistoryResponse)
async def get_execution_history(
    ds_id: str,
    limit: int = 50,
    status: Optional[str] = None
):
    """
    Get execution history for a datasource.

    Args:
        ds_id: Datasource ID
        limit: Maximum number of records (default: 50)
        status: Filter by status (executed, failed, etc.)

    Returns:
        List of execution records
    """
    try:
        orchestrator = MCPOrchestrator(ds_id)
        history = orchestrator.get_execution_history(limit=limit)

        # Filter by status if provided
        if status:
            history = [h for h in history if h["status"] == status]

        logger.info(f"Retrieved {len(history)} history records for {ds_id}")

        return HistoryResponse(
            history=history,
            count=len(history),
            datasource_id=ds_id
        )

    except Exception as e:
        logger.error(f"Failed to get execution history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve execution history: {str(e)}"
        )


@router.get("/{ds_id}/statistics", response_model=StatisticsResponse)
async def get_mcp_statistics(ds_id: str):
    """
    Get MCP usage statistics for a datasource.

    Args:
        ds_id: Datasource ID

    Returns:
        Statistics object with counts and metrics
    """
    try:
        orchestrator = MCPOrchestrator(ds_id)
        stats = orchestrator.get_statistics()

        logger.info(f"Retrieved MCP statistics for {ds_id}")

        return StatisticsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.get("/health")
async def mcp_health_check():
    """
    Check MCP integration health status.

    Returns:
        Health status and configuration
    """
    mcp_client = get_mcp_client()

    health_status = {
        "mcp_enabled": mcp_client is not None,
        "timestamp": datetime.utcnow().isoformat()
    }

    if mcp_client:
        try:
            credentials_valid = await mcp_client.validate_credentials()
            health_status["credentials_valid"] = credentials_valid
            health_status["status"] = "healthy" if credentials_valid else "degraded"
        except Exception as e:
            health_status["status"] = "error"
            health_status["error"] = str(e)
    else:
        health_status["status"] = "disabled"
        health_status["message"] = "MCP integration not configured"

    return health_status


def _generate_demo_suggestions(ds_id: str, request: MCPSuggestionRequest) -> List[Dict[str, Any]]:
    """
    Generate demo MCP suggestions when MCP is not configured.
    This allows users to see and test the MCP approval workflow.
    """
    import uuid
    from datetime import datetime

    demo_suggestions = [
        {
            "id": f"demo-{uuid.uuid4().hex[:8]}",
            "approval_id": f"approval-{uuid.uuid4().hex[:12]}",
            "mcp_tool": "database_optimizer",
            "sql": "CREATE INDEX idx_students_enrollment_year ON students(enrollment_year);",
            "description": "Create index on students.enrollment_year for faster filtering",
            "rationale": "Queries filtering by enrollment_year will benefit from this index, reducing full table scans.",
            "category": "index",
            "risk_level": "low",
            "impact_level": "moderate",
            "warnings": [],
            "blocking_issues": [],
            "tables_affected": ["students"],
            "is_reversible": True,
            "requires_backup": False,
            "requires_confirmation": False,
            "requires_double_confirmation": False,
            "recommendation": "Safe to execute. Index creation is reversible.",
            "impact_details": {
                "estimated_improvement": "30-50% faster queries on enrollment_year",
                "disk_space": "~5MB"
            },
            "status": "pending_approval",
            "generated_at": datetime.utcnow().isoformat(),
            "validated_at": datetime.utcnow().isoformat()
        },
        {
            "id": f"demo-{uuid.uuid4().hex[:8]}",
            "approval_id": f"approval-{uuid.uuid4().hex[:12]}",
            "mcp_tool": "query_optimizer",
            "sql": "ANALYZE students;",
            "description": "Update table statistics for query optimizer",
            "rationale": "Fresh statistics help the database choose optimal query plans.",
            "category": "optimization",
            "risk_level": "low",
            "impact_level": "minimal",
            "warnings": ["May briefly lock the table"],
            "blocking_issues": [],
            "tables_affected": ["students"],
            "is_reversible": True,
            "requires_backup": False,
            "requires_confirmation": False,
            "requires_double_confirmation": False,
            "recommendation": "Safe to execute during low-traffic periods.",
            "impact_details": {
                "estimated_improvement": "Better query plan selection",
                "duration": "< 1 second"
            },
            "status": "pending_approval",
            "generated_at": datetime.utcnow().isoformat(),
            "validated_at": datetime.utcnow().isoformat()
        },
        {
            "id": f"demo-{uuid.uuid4().hex[:8]}",
            "approval_id": f"approval-{uuid.uuid4().hex[:12]}",
            "mcp_tool": "performance_tuner",
            "sql": "CREATE INDEX idx_enrollments_student_course ON enrollments(student_id, course_id);",
            "description": "Composite index for student-course lookups",
            "rationale": "JOIN queries between students and courses will be significantly faster.",
            "category": "index",
            "risk_level": "medium",
            "impact_level": "significant",
            "warnings": ["Index creation may take several minutes on large tables"],
            "blocking_issues": [],
            "tables_affected": ["enrollments"],
            "is_reversible": True,
            "requires_backup": True,
            "requires_confirmation": True,
            "requires_double_confirmation": False,
            "recommendation": "Create during maintenance window. Consider testing on staging first.",
            "impact_details": {
                "estimated_improvement": "50-70% faster JOIN queries",
                "disk_space": "~15MB"
            },
            "status": "pending_approval",
            "generated_at": datetime.utcnow().isoformat(),
            "validated_at": datetime.utcnow().isoformat()
        }
    ]

    # Limit to requested max_suggestions
    return demo_suggestions[:request.max_suggestions]
