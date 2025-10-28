"""
Automated Alert Monitor - Continuously monitors datasources via FastAPI and displays alerts

This script:
1. Registers datasources with the FastAPI backend
2. Periodically triggers alert evaluation via POST /alerts/evaluate
3. Fetches and displays active alerts from GET /alerts/active
4. Shows alert changes in real-time
"""

import requests
import time
import json
from datetime import datetime
import signal
import sys


class AutomatedAlertMonitor:
    """Automated monitoring using FastAPI backend"""

    def __init__(self, api_base_url="http://127.0.0.1:8095", interval_seconds=10):
        self.api_base = api_base_url
        self.interval = interval_seconds
        self.running = True
        self.registered_datasources = []
        self.known_alert_ids = set()
        self.iteration = 0

        # Setup signal handler
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        print("\n\n[SHUTDOWN] Stopping monitoring...")
        self.running = False

    def print_header(self):
        """Print monitoring header"""
        print("\n" + "=" * 100)
        print("  Automated Alert Monitor - FastAPI Backend Integration")
        print("=" * 100)
        print(f"  API Base URL: {self.api_base}")
        print(f"  Monitoring Interval: {self.interval} seconds")
        print("=" * 100 + "\n")

    def check_backend_health(self):
        """Check if FastAPI backend is running"""
        try:
            response = requests.get(f"{self.api_base}/healthz", timeout=5)
            return response.status_code == 200
        except:
            return False

    def register_datasource(self, ds_id, engine, dsn):
        """Register a datasource with the backend"""
        try:
            payload = {"id": ds_id, "engine": engine, "dsn": dsn}
            response = requests.post(
                f"{self.api_base}/datasources",
                json=payload,
                timeout=10
            )

            if response.status_code == 201:
                self.registered_datasources.append(ds_id)
                print(f"[OK] Registered datasource: {ds_id} ({engine})")
                return True
            elif response.status_code == 409:
                print(f"[INFO] Datasource {ds_id} already registered")
                self.registered_datasources.append(ds_id)
                return True
            else:
                print(f"[ERROR] Failed to register {ds_id}: {response.text}")
                return False
        except Exception as e:
            print(f"[ERROR] Failed to register {ds_id}: {e}")
            return False

    def evaluate_alerts(self, ds_id):
        """Trigger alert evaluation for a datasource"""
        try:
            response = requests.post(
                f"{self.api_base}/alerts/evaluate/{ds_id}",
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"[WARN] Alert evaluation failed for {ds_id}: {response.text}")
                return None
        except Exception as e:
            print(f"[ERROR] Alert evaluation error for {ds_id}: {e}")
            return None

    def get_active_alerts(self, ds_id=None):
        """Get active alerts from backend"""
        try:
            url = f"{self.api_base}/alerts/active"
            if ds_id:
                url += f"?datasource_id={ds_id}"

            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("alerts", [])
            else:
                print(f"[WARN] Failed to get active alerts: {response.text}")
                return []
        except Exception as e:
            print(f"[ERROR] Failed to get active alerts: {e}")
            return []

    def display_alert(self, alert, is_new=False):
        """Display alert details"""
        tag = "[NEW ALERT]" if is_new else "[ACTIVE]"

        print("\n" + "!" * 100)
        print(f"{tag} {alert['severity']} - {alert['title']}")
        print("!" * 100)
        print(f"  Alert ID: {alert['id']}")
        print(f"  Datasource: {alert['datasource_id']} ({alert['datasource_engine']})")
        print(f"  Triggered: {alert['triggered_at']}")
        print(f"  Status: {alert['status']}")
        print(f"  Message: {alert['message']}")

        if alert.get('metric_value') is not None:
            print(f"  Metric Value: {alert['metric_value']} (threshold: {alert['threshold']})")

        print("!" * 100 + "\n")

    def monitor_iteration(self):
        """Single monitoring iteration"""
        self.iteration += 1
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print(f"[{timestamp}] Iteration #{self.iteration}")
        print(f"  Monitoring {len(self.registered_datasources)} datasource(s)...")

        # Evaluate alerts for each datasource
        total_triggered = 0
        for ds_id in self.registered_datasources:
            result = self.evaluate_alerts(ds_id)

            if result:
                alerts_count = result.get("alerts_triggered", 0)
                metrics_count = result.get("metrics_collected", 0)

                print(f"  [{ds_id}] Metrics: {metrics_count}, Alerts triggered: {alerts_count}")
                total_triggered += alerts_count

        # Get all active alerts
        active_alerts = self.get_active_alerts()

        print(f"  Total active alerts: {len(active_alerts)}")

        # Display new alerts
        new_alert_count = 0
        for alert in active_alerts:
            alert_id = alert['id']

            if alert_id not in self.known_alert_ids:
                # New alert
                self.display_alert(alert, is_new=True)
                self.known_alert_ids.add(alert_id)
                new_alert_count += 1

        if new_alert_count == 0 and len(active_alerts) > 0:
            print(f"  [INFO] No new alerts (all {len(active_alerts)} alerts already known)")

        # Check for resolved alerts
        current_alert_ids = {alert['id'] for alert in active_alerts}
        resolved_ids = self.known_alert_ids - current_alert_ids

        if resolved_ids:
            print(f"  [RESOLVED] {len(resolved_ids)} alert(s) auto-resolved:")
            for resolved_id in resolved_ids:
                print(f"    - {resolved_id}")
            self.known_alert_ids = current_alert_ids

        print()

    def start(self):
        """Start automated monitoring"""
        self.print_header()

        # Check backend health
        print("[CHECK] Verifying FastAPI backend is running...")
        if not self.check_backend_health():
            print("[ERROR] FastAPI backend is not running!")
            print("        Please start the backend with: myenv\\Scripts\\python.exe run.py")
            return

        print("[OK] FastAPI backend is running\n")

        # Register test datasources
        print("[SETUP] Registering datasources...")
        self.register_datasource(
            "pg-university",
            "postgres",
            "postgresql://postgres:postgres@localhost:5432/UniversityDB"
        )
        print()

        # Initial alert check
        print("[INIT] Performing initial alert check...")
        active_alerts = self.get_active_alerts()
        print(f"[INIT] Found {len(active_alerts)} existing active alert(s)\n")

        if active_alerts:
            for alert in active_alerts:
                self.display_alert(alert, is_new=False)
                self.known_alert_ids.add(alert['id'])

        print("=" * 100)
        print("[START] Starting continuous monitoring...")
        print("        Press Ctrl+C to stop")
        print("=" * 100 + "\n")

        # Monitoring loop
        while self.running:
            try:
                self.monitor_iteration()

                # Wait for next iteration
                for i in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                print(f"[ERROR] Monitoring iteration failed: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.interval)

        # Show final summary
        self.show_summary()

    def show_summary(self):
        """Show final monitoring summary"""
        print("\n" + "=" * 100)
        print("  Monitoring Summary")
        print("=" * 100)
        print(f"  Total Iterations: {self.iteration}")
        print(f"  Monitored Datasources: {len(self.registered_datasources)}")

        # Get final active alerts
        active_alerts = self.get_active_alerts()
        print(f"  Final Active Alerts: {len(active_alerts)}")

        if active_alerts:
            print("\n  Active Alerts:")
            for idx, alert in enumerate(active_alerts, 1):
                print(f"    {idx}. [{alert['severity']}] {alert['title']}")
                print(f"       Datasource: {alert['datasource_id']}")
                print(f"       Triggered: {alert['triggered_at']}")
                print(f"       Status: {alert['status']}\n")

        print("=" * 100 + "\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Automated alert monitoring via FastAPI backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor with default settings (10 second interval)
  python automated_alert_monitor.py

  # Monitor with 5 second interval
  python automated_alert_monitor.py --interval 5

  # Monitor with custom API URL
  python automated_alert_monitor.py --api http://localhost:8095
        """
    )

    parser.add_argument(
        '--api',
        type=str,
        default='http://127.0.0.1:8095',
        help='FastAPI base URL (default: http://127.0.0.1:8095)'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=10,
        help='Monitoring interval in seconds (default: 10)'
    )

    args = parser.parse_args()

    try:
        monitor = AutomatedAlertMonitor(
            api_base_url=args.api,
            interval_seconds=args.interval
        )
        monitor.start()
    except KeyboardInterrupt:
        print("\n\n[WARN] Monitoring interrupted by user")
    except Exception as e:
        print(f"\n\n[FATAL] Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
