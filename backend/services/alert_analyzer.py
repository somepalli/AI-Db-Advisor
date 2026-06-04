"""
Alert Analyzer - AI-powered alert analysis and recommendation engine

This module analyzes alerts and provides:
1. Root cause analysis
2. Immediate remediation actions
3. Long-term optimization recommendations
4. Expected impact/improvement estimates
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import json

from .ai_client import LLMClient
from .alert_engine import Alert, AlertSeverity
from ..deps import resolve_agent
from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class AlertRecommendation:
    """Single recommendation for resolving an alert"""
    type: str  # "config", "index", "query", "action", "note"
    summary: str
    rationale: str
    sql: Optional[str] = None
    command: Optional[str] = None
    risk_level: str = "low"  # "low", "medium", "high"
    expected_improvement: Optional[str] = None
    priority: int = 1  # 1 (highest) to 5 (lowest)


@dataclass
class AlertAnalysis:
    """Complete AI analysis of an alert"""
    alert_id: str
    analyzed_at: datetime
    root_cause: str
    immediate_actions: List[str]
    recommendations: List[AlertRecommendation]
    related_metrics: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # 0.0 to 1.0
    estimated_resolution_time: Optional[str] = None


class AlertAnalyzer:
    """
    AI-powered alert analyzer that provides intelligent recommendations

    Usage:
        analyzer = AlertAnalyzer()
        analysis = analyzer.analyze(alert)
        print(analysis.root_cause)
        for rec in analysis.recommendations:
            print(rec.summary, rec.sql)
    """

    def __init__(self, ai_client: Optional[LLMClient] = None):
        self.ai_client = ai_client or LLMClient()

    def analyze(self, alert: Alert) -> AlertAnalysis:
        """
        Analyze an alert and generate recommendations

        Args:
            alert: Alert instance to analyze

        Returns:
            AlertAnalysis with root cause, actions, and recommendations
        """
        logger.info(f"Analyzing alert: {alert.id} ({alert.title})")

        try:
            # Build context for AI analysis
            context = self._build_context(alert)

            # Generate AI analysis
            ai_response = self._call_ai_analyzer(alert, context)

            # Parse and structure the response
            analysis = self._parse_ai_response(alert, ai_response)

            logger.info(f"Alert analysis complete: {alert.id} - {len(analysis.recommendations)} recommendations")
            return analysis

        except Exception as e:
            logger.error(f"Alert analysis failed for {alert.id}: {e}")
            # Return fallback analysis
            return self._fallback_analysis(alert)

    def _build_context(self, alert: Alert) -> Dict[str, Any]:
        """Build comprehensive context for AI analysis"""
        context = {
            "alert": {
                "id": alert.id,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "datasource_id": alert.datasource_id,
                "datasource_engine": alert.datasource_engine,
                "triggered_at": alert.triggered_at.isoformat(),
                "metric_value": alert.metric_value,
                "threshold": alert.threshold,
                "metadata": alert.metadata
            }
        }

        # Get database-specific context
        try:
            agent = resolve_agent(alert.datasource_id)

            # Get current database stats
            context["database"] = {
                "engine": alert.datasource_engine,
                "stats": agent.stats(),
            }

            # For specific alert types, gather more context
            if "disk" in alert.title.lower() or "storage" in alert.title.lower():
                # Get table sizes
                schema = agent.get_schema()
                context["tables"] = list(schema.get("tables", {}).keys())[:10]

            elif "latency" in alert.title.lower() or "slow" in alert.title.lower():
                # Get top queries
                context["top_queries"] = agent.get_top_queries(limit=5)

            elif "replication" in alert.title.lower():
                # Get locks that might be blocking replication
                context["locks"] = agent.locks()

            elif "connection" in alert.title.lower():
                # Get current connection count
                stats = agent.stats()
                context["connection_info"] = {
                    "active_backends": stats.get("active_backends", 0),
                    "max_connections": stats.get("max_connections", 100)
                }

        except Exception as e:
            logger.warning(f"Failed to gather database context for {alert.datasource_id}: {e}")
            context["database"] = {"engine": alert.datasource_engine, "error": str(e)}

        return context

    def _call_ai_analyzer(self, alert: Alert, context: Dict[str, Any]) -> Dict[str, Any]:
        """Call AI to analyze the alert"""

        system_prompt = """You are an expert Database Administrator analyzing a critical database alert.

Your task is to analyze the alert and provide:
1. Root cause analysis
2. Immediate actions to mitigate the issue
3. Long-term recommendations to prevent recurrence

Format your response as JSON with this structure:
{
  "root_cause": "Brief explanation of why this alert triggered",
  "confidence": 0.85,
  "immediate_actions": [
    "Action 1 to take right now",
    "Action 2 to take right now",
    "Action 3 to take right now"
  ],
  "recommendations": [
    {
      "type": "config|index|query|action|note",
      "summary": "Brief description of the recommendation",
      "rationale": "Why this will help",
      "sql": "SQL statement if applicable (or null)",
      "command": "Shell command if applicable (or null)",
      "risk_level": "low|medium|high",
      "expected_improvement": "Expected impact (e.g., '30% reduction in latency')",
      "priority": 1
    }
  ],
  "estimated_resolution_time": "5 minutes|1 hour|1 day|etc"
}

Guidelines:
- Be specific and actionable
- Include SQL statements where relevant
- Prioritize immediate safety (prevent data loss, restore service)
- Consider the database engine ({engine})
- Reference actual metric values from the alert
- Provide realistic time estimates
"""

        user_prompt = f"""Analyze this database alert:

**Alert Details:**
- Severity: {alert.severity.value}
- Title: {alert.title}
- Message: {alert.message}
- Database: {alert.datasource_engine}
- Metric Value: {alert.metric_value}
- Threshold: {alert.threshold}
- Triggered: {alert.triggered_at.isoformat()}

**Database Context:**
{json.dumps(context.get('database', {}), indent=2)}

**Additional Context:**
{json.dumps({k: v for k, v in context.items() if k != 'alert' and k != 'database'}, indent=2)}

Provide a comprehensive analysis with specific, actionable recommendations."""

        messages = [
            {"role": "system", "content": system_prompt.format(engine=alert.datasource_engine)},
            {"role": "user", "content": user_prompt}
        ]

        logger.debug(f"Calling AI with prompt length: {len(user_prompt)} chars")

        response = self.ai_client.chat(messages, format="json", max_tokens=2000)

        return response

    def _parse_ai_response(self, alert: Alert, ai_response: Dict[str, Any]) -> AlertAnalysis:
        """Parse AI response into structured AlertAnalysis"""

        # Extract recommendations
        recommendations = []
        for rec_data in ai_response.get("recommendations", []):
            rec = AlertRecommendation(
                type=rec_data.get("type", "note"),
                summary=rec_data.get("summary", ""),
                rationale=rec_data.get("rationale", ""),
                sql=rec_data.get("sql"),
                command=rec_data.get("command"),
                risk_level=rec_data.get("risk_level", "low"),
                expected_improvement=rec_data.get("expected_improvement"),
                priority=rec_data.get("priority", 1)
            )
            recommendations.append(rec)

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority)

        analysis = AlertAnalysis(
            alert_id=alert.id,
            analyzed_at=datetime.now(),
            root_cause=ai_response.get("root_cause", "Unable to determine root cause"),
            immediate_actions=ai_response.get("immediate_actions", []),
            recommendations=recommendations,
            confidence=ai_response.get("confidence", 0.0),
            estimated_resolution_time=ai_response.get("estimated_resolution_time")
        )

        return analysis

    def _fallback_analysis(self, alert: Alert) -> AlertAnalysis:
        """Generate fallback analysis when AI fails"""

        # Rule-based fallback based on alert type
        root_cause = "Alert triggered based on threshold breach"
        immediate_actions = ["Investigate the alert in the database", "Check recent changes"]
        recommendations = []

        if "disk" in alert.title.lower():
            root_cause = f"Disk space is critically low at {alert.metric_value}%"
            immediate_actions = [
                "Check disk usage with df -h",
                "Identify large files/tables consuming space",
                "Consider emergency cleanup of old logs/backups"
            ]
            recommendations.append(AlertRecommendation(
                type="action",
                summary="Free up disk space immediately",
                rationale="Prevent database shutdown due to out-of-space errors",
                command="du -sh /var/lib/postgresql/* | sort -h",
                risk_level="low",
                priority=1
            ))

        elif "latency" in alert.title.lower():
            root_cause = f"Query latency exceeded SLO: {alert.metric_value}ms > {alert.threshold}ms"
            immediate_actions = [
                "Check current query load",
                "Review pg_stat_statements for slow queries",
                "Check for blocking locks"
            ]
            recommendations.append(AlertRecommendation(
                type="query",
                summary="Analyze slow queries",
                rationale="Identify queries causing latency spikes",
                sql="SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;",
                risk_level="low",
                priority=1
            ))

        elif "replication" in alert.title.lower():
            root_cause = f"Replication lag exceeded RPO: {alert.metric_value}s > {alert.threshold}s"
            immediate_actions = [
                "Check standby server resources (CPU, I/O)",
                "Verify network connectivity to standby",
                "Review WAL shipping status"
            ]

        elif "connection" in alert.title.lower():
            root_cause = f"Connection utilization critical: {alert.metric_value}%"
            immediate_actions = [
                "Review active connections",
                "Identify long-running sessions",
                "Consider increasing max_connections (with caution)"
            ]

        return AlertAnalysis(
            alert_id=alert.id,
            analyzed_at=datetime.now(),
            root_cause=root_cause,
            immediate_actions=immediate_actions,
            recommendations=recommendations,
            confidence=0.5,  # Low confidence for rule-based fallback
            estimated_resolution_time="15-30 minutes"
        )


def build_ai_context(alert: Alert, include_schema: bool = False) -> str:
    """
    Build AI context string for alert analysis

    Args:
        alert: Alert to analyze
        include_schema: Whether to include database schema

    Returns:
        Formatted context string
    """
    lines = [
        f"Alert: {alert.title}",
        f"Severity: {alert.severity.value}",
        f"Database: {alert.datasource_engine} ({alert.datasource_id})",
        f"Message: {alert.message}",
        f"Metric: {alert.metric_value} (threshold: {alert.threshold})",
        f"Triggered: {alert.triggered_at.isoformat()}"
    ]

    if alert.metadata:
        lines.append(f"Metadata: {json.dumps(alert.metadata, indent=2)}")

    if include_schema:
        try:
            agent = resolve_agent(alert.datasource_id)
            schema = agent.get_schema()
            lines.append("\nDatabase Schema:")
            for table_name in list(schema.get("tables", {}).keys())[:5]:
                lines.append(f"  - {table_name}")
        except Exception as e:
            logger.warning(f"Failed to include schema: {e}")

    return "\n".join(lines)
