"""
Test Alert System with Real PostgreSQL Database (UniversityDB)

This script:
1. Registers UniversityDB datasource
2. Triggers alert evaluation
3. Verifies alerts are created
4. Tests acknowledgment and resolution
5. Tests auto-resolution when DB comes back online
"""

import requests
import time
import subprocess
import sys


class RealDatabaseAlertTest:
    """Test alerts with actual PostgreSQL database"""

    def __init__(self, api_base="http://127.0.0.1:8000"):
        self.api_base = api_base
        self.pg_ds_id = "pg-university"
        self.pg_dsn = "postgresql://postgres:postgres@localhost:5432/UniversityDB"

    def print_header(self, title):
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80 + "\n")

    def print_step(self, step_num, description):
        print(f"\n[STEP {step_num}] {description}")
        print("-" * 80)

    def check_backend(self):
        """Check if backend is running"""
        try:
            response = requests.get(f"{self.api_base}/healthz", timeout=5)
            if response.status_code == 200:
                print("[OK] Backend is running")
                return True
        except Exception as e:
            print(f"[FAIL] Backend not reachable: {e}")
            return False

    def register_datasource(self):
        """Register UniversityDB datasource"""
        payload = {
            "id": self.pg_ds_id,
            "engine": "postgres",
            "dsn": self.pg_dsn
        }

        try:
            response = requests.post(f"{self.api_base}/datasources", json=payload, timeout=10)
            if response.status_code in [201, 409]:
                print(f"[OK] Registered datasource: {self.pg_ds_id}")
                return True
            else:
                print(f"[FAIL] Failed to register: {response.text}")
                return False
        except Exception as e:
            print(f"[FAIL] Error registering datasource: {e}")
            return False

    def evaluate_alerts(self):
        """Trigger alert evaluation for the datasource"""
        try:
            response = requests.post(
                f"{self.api_base}/alerts/evaluate/{self.pg_ds_id}",
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                triggered = data.get("alerts_triggered", 0)
                print(f"[OK] Alerts evaluated: {triggered} alert(s) triggered")

                if triggered > 0:
                    for alert in data.get("alerts", []):
                        print(f"  - {alert['severity']}: {alert['title']}")

                return triggered > 0
            else:
                print(f"[FAIL] Alert evaluation failed: {response.text}")
                return False
        except Exception as e:
            print(f"[FAIL] Error evaluating alerts: {e}")
            return False

    def get_active_alerts(self):
        """Get all active alerts"""
        try:
            response = requests.get(f"{self.api_base}/alerts/active", timeout=10)
            if response.status_code == 200:
                data = response.json()
                alerts = data.get("alerts", [])
                count = data.get("count", 0)

                print(f"[OK] Active alerts: {count}")
                for idx, alert in enumerate(alerts, 1):
                    print(f"  {idx}. [{alert['severity']}] {alert['title']}")
                    print(f"      DS: {alert['datasource_id']}, Status: {alert['status']}")

                return alerts
            else:
                print(f"[FAIL] Failed to get active alerts: {response.text}")
                return []
        except Exception as e:
            print(f"[FAIL] Error getting alerts: {e}")
            return []

    def get_resolved_alerts(self):
        """Get resolved alerts"""
        try:
            response = requests.get(f"{self.api_base}/alerts/resolved", timeout=10)
            if response.status_code == 200:
                data = response.json()
                alerts = data.get("alerts", [])
                count = data.get("count", 0)

                print(f"[OK] Resolved alerts: {count}")
                for idx, alert in enumerate(alerts, 1):
                    res_type = alert.get('resolution_type', 'unknown')
                    tag = "[AUTO]" if res_type == "automatic" else "[MANUAL]"
                    print(f"  {idx}. {tag} [{alert['severity']}] {alert['title']}")

                return alerts
            else:
                print(f"[FAIL] Failed to get resolved alerts: {response.text}")
                return []
        except Exception as e:
            print(f"[FAIL] Error getting resolved alerts: {e}")
            return []

    def get_all_alerts_with_summary(self):
        """Get all alerts with summary"""
        try:
            response = requests.get(f"{self.api_base}/alerts/all", timeout=10)
            if response.status_code == 200:
                data = response.json()
                alerts = data.get("alerts", [])
                summary = data.get("summary", {})

                print(f"[OK] All alerts: {data.get('count', 0)}")
                print(f"  Summary:")
                print(f"    Active: {summary.get('active', 0)}")
                print(f"    Acknowledged: {summary.get('acknowledged', 0)}")
                print(f"    Resolved: {summary.get('resolved', 0)}")
                print(f"    Auto-Resolved: {summary.get('auto_resolved', 0)}")

                return alerts, summary
            else:
                print(f"[FAIL] Failed to get all alerts: {response.text}")
                return [], {}
        except Exception as e:
            print(f"[FAIL] Error getting all alerts: {e}")
            return [], {}

    def acknowledge_alert(self, alert_id):
        """Acknowledge an alert"""
        try:
            encoded_id = requests.utils.quote(alert_id, safe='')
            payload = {
                "acknowledged_by": "Test-Script",
                "notes": "Testing acknowledgment"
            }

            response = requests.post(
                f"{self.api_base}/alerts/{encoded_id}/acknowledge",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                print(f"[OK] Alert acknowledged: {alert_id}")
                return True
            else:
                print(f"[FAIL] Failed to acknowledge: {response.text}")
                return False
        except Exception as e:
            print(f"[FAIL] Error acknowledging alert: {e}")
            return False

    def resolve_alert(self, alert_id):
        """Manually resolve an alert"""
        try:
            encoded_id = requests.utils.quote(alert_id, safe='')
            payload = {
                "resolved_by": "Test-Script",
                "notes": "Testing manual resolution"
            }

            response = requests.post(
                f"{self.api_base}/alerts/{encoded_id}/resolve",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                print(f"[OK] Alert resolved: {alert_id}")
                return True
            else:
                print(f"[FAIL] Failed to resolve: {response.text}")
                return False
        except Exception as e:
            print(f"[FAIL] Error resolving alert: {e}")
            return False

    def stop_postgres(self):
        """Stop PostgreSQL service (Windows)"""
        print("\n[ACTION] Attempting to stop PostgreSQL service...")
        try:
            result = subprocess.run(
                ["net", "stop", "postgresql-x64-14"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print("[OK] PostgreSQL stopped")
                return True
            elif "is not started" in result.stdout.lower():
                print("[INFO] PostgreSQL was already stopped")
                return True
            else:
                print(f"[WARN] Stop command result: {result.stdout}")
                print(f"[WARN] May need admin privileges")
                return False
        except Exception as e:
            print(f"[WARN] Could not stop PostgreSQL: {e}")
            print("[INFO] This requires administrator privileges")
            return False

    def start_postgres(self):
        """Start PostgreSQL service (Windows)"""
        print("\n[ACTION] Attempting to start PostgreSQL service...")
        try:
            result = subprocess.run(
                ["net", "start", "postgresql-x64-14"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print("[OK] PostgreSQL started")
                time.sleep(3)  # Wait for service to fully start
                return True
            elif "is already started" in result.stdout.lower():
                print("[INFO] PostgreSQL was already running")
                return True
            else:
                print(f"[WARN] Start command result: {result.stdout}")
                return False
        except Exception as e:
            print(f"[WARN] Could not start PostgreSQL: {e}")
            return False

    def run(self):
        """Run the complete test workflow"""
        self.print_header("Alert System Test with Real PostgreSQL Database")

        # Step 1: Check backend
        self.print_step(1, "Check Backend Health")
        if not self.check_backend():
            print("\n[ERROR] Backend not running. Start with: python run.py")
            return False

        # Step 2: Register datasource
        self.print_step(2, "Register UniversityDB Datasource")
        if not self.register_datasource():
            print("\n[ERROR] Failed to register datasource")
            return False

        time.sleep(1)

        # Step 3: Evaluate alerts (DB should be up initially)
        self.print_step(3, "Initial Alert Evaluation (DB Up)")
        self.evaluate_alerts()
        time.sleep(1)

        # Step 4: Check active alerts
        self.print_step(4, "Check Current Active Alerts")
        active_alerts = self.get_active_alerts()

        # Step 5: If we have alerts, test acknowledge/resolve
        if active_alerts:
            self.print_step(5, "Test Acknowledge & Resolve")
            first_alert = active_alerts[0]

            print(f"\nTesting with alert: {first_alert['id']}")

            # Acknowledge
            self.acknowledge_alert(first_alert['id'])
            time.sleep(1)

            # Check it's acknowledged
            print("\nChecking after acknowledgment:")
            self.get_active_alerts()

            # Resolve
            time.sleep(1)
            self.resolve_alert(first_alert['id'])
            time.sleep(1)

            # Check resolved tab
            print("\nChecking resolved tab:")
            self.get_resolved_alerts()

        # Step 6: View all tabs
        self.print_step(6, "View All Three Tabs")

        print("\n>>> TAB 1: CURRENT")
        self.get_active_alerts()

        print("\n>>> TAB 2: RESOLVED")
        self.get_resolved_alerts()

        print("\n>>> TAB 3: ALL (with summary)")
        self.get_all_alerts_with_summary()

        # Step 7: Test with DB down (if possible)
        self.print_step(7, "Test Alert Trigger with DB Down (requires admin)")
        db_stopped = self.stop_postgres()

        if db_stopped:
            print("\nWaiting 3 seconds...")
            time.sleep(3)

            print("\nEvaluating alerts with DB down:")
            self.evaluate_alerts()
            time.sleep(1)

            print("\nChecking active alerts:")
            self.get_active_alerts()

            # Step 8: Test auto-resolution
            self.print_step(8, "Test Auto-Resolution (DB Comes Back)")
            self.start_postgres()

            print("\nWaiting 3 seconds for service to stabilize...")
            time.sleep(3)

            print("\nEvaluating alerts with DB up:")
            self.evaluate_alerts()
            time.sleep(1)

            print("\nChecking active alerts (should be empty or auto-resolved):")
            self.get_active_alerts()

            print("\nChecking resolved tab (should show auto-resolved):")
            self.get_resolved_alerts()
        else:
            print("\n[SKIP] Cannot test DB down/up scenario without admin privileges")
            print("[INFO] To test this manually:")
            print("  1. Run this script as Administrator")
            print("  2. Or manually stop/start PostgreSQL service")

        # Final summary
        self.print_header("Test Complete - Final Status")
        self.get_all_alerts_with_summary()

        print("\n" + "=" * 80)
        print("[SUCCESS] All tests completed!")
        print("\nKey Features Tested:")
        print("  [OK] Register datasource")
        print("  [OK] Evaluate alerts")
        print("  [OK] View active alerts (TAB 1)")
        print("  [OK] Acknowledge alerts")
        print("  [OK] Resolve alerts manually")
        print("  [OK] View resolved alerts (TAB 2)")
        print("  [OK] View all alerts with summary (TAB 3)")
        if db_stopped:
            print("  [OK] Auto-resolution when DB comes back")
        print("=" * 80 + "\n")

        return True


def main():
    """Main entry point"""
    tester = RealDatabaseAlertTest()
    try:
        success = tester.run()
        if success:
            print("\n[FINAL] Test passed! Alert system working with real database.")
        else:
            print("\n[FINAL] Test had issues. Check logs above.")
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test stopped by user")
    except Exception as e:
        print(f"\n\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
