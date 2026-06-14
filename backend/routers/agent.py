"""
Agent Router — autonomous, metadata-only investigation loop.

POST /agent/{ds_id}/investigate runs a bounded plan→read→diagnose→propose loop.
It NEVER executes anything: proposals are screened by the guardrail wall and the
queueable ones are routed into the existing HITL approval workflow as PENDING.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import logging

from ..services.agent_loop import run_investigation
from ..services import destructive_alerts
from ..deps import resolve_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


class InvestigateRequest(BaseModel):
    goal: str = Field(..., description="What to investigate, e.g. 'slow enrollment lookups'")
    max_iters: int = Field(6, ge=1, le=20, description="Maximum plan/read iterations")
    token_budget: int = Field(8000, ge=500, le=100000)


class InvestigateResponse(BaseModel):
    ds_id: str
    goal: str
    iterations: int
    trace: List[Dict[str, Any]]
    approval_ids: List[str]
    blocked: List[Dict[str, Any]]


@router.post("/{ds_id}/investigate", response_model=InvestigateResponse)
async def investigate(
    ds_id: str,
    body: InvestigateRequest,
    user_id: str = Header(default="agent", alias="X-User-ID"),
):
    """Run the bounded metadata-only agent loop and return its trace + pending approvals."""
    try:
        resolve_agent(ds_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Datasource not found: {ds_id}")

    try:
        result = await run_investigation(
            ds_id, body.goal,
            max_iters=body.max_iters,
            token_budget=body.token_budget,
            submitted_by=user_id,
        )
        return InvestigateResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent investigation failed for {ds_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")


class DestructiveAlertsResponse(BaseModel):
    ds_id: str
    alerts: List[Dict[str, Any]]
    count: int


@router.get("/{ds_id}/destructive-alerts", response_model=DestructiveAlertsResponse)
async def get_destructive_alerts(ds_id: str, limit: int = 100):
    """
    List recent DESTRUCTIVE_BLOCKED alarms for a datasource. These are
    informational only — they were blocked at the guardrail wall and can never
    be approved or executed.
    """
    alerts = destructive_alerts.get_recent(ds_id=ds_id, limit=limit)
    return DestructiveAlertsResponse(ds_id=ds_id, alerts=alerts, count=len(alerts))
