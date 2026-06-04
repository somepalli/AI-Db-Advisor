"""
Alert Engine - Rule-based monitoring and alert triggering system

This module implements the core alert engine that:
1. Evaluates monitoring rules against collected metrics
2. Triggers alerts when thresholds are breached
3. Manages alert lifecycle (creation, acknowledgment, resolution)
4. Implements hysteresis to prevent alert flapping
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Literal
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels matching DBA priority system"""
    P1 = "P1"  # Critical - Page immediately
    P2 = "P2"  # High - Act within an hour
    P3 = "P3"  # Medium - Hygiene/Capacity planning


class AlertStatus(str, Enum):
    """Alert lifecycle status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    AUTO_RESOLVED = "auto_resolved"


@dataclass
class MetricSnapshot:
    """Single metric observation at a point in time"""
    timestamp: datetime
    metric: str
    value: Any
    datasource_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertCondition:
    """Single condition in an alert rule"""
    metric: str
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    threshold: Any
    duration_minutes: int = 0  # Sustained breach required

    def evaluate(self, value: Any) -> bool:
        """Evaluate condition against a value"""
        try:
            if self.operator == "<":
                return value < self.threshold
            elif self.operator == "<=":
                return value <= self.threshold
            elif self.operator == ">":
                return value > self.threshold
            elif self.operator == ">=":
                return value >= self.threshold
            elif self.operator == "==":
                return value == self.threshold
            elif self.operator == "!=":
                return value != self.threshold
            else:
                logger.warning(f"Unknown operator: {self.operator}")
                return False
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False


@dataclass
class AlertRule:
    """Alert rule definition"""
    id: str
    name: str
    severity: AlertSeverity
    description: str
    enabled: bool = True
    datasource_types: List[str] = field(default_factory=lambda: ["*"])  # "*" = all types
    conditions: List[AlertCondition] = field(default_factory=list)
    notification_channels: List[str] = field(default_factory=lambda: ["websocket"])
    auto_resolve: bool = True
    cooldown_minutes: int = 15  # Min time between repeat alerts
    ai_analysis_enabled: bool = True
    evaluation_interval_seconds: int = 30

    def matches_datasource(self, engine: str) -> bool:
        """Check if rule applies to datasource engine type"""
        wildcards = {"*", "all"}
        return bool(wildcards.intersection(self.datasource_types)) or engine in self.datasource_types


@dataclass
class Alert:
    """Alert instance"""
    id: str
    rule_id: str
    severity: AlertSeverity
    title: str
    message: str
    datasource_id: str
    datasource_engine: str
    triggered_at: datetime
    status: AlertStatus = AlertStatus.ACTIVE
    metric_value: Any = None
    threshold: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    ack_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    auto_resolved: bool = False


class AlertEngine:
    """
    Core alert engine for evaluating rules and triggering alerts

    Usage:
        engine = AlertEngine()
        metrics = collect_metrics("pg_university")
        alerts = engine.evaluate_all_rules("pg_university", "postgres", metrics)
    """

    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.metric_history: Dict[str, List[MetricSnapshot]] = {}
        self._load_default_rules()

    def _load_default_rules(self):
        """Load default DBA alert rules"""

        # P1 Critical Rules
        self.add_rule(AlertRule(
            id="db_down",
            name="Primary Database Down",
            severity=AlertSeverity.P1,
            description="Database instance is not responding",
            datasource_types=["*"],
            conditions=[
                AlertCondition(metric="db_up", operator="==", threshold=0, duration_minutes=0)
            ],
            cooldown_minutes=5
        ))

        self.add_rule(AlertRule(
            id="write_latency_slo",
            name="Write Latency SLO Breach",
            severity=AlertSeverity.P1,
            description="Write P99 latency exceeds 250ms SLO",
            datasource_types=["postgres", "mysql", "sqlserver", "oracle"],
            conditions=[
                AlertCondition(metric="write_p99_latency_ms", operator=">", threshold=250, duration_minutes=5)
            ]
        ))

        self.add_rule(AlertRule(
            id="read_latency_slo",
            name="Read Latency SLO Breach",
            severity=AlertSeverity.P1,
            description="Read P99 latency exceeds 250ms SLO",
            datasource_types=["postgres", "mysql", "sqlserver", "oracle"],
            conditions=[
                AlertCondition(metric="read_p99_latency_ms", operator=">", threshold=250, duration_minutes=5)
            ]
        ))

        self.add_rule(AlertRule(
            id="replication_lag_critical",
            name="Replication Lag Critical",
            severity=AlertSeverity.P1,
            description="Standby replica lag exceeds RPO (300 seconds)",
            datasource_types=["postgres", "mysql"],
            conditions=[
                AlertCondition(metric="replay_lag_seconds", operator=">", threshold=300, duration_minutes=2)
            ]
        ))

        self.add_rule(AlertRule(
            id="disk_space_critical",
            name="Disk Space Critical",
            severity=AlertSeverity.P1,
            description="Disk free space below 10% or < 30 min runway",
            datasource_types=["*"],
            conditions=[
                AlertCondition(metric="disk_free_percent", operator="<", threshold=10, duration_minutes=0)
            ],
            cooldown_minutes=30
        ))

        self.add_rule(AlertRule(
            id="backup_policy_breach",
            name="Backup Policy Breach",
            severity=AlertSeverity.P1,
            description="Last successful backup exceeds policy (24 hours)",
            datasource_types=["*"],
            conditions=[
                AlertCondition(metric="last_backup_hours_ago", operator=">", threshold=24, duration_minutes=0)
            ],
            cooldown_minutes=60
        ))

        self.add_rule(AlertRule(
            id="connection_exhaustion",
            name="Connection Pool Exhaustion",
            severity=AlertSeverity.P1,
            description="Active connections >= 98% of max_connections",
            datasource_types=["postgres", "mysql", "sqlserver"],
            conditions=[
                AlertCondition(metric="connection_utilization_percent", operator=">=", threshold=98, duration_minutes=3)
            ]
        ))

        self.add_rule(AlertRule(
            id="deadlock_storm",
            name="Deadlock Storm",
            severity=AlertSeverity.P1,
            description="Deadlocks exceeding normal rate",
            datasource_types=["postgres", "mysql", "sqlserver"],
            conditions=[
                AlertCondition(metric="deadlocks_per_minute", operator=">", threshold=10, duration_minutes=5)
            ]
        ))

        # P2 High Priority Rules
        self.add_rule(AlertRule(
            id="cpu_high",
            name="CPU Utilization High",
            severity=AlertSeverity.P2,
            description="CPU sustained above 85% for 10 minutes",
            datasource_types=["*"],
            conditions=[
                AlertCondition(metric="cpu_percent", operator=">", threshold=85, duration_minutes=10)
            ]
        ))

        self.add_rule(AlertRule(
            id="memory_pressure",
            name="Memory Pressure",
            severity=AlertSeverity.P2,
            description="High memory usage or OS swapping",
            datasource_types=["*"],
            conditions=[
                AlertCondition(metric="memory_percent", operator=">", threshold=90, duration_minutes=10)
            ]
        ))

        self.add_rule(AlertRule(
            id="long_running_transaction",
            name="Long Running Transaction",
            severity=AlertSeverity.P2,
            description="Transaction open for > 30 minutes",
            datasource_types=["postgres", "mysql", "sqlserver"],
            conditions=[
                AlertCondition(metric="max_transaction_age_minutes", operator=">", threshold=30, duration_minutes=0)
            ]
        ))

        self.add_rule(AlertRule(
            id="table_bloat_high",
            name="Table Bloat High",
            severity=AlertSeverity.P2,
            description="Table bloat exceeds 30%",
            datasource_types=["postgres"],
            conditions=[
                AlertCondition(metric="max_table_bloat_percent", operator=">", threshold=30, duration_minutes=0)
            ],
            cooldown_minutes=360  # 6 hours - bloat changes slowly
        ))

        self.add_rule(AlertRule(
            id="slow_checkpoint",
            name="Slow Checkpoint",
            severity=AlertSeverity.P2,
            description="Checkpoint write/sync time excessive",
            datasource_types=["postgres"],
            conditions=[
                AlertCondition(metric="checkpoint_write_time_seconds", operator=">", threshold=30, duration_minutes=0)
            ]
        ))

        # P3 Medium Priority Rules
        self.add_rule(AlertRule(
            id="storage_forecast_critical",
            name="Storage Exhaustion Forecast",
            severity=AlertSeverity.P3,
            description="Storage projected to fill in < 14 days",
            datasource_types=["*"],
            conditions=[
                AlertCondition(metric="storage_runway_days", operator="<", threshold=14, duration_minutes=0)
            ],
            cooldown_minutes=1440  # 24 hours
        ))

        self.add_rule(AlertRule(
            id="cache_hit_degradation",
            name="Cache Hit Ratio Degradation",
            severity=AlertSeverity.P3,
            description="Buffer cache hit ratio below 95%",
            datasource_types=["postgres", "mysql"],
            conditions=[
                AlertCondition(metric="cache_hit_ratio_percent", operator="<", threshold=95, duration_minutes=30)
            ]
        ))

        self.add_rule(AlertRule(
            id="unused_index",
            name="Unused Index Detected",
            severity=AlertSeverity.P3,
            description="Index not used in 7+ days",
            datasource_types=["postgres", "mysql"],
            conditions=[
                AlertCondition(metric="unused_index_count", operator=">", threshold=0, duration_minutes=0)
            ],
            cooldown_minutes=10080  # 7 days
        ))

    def add_rule(self, rule: AlertRule):
        """Add or update an alert rule"""
        self.rules[rule.id] = rule
        logger.info(f"Alert rule added: {rule.id} ({rule.name})")

    def remove_rule(self, rule_id: str):
        """Remove an alert rule"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Alert rule removed: {rule_id}")

    def record_metric(self, snapshot: MetricSnapshot):
        """Record a metric snapshot for evaluation"""
        key = f"{snapshot.datasource_id}:{snapshot.metric}"

        if key not in self.metric_history:
            self.metric_history[key] = []

        self.metric_history[key].append(snapshot)

        # Keep only last 24 hours of history
        cutoff = datetime.now() - timedelta(hours=24)
        self.metric_history[key] = [
            s for s in self.metric_history[key]
            if s.timestamp >= cutoff
        ]

    def evaluate_all_rules(
        self,
        datasource_id: str,
        engine: str,
        metrics: Dict[str, Any]
    ) -> List[Alert]:
        """
        Evaluate all applicable rules against current metrics

        Args:
            datasource_id: Datasource identifier
            engine: Database engine type (postgres, mysql, etc.)
            metrics: Dictionary of metric_name -> value

        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        now = datetime.now()

        # Record metrics in history
        for metric_name, value in metrics.items():
            snapshot = MetricSnapshot(
                timestamp=now,
                metric=metric_name,
                value=value,
                datasource_id=datasource_id
            )
            self.record_metric(snapshot)

        # Evaluate each rule
        for rule in self.rules.values():
            if not rule.enabled:
                continue

            if not rule.matches_datasource(engine):
                continue

            # Check cooldown period
            if self._in_cooldown(rule.id, datasource_id):
                continue

            # Evaluate all conditions
            alert = self._evaluate_rule(rule, datasource_id, engine, metrics)

            if alert:
                triggered_alerts.append(alert)
                self.active_alerts[alert.id] = alert
                self.alert_history.append(alert)
                logger.warning(
                    f"Alert triggered: {alert.title} "
                    f"[{alert.severity}] for {datasource_id}"
                )

        # Auto-resolve alerts if conditions clear
        if any(rule.auto_resolve for rule in self.rules.values()):
            self._auto_resolve_alerts(datasource_id, metrics)

        return triggered_alerts

    def _evaluate_rule(
        self,
        rule: AlertRule,
        datasource_id: str,
        engine: str,
        metrics: Dict[str, Any]
    ) -> Optional[Alert]:
        """Evaluate a single rule"""

        for condition in rule.conditions:
            metric_value = metrics.get(condition.metric)

            if metric_value is None:
                # Metric not available - skip this rule
                return None

            # Check if sustained duration is required
            if condition.duration_minutes > 0:
                if not self._check_sustained_breach(
                    datasource_id,
                    condition,
                    condition.duration_minutes
                ):
                    return None
            else:
                # Instant evaluation
                if not condition.evaluate(metric_value):
                    return None

        # All conditions met - trigger alert
        alert_id = f"{rule.id}:{datasource_id}:{datetime.now().timestamp()}"

        # Get first condition for message (simplified)
        primary_condition = rule.conditions[0]
        metric_value = metrics.get(primary_condition.metric)

        alert = Alert(
            id=alert_id,
            rule_id=rule.id,
            severity=rule.severity,
            title=rule.name,
            message=self._build_alert_message(rule, metrics),
            datasource_id=datasource_id,
            datasource_engine=engine,
            triggered_at=datetime.now(),
            metric_value=metric_value,
            threshold=primary_condition.threshold,
            metadata={
                "rule": rule.id,
                "conditions": [
                    {"metric": c.metric, "value": metrics.get(c.metric), "threshold": c.threshold}
                    for c in rule.conditions
                ]
            }
        )

        return alert

    def _check_sustained_breach(
        self,
        datasource_id: str,
        condition: AlertCondition,
        duration_minutes: int
    ) -> bool:
        """Check if the condition has been breached continuously for `duration_minutes`.

        We look at the most recent *contiguous* run of breaching snapshots (ending at
        the latest snapshot) and check that it spans at least `duration_minutes`.
        """
        key = f"{datasource_id}:{condition.metric}"

        snapshots = self.metric_history.get(key)
        if not snapshots:
            return False

        # Oldest -> newest
        ordered = sorted(snapshots, key=lambda s: s.timestamp)

        # Walk backwards collecting the contiguous tail of breaching snapshots.
        breaching_tail = []
        for snapshot in reversed(ordered):
            if condition.evaluate(snapshot.value):
                breaching_tail.append(snapshot)
            else:
                break

        if not breaching_tail:
            return False

        oldest_breaching = min(breaching_tail, key=lambda s: s.timestamp)
        time_span_minutes = (datetime.now() - oldest_breaching.timestamp).total_seconds() / 60

        return time_span_minutes >= duration_minutes

    def _build_alert_message(self, rule: AlertRule, metrics: Dict[str, Any]) -> str:
        """Build human-readable alert message"""
        parts = [rule.description]

        for condition in rule.conditions:
            value = metrics.get(condition.metric)
            if value is not None:
                parts.append(
                    f"{condition.metric}={value} "
                    f"(threshold: {condition.operator} {condition.threshold})"
                )

        return ". ".join(parts)

    def _in_cooldown(self, rule_id: str, datasource_id: str) -> bool:
        """Check if alert is in cooldown period"""
        rule = self.rules.get(rule_id)
        if not rule or rule.cooldown_minutes == 0:
            return False

        # Find most recent alert for this rule+datasource
        recent_alerts = [
            a for a in reversed(self.alert_history)
            if a.rule_id == rule_id and a.datasource_id == datasource_id
        ]

        if not recent_alerts:
            return False

        last_alert = recent_alerts[0]
        cooldown_end = last_alert.triggered_at + timedelta(minutes=rule.cooldown_minutes)

        return datetime.now() < cooldown_end

    def _auto_resolve_alerts(self, datasource_id: str, metrics: Dict[str, Any]):
        """Auto-resolve alerts when conditions clear"""
        for alert_id, alert in list(self.active_alerts.items()):
            if alert.datasource_id != datasource_id:
                continue

            # Auto-resolve alerts that are still open (active or acknowledged).
            if alert.status not in (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED):
                continue

            rule = self.rules.get(alert.rule_id)
            if not rule or not rule.auto_resolve:
                continue

            # Only auto-resolve when the data positively confirms every condition has
            # cleared. A missing metric is treated as "unknown" (not clear) so we don't
            # silently resolve an alert — especially an acknowledged, human-owned one —
            # on absent or transient data.
            all_clear = True
            for condition in rule.conditions:
                value = metrics.get(condition.metric)
                if value is None or condition.evaluate(value):
                    all_clear = False
                    break

            if all_clear:
                alert.status = AlertStatus.AUTO_RESOLVED
                alert.resolved_at = datetime.now()
                alert.auto_resolved = True
                del self.active_alerts[alert_id]
                logger.info(f"Alert auto-resolved: {alert.title} for {datasource_id}")

    def get_active_alerts(
        self,
        datasource_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """Get currently active alerts with optional filters"""
        alerts = list(self.active_alerts.values())

        if datasource_id:
            alerts = [a for a in alerts if a.datasource_id == datasource_id]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        # Sort by severity (P1 first) then timestamp
        severity_order = {"P1": 0, "P2": 1, "P3": 2}
        alerts.sort(key=lambda a: (severity_order.get(a.severity.value, 999), a.triggered_at))

        return alerts

    def acknowledge_alert(self, alert_id: str, user: str, notes: str = "") -> bool:
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now()
            alert.acknowledged_by = user
            alert.ack_note = notes or None
            if notes:
                alert.metadata["acknowledgment_notes"] = notes
            logger.info(f"Alert acknowledged: {alert_id} by {user}")
            return True
        return False

    def resolve_alert(self, alert_id: str, user: str = None, notes: str = "") -> bool:
        """Manually resolve an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            alert.resolved_by = user
            alert.resolution_note = notes or None
            if notes:
                alert.metadata["resolution_notes"] = notes
            del self.active_alerts[alert_id]
            logger.info(f"Alert resolved: {alert_id}" + (f" by {user}" if user else ""))
            return True
        return False

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Get a single alert by ID

        Args:
            alert_id: Alert identifier

        Returns:
            Alert if found, None otherwise
        """
        # Check active alerts first
        if alert_id in self.active_alerts:
            return self.active_alerts[alert_id]

        # Check history
        for alert in reversed(self.alert_history):
            if alert.id == alert_id:
                return alert

        return None

    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        status: Optional[AlertStatus] = None,
        datasource_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Alert]:
        """
        Get filtered list of alerts with pagination

        Args:
            severity: Filter by severity (P1/P2/P3)
            status: Filter by status (active/acknowledged/resolved/auto_resolved)
            datasource_id: Filter by datasource
            limit: Maximum number of alerts to return
            offset: Number of alerts to skip (for pagination)

        Returns:
            List of alerts matching filters
        """
        # Combine active and historical alerts
        all_alerts = list(self.active_alerts.values()) + self.alert_history

        # Remove duplicates (active alerts might also be in history)
        seen = set()
        unique_alerts = []
        for alert in all_alerts:
            if alert.id not in seen:
                seen.add(alert.id)
                unique_alerts.append(alert)

        # Apply filters
        filtered = unique_alerts

        if severity:
            filtered = [a for a in filtered if a.severity == severity]

        if status:
            filtered = [a for a in filtered if a.status == status]

        if datasource_id:
            filtered = [a for a in filtered if a.datasource_id == datasource_id]

        # Sort by triggered time (newest first)
        filtered.sort(key=lambda a: a.triggered_at, reverse=True)

        # Apply pagination
        paginated = filtered[offset:offset + limit]

        return paginated

    def _record_metric_snapshot(
        self,
        datasource_id: str,
        metric: str,
        value: Any,
        timestamp: Optional[datetime] = None
    ):
        """
        Record a metric snapshot for sustained threshold detection

        Args:
            datasource_id: Datasource identifier
            metric: Metric name
            value: Metric value
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        snapshot = MetricSnapshot(
            timestamp=timestamp,
            metric=metric,
            value=value,
            datasource_id=datasource_id
        )

        self.record_metric(snapshot)


def calculate_runway(
    free_space: float,
    daily_growth: float,
    unit: Literal["days", "hours"] = "days"
) -> float:
    """
    Calculate runway until resource exhaustion

    Args:
        free_space: Current free space (GB, %, etc.)
        daily_growth: Average daily growth rate (same units)
        unit: Return runway in days or hours

    Returns:
        Runway in specified unit
    """
    if daily_growth <= 0:
        return float('inf')

    runway_days = free_space / daily_growth

    if unit == "hours":
        return runway_days * 24

    return runway_days
