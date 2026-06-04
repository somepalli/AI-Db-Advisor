"""
Unit tests for Alert Engine

Tests alert rule evaluation, threshold detection, and alert lifecycle management
"""

import pytest
from datetime import datetime, timedelta
from backend.services.alert_engine import (
    AlertEngine,
    AlertRule,
    AlertCondition,
    AlertSeverity,
    AlertStatus,
    MetricSnapshot,
    calculate_runway
)


class TestAlertConditions:
    """Test alert condition evaluation"""

    def test_greater_than_condition(self):
        """Test > operator"""
        condition = AlertCondition(
            metric="cpu_percent",
            operator=">",
            threshold=85.0
        )

        assert condition.evaluate(90.0) is True
        assert condition.evaluate(85.0) is False
        assert condition.evaluate(80.0) is False

    def test_greater_equal_condition(self):
        """Test >= operator"""
        condition = AlertCondition(
            metric="cpu_percent",
            operator=">=",
            threshold=85.0
        )

        assert condition.evaluate(90.0) is True
        assert condition.evaluate(85.0) is True
        assert condition.evaluate(80.0) is False

    def test_less_than_condition(self):
        """Test < operator"""
        condition = AlertCondition(
            metric="disk_free_percent",
            operator="<",
            threshold=10.0
        )

        assert condition.evaluate(5.0) is True
        assert condition.evaluate(10.0) is False
        assert condition.evaluate(15.0) is False

    def test_equality_condition(self):
        """Test == operator"""
        condition = AlertCondition(
            metric="db_up",
            operator="==",
            threshold=0
        )

        assert condition.evaluate(0) is True
        assert condition.evaluate(1) is False

    def test_not_equal_condition(self):
        """Test != operator"""
        condition = AlertCondition(
            metric="sync_state",
            operator="!=",
            threshold="sync"
        )

        assert condition.evaluate("async") is True
        assert condition.evaluate("sync") is False


