"""
Background monitoring service for continuous datasource health monitoring.

This service runs background tasks for each registered datasource, collecting
metrics every 30 seconds and evaluating alert rules.
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from ..services.alert_engine import AlertEngine, Alert, MetricSnapshot
from ..services.registry import get_agent_for
from ..services.metrics_collector import MetricsCollector
from ..config import settings

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Background monitoring service that continuously monitors registered datasources.

    For each datasource, runs a monitoring loop that:
    1. Collects metrics every 30 seconds
    2. Evaluates all alert rules
    3. Enriches alerts with AI analysis
    4. Triggers notifications
    """

    def __init__(self, alert_engine: AlertEngine):
        self.alert_engine = alert_engine
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.metrics_collectors: Dict[str, MetricsCollector] = {}
        self.running = False

    async def start(self):
        """Start monitoring all registered datasources"""
        self.running = True
        logger.info("Starting monitoring service...")

        # Start monitoring for all registered datasources
        for ds_id, ds_config in settings.DATASOURCES.items():
            engine = ds_config.get("engine", "postgres")
            await self.start_monitoring_datasource(ds_id, engine)

        logger.info(f"Monitoring service started for {len(self.monitoring_tasks)} datasources")

    async def stop(self):
        """Stop all monitoring tasks"""
        self.running = False
        logger.info("Stopping monitoring service...")

        # Cancel all monitoring tasks
        for ds_id, task in self.monitoring_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Monitoring task for {ds_id} cancelled")

        self.monitoring_tasks.clear()
        logger.info("Monitoring service stopped")

    async def start_monitoring_datasource(self, datasource_id: str, engine: str):
        """Start monitoring a specific datasource"""
        if datasource_id in self.monitoring_tasks:
            logger.warning(f"Monitoring already active for {datasource_id}")
            return

        logger.info(f"Starting monitoring for datasource: {datasource_id} (engine: {engine})")

        # Create monitoring task
        task = asyncio.create_task(
            self._monitoring_loop(datasource_id, engine)
        )
        self.monitoring_tasks[datasource_id] = task

        # Give the event loop a chance to start the task
        await asyncio.sleep(0)

    async def stop_monitoring_datasource(self, datasource_id: str):
        """Stop monitoring a specific datasource"""
        if datasource_id not in self.monitoring_tasks:
            logger.warning(f"No active monitoring for {datasource_id}")
            return

        logger.info(f"Stopping monitoring for datasource: {datasource_id}")

        task = self.monitoring_tasks.pop(datasource_id)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Monitoring task for {datasource_id} cancelled")

    async def _monitoring_loop(self, datasource_id: str, engine: str):
        """
        Main monitoring loop for a datasource.

        Runs continuously, collecting metrics and evaluating rules every 30 seconds.
        """
        logger.info(f"Monitoring loop started for {datasource_id}")

        # Import notification service here to avoid circular imports
        try:
            logger.info(f"[DEBUG] Importing notification_service for {datasource_id}")
            from ..services.notification_service import get_notification_service
            logger.info(f"[DEBUG] Import successful, creating notification_service for {datasource_id}")
            notification_service = get_notification_service()
            logger.info(f"[DEBUG] Notification service created for {datasource_id}")
        except Exception as e:
            logger.error(f"[DEBUG] FAILED to create notification service for {datasource_id}: {e}", exc_info=True)
            raise

        logger.info(f"[DEBUG] About to enter while loop for {datasource_id}, self.running={self.running}")

        while self.running:
            logger.info(f"[DEBUG] Monitoring iteration START for {datasource_id}")
            try:
                # Collect metrics (returns dict)
                logger.info(f"[DEBUG] About to collect metrics for {datasource_id}")
                metrics_dict = await self._collect_metrics_async(datasource_id)
                logger.info(f"[DEBUG] Metrics collected for {datasource_id}: {metrics_dict}")

                # Evaluate alert rules
                logger.info(f"[DEBUG] About to evaluate alert rules for {datasource_id}")
                triggered_alerts = self.alert_engine.evaluate_all_rules(
                    datasource_id=datasource_id,
                    engine=engine,
                    metrics=metrics_dict
                )
                logger.info(f"[DEBUG] Alert evaluation complete for {datasource_id}: {len(triggered_alerts)} alerts triggered")

                # Process newly triggered alerts
                if triggered_alerts:
                    logger.info(f"ALERT: {len(triggered_alerts)} alerts triggered for {datasource_id}")

                    for alert in triggered_alerts:
                        logger.info(f"[DEBUG] Processing alert: {alert.rule_id} for {datasource_id}")
                        # Add AI analysis to the alert
                        await self._enrich_alert_with_ai(alert, metrics_dict)

                        # Send notifications
                        await notification_service.send_alert_notification(alert)

                        logger.info(f"Alert processed: {alert.title} (severity: {alert.severity})")
                else:
                    logger.info(f"[DEBUG] No alerts triggered for {datasource_id} in this iteration")

                # Sleep for 30 seconds before next iteration
                logger.info(f"[DEBUG] Sleeping 30 seconds for {datasource_id}")
                await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"Error in monitoring loop for {datasource_id}: {e}", exc_info=True)
                # Continue monitoring even if one iteration fails
                await asyncio.sleep(30)

    async def _collect_metrics_async(self, datasource_id: str) -> MetricSnapshot:
        """
        Collect metrics from a datasource asynchronously.

        Wraps the synchronous metric collection in an async executor.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._collect_metrics, datasource_id)

    def _collect_metrics(self, datasource_id: str) -> dict:
        """
        Collect comprehensive metrics from a datasource (synchronous).

        Uses MetricsCollector to gather all 20+ metrics required for the 16 alert rules.
        """
        try:
            # Get datasource config
            ds_config = settings.DATASOURCES.get(datasource_id)
            if not ds_config:
                logger.error(f"Datasource {datasource_id} not found")
                return self._empty_metrics()

            # Get database agent
            agent = get_agent_for(ds_config["engine"], ds_config["dsn"])

            # Get or create metrics collector for this datasource
            if datasource_id not in self.metrics_collectors:
                logger.info(f"Creating MetricsCollector for {datasource_id}")
                self.metrics_collectors[datasource_id] = MetricsCollector(agent)

            collector = self.metrics_collectors[datasource_id]

            # Collect all comprehensive metrics
            metrics = collector.collect_all_metrics(datasource_id)

            logger.info(f"Collected {len(metrics)} metrics for {datasource_id}")
            logger.debug(f"Metrics snapshot: db_up={metrics.get('db_up')}, "
                        f"cpu={metrics.get('cpu_percent')}%, "
                        f"memory={metrics.get('memory_percent')}%, "
                        f"disk_free={metrics.get('disk_free_percent')}%")

            return metrics

        except Exception as e:
            logger.error(f"Failed to collect metrics for {datasource_id}: {e}", exc_info=True)
            return self._empty_metrics()

    def _empty_metrics(self) -> dict:
        """Return empty metrics dict for error cases"""
        return {
            # Basic metrics
            "db_up": 0,
            "connection_count": 0,
            "db_size_mb": 0,
            "table_count": 0,
            "lock_count": 0,
            "blocking_locks": 0,

            # Performance metrics
            "write_p99_latency_ms": 0.0,
            "read_p99_latency_ms": 0.0,
            "deadlocks_per_minute": 0.0,

            # Resource metrics
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "disk_free_percent": 0.0,
            "connection_utilization_percent": 0.0,

            # Replication and backup
            "replay_lag_seconds": 0.0,
            "last_backup_hours_ago": 0.0,

            # Health metrics
            "max_transaction_age_minutes": 0.0,
            "max_table_bloat_percent": 0.0,
            "checkpoint_write_time_seconds": 0.0,
            "storage_runway_days": 9999.0,
            "cache_hit_ratio_percent": 100.0,
            "unused_index_count": 0
        }

    async def _enrich_alert_with_ai(self, alert: Alert, metrics: dict):
        """
        Enrich alert with AI-generated analysis and suggestions.

        Uses the AI suggestion service to analyze the alert context and
        add root cause analysis, immediate actions, and runbook steps.
        """
        try:
            logger.info(f"Enriching alert {alert.id} with AI analysis...")

            # Build context for AI
            context = {
                "alert": {
                    "title": alert.title,
                    "severity": alert.severity,
                    "message": alert.message,
                    "metric_value": alert.metric_value,
                    "threshold": alert.threshold
                },
                "metrics": metrics
            }

            # Generate AI analysis prompt
            prompt = f"""Analyze this database alert and provide structured guidance:

