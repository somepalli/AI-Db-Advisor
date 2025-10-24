"""
Real Alert Scenario Demo - Generates and displays actual alerts

This script:
1. Sets up a test PostgreSQL datasource connection
2. Simulates various metric conditions (high CPU, low disk, etc.)
3. Evaluates alert rules and triggers alerts
4. Displays triggered alerts in a formatted table
5. Shows AI analysis for P1 critical alerts
"""

import sys
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.venv', 'app'))

from app.services.alert_engine import (
    AlertEngine,
    AlertRule,
    AlertCondition,
    AlertSeverity,
    AlertStatus,
    Alert,
    MetricSnapshot
)
from app.services.alert_analyzer import AlertAnalyzer
from app.config import settings


class AlertDemoRunner:
    """Run real alert scenarios and display results"""

    def __init__(self):
        self.engine = AlertEngine()
        self.analyzer = AlertAnalyzer()
        self.scenarios = []

    def print_header(self, title: str):
        """Print formatted section header"""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80 + "\n")

    def print_alert(self, alert: Alert, index: int):
        """Print formatted alert details"""
        severity_colors = {
            "P1": "🔴",
            "P2": "🟠",
            "P3": "🟡"
        }
        icon = severity_colors.get(alert.severity.value, "⚪")

        print(f"{icon} Alert #{index}: {alert.title}")
        print(f"   Severity: {alert.severity.value}")
        print(f"   Datasource: {alert.datasource_id} ({alert.datasource_engine})")
        print(f"   Triggered: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Status: {alert.status.value}")
        print(f"   Message: {alert.message}")
        print(f"   Metric Value: {alert.metric_value} (threshold: {alert.threshold})")
        print()

    def scenario_1_critical_disk_space(self):
        """Scenario 1: Critical disk space (P1 - immediate trigger)"""
        self.print_header("Scenario 1: Critical Disk Space (P1)")

        print("Simulating: Disk space at 5% (critical threshold: <10%)")
        print("Expected: Immediate P1 alert\n")

        metrics = {
            "disk_free_percent": 5.0,
            "disk_free_gb": 15.0,
            "total_db_size_gb": 100.0,
            "storage_runway_days": 3.0,
            "cpu_percent": 45.0,
            "memory_percent": 60.0,
            "db_up": 1
        }

        alerts = self.engine.evaluate_all_rules(
            datasource_id="prod-postgres-01",
            engine="postgres",
            metrics=metrics
        )

        if alerts:
            print(f"✅ Triggered {len(alerts)} alert(s):\n")
            for idx, alert in enumerate(alerts, 1):
                self.print_alert(alert, idx)
                if alert.severity == AlertSeverity.P1:
                    self.get_ai_analysis(alert)
        else:
            print("❌ No alerts triggered (unexpected)")

        return alerts

    def scenario_2_high_cpu_sustained(self):
        """Scenario 2: High CPU sustained over time (P2)"""
        self.print_header("Scenario 2: High CPU - Sustained Breach (P2)")

        print("Simulating: CPU at 90% for 15 minutes (threshold: >85% for 10 min)")
        print("Expected: P2 alert after sustained breach\n")

        # Record metrics over time to simulate sustained breach
        datasource_id = "prod-postgres-02"
        print("Recording metric snapshots over 15 minutes...")

        for minutes_ago in range(15, 0, -1):
            timestamp = datetime.now() - timedelta(minutes=minutes_ago)
            self.engine._record_metric_snapshot(
                datasource_id=datasource_id,
                metric="cpu_percent",
                value=90.0,
                timestamp=timestamp
            )
            print(f"  [{minutes_ago} min ago] CPU: 90.0%")

        print("\nEvaluating alert rules...\n")

        metrics = {
            "cpu_percent": 90.0,
            "memory_percent": 65.0,
            "disk_free_percent": 30.0,
            "db_up": 1
        }

        alerts = self.engine.evaluate_all_rules(
            datasource_id=datasource_id,
            engine="postgres",
            metrics=metrics
        )

        if alerts:
            print(f"✅ Triggered {len(alerts)} alert(s):\n")
            for idx, alert in enumerate(alerts, 1):
                self.print_alert(alert, idx)
        else:
            print("⚠️  No alerts triggered yet (may need more time for sustained breach)")

        return alerts

    def scenario_3_replication_lag(self):
        """Scenario 3: Replication lag exceeds RPO (P1)"""
        self.print_header("Scenario 3: Replication Lag Critical (P1)")

        print("Simulating: Replica lag at 450 seconds (critical threshold: >300s)")
        print("Expected: Immediate P1 alert for replication lag\n")

        metrics = {
            "replay_lag_seconds": 450.0,
            "num_standbys": 2,
            "sync_state": "async",
            "cpu_percent": 50.0,
            "memory_percent": 60.0,
            "disk_free_percent": 35.0,
            "db_up": 1
        }

        alerts = self.engine.evaluate_all_rules(
            datasource_id="prod-postgres-standby",
            engine="postgres",
            metrics=metrics
        )

        if alerts:
            print(f"✅ Triggered {len(alerts)} alert(s):\n")
            for idx, alert in enumerate(alerts, 1):
                self.print_alert(alert, idx)
                if alert.severity == AlertSeverity.P1:
                    self.get_ai_analysis(alert)
        else:
            print("❌ No alerts triggered (unexpected)")

        return alerts

    def scenario_4_connection_exhaustion(self):
        """Scenario 4: Connection pool near exhaustion (P1)"""
        self.print_header("Scenario 4: Connection Pool Exhaustion (P1)")

        print("Simulating: 99% of max connections in use (threshold: >=98%)")
        print("Expected: Immediate P1 alert\n")

        # Simulate sustained breach (3+ minutes)
        datasource_id = "prod-postgres-03"
        for minutes_ago in range(5, 0, -1):
            timestamp = datetime.now() - timedelta(minutes=minutes_ago)
            self.engine._record_metric_snapshot(
                datasource_id=datasource_id,
                metric="connection_utilization_percent",
                value=99.0,
                timestamp=timestamp
            )

        metrics = {
            "connection_utilization_percent": 99.0,
            "current_connections": 99,
            "max_connections": 100,
            "cpu_percent": 70.0,
            "memory_percent": 75.0,
            "disk_free_percent": 40.0,
            "db_up": 1
        }

        alerts = self.engine.evaluate_all_rules(
            datasource_id=datasource_id,
            engine="postgres",
            metrics=metrics
        )

        if alerts:
            print(f"✅ Triggered {len(alerts)} alert(s):\n")
            for idx, alert in enumerate(alerts, 1):
                self.print_alert(alert, idx)
                if alert.severity == AlertSeverity.P1:
                    self.get_ai_analysis(alert)
        else:
            print("❌ No alerts triggered (check duration requirements)")

        return alerts

    def scenario_5_table_bloat(self):
        """Scenario 5: High table bloat (P2)"""
        self.print_header("Scenario 5: High Table Bloat (P2)")

        print("Simulating: Table bloat at 45% (threshold: >30%)")
        print("Expected: P2 alert for table bloat\n")

        metrics = {
            "max_table_bloat_percent": 45.0,
            "unused_index_count": 5,
            "cpu_percent": 55.0,
            "memory_percent": 60.0,
            "disk_free_percent": 40.0,
            "db_up": 1
        }

        alerts = self.engine.evaluate_all_rules(
            datasource_id="prod-postgres-04",
            engine="postgres",
            metrics=metrics
        )

        if alerts:
            print(f"✅ Triggered {len(alerts)} alert(s):\n")
            for idx, alert in enumerate(alerts, 1):
                self.print_alert(alert, idx)
        else:
            print("❌ No alerts triggered (unexpected)")

        return alerts

    def scenario_6_cache_degradation(self):
        """Scenario 6: Cache hit ratio degradation (P3)"""
        self.print_header("Scenario 6: Cache Hit Ratio Degradation (P3)")

        print("Simulating: Cache hit ratio at 88% sustained for 35 minutes (threshold: <95% for 30 min)")
        print("Expected: P3 alert for cache degradation\n")

        datasource_id = "prod-postgres-05"

        # Record sustained low cache hit ratio
        for minutes_ago in range(35, 0, -1):
            timestamp = datetime.now() - timedelta(minutes=minutes_ago)
            self.engine._record_metric_snapshot(
                datasource_id=datasource_id,
                metric="cache_hit_ratio_percent",
                value=88.0,
                timestamp=timestamp
            )

        metrics = {
            "cache_hit_ratio_percent": 88.0,
            "cpu_percent": 60.0,
            "memory_percent": 85.0,
            "disk_free_percent": 35.0,
            "db_up": 1
        }

        alerts = self.engine.evaluate_all_rules(
            datasource_id=datasource_id,
            engine="postgres",
            metrics=metrics
        )

        if alerts:
            print(f"✅ Triggered {len(alerts)} alert(s):\n")
            for idx, alert in enumerate(alerts, 1):
                self.print_alert(alert, idx)
        else:
            print("⚠️  No alerts triggered (may need more sustained history)")

        return alerts

    def get_ai_analysis(self, alert: Alert):
        """Get and display AI analysis for critical alerts"""
        print("   🤖 AI Analysis:")
        print("   " + "-" * 76)

        try:
            analysis = self.analyzer.analyze(alert)

            print(f"   Root Cause: {analysis.root_cause}")
            print(f"   Confidence: {analysis.confidence * 100:.1f}%")

            if analysis.immediate_actions:
                print(f"\n   Immediate Actions:")
                for action in analysis.immediate_actions:
                    print(f"     • {action}")

            if analysis.recommendations:
                print(f"\n   Recommendations:")
                for idx, rec in enumerate(analysis.recommendations, 1):
                    print(f"     {idx}. [{rec.type}] {rec.summary}")
                    if rec.sql:
                        print(f"        SQL: {rec.sql}")
                    if rec.command:
                        print(f"        Command: {rec.command}")
                    print(f"        Risk: {rec.risk_level}, Priority: {rec.priority}")

            print()

        except Exception as e:
            print(f"   ⚠️  AI analysis failed: {e}\n")

    def show_summary(self, all_alerts: List[List[Alert]]):
        """Show summary of all triggered alerts"""
        self.print_header("Alert Summary")

        total_alerts = sum(len(alerts) for alerts in all_alerts)
        p1_count = sum(1 for alerts in all_alerts for a in alerts if a.severity == AlertSeverity.P1)
        p2_count = sum(1 for alerts in all_alerts for a in alerts if a.severity == AlertSeverity.P2)
        p3_count = sum(1 for alerts in all_alerts for a in alerts if a.severity == AlertSeverity.P3)

        print(f"Total Alerts Triggered: {total_alerts}")
        print(f"  🔴 P1 Critical: {p1_count}")
        print(f"  🟠 P2 High: {p2_count}")
        print(f"  🟡 P3 Medium: {p3_count}")
        print()

        # Show active alerts
        active_alerts = self.engine.get_active_alerts()
        print(f"Active Alerts: {len(active_alerts)}")
        for idx, alert in enumerate(active_alerts, 1):
            print(f"  {idx}. [{alert.severity.value}] {alert.title} - {alert.datasource_id}")

        print()

    def run_all_scenarios(self):
        """Run all alert scenarios"""
        self.print_header("AI DB Advisor - Real Alert Scenario Demo")

        print("This demo will simulate various database conditions and trigger real alerts.")
        print("The alert engine will evaluate metrics against predefined rules.\n")

        input("Press Enter to start demo...")

        all_alerts = []

        # Run scenarios
        all_alerts.append(self.scenario_1_critical_disk_space())
        input("\nPress Enter for next scenario...")

        all_alerts.append(self.scenario_2_high_cpu_sustained())
        input("\nPress Enter for next scenario...")

        all_alerts.append(self.scenario_3_replication_lag())
        input("\nPress Enter for next scenario...")

        all_alerts.append(self.scenario_4_connection_exhaustion())
        input("\nPress Enter for next scenario...")

        all_alerts.append(self.scenario_5_table_bloat())
        input("\nPress Enter for next scenario...")

        all_alerts.append(self.scenario_6_cache_degradation())

        # Summary
        self.show_summary(all_alerts)

        self.print_header("Demo Complete")
        print("All alert scenarios have been executed.")
        print("\nNext steps:")
        print("  1. View alerts via API: GET http://127.0.0.1:8000/alerts/active")
        print("  2. Get alert details: GET http://127.0.0.1:8000/alerts/{alert_id}")
        print("  3. Acknowledge alert: POST http://127.0.0.1:8000/alerts/{alert_id}/acknowledge")
        print("  4. Get AI analysis: POST http://127.0.0.1:8000/alerts/{alert_id}/analyze")
        print()


def main():
    """Main entry point"""
    try:
        demo = AlertDemoRunner()
        demo.run_all_scenarios()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
