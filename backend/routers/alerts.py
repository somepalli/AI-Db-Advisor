"""
Alert API Router - Endpoints for alert management and monitoring

Provides endpoints for:
- Managing alert rules
- Viewing active/historical alerts
- Acknowledging and resolving alerts
- Getting AI analysis for alerts
- Starting/stopping monitoring for datasources
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from ..services.alert_engine import (
    AlertEngine,
    AlertRule,
    AlertCondition,
    AlertSeverity,
    AlertStatus,
    Alert
)
from ..services.alert_analyzer import AlertAnalyzer, AlertAnalysis
from ..services.metrics_collector import collect_all_metrics
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["Alerts"])

# Global alert engine instance (in production, use dependency injection)
alert_engine = AlertEngine()
alert_analyzer = AlertAnalyzer()

# Track which datasources are being monitored
monitoring_tasks: Dict[str, bool] = {}


# ============================================================================
# Request/Response Models
# ============================================================================

class AlertRuleRequest(BaseModel):
    """Request model for creating/updating alert rules"""
    id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    severity: str = Field(..., description="P1, P2, or P3")
    description: str = Field(..., description="Rule description")
    enabled: bool = Field(True, description="Whether rule is active")
    datasource_types: List[str] = Field(["*"], description="List of engine types or ['*'] for all")
    conditions: List[Dict[str, Any]] = Field(..., description="List of alert conditions")
    auto_resolve: bool = Field(True, description="Auto-resolve when conditions clear")
    cooldown_minutes: int = Field(15, description="Minutes before same alert can retrigger")


class AlertResponse(BaseModel):
    """Response model for alert details"""
    id: str
    rule_id: str
    severity: str
    title: str
    message: str
    datasource_id: str
    datasource_engine: str
    triggered_at: datetime
    status: str
    metric_value: Optional[Any] = None
    threshold: Optional[Any] = None
    metadata: Dict[str, Any] = {}
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    auto_resolved: bool = False


class AcknowledgeRequest(BaseModel):
    """Request model for acknowledging an alert"""
    acknowledged_by: str = Field(..., description="User who acknowledged the alert")
    notes: str = Field("", description="Optional acknowledgment notes")


class ResolveRequest(BaseModel):
    """Request model for resolving an alert"""
    resolved_by: Optional[str] = Field(None, description="User who resolved the alert")
    notes: str = Field("", description="Optional resolution notes")


class MonitoringConfigRequest(BaseModel):
    """Request model for updating monitoring configuration"""
    evaluation_interval_seconds: int = Field(30, ge=10, le=300, description="How often to evaluate rules (10-300s)")
    enabled_rules: Optional[List[str]] = Field(None, description="List of rule IDs to enable (null = all)")


# ============================================================================
# Alert Retrieval Endpoints
# ============================================================================

@router.get("/active", response_model=Dict[str, Any])
async def get_active_alerts(
    datasource_id: Optional[str] = None,
    severity: Optional[str] = None
):
    """
    Get all currently active alerts (status: active or acknowledged)

    Query Parameters:
    - datasource_id: Filter by datasource
    - severity: Filter by severity (P1, P2, P3)

    Returns:
    - alerts: List of active/acknowledged alerts
    - count: Number of alerts
    """
    try:
        severity_enum = AlertSeverity(severity) if severity else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    alerts = alert_engine.get_active_alerts(
        datasource_id=datasource_id,
        severity=severity_enum
    )

    return {
        "alerts": [_alert_to_dict(a) for a in alerts],
        "count": len(alerts)
    }


@router.get("/resolved", response_model=Dict[str, Any])
async def get_resolved_alerts(
    datasource_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100
):
    """
    Get resolved alerts (status: resolved or auto_resolved)

    Query Parameters:
    - datasource_id: Filter by datasource
    - severity: Filter by severity (P1, P2, P3)
    - limit: Maximum number of alerts (default 100)

    Returns:
    - alerts: List of resolved alerts with resolution_type tag
    - count: Number of alerts
    """
    try:
        severity_enum = AlertSeverity(severity) if severity else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    # Get alerts with resolved or auto_resolved status
    all_alerts = alert_engine.get_alerts(
        severity=severity_enum,
        datasource_id=datasource_id,
        limit=limit
    )

    # Filter only resolved ones
    resolved_alerts = [
        a for a in all_alerts
        if a.status in [AlertStatus.RESOLVED, AlertStatus.AUTO_RESOLVED]
    ]

    # Add resolution_type tag
    alerts_with_tag = []
    for alert in resolved_alerts:
        alert_dict = _alert_to_dict(alert)
        alert_dict["resolution_type"] = "automatic" if alert.auto_resolved else "manual"
        alerts_with_tag.append(alert_dict)

    return {
        "alerts": alerts_with_tag,
        "count": len(alerts_with_tag)
    }


@router.get("/all", response_model=Dict[str, Any])
async def get_all_alerts(
    datasource_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100
):
    """
    Get all alerts regardless of status

    Query Parameters:
    - datasource_id: Filter by datasource
    - severity: Filter by severity (P1, P2, P3)
    - limit: Maximum number of alerts (default 100)

    Returns:
    - alerts: List of all alerts with resolution_type tag
    - count: Number of alerts
    - summary: Count by status
    """
    try:
        severity_enum = AlertSeverity(severity) if severity else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    all_alerts = alert_engine.get_alerts(
        severity=severity_enum,
        datasource_id=datasource_id,
        limit=limit
    )

    # Add resolution_type tag to all alerts
    alerts_with_tag = []
    for alert in all_alerts:
        alert_dict = _alert_to_dict(alert)
        if alert.status in [AlertStatus.RESOLVED, AlertStatus.AUTO_RESOLVED]:
            alert_dict["resolution_type"] = "automatic" if alert.auto_resolved else "manual"
        else:
            alert_dict["resolution_type"] = None
        alerts_with_tag.append(alert_dict)

    # Calculate summary
    summary = {
        "active": sum(1 for a in all_alerts if a.status == AlertStatus.ACTIVE),
        "acknowledged": sum(1 for a in all_alerts if a.status == AlertStatus.ACKNOWLEDGED),
        "resolved": sum(1 for a in all_alerts if a.status == AlertStatus.RESOLVED),
        "auto_resolved": sum(1 for a in all_alerts if a.status == AlertStatus.AUTO_RESOLVED),
    }

    return {
        "alerts": alerts_with_tag,
        "count": len(alerts_with_tag),
        "summary": summary
    }


@router.get("/history", response_model=Dict[str, Any])
async def get_alert_history(
    datasource_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100
):
    """
    Get alert history

    Query Parameters:
    - datasource_id: Filter by datasource
    - severity: Filter by severity
    - limit: Maximum number of alerts to return (default 100)

    Returns:
    - alerts: List of historical alerts
    - count: Number of alerts returned
    """
    alerts = alert_engine.alert_history

    # Apply filters
    if datasource_id:
        alerts = [a for a in alerts if a.datasource_id == datasource_id]

    if severity:
        try:
            severity_enum = AlertSeverity(severity)
            alerts = [a for a in alerts if a.severity == severity_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    # Sort by triggered_at desc and limit
    alerts = sorted(alerts, key=lambda a: a.triggered_at, reverse=True)[:limit]

    return {
        "alerts": [_alert_to_dict(a) for a in alerts],
        "count": len(alerts)
    }


# ============================================================================
# Alert Rule Management Endpoints (MUST be before /{alert_id})
# ============================================================================

@router.get("/rules", response_model=Dict[str, Any])
async def get_alert_rules():
    """Get all alert rules (default + custom)"""
    return {
        "rules": [
            {
                "id": rule.id,
                "name": rule.name,
                "severity": rule.severity.value,
                "description": rule.description,
                "enabled": rule.enabled,
                "datasource_types": rule.datasource_types,
                "conditions": [
                    {
                        "metric": cond.metric,
                        "operator": cond.operator,
                        "threshold": cond.threshold,
                        "duration_minutes": cond.duration_minutes
                    }
                    for cond in rule.conditions
                ],
                "auto_resolve": rule.auto_resolve,
                "cooldown_minutes": rule.cooldown_minutes
            }
            for rule in alert_engine.rules.values()
        ],
        "count": len(alert_engine.rules)
    }


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str):
    """Get details of a specific alert"""

    # Check active alerts first
    if alert_id in alert_engine.active_alerts:
        return _alert_to_dict(alert_engine.active_alerts[alert_id])

    # Check history
    for alert in alert_engine.alert_history:
        if alert.id == alert_id:
            return _alert_to_dict(alert)

    raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")


# ============================================================================
# Alert Lifecycle Endpoints
# ============================================================================

@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(alert_id: str, request: AcknowledgeRequest):
    """
    Acknowledge an alert

    This marks the alert as acknowledged but keeps it active.
    """
    success = alert_engine.acknowledge_alert(
        alert_id=alert_id,
        user=request.acknowledged_by,
        notes=request.notes
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Alert not found or already resolved: {alert_id}")

    return _alert_to_dict(alert_engine.active_alerts[alert_id])


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(alert_id: str, request: ResolveRequest):
    """
    Manually resolve an alert

    This removes the alert from the active list.
    """
    # Get alert before resolving (for response)
    alert = alert_engine.active_alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")

    alert_dict = _alert_to_dict(alert)

    success = alert_engine.resolve_alert(
        alert_id=alert_id,
        user=request.resolved_by,
        notes=request.notes
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")

    # Update dict with resolved status
    alert_dict["status"] = "resolved"
    alert_dict["resolved_at"] = datetime.now()

    return alert_dict


# ============================================================================
# AI Analysis Endpoints
# ============================================================================

@router.post("/{alert_id}/analyze", response_model=Dict[str, Any])
async def analyze_alert(alert_id: str):
    """
    Get AI-powered analysis and recommendations for an alert

    Returns:
    - root_cause: AI's analysis of why the alert triggered
    - immediate_actions: List of urgent actions to take
    - recommendations: Structured list of fixes with SQL/commands
    - confidence: AI confidence score (0.0 to 1.0)
    """
    # Get alert
    alert = alert_engine.active_alerts.get(alert_id)
    if not alert:
        # Check history
        alert = next((a for a in alert_engine.alert_history if a.id == alert_id), None)
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")

    # Analyze with AI
    analysis = alert_analyzer.analyze(alert)

    return {
        "alert_id": analysis.alert_id,
        "analyzed_at": analysis.analyzed_at.isoformat(),
        "root_cause": analysis.root_cause,
        "confidence": analysis.confidence,
        "immediate_actions": analysis.immediate_actions,
        "recommendations": [
            {
                "type": rec.type,
                "summary": rec.summary,
                "rationale": rec.rationale,
                "sql": rec.sql,
                "command": rec.command,
                "risk_level": rec.risk_level,
                "expected_improvement": rec.expected_improvement,
                "priority": rec.priority
            }
            for rec in analysis.recommendations
        ],
        "estimated_resolution_time": analysis.estimated_resolution_time
    }


# ============================================================================
# Alert Rule Management Endpoints (continued)
# ============================================================================

@router.post("/rules", response_model=Dict[str, Any])
async def create_alert_rule(request: AlertRuleRequest):
    """
    Create a custom alert rule

    Example request:
    {
      "id": "custom_cpu_high",
      "name": "Custom CPU Alert",
      "severity": "P2",
      "description": "CPU > 90% for 5 minutes",
      "conditions": [
        {
          "metric": "cpu_percent",
          "operator": ">",
          "threshold": 90,
          "duration_minutes": 5
        }
      ]
    }
    """
    try:
        severity = AlertSeverity(request.severity)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {request.severity}")

    # Parse conditions
    conditions = []
    for cond_data in request.conditions:
        condition = AlertCondition(
            metric=cond_data["metric"],
            operator=cond_data["operator"],
            threshold=cond_data["threshold"],
            duration_minutes=cond_data.get("duration_minutes", 0)
        )
        conditions.append(condition)

    # Create rule
    rule = AlertRule(
        id=request.id,
        name=request.name,
        severity=severity,
        description=request.description,
        enabled=request.enabled,
        datasource_types=request.datasource_types,
        conditions=conditions,
        auto_resolve=request.auto_resolve,
        cooldown_minutes=request.cooldown_minutes
    )

    alert_engine.add_rule(rule)

    return {
        "message": f"Alert rule created: {rule.id}",
        "rule_id": rule.id
    }


@router.put("/rules/{rule_id}", response_model=Dict[str, Any])
async def update_alert_rule(rule_id: str, request: AlertRuleRequest):
    """Update an existing alert rule"""
    if rule_id not in alert_engine.rules:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")

    # Create updated rule (same logic as create)
    try:
        severity = AlertSeverity(request.severity)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {request.severity}")

    conditions = []
    for cond_data in request.conditions:
        condition = AlertCondition(
            metric=cond_data["metric"],
            operator=cond_data["operator"],
            threshold=cond_data["threshold"],
            duration_minutes=cond_data.get("duration_minutes", 0)
        )
        conditions.append(condition)

    rule = AlertRule(
        id=rule_id,
        name=request.name,
        severity=severity,
        description=request.description,
        enabled=request.enabled,
        datasource_types=request.datasource_types,
        conditions=conditions,
        auto_resolve=request.auto_resolve,
        cooldown_minutes=request.cooldown_minutes
    )

    alert_engine.add_rule(rule)

    return {
        "message": f"Alert rule updated: {rule_id}",
        "rule_id": rule_id
    }


@router.delete("/rules/{rule_id}", response_model=Dict[str, Any])
async def delete_alert_rule(rule_id: str):
    """Delete a custom alert rule (cannot delete default rules)"""
    # Prevent deletion of default rules
    default_rule_ids = [
        "db_down", "write_latency_slo", "read_latency_slo", "replication_lag_critical",
        "disk_space_critical", "backup_policy_breach", "connection_exhaustion", "deadlock_storm",
        "cpu_high", "memory_pressure", "long_running_transaction", "table_bloat_high",
        "slow_checkpoint", "storage_forecast_critical", "cache_hit_degradation", "unused_index"
    ]

    if rule_id in default_rule_ids:
        raise HTTPException(status_code=403, detail=f"Cannot delete default rule: {rule_id}")

    if rule_id not in alert_engine.rules:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")

    alert_engine.remove_rule(rule_id)

    return {
        "message": f"Alert rule deleted: {rule_id}",
        "rule_id": rule_id
    }


# ============================================================================
# Monitoring Control Endpoints
# ============================================================================

@router.post("/monitoring/{ds_id}/start", response_model=Dict[str, Any])
async def start_monitoring(ds_id: str, background_tasks: BackgroundTasks):
    """
    Start monitoring a datasource

    This begins periodic metric collection and alert evaluation.
    """
    if ds_id not in settings.DATASOURCES:
        raise HTTPException(status_code=404, detail=f"Datasource not found: {ds_id}")

    if monitoring_tasks.get(ds_id):
        return {
            "message": f"Monitoring already active for {ds_id}",
            "datasource_id": ds_id,
            "status": "active"
        }

    # Start monitoring using the monitoring service
    from ..services.monitoring_service import get_monitoring_service
    monitoring_service = get_monitoring_service(alert_engine)

    datasource = settings.DATASOURCES[ds_id]
    engine = datasource.get("engine", "postgres")

    await monitoring_service.start_monitoring_datasource(ds_id, engine)
    monitoring_tasks[ds_id] = True

    logger.info(f"Started monitoring for {ds_id}")

    return {
        "message": f"Monitoring started for {ds_id}",
        "datasource_id": ds_id,
        "status": "active"
    }


@router.post("/monitoring/{ds_id}/stop", response_model=Dict[str, Any])
async def stop_monitoring(ds_id: str):
    """Stop monitoring a datasource"""
    if ds_id not in monitoring_tasks:
        raise HTTPException(status_code=404, detail=f"Monitoring not active for {ds_id}")

    # Stop monitoring using the monitoring service
    from ..services.monitoring_service import get_monitoring_service
    monitoring_service = get_monitoring_service(alert_engine)

    await monitoring_service.stop_monitoring_datasource(ds_id)
    monitoring_tasks[ds_id] = False
    logger.info(f"Stopped monitoring for {ds_id}")

    return {
        "message": f"Monitoring stopped for {ds_id}",
        "datasource_id": ds_id,
        "status": "stopped"
    }


@router.get("/monitoring/status", response_model=Dict[str, Any])
async def get_monitoring_status():
    """Get monitoring status for all datasources"""
    return {
        "monitored_datasources": [
            {
                "datasource_id": ds_id,
                "status": "active" if active else "stopped"
            }
            for ds_id, active in monitoring_tasks.items()
        ],
        "total_monitored": sum(1 for active in monitoring_tasks.values() if active)
    }


@router.put("/monitoring/{ds_id}/config", response_model=Dict[str, Any])
async def update_monitoring_config(ds_id: str, request: MonitoringConfigRequest):
    """Update monitoring configuration for a datasource"""
    if ds_id not in settings.DATASOURCES:
        raise HTTPException(status_code=404, detail=f"Datasource not found: {ds_id}")

    # In production, this would update the monitoring task configuration
    logger.info(f"Updated monitoring config for {ds_id}: interval={request.evaluation_interval_seconds}s")

    return {
        "message": f"Monitoring configuration updated for {ds_id}",
        "datasource_id": ds_id,
        "config": {
            "evaluation_interval_seconds": request.evaluation_interval_seconds,
            "enabled_rules": request.enabled_rules or "all"
        }
    }


# ============================================================================
# Manual Metric Evaluation (for testing)
# ============================================================================

@router.post("/evaluate/{ds_id}", response_model=Dict[str, Any])
async def manual_evaluate(ds_id: str):
    """
    Manually trigger alert evaluation for a datasource

    Useful for testing alert rules without waiting for scheduled evaluation.
    """
    if ds_id not in settings.DATASOURCES:
        raise HTTPException(status_code=404, detail=f"Datasource not found: {ds_id}")

    try:
        # Collect metrics
        metrics = collect_all_metrics(ds_id)

        # Evaluate rules
        datasource = settings.DATASOURCES[ds_id]
        engine = datasource["engine"] if isinstance(datasource, dict) else datasource.engine
        alerts = alert_engine.evaluate_all_rules(ds_id, engine, metrics)

        return {
            "message": f"Evaluated {len(alert_engine.rules)} rules for {ds_id}",
            "datasource_id": ds_id,
            "metrics_collected": len(metrics),
            "alerts_triggered": len(alerts),
            "alerts": [_alert_to_dict(a) for a in alerts]
        }

    except Exception as e:
        logger.error(f"Manual evaluation failed for {ds_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


# ============================================================================
# Helper Functions
# ============================================================================

def _alert_to_dict(alert: Alert) -> Dict[str, Any]:
    """Convert Alert object to dictionary"""
    return {
        "id": alert.id,
        "rule_id": alert.rule_id,
        "severity": alert.severity.value,
        "title": alert.title,
        "message": alert.message,
        "datasource_id": alert.datasource_id,
        "datasource_engine": alert.datasource_engine,
        "triggered_at": alert.triggered_at.isoformat(),
        "status": alert.status.value,
        "metric_value": alert.metric_value,
        "threshold": alert.threshold,
        "metadata": alert.metadata,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "acknowledged_by": alert.acknowledged_by,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "auto_resolved": alert.auto_resolved
    }