class TestAlertRuleEvaluation:
    """Test alert rule threshold evaluation"""

    def test_simple_threshold_breach(self):
        """Test basic threshold comparison"""
        engine = AlertEngine()

        rule = AlertRule(
            id="cpu_high_test",
            name="CPU High",
            severity=AlertSeverity.P2,
            description="CPU > 85%",
            conditions=[
                AlertCondition(metric="cpu_percent", operator=">", threshold=85.0, duration_minutes=0)
            ]
        )

        engine.add_rule(rule)

        # Trigger alert
        metrics = {"cpu_percent": 92.0}
        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        # Filter to our specific test rule (default rules may also trigger)
        test_alerts = [a for a in alerts if a.rule_id == "cpu_high_test"]
        assert len(test_alerts) == 1
        assert test_alerts[0].severity == AlertSeverity.P2
        assert test_alerts[0].metric_value == 92.0

    def test_threshold_not_breached(self):
        """Test no alert when threshold not breached"""
        engine = AlertEngine()

        rule = AlertRule(
            id="cpu_high_test",
            name="CPU High",
            severity=AlertSeverity.P2,
            description="CPU > 85%",
            conditions=[
                AlertCondition(metric="cpu_percent", operator=">", threshold=85.0)
            ]
        )

        engine.add_rule(rule)

        # No breach
        metrics = {"cpu_percent": 75.0}
        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        assert len(alerts) == 0

    def test_sustained_threshold_breach(self):
        """Test sustained threshold requirement"""
        engine = AlertEngine()

        rule = AlertRule(
            id="cpu_sustained_test",
            name="CPU Sustained High",
            severity=AlertSeverity.P2,
            description="CPU > 85% for 10 min",
            conditions=[
                AlertCondition(
                    metric="cpu_percent",
                    operator=">",
                    threshold=85.0,
                    duration_minutes=10
                )
            ]
        )

        engine.add_rule(rule)

        # Simulate 15 minutes of high CPU (to ensure we cover the 10-min window)
        now = datetime.now()
        for i in range(15, 0, -1):
            snapshot = MetricSnapshot(
                timestamp=now - timedelta(minutes=i),
                metric="cpu_percent",
                value=92.0,
                datasource_id="test_ds"
            )
            engine.record_metric(snapshot)

        # Should trigger (oldest snapshot in 10-min window is now 10+ min old)
        metrics = {"cpu_percent": 92.0}
        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        # Find our specific alert (default rules also loaded)
        cpu_alerts = [a for a in alerts if a.rule_id == "cpu_sustained_test"]
        assert len(cpu_alerts) == 1

    def test_insufficient_duration_no_alert(self):
        """Test that brief spikes don't trigger sustained alerts"""
        engine = AlertEngine()

        # Clear default rules to avoid interference
        engine.rules.clear()

        rule = AlertRule(
            id="cpu_sustained_test",
            name="CPU Sustained High",
            severity=AlertSeverity.P2,
            description="CPU > 85% for 10 min",
            conditions=[
                AlertCondition(
                    metric="cpu_percent",
                    operator=">",
                    threshold=85.0,
                    duration_minutes=10
                )
            ]
        )

        engine.add_rule(rule)

        # Only 5 minutes of high CPU
        now = datetime.now()
        for i in range(5, 0, -1):
            snapshot = MetricSnapshot(
                timestamp=now - timedelta(minutes=i),
                metric="cpu_percent",
                value=92.0,
                datasource_id="test_ds"
            )
            engine.record_metric(snapshot)

        # Should NOT trigger (only 5 min duration, need 10)
        metrics = {"cpu_percent": 92.0}
        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        cpu_alerts = [a for a in alerts if a.rule_id == "cpu_sustained_test"]
        assert len(cpu_alerts) == 0

    def test_multi_condition_rule_all_met(self):
        """Test rule with multiple conditions - all must be met"""
        engine = AlertEngine()

        rule = AlertRule(
            id="replication_lag_test",
            name="Replication Lag Critical",
            severity=AlertSeverity.P1,
            description="Lag > RPO AND not sync",
            conditions=[
                AlertCondition(metric="replay_lag_seconds", operator=">", threshold=300),
                AlertCondition(metric="sync_state", operator="!=", threshold="sync")
            ]
        )

        engine.add_rule(rule)

        # Both conditions met
        metrics = {
            "replay_lag_seconds": 450,
            "sync_state": "async"
        }

        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        repl_alerts = [a for a in alerts if a.rule_id == "replication_lag_test"]
        assert len(repl_alerts) == 1
        assert repl_alerts[0].severity == AlertSeverity.P1

    def test_multi_condition_rule_partial_met(self):
        """Test rule with multiple conditions - only some met"""
        engine = AlertEngine()

        rule = AlertRule(
            id="replication_lag_test",
            name="Replication Lag Critical",
            severity=AlertSeverity.P1,
            description="Lag > RPO AND not sync",
            conditions=[
                AlertCondition(metric="replay_lag_seconds", operator=">", threshold=300),
                AlertCondition(metric="sync_state", operator="!=", threshold="sync")
            ]
        )

        engine.add_rule(rule)

        # Only first condition met
        metrics = {
            "replay_lag_seconds": 450,
            "sync_state": "sync"  # This blocks alert
        }

        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        repl_alerts = [a for a in alerts if a.rule_id == "replication_lag_test"]
        assert len(repl_alerts) == 0


class TestAlertLifecycle:
    """Test alert lifecycle management"""

    def test_active_alerts_tracking(self):
        """Test that active alerts are tracked"""
        engine = AlertEngine()

        metrics = {"disk_free_percent": 8}  # Triggers P1 disk alert
        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        disk_alerts = [a for a in alerts if "disk" in a.title.lower()]
        assert len(disk_alerts) >= 1

        # Check active alerts
        active = engine.get_active_alerts()
        assert len(active) > 0

    def test_acknowledge_alert(self):
        """Test alert acknowledgment"""
        engine = AlertEngine()

        metrics = {"disk_free_percent": 5}
        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        assert len(alerts) > 0
        alert_id = alerts[0].id

        # Acknowledge
        success = engine.acknowledge_alert(alert_id, "test_user", "Investigating disk issue")

        assert success is True
        assert engine.active_alerts[alert_id].status == AlertStatus.ACKNOWLEDGED
        assert engine.active_alerts[alert_id].acknowledged_by == "test_user"

    def test_resolve_alert(self):
        """Test manual alert resolution"""
        engine = AlertEngine()

        metrics = {"disk_free_percent": 5}
        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        assert len(alerts) > 0
        alert_id = alerts[0].id

        # Resolve
        success = engine.resolve_alert(alert_id, "test_user", "Disk space freed")

        assert success is True
        # Alert should be removed from active alerts
        assert alert_id not in engine.active_alerts

    def test_auto_resolve_when_condition_clears(self):
        """Test auto-resolution when conditions clear"""
        engine = AlertEngine()

        # Clear default rules, add custom one
        engine.rules.clear()

        rule = AlertRule(
            id="disk_test",
            name="Disk Space Low",
            severity=AlertSeverity.P1,
            description="Disk < 10%",
            conditions=[
                AlertCondition(metric="disk_free_percent", operator="<", threshold=10)
            ],
            auto_resolve=True
        )

        engine.add_rule(rule)

        # Trigger alert
        metrics = {"disk_free_percent": 8}
        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        assert len(alerts) == 1
        assert len(engine.active_alerts) == 1

        # Condition clears
        metrics_cleared = {"disk_free_percent": 15}
        engine.evaluate_all_rules("test_ds", "postgres", metrics_cleared)

        # Alert should auto-resolve
        assert len(engine.active_alerts) == 0

    def test_cooldown_period_prevents_repeat(self):
        """Test cooldown prevents repeated alerts"""
        engine = AlertEngine()

        rule = AlertRule(
            id="disk_cooldown_test",
            name="Disk Space Low",
            severity=AlertSeverity.P1,
            description="Disk < 10%",
            conditions=[
                AlertCondition(metric="disk_free_percent", operator="<", threshold=10)
            ],
            cooldown_minutes=30
        )

        engine.add_rule(rule)

        # First trigger
        metrics = {"disk_free_percent": 8}
        alerts1 = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        disk_alerts1 = [a for a in alerts1 if a.rule_id == "disk_cooldown_test"]
        assert len(disk_alerts1) == 1

        # Immediate re-evaluation (within cooldown)
        alerts2 = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        disk_alerts2 = [a for a in alerts2 if a.rule_id == "disk_cooldown_test"]
        # Should NOT trigger again due to cooldown
        assert len(disk_alerts2) == 0


