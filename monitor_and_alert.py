"""
Continuous Alert Monitoring - Detects database status changes in real-time

This script:
1. Continuously monitors registered datasources
2. Collects metrics every 30 seconds
3. Evaluates alert rules (including db_down)
4. Displays triggered alerts immediately
5. Shows when PostgreSQL goes down
"""

import sys
import os
import time
from datetime import datetime
import signal

# Add app directory to path
app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.venv', 'app')
sys.path.insert(0, app_path)

from services.alert_engine import AlertEngine, AlertSeverity, AlertStatus
from services.alert_analyzer import AlertAnalyzer
from config import settings
from deps import resolve_agent


class ContinuousAlertMonitor:
    """Continuous monitoring for database alerts"""

    def __init__(self, evaluation_interval_seconds: int = 30):
        self.engine = AlertEngine()
        self.analyzer = AlertAnalyzer()
        self.interval = evaluation_interval_seconds
        self.running = True
        self.iteration = 0

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        print("\n\n🛑 Shutting down monitoring...")
        self.running = False

    def print_header(self):
        """Print monitoring header"""
        print("\n" + "=" * 100)
        print("  🔍 AI DB Advisor - Continuous Alert Monitoring")
        print("=" * 100)
        print(f"  Monitoring Interval: {self.interval} seconds")
        print(f"  Alert Rules Loaded: {len(self.engine.rules)}")
        print("=" * 100 + "\n")

    def register_test_datasource(self):
        """Register a test PostgreSQL datasource"""
        from schemas import DataSource

        # Check if UniversityDB is available
        datasource = DataSource(
            id="pg-university",
            engine="postgres",
            dsn="postgresql://postgres:postgres@localhost:5432/UniversityDB"
        )

        settings.DATASOURCES[datasource.id] = datasource
        print(f"✅ Registered datasource: {datasource.id}")
        print(f"   Engine: {datasource.engine}")
        print(f"   DSN: {datasource.dsn}\n")

        return datasource.id

    def collect_metrics(self, datasource_id: str) -> dict:
        """Collect metrics from a datasource"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "datasource_id": datasource_id,
            "db_up": 0  # Default to down
        }

        try:
            agent = resolve_agent(datasource_id)
            datasource = settings.DATASOURCES[datasource_id]

            # Test database connection
            if datasource.engine.startswith("postgres"):
                try:
                    result = agent.query("SELECT 1 as health_check")
                    if result:
                        metrics["db_up"] = 1

                        # Collect additional metrics if DB is up
                        stats = agent.query("""
                            SELECT
                                (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_conn,
                                (SELECT count(*) FROM pg_stat_activity) as current_conn,
                                pg_database_size(current_database()) / (1024^3) as db_size_gb
                        """)

                        if stats:
                            row = stats[0]
                            metrics["max_connections"] = row.get("max_conn", 100)
                            metrics["current_connections"] = row.get("current_conn", 0)
                            metrics["total_db_size_gb"] = row.get("db_size_gb", 0)

                            if metrics["max_connections"] > 0:
                                metrics["connection_utilization_percent"] = (
                                    metrics["current_connections"] / metrics["max_connections"]
                                ) * 100

                        # Get cache hit ratio
                        cache_stats = agent.query("""
                            SELECT
                                blks_read,
                                blks_hit
                            FROM pg_stat_database
                            WHERE datname = current_database()
                        """)

                        if cache_stats:
                            blks_read = cache_stats[0].get("blks_read", 0)
                            blks_hit = cache_stats[0].get("blks_hit", 0)
                            if blks_read + blks_hit > 0:
                                metrics["cache_hit_ratio_percent"] = (
                                    blks_hit / (blks_read + blks_hit)
                                ) * 100

                        # Placeholder for other metrics
                        metrics["cpu_percent"] = 45.0  # Would come from node_exporter
                        metrics["memory_percent"] = 60.0
                        metrics["disk_free_percent"] = 35.0

                except Exception as e:
                    print(f"   ⚠️  Database connection failed: {e}")
                    metrics["db_up"] = 0
                    metrics["error"] = str(e)

        except Exception as e:
            print(f"   ❌ Metric collection error: {e}")
            metrics["db_up"] = 0
            metrics["error"] = str(e)

        return metrics

    def display_alert(self, alert):
        """Display alert with formatting"""
        severity_icons = {
            "P1": "🔴",
            "P2": "🟠",
            "P3": "🟡"
        }

        icon = severity_icons.get(alert.severity.value, "⚪")

        print("\n" + "!" * 100)
        print(f"{icon} ALERT TRIGGERED: {alert.title}")
        print("!" * 100)
        print(f"  Severity: {alert.severity.value}")
        print(f"  Datasource: {alert.datasource_id} ({alert.datasource_engine})")
        print(f"  Triggered: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Status: {alert.status.value}")
        print(f"  Message: {alert.message}")
        if alert.metric_value is not None:
            print(f"  Metric Value: {alert.metric_value} (threshold: {alert.threshold})")
        print("!" * 100 + "\n")

        # AI analysis for P1 critical alerts
        if alert.severity == AlertSeverity.P1:
            try:
                print("  🤖 Running AI Analysis...")
                analysis = self.analyzer.analyze(alert)

                print(f"  Root Cause: {analysis.root_cause}")
                print(f"  Confidence: {analysis.confidence * 100:.1f}%")

                if analysis.immediate_actions:
                    print(f"\n  Immediate Actions:")
                    for action in analysis.immediate_actions:
                        print(f"    • {action}")

                if analysis.recommendations:
                    print(f"\n  Recommendations:")
                    for idx, rec in enumerate(analysis.recommendations[:3], 1):
                        print(f"    {idx}. [{rec.type}] {rec.summary}")

                print()

            except Exception as e:
                print(f"  ⚠️  AI analysis error: {e}\n")

    def monitor_iteration(self, datasource_id: str):
        """Single monitoring iteration"""
        self.iteration += 1
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print(f"[{timestamp}] Iteration #{self.iteration} - Monitoring {datasource_id}...")

        # Collect metrics
        metrics = self.collect_metrics(datasource_id)

        # Display key metrics
        db_status = "🟢 UP" if metrics.get("db_up") == 1 else "🔴 DOWN"
        print(f"   Database Status: {db_status}")

        if metrics.get("db_up") == 1:
            if "current_connections" in metrics:
                print(f"   Connections: {metrics['current_connections']}/{metrics['max_connections']} " +
                      f"({metrics['connection_utilization_percent']:.1f}%)")
            if "cache_hit_ratio_percent" in metrics:
                print(f"   Cache Hit Ratio: {metrics['cache_hit_ratio_percent']:.2f}%")
            if "total_db_size_gb" in metrics:
                print(f"   Database Size: {metrics['total_db_size_gb']:.2f} GB")
        else:
            if "error" in metrics:
                print(f"   Error: {metrics['error']}")

        # Evaluate alert rules
        datasource = settings.DATASOURCES[datasource_id]
        alerts = self.engine.evaluate_all_rules(
            datasource_id=datasource_id,
            engine=datasource.engine,
            metrics=metrics
        )

        # Display triggered alerts
        if alerts:
            print(f"   ⚠️  {len(alerts)} alert(s) triggered!")
            for alert in alerts:
                self.display_alert(alert)
        else:
            print(f"   ✅ No new alerts")

        # Show active alerts summary
        active_alerts = self.engine.get_active_alerts()
        if active_alerts:
            print(f"   📊 Active Alerts: {len(active_alerts)}")
            for alert in active_alerts[:5]:  # Show first 5
                print(f"      - [{alert.severity.value}] {alert.title} ({alert.datasource_id})")

        print()

    def start(self):
        """Start continuous monitoring"""
        self.print_header()

        # Register test datasource
        datasource_id = self.register_test_datasource()

        print(f"🚀 Starting continuous monitoring...")
        print(f"   Press Ctrl+C to stop\n")
        print("=" * 100 + "\n")

        # Initial status check
        print("🔍 Performing initial health check...")
        initial_metrics = self.collect_metrics(datasource_id)
        if initial_metrics.get("db_up") == 1:
            print("✅ Database is currently UP and responding\n")
        else:
            print("⚠️  Database is currently DOWN or unreachable\n")

        print("Starting monitoring loop...\n")

        # Monitoring loop
        while self.running:
            try:
                self.monitor_iteration(datasource_id)

                # Wait for next iteration
                for i in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                print(f"❌ Error during monitoring: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.interval)

        print("\n✅ Monitoring stopped\n")

        # Show final summary
        self.show_final_summary()

    def show_final_summary(self):
        """Show final alert summary"""
        print("\n" + "=" * 100)
        print("  📊 Final Alert Summary")
        print("=" * 100 + "\n")

        active_alerts = self.engine.get_active_alerts()
        all_alerts = self.engine.get_alerts(limit=100)

        p1_count = len([a for a in all_alerts if a.severity == AlertSeverity.P1])
        p2_count = len([a for a in all_alerts if a.severity == AlertSeverity.P2])
        p3_count = len([a for a in all_alerts if a.severity == AlertSeverity.P3])

        print(f"Total Alerts Triggered: {len(all_alerts)}")
        print(f"  🔴 P1 Critical: {p1_count}")
        print(f"  🟠 P2 High: {p2_count}")
        print(f"  🟡 P3 Medium: {p3_count}")
        print(f"\nCurrently Active: {len(active_alerts)}")

        if active_alerts:
            print("\nActive Alerts:")
            for idx, alert in enumerate(active_alerts, 1):
                print(f"  {idx}. [{alert.severity.value}] {alert.title}")
                print(f"     Datasource: {alert.datasource_id}")
                print(f"     Triggered: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"     Status: {alert.status.value}\n")

        print()


def main():
    """Main entry point"""
    print("\n🚀 AI DB Advisor - Continuous Alert Monitoring\n")

    # Parse command line args
    import argparse
    parser = argparse.ArgumentParser(description="Continuous database alert monitoring")
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Evaluation interval in seconds (default: 30)'
    )
    args = parser.parse_args()

    try:
        monitor = ContinuousAlertMonitor(evaluation_interval_seconds=args.interval)
        monitor.start()
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoring interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