Alert: {alert.title}
Severity: {alert.severity}
Message: {alert.message}
Current Value: {alert.metric_value}
Threshold: {alert.threshold}

Database Status:
- Connection Count: {metrics.get('connection_count', 0)}
- Database Size: {metrics.get('db_size_mb', 0)} MB
- Lock Count: {metrics.get('lock_count', 0)}
- Blocking Locks: {metrics.get('blocking_locks', 0)}
- Database Up: {metrics.get('db_up', 0)}

Provide a JSON response with:
1. root_cause: Brief explanation of likely root cause (2-3 sentences)
2. immediate_actions: List of 2-4 immediate actions to take
3. runbook_steps: Detailed step-by-step remediation guide (4-6 steps)
4. risk_level: "low", "medium", or "high"
5. estimated_impact: Brief description of business impact

Format as valid JSON.
"""

            # Get AI suggestions (using existing AI client)
            from ..services.ai_client import LLMClient
            llm_client = LLMClient()

            ai_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: llm_client.chat(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a database reliability expert. Provide clear, actionable alert analysis.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    json_response=True,
                    max_tokens=1000,
                ),
            )

            if ai_response:
                # Store AI analysis in alert metadata
                if not alert.metadata:
                    alert.metadata = {}

                alert.metadata["ai_analysis"] = ai_response
                logger.info(f"✅ AI analysis added to alert {alert.id}")
            else:
                logger.warning(f"No AI analysis generated for alert {alert.id}")

        except Exception as e:
            logger.error(f"Failed to enrich alert with AI: {e}", exc_info=True)
            # Don't fail the alert if AI enrichment fails
            if not alert.metadata:
                alert.metadata = {}
            alert.metadata["ai_analysis"] = {
                "error": "AI analysis failed",
                "root_cause": "Unable to generate AI analysis",
                "immediate_actions": ["Check logs for details", "Review alert manually"],
                "risk_level": "unknown"
            }


# Singleton instance
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service(alert_engine: Optional[AlertEngine] = None) -> MonitoringService:
    """Get or create the monitoring service singleton"""
    global _monitoring_service

    if _monitoring_service is None:
        if alert_engine is None:
            from routers.alerts import alert_engine as default_engine
            alert_engine = default_engine
        _monitoring_service = MonitoringService(alert_engine)

    return _monitoring_service
