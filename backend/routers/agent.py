"""
Agent Router — autonomous, metadata-only investigation loop.

POST /agent/{ds_id}/investigate runs a bounded plan→read→diagnose→propose loop.
It NEVER executes anything: proposals are screened by the guardrail wall and the
queueable ones are routed into the existing HITL approval workflow as PENDING.

New autonomous endpoints:
  POST /agent/scan-all     — fan out proactive investigation to ALL datasources
  GET  /agent/scan/status  — poll progress of an active scan
  GET  /agent/scan/results — retrieve latest per-DS result summaries
"""
import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
import logging

from ..services.agent_loop import run_investigation, build_proactive_goal
from ..services import agent_scan_store
from ..services.agent_scan_store import PerDsResult
from ..services import destructive_alerts
from ..services import approval_store
from ..deps import resolve_agent
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

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


class ScanAllRequest(BaseModel):
    max_iters_per_ds: int = Field(8, ge=1, le=20)
    token_budget_per_ds: int = Field(8000, ge=500, le=100000)


class ScanAllResponse(BaseModel):
    scan_id: str
    started_at: str
    ds_count: int
    message: str


class ScanStatusResponse(BaseModel):
    scanning: bool
    scan_id: Optional[str]
    in_progress: List[str]
    completed: List[str]
    failed: List[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    elapsed_s: Optional[float]
    step_info: Dict[str, str] = {}   # ds_id → "step N: tool_name"


class PerDsResultSummary(BaseModel):
    ds_id: str
    status: str
    last_scanned_at: Optional[str]
    top_finding: Optional[str]
    approval_count: int
    blocked_count: int
    error: Optional[str]
    trace_length: int


class ScanResultsResponse(BaseModel):
    results: List[PerDsResultSummary]


class DestructiveAlertsResponse(BaseModel):
    ds_id: str
    alerts: List[Dict[str, Any]]
    count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_top_finding(trace: list) -> Optional[str]:
    """Derive a short human-readable finding from the agent trace."""
    for step in reversed(trace):
        if step.get("action") == "propose_queued":
            sql = (step.get("sql") or "").strip()
            return sql[:80] + ("…" if len(sql) > 80 else "")
    for step in reversed(trace):
        if step.get("action") == "finish":
            summary = (step.get("summary") or "").strip()
            return summary[:120] + ("…" if len(summary) > 120 else "")
    return None


async def _run_scan_background(
    scan_id: str,
    ds_map: dict,
    max_iters: int,
    token_budget: int,
    submitted_by: str,
) -> None:
    """Fan out run_investigation() to all datasources with a concurrency cap."""
    semaphore = asyncio.Semaphore(3)

    # Audit: scan started
    approval_store.append_audit(
        "scan_started",
        actor=submitted_by,
        detail={"scan_id": scan_id, "ds_ids": list(ds_map.keys()), "max_iters": max_iters},
    )

    async def _investigate_one(ds_id: str, cfg: Any) -> None:
        async with semaphore:
            engine = (
                getattr(cfg, "engine", None)
                or (cfg.get("engine") if isinstance(cfg, dict) else None)
                or "unknown"
            )
            goal = build_proactive_goal(engine)

            def _progress(step: int, action: str, tool: str) -> None:
                label = tool if tool else action
                agent_scan_store.update_step_info(scan_id, ds_id, f"step {step}: {label}")

            try:
                result = await run_investigation(
                    ds_id, goal,
                    max_iters=max_iters,
                    token_budget=token_budget,
                    submitted_by=submitted_by,
                    progress_callback=_progress,
                )
                status = (
                    "blocked" if result["blocked"] else
                    "approved" if result["approval_ids"] else "ok"
                )
                top_finding = _extract_top_finding(result["trace"])
                per = PerDsResult(
                    ds_id=ds_id,
                    status=status,
                    trace=result["trace"],
                    approval_ids=result["approval_ids"],
                    blocked=result["blocked"],
                    error=None,
                    scanned_at=datetime.utcnow().isoformat(),
                    top_finding=top_finding,
                )
                agent_scan_store.mark_done(scan_id, ds_id, per)

                # Record finding for agent institutional memory + audit trail
                approval_store.record_scan_finding(
                    ds_id=ds_id, scan_id=scan_id, status=status,
                    top_finding=top_finding,
                    approval_ids=result["approval_ids"],
                    blocked_count=len(result["blocked"]),
                    trace_length=len(result["trace"]),
                )
                approval_store.append_audit(
                    "scan_completed",
                    ds_id=ds_id, actor=submitted_by,
                    detail={
                        "scan_id": scan_id, "status": status,
                        "top_finding": top_finding,
                        "approval_ids": result["approval_ids"],
                        "blocked_count": len(result["blocked"]),
                    },
                )
            except Exception as e:
                logger.error(f"Auto-scan failed for {ds_id}: {e}", exc_info=True)
                agent_scan_store.mark_failed(scan_id, ds_id, str(e))
                approval_store.append_audit(
                    "scan_failed",
                    ds_id=ds_id, actor=submitted_by,
                    detail={"scan_id": scan_id, "error": str(e)[:200]},
                )

    await asyncio.gather(*[
        _investigate_one(ds_id, cfg) for ds_id, cfg in ds_map.items()
    ])


# ---------------------------------------------------------------------------
# Autonomous scan endpoints (literal paths — must come before /{ds_id}/*)
# ---------------------------------------------------------------------------

@router.post("/scan-all", response_model=ScanAllResponse)
async def scan_all(
    body: ScanAllRequest = ScanAllRequest(),
    user_id: str = Header(default="agent-auto", alias="X-User-ID"),
):
    """Fan out proactive investigations to all connected datasources concurrently.

    Returns immediately with a scan_id; poll GET /agent/scan/status for progress
    and GET /agent/scan/results for per-datasource summaries once scanning=false.
    """
    ds_map = dict(settings.DATASOURCES)
    if not ds_map:
        raise HTTPException(status_code=404, detail="No datasources registered")

    scan_id = f"scan-{uuid.uuid4().hex[:12]}"
    agent_scan_store.start_scan(scan_id, list(ds_map.keys()))

    asyncio.create_task(
        _run_scan_background(
            scan_id=scan_id,
            ds_map=ds_map,
            max_iters=body.max_iters_per_ds,
            token_budget=body.token_budget_per_ds,
            submitted_by=user_id,
        )
    )

    return ScanAllResponse(
        scan_id=scan_id,
        started_at=datetime.utcnow().isoformat(),
        ds_count=len(ds_map),
        message="Scan started; poll GET /agent/scan/status for progress",
    )


@router.get("/scan/status", response_model=ScanStatusResponse)
async def get_scan_status():
    """Return progress of the current (or most recent) scan."""
    state = agent_scan_store.get_status()
    if state is None:
        return ScanStatusResponse(
            scanning=False, scan_id=None,
            in_progress=[], completed=[], failed=[],
            started_at=None, finished_at=None, elapsed_s=None,
        )
    elapsed: Optional[float] = None
    if state.started_at:
        try:
            elapsed = round(
                (datetime.utcnow() - datetime.fromisoformat(state.started_at)).total_seconds(), 1
            )
        except Exception:
            pass
    return ScanStatusResponse(
        scanning=state.scanning,
        scan_id=state.scan_id,
        in_progress=list(state.in_progress),
        completed=list(state.completed),
        failed=list(state.failed),
        started_at=state.started_at,
        finished_at=state.finished_at,
        elapsed_s=elapsed,
        step_info=dict(state.step_info),
    )


@router.get("/scan/results", response_model=ScanResultsResponse)
async def get_scan_results():
    """Return the latest per-datasource result summary (no full trace)."""
    _SEVERITY = {"error": 0, "blocked": 1, "approved": 2, "ok": 3, "no_finding": 4}
    all_r = agent_scan_store.get_all_latest()
    summaries = [
        PerDsResultSummary(
            ds_id=r.ds_id,
            status=r.status,
            last_scanned_at=r.scanned_at,
            top_finding=r.top_finding,
            approval_count=len(r.approval_ids),
            blocked_count=len(r.blocked),
            error=r.error,
            trace_length=len(r.trace),
        )
        for r in all_r.values()
    ]
    summaries.sort(key=lambda s: _SEVERITY.get(s.status, 9))
    return ScanResultsResponse(results=summaries)


# ---------------------------------------------------------------------------
# Per-datasource endpoints (parameterised — must come after literal paths)
# ---------------------------------------------------------------------------

@router.get("/audit")
async def get_global_audit(ds_id: Optional[str] = None, limit: int = 200):
    """Return the full append-only audit trail across all DSes, newest first.

    Pass ?ds_id=<id> to filter to a single datasource.
    """
    entries = approval_store.get_audit_log(ds_id=ds_id, limit=limit)
    return {"entries": entries, "total": len(entries), "ds_id": ds_id}


@router.get("/{ds_id}/approvals/{approval_id}/audit")
async def get_approval_audit(ds_id: str, approval_id: str):
    """Return the append-only audit trail for a single approval record."""
    audit = approval_store.get_audit(approval_id)
    return {"approval_id": approval_id, "ds_id": ds_id, "audit": audit}


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
        approval_store.append_audit(
            "investigation_run",
            ds_id=ds_id, actor=user_id,
            detail={
                "goal": body.goal[:200],
                "iterations": result["iterations"],
                "approval_ids": result["approval_ids"],
                "blocked_count": len(result["blocked"]),
            },
        )
        top_finding = _extract_top_finding(result["trace"])
        if top_finding or result["approval_ids"]:
            approval_store.record_scan_finding(
                ds_id=ds_id, scan_id="manual",
                status="approved" if result["approval_ids"] else "ok",
                top_finding=top_finding,
                approval_ids=result["approval_ids"],
                blocked_count=len(result["blocked"]),
                trace_length=result["iterations"],
            )
        return InvestigateResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent investigation failed for {ds_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")


@router.get("/{ds_id}/destructive-alerts", response_model=DestructiveAlertsResponse)
async def get_destructive_alerts(ds_id: str, limit: int = 100):
    """
    List recent DESTRUCTIVE_BLOCKED alarms for a datasource. These are
    informational only — they were blocked at the guardrail wall and can never
    be approved or executed.
    """
    alerts = destructive_alerts.get_recent(ds_id=ds_id, limit=limit)
    return DestructiveAlertsResponse(ds_id=ds_id, alerts=alerts, count=len(alerts))
