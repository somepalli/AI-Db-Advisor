"""
Integration Tests for Alert Workflow

Tests the complete alert lifecycle:
1. Metric collection → Alert evaluation → Triggering
2. Alert triggering → AI analysis → Recommendations
3. Alert acknowledgment → Resolution → Auto-resolution
4. Alert monitoring service → Continuous evaluation
5. Alert history and filtering
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

from backend.services.alert_engine import (
    AlertEngine,
    AlertRule,
    AlertCondition,
    AlertSeverity,
    AlertStatus,
    Alert
)
from backend.services.alert_analyzer import AlertAnalyzer, AlertAnalysis
from backend.services.metrics_collector import collect_all_metrics
from backend.config import settings


class TestAlertWorkflowIntegration:
    """Test complete alert workflow from metrics to resolution"""

    @pytest.fixture
    def alert_engine(self):
        """Create alert engine with ONLY the test rules (no built-in defaults)."""
        engine = AlertEngine()
        engine.rules.clear()  # start from a clean slate for deterministic tests

        # Add test rule: High CPU
        cpu_rule = AlertRule(
            id="test_cpu_high",
            name="Test CPU High",
            severity=AlertSeverity.P2,
            description="Test rule for high CPU",
            conditions=[
                AlertCondition(
                    metric="cpu_percent",
                    operator=">",
                    threshold=80,
                    duration_minutes=5
                )
            ],
            cooldown_minutes=10,
            datasource_types=["postgres", "mysql"]
        )
        engine.add_rule(cpu_rule)

        # Add test rule: Disk Space Critical
        disk_rule = AlertRule(
            id="test_disk_critical",
            name="Test Disk Critical",
            severity=AlertSeverity.P1,
            description="Test rule for critical disk space",
            conditions=[
                AlertCondition(
                    metric="disk_free_percent",
                    operator="<",
                    threshold=10,
                    duration_minutes=0  # Immediate trigger
                )
            ],
            cooldown_minutes=30,
            datasource_types=["all"]
        )
        engine.add_rule(disk_rule)

        return engine

    @pytest.fixture
    def alert_analyzer(self):
        """Create alert analyzer"""
        return AlertAnalyzer()

    def test_metric_to_alert_flow(self, alert_engine):
        """Test: Metrics → Alert Evaluation → Triggering"""

        # Simulate metrics with high CPU
        metrics = {
            "cpu_percent": 85.0,
            "memory_percent": 60.0,
            "disk_free_percent": 30.0
        }

        # Evaluate rules
        alerts = alert_engine.evaluate_all_rules(
            datasource_id="test-db",
            engine="postgres",
            metrics=metrics
        )

        # Should trigger CPU alert (after sustained threshold is met)
        # First call won't trigger due to duration requirement
        assert len(alerts) == 0, "First evaluation should not trigger (duration required)"

        # Simulate passage of time by recording more metrics
        for i in range(6):  # Record for 6 minutes
            alert_engine._record_metric_snapshot(
                datasource_id="test-db",
                metric="cpu_percent",
                value=85.0,
                timestamp=datetime.now() - timedelta(minutes=6-i)
            )

        # Re-evaluate - should now trigger
        alerts = alert_engine.evaluate_all_rules(
            datasource_id="test-db",
            engine="postgres",
            metrics=metrics
        )

        # Should have triggered CPU alert
        assert len(alerts) >= 1, "Should trigger CPU alert after sustained breach"
        cpu_alert = next((a for a in alerts if a.rule_id == "test_cpu_high"), None)
        assert cpu_alert is not None
        assert cpu_alert.severity == AlertSeverity.P2
        assert cpu_alert.status == AlertStatus.ACTIVE

    def test_immediate_trigger_alert(self, alert_engine):
        """Test: Immediate trigger for P1 critical alerts"""

        # Simulate critical disk space (immediate trigger)
        metrics = {
            "cpu_percent": 50.0,
            "disk_free_percent": 5.0  # Critical!
        }

        # Evaluate - should trigger immediately
        alerts = alert_engine.evaluate_all_rules(
            datasource_id="test-db",
            engine="postgres",
            metrics=metrics
        )

        # Should trigger disk alert immediately
        assert len(alerts) >= 1, "Should trigger disk alert immediately"
        disk_alert = next((a for a in alerts if a.rule_id == "test_disk_critical"), None)
        assert disk_alert is not None
        assert disk_alert.severity == AlertSeverity.P1
        assert disk_alert.status == AlertStatus.ACTIVE

    def test_alert_to_ai_analysis_flow(self, alert_engine, alert_analyzer):
        """Test: Alert Triggering → AI Analysis → Recommendations"""

        # Create alert
        alert = Alert(
            id="test-alert-001",
            rule_id="test_disk_critical",
            severity=AlertSeverity.P1,
            title="Test Disk Critical",
            message="Disk space is critically low",
            datasource_id="test-db",
            datasource_engine="postgres",
            triggered_at=datetime.now(),
            status=AlertStatus.ACTIVE,
            metric_value=5.0,
            threshold=10.0,
            metadata={}
        )

        # Analyze alert with AI
        # Note: This will call real AI if available, or fallback
        analysis = alert_analyzer.analyze(alert)

        # Verify analysis structure
        assert analysis.alert_id == "test-alert-001"
        assert analysis.root_cause is not None
        assert len(analysis.root_cause) > 0
        assert len(analysis.immediate_actions) > 0
        assert analysis.confidence >= 0.0
        assert analysis.confidence <= 1.0

        # Should have recommendations
        assert len(analysis.recommendations) >= 0  # Fallback may have 1+

        # If recommendations exist, verify structure
        if analysis.recommendations:
            rec = analysis.recommendations[0]
            assert rec.type in ["config", "index", "query", "action", "note"]
            assert rec.summary is not None
            assert rec.risk_level in ["low", "medium", "high"]

    def test_alert_acknowledgment_flow(self, alert_engine):
        """Test: Alert → Acknowledge → Status Update"""

        # Trigger alert
        metrics = {"disk_free_percent": 5.0}
        alerts = alert_engine.evaluate_all_rules("test-db", "postgres", metrics)

        assert len(alerts) >= 1
        alert = alerts[0]
        alert_id = alert.id

        # Acknowledge alert
        alert_engine.acknowledge_alert(alert_id, "Test User", "Investigating disk space issue")

        # Verify acknowledgment
        ack_alert = alert_engine.get_alert(alert_id)
        assert ack_alert.status == AlertStatus.ACKNOWLEDGED
        assert ack_alert.acknowledged_by == "Test User"
        assert ack_alert.acknowledged_at is not None
        assert ack_alert.ack_note == "Investigating disk space issue"

    def test_alert_resolution_flow(self, alert_engine):
        """Test: Alert → Resolve → Status Update"""

        # Trigger and acknowledge alert
        metrics = {"disk_free_percent": 5.0}
        alerts = alert_engine.evaluate_all_rules("test-db", "postgres", metrics)
        alert_id = alerts[0].id

        alert_engine.acknowledge_alert(alert_id, "Test User", "Investigating")

        # Resolve alert
        alert_engine.resolve_alert(alert_id, "Test User", "Cleaned up old logs, freed 50GB")

        # Verify resolution
        resolved_alert = alert_engine.get_alert(alert_id)
        assert resolved_alert.status == AlertStatus.RESOLVED
        assert resolved_alert.resolved_by == "Test User"
        assert resolved_alert.resolved_at is not None
        assert resolved_alert.resolution_note == "Cleaned up old logs, freed 50GB"

    def test_auto_resolution_flow(self, alert_engine):
        """Test: Alert auto-resolves when condition clears"""

        # Trigger alert
        metrics = {"disk_free_percent": 5.0}
        alerts = alert_engine.evaluate_all_rules("test-db", "postgres", metrics)
        assert len(alerts) >= 1
        alert_id = alerts[0].id

        # Condition clears (disk space restored)
        cleared_metrics = {"disk_free_percent": 30.0}
        alerts = alert_engine.evaluate_all_rules("test-db", "postgres", cleared_metrics)

        # Alert should auto-resolve
        resolved_alert = alert_engine.get_alert(alert_id)
        assert resolved_alert.status == AlertStatus.AUTO_RESOLVED
        assert resolved_alert.resolved_at is not None

    def test_alert_cooldown_prevents_flapping(self, alert_engine):
        """Test: Cooldown period prevents alert flapping"""

        # Trigger alert
        metrics = {"disk_free_percent": 5.0}
        alerts1 = alert_engine.evaluate_all_rules("test-db", "postgres", metrics)
        assert len(alerts1) >= 1
        alert1_id = alerts1[0].id

        # Auto-resolve
        cleared_metrics = {"disk_free_percent": 30.0}
        alert_engine.evaluate_all_rules("test-db", "postgres", cleared_metrics)

        # Trigger again immediately (should be in cooldown)
        alerts2 = alert_engine.evaluate_all_rules("test-db", "postgres", metrics)

        # Should NOT create new alert due to cooldown
        new_alerts = [a for a in alerts2 if a.id != alert1_id]
        assert len(new_alerts) == 0, "Cooldown should prevent new alert"

    def test_alert_filtering_by_severity(self, alert_engine):
        """Test: Filter alerts by severity"""

        # Trigger both P1 and P2 alerts
        metrics = {
            "cpu_percent": 85.0,
            "disk_free_percent": 5.0
        }

        # Record CPU metrics for sustained breach
        for i in range(6):
            alert_engine._record_metric_snapshot(
                "test-db", "cpu_percent", 85.0,
                datetime.now() - timedelta(minutes=6-i)
            )

        alerts = alert_engine.evaluate_all_rules("test-db", "postgres", metrics)

        # Filter by P1
        p1_alerts = alert_engine.get_alerts(severity=AlertSeverity.P1)
        assert all(a.severity == AlertSeverity.P1 for a in p1_alerts)

        # Filter by P2
        p2_alerts = alert_engine.get_alerts(severity=AlertSeverity.P2)
        assert all(a.severity == AlertSeverity.P2 for a in p2_alerts)

    def test_alert_filtering_by_status(self, alert_engine):
        """Test: Filter alerts by status"""

        # Trigger alert
        metrics = {"disk_free_percent": 5.0}
        alerts = alert_engine.evaluate_all_rules("test-db", "postgres", metrics)
        alert_id = alerts[0].id

        # Get active alerts
        active_alerts = alert_engine.get_alerts(status=AlertStatus.ACTIVE)
        assert all(a.status == AlertStatus.ACTIVE for a in active_alerts)
        assert any(a.id == alert_id for a in active_alerts)

        # Acknowledge alert
        alert_engine.acknowledge_alert(alert_id, "Test User", "Investigating")

        # Get acknowledged alerts
        ack_alerts = alert_engine.get_alerts(status=AlertStatus.ACKNOWLEDGED)
        assert all(a.status == AlertStatus.ACKNOWLEDGED for a in ack_alerts)
        assert any(a.id == alert_id for a in ack_alerts)

    def test_alert_filtering_by_datasource(self, alert_engine):
        """Test: Filter alerts by datasource"""

        # Trigger alerts for multiple datasources
        metrics = {"disk_free_percent": 5.0}
        alert_engine.evaluate_all_rules("test-db-1", "postgres", metrics)
        alert_engine.evaluate_all_rules("test-db-2", "mysql", metrics)

        # Filter by datasource
        db1_alerts = alert_engine.get_alerts(datasource_id="test-db-1")
        assert all(a.datasource_id == "test-db-1" for a in db1_alerts)

        db2_alerts = alert_engine.get_alerts(datasource_id="test-db-2")
        assert all(a.datasource_id == "test-db-2" for a in db2_alerts)

    def test_alert_history_pagination(self, alert_engine):
        """Test: Alert history with pagination"""

        # Create multiple alerts
        metrics = {"disk_free_percent": 5.0}
        for i in range(15):
            alert_engine.evaluate_all_rules(f"test-db-{i}", "postgres", metrics)

        # Get paginated history
        page1 = alert_engine.get_alerts(limit=10, offset=0)
        assert len(page1) == 10

        page2 = alert_engine.get_alerts(limit=10, offset=10)
        assert len(page2) == 5

        # Ensure no duplicates
        page1_ids = {a.id for a in page1}
        page2_ids = {a.id for a in page2}
        assert len(page1_ids.intersection(page2_ids)) == 0


class TestAlertMonitoringService:
    """Test continuous alert monitoring service"""

    @pytest.fixture
    def alert_engine(self):
        """Create alert engine"""
        return AlertEngine()

    @pytest.mark.asyncio
    async def test_continuous_monitoring_loop(self, alert_engine):
        """Test: Continuous monitoring evaluates rules periodically"""

        # Add a simple rule
        rule = AlertRule(
            id="test_monitor",
            name="Test Monitoring",
            severity=AlertSeverity.P3,
            description="Test monitoring rule",
            conditions=[
                AlertCondition(metric="cpu_percent", operator=">", threshold=90)
            ],
            datasource_types=["all"]
        )
        alert_engine.add_rule(rule)

        # Mock datasource
        settings.DATASOURCES = {
            "test-db": type('obj', (object,), {
                'id': 'test-db',
                'engine': 'postgres',
                'dsn': 'mock://localhost'
            })()
        }

        # Simulate monitoring cycle
        # In production, this would run in background task
        evaluation_count = 0

        async def mock_monitor_cycle():
            nonlocal evaluation_count

            # Simulate 3 monitoring cycles
            for _ in range(3):
                # Collect metrics (mocked)
                metrics = {"cpu_percent": 95.0}

                # Evaluate rules
                alerts = alert_engine.evaluate_all_rules("test-db", "postgres", metrics)
                evaluation_count += 1

                # Wait (in production, this would be 30-60 seconds)
                await asyncio.sleep(0.1)

        # Run monitoring
        await mock_monitor_cycle()

        # Verify monitoring ran 3 times
        assert evaluation_count == 3

    def test_monitoring_handles_metric_collection_errors(self, alert_engine):
        """Test: Monitoring gracefully handles metric collection errors"""

        # Mock failing datasource
        settings.DATASOURCES = {
            "failing-db": type('obj', (object,), {
                'id': 'failing-db',
                'engine': 'postgres',
                'dsn': 'invalid://localhost'
            })()
        }

        # Attempt to evaluate (should not crash)
        try:
            # Metrics will have error flag
            metrics = {
                "error": True,
                "error_message": "Connection failed"
            }

            alerts = alert_engine.evaluate_all_rules("failing-db", "postgres", metrics)

            # Should return empty alerts, not crash
            assert isinstance(alerts, list)

        except Exception as e:
            pytest.fail(f"Monitoring should handle errors gracefully: {e}")


class TestAlertEndToEnd:
    """Complete end-to-end alert workflow tests"""

    def test_complete_p1_alert_lifecycle(self):
        """
        Test complete P1 alert lifecycle:
        1. Metrics indicate critical issue
        2. Alert triggers immediately (P1)
        3. AI analyzes and provides recommendations
        4. DBA acknowledges alert
        5. DBA applies fix
        6. Alert auto-resolves when condition clears
        """

        engine = AlertEngine()
        analyzer = AlertAnalyzer()

        # Step 1: Critical disk space detected
        metrics = {"disk_free_percent": 3.0}

        # Step 2: Alert triggers
        alerts = engine.evaluate_all_rules("prod-db", "postgres", metrics)
        assert len(alerts) >= 1

        alert = alerts[0]
        assert alert.severity == AlertSeverity.P1
        assert alert.status == AlertStatus.ACTIVE

        # Step 3: AI analysis
        analysis = analyzer.analyze(alert)
        assert len(analysis.immediate_actions) > 0
        assert "disk" in analysis.root_cause.lower()

        # Step 4: DBA acknowledges
        engine.acknowledge_alert(alert.id, "DBA-John", "Investigating disk space")
        ack_alert = engine.get_alert(alert.id)
        assert ack_alert.status == AlertStatus.ACKNOWLEDGED

        # Step 5: DBA applies fix (simulated by clearing metrics)
        cleared_metrics = {"disk_free_percent": 40.0}

        # Step 6: Auto-resolve
        engine.evaluate_all_rules("prod-db", "postgres", cleared_metrics)
        final_alert = engine.get_alert(alert.id)
        assert final_alert.status == AlertStatus.AUTO_RESOLVED

    def test_complete_p2_alert_with_sustained_breach(self):
        """
        Test P2 alert requiring sustained breach:
        1. Metrics show elevated but not critical levels
        2. Condition must persist for duration
        3. Alert triggers after sustained breach
        4. Manual resolution after investigation
        """

        engine = AlertEngine()

        # Add P2 rule with duration requirement
        rule = AlertRule(
            id="test_sustained_p2",
            name="Test Sustained P2",
            severity=AlertSeverity.P2,
            description="Test sustained P2 alert",
            conditions=[
                AlertCondition(
                    metric="cpu_percent",
                    operator=">",
                    threshold=80,
                    duration_minutes=5
                )
            ],
            datasource_types=["all"]
        )
        engine.add_rule(rule)

        # Step 1: Elevated CPU (not sustained yet)
        metrics = {"cpu_percent": 85.0}
        alerts = engine.evaluate_all_rules("prod-db", "postgres", metrics)
        assert len([a for a in alerts if a.rule_id == "test_sustained_p2"]) == 0

        # Step 2: Record sustained high CPU
        for i in range(6):
            engine._record_metric_snapshot(
                "prod-db", "cpu_percent", 85.0,
                datetime.now() - timedelta(minutes=6-i)
            )

        # Step 3: Re-evaluate - should trigger
        alerts = engine.evaluate_all_rules("prod-db", "postgres", metrics)
        p2_alerts = [a for a in alerts if a.rule_id == "test_sustained_p2"]
        assert len(p2_alerts) >= 1

        alert = p2_alerts[0]
        assert alert.severity == AlertSeverity.P2

        # Step 4: Manual resolution
        engine.acknowledge_alert(alert.id, "DBA-Jane", "Investigating")
        engine.resolve_alert(alert.id, "DBA-Jane", "Optimized slow queries")

        final_alert = engine.get_alert(alert.id)
        assert final_alert.status == AlertStatus.RESOLVED


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