class TestAlertFiltering:
    """Test alert filtering and querying"""

    def test_get_active_alerts_by_datasource(self):
        """Test filtering alerts by datasource"""
        engine = AlertEngine()

        # Trigger alerts for two datasources
        metrics = {"disk_free_percent": 5}
        engine.evaluate_all_rules("ds1", "postgres", metrics)
        engine.evaluate_all_rules("ds2", "mysql", metrics)

        # Get alerts for specific datasource
        ds1_alerts = engine.get_active_alerts(datasource_id="ds1")

        assert all(a.datasource_id == "ds1" for a in ds1_alerts)

    def test_get_active_alerts_by_severity(self):
        """Test filtering alerts by severity"""
        engine = AlertEngine()

        # Trigger both P1 and P2 alerts
        metrics = {
            "disk_free_percent": 5,  # P1
            "cpu_percent": 90  # P2 (if sustained)
        }
        engine.evaluate_all_rules("test_ds", "postgres", metrics)

        # Get only P1 alerts
        p1_alerts = engine.get_active_alerts(severity=AlertSeverity.P1)

        assert all(a.severity == AlertSeverity.P1 for a in p1_alerts)

    def test_alerts_sorted_by_severity(self):
        """Test alerts are sorted P1 > P2 > P3"""
        engine = AlertEngine()

        # Trigger multiple severities
        metrics = {
            "disk_free_percent": 5,  # P1
            "cpu_percent": 90,  # P2
            "cache_hit_ratio_percent": 85  # P3 (default rule)
        }
        engine.evaluate_all_rules("test_ds", "postgres", metrics)

        active = engine.get_active_alerts()

        if len(active) > 1:
            # Verify P1 comes before P2 comes before P3
            severities = [a.severity.value for a in active]
            severity_order = {"P1": 0, "P2": 1, "P3": 2}
            sorted_severities = sorted(severities, key=lambda s: severity_order[s])
            assert severities == sorted_severities


class TestDatasourceTypeMatching:
    """Test rules matching datasource types"""

    def test_rule_matches_specific_engine(self):
        """Test rule applies to specific engine"""
        rule = AlertRule(
            id="pg_specific",
            name="PostgreSQL Specific",
            severity=AlertSeverity.P2,
            description="Only for PostgreSQL",
            datasource_types=["postgres"],
            conditions=[]
        )

        assert rule.matches_datasource("postgres") is True
        assert rule.matches_datasource("mysql") is False

    def test_rule_matches_wildcard(self):
        """Test rule applies to all engines with wildcard"""
        rule = AlertRule(
            id="universal",
            name="Universal Rule",
            severity=AlertSeverity.P1,
            description="All databases",
            datasource_types=["*"],
            conditions=[]
        )

        assert rule.matches_datasource("postgres") is True
        assert rule.matches_datasource("mysql") is True
        assert rule.matches_datasource("mongodb") is True

    def test_rule_matches_multiple_engines(self):
        """Test rule applies to multiple specific engines"""
        rule = AlertRule(
            id="sql_only",
            name="SQL Databases Only",
            severity=AlertSeverity.P2,
            description="SQL databases",
            datasource_types=["postgres", "mysql", "sqlserver"],
            conditions=[]
        )

        assert rule.matches_datasource("postgres") is True
        assert rule.matches_datasource("mysql") is True
        assert rule.matches_datasource("mongodb") is False


class TestRunwayCalculation:
    """Test resource runway calculations"""

    def test_runway_calculation_days(self):
        """Test runway calculation in days"""
        # 100 GB free, 5 GB/day growth
        runway = calculate_runway(100, 5, unit="days")

        assert runway == 20

    def test_runway_calculation_hours(self):
        """Test runway calculation in hours"""
        # 10 GB free, 5 GB/day growth
        runway = calculate_runway(10, 5, unit="hours")

        assert runway == 48  # 2 days * 24 hours

    def test_runway_zero_growth(self):
        """Test runway with zero growth (infinite)"""
        runway = calculate_runway(100, 0)

        assert runway == float('inf')

    def test_runway_negative_growth(self):
        """Test runway with negative growth (shrinking)"""
        runway = calculate_runway(100, -5)

        assert runway == float('inf')


class TestDefaultRules:
    """Test default alert rules are loaded correctly"""

    def test_default_rules_loaded(self):
        """Test that default DBA rules are loaded"""
        engine = AlertEngine()

        # Check for key P1 rules
        assert "db_down" in engine.rules
        assert "write_latency_slo" in engine.rules
        assert "replication_lag_critical" in engine.rules
        assert "disk_space_critical" in engine.rules

        # Check for P2 rules
        assert "cpu_high" in engine.rules
        assert "long_running_transaction" in engine.rules

        # Check for P3 rules
        assert "storage_forecast_critical" in engine.rules

    def test_db_down_rule_config(self):
        """Test database down rule configuration"""
        engine = AlertEngine()
        rule = engine.rules["db_down"]

        assert rule.severity == AlertSeverity.P1
        assert rule.datasource_types == ["*"]  # All databases
        assert len(rule.conditions) == 1
        assert rule.conditions[0].metric == "db_up"
        assert rule.conditions[0].threshold == 0

    def test_write_latency_rule_config(self):
        """Test write latency SLO rule configuration"""
        engine = AlertEngine()
        rule = engine.rules["write_latency_slo"]

        assert rule.severity == AlertSeverity.P1
        assert "postgres" in rule.datasource_types
        assert rule.conditions[0].threshold == 250  # 250ms SLO


class TestMetricHistory:
    """Test metric history management"""

    def test_metric_history_recorded(self):
        """Test metrics are recorded in history"""
        engine = AlertEngine()

        snapshot = MetricSnapshot(
            timestamp=datetime.now(),
            metric="cpu_percent",
            value=85.0,
            datasource_id="test_ds"
        )

        engine.record_metric(snapshot)

        key = "test_ds:cpu_percent"
        assert key in engine.metric_history
        assert len(engine.metric_history[key]) == 1

    def test_metric_history_cleanup(self):
        """Test old metrics are cleaned up (> 24 hours)"""
        engine = AlertEngine()

        # Add old metric (25 hours ago)
        old_snapshot = MetricSnapshot(
            timestamp=datetime.now() - timedelta(hours=25),
            metric="cpu_percent",
            value=85.0,
            datasource_id="test_ds"
        )

        engine.record_metric(old_snapshot)

        # Add recent metric
        recent_snapshot = MetricSnapshot(
            timestamp=datetime.now(),
            metric="cpu_percent",
            value=90.0,
            datasource_id="test_ds"
        )

        engine.record_metric(recent_snapshot)

        # Old metric should be cleaned up
        key = "test_ds:cpu_percent"
        assert len(engine.metric_history[key]) == 1
        assert engine.metric_history[key][0].value == 90.0


class TestAlertMessages:
    """Test alert message generation"""

    def test_alert_message_includes_metrics(self):
        """Test alert message includes metric values"""
        engine = AlertEngine()

        metrics = {"disk_free_percent": 5}
        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        disk_alerts = [a for a in alerts if "disk" in a.title.lower()]

        if disk_alerts:
            alert = disk_alerts[0]
            assert "5" in alert.message or alert.metric_value == 5

    def test_alert_metadata_includes_conditions(self):
        """Test alert metadata includes all condition values"""
        engine = AlertEngine()

        metrics = {
            "replay_lag_seconds": 450,
            "sync_state": "async"
        }

        alerts = engine.evaluate_all_rules("test_ds", "postgres", metrics)

        repl_alerts = [a for a in alerts if "replication" in a.title.lower()]

        if repl_alerts:
            alert = repl_alerts[0]
            assert "conditions" in alert.metadata
            assert len(alert.metadata["conditions"]) > 0
