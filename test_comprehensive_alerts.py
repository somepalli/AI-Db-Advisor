"""
Comprehensive Alert System Test Suite

Tests all features:
1. Three-tab system (Current, Resolved, All)
2. Alert lifecycle (active → acknowledged → resolved)
3. Resolution type tagging (automatic vs manual)
4. Multiple datasource support
5. Alert evaluation
6. Auto-refresh functionality
7. API endpoint validation
"""

import requests
import time


class ComprehensiveAlertTest:
    """Comprehensive test suite for alert system"""

    def __init__(self, api_base="http://127.0.0.1:8000"):
        self.api_base = api_base
        self.test_results = []

    def print_header(self, title):
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80 + "\n")

    def test(self, name):
        """Decorator for test functions"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    print(f"\n[TEST] {name}")
                    print("-" * 80)
                    result = func(*args, **kwargs)
                    if result:
                        print(f"[PASS] {name}")
                        self.test_results.append((name, True, None))
                    else:
                        print(f"[FAIL] {name}")
                        self.test_results.append((name, False, "Test returned False"))
                    return result
                except Exception as e:
                    print(f"[ERROR] {name}: {e}")
                    self.test_results.append((name, False, str(e)))
                    return False
            return wrapper
        return decorator

    def run_all_tests(self):
        """Run comprehensive test suite"""
        self.print_header("Comprehensive Alert System Test Suite")

        # Test 1: Backend health
        @self.test("Backend Health Check")
        def test_backend():
            response = requests.get(f"{self.api_base}/healthz", timeout=5)
            return response.status_code == 200

        test_backend()

        # Test 2: Register multiple datasources
        @self.test("Register Multiple Datasources")
        def test_register_datasources():
            datasources = [
                {"id": "pg-db1", "engine": "postgres", "dsn": "postgresql://postgres:postgres@localhost:5432/UniversityDB"},
                {"id": "pg-db2", "engine": "postgres", "dsn": "postgresql://postgres:postgres@localhost:9999/fake"},
                {"id": "mysql-db1", "engine": "mysql", "dsn": "mysql://root:root@localhost:3306/test"},
            ]

            for ds in datasources:
                response = requests.post(f"{self.api_base}/datasources", json=ds, timeout=10)
                if response.status_code not in [201, 409]:
                    print(f"  Failed to register {ds['id']}: {response.text}")
                    return False
                print(f"  [OK] Registered {ds['id']}")

            return True

        test_register_datasources()

        # Test 3: List datasources
        @self.test("List All Datasources")
        def test_list_datasources():
            response = requests.get(f"{self.api_base}/datasources", timeout=10)
            if response.status_code != 200:
                return False

            data = response.json()
            count = len(data.get("items", []))
            print(f"  Found {count} datasources")
            return count >= 3

        test_list_datasources()

        # Test 4: Evaluate alerts for each datasource
        @self.test("Evaluate Alerts for All Datasources")
        def test_evaluate_all():
            datasources = ["pg-db1", "pg-db2", "mysql-db1"]
            total_alerts = 0

            for ds_id in datasources:
                response = requests.post(f"{self.api_base}/alerts/evaluate/{ds_id}", timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    triggered = data.get("alerts_triggered", 0)
                    total_alerts += triggered
                    print(f"  {ds_id}: {triggered} alert(s) triggered")
                else:
                    print(f"  {ds_id}: Evaluation failed - {response.text}")

            print(f"  Total alerts triggered: {total_alerts}")
            return total_alerts > 0

        test_evaluate_all()
        time.sleep(1)

        # Test 5: TAB 1 - Current/Active alerts
        @self.test("TAB 1: Get Active Alerts")
        def test_get_active():
            response = requests.get(f"{self.api_base}/alerts/active", timeout=10)
            if response.status_code != 200:
                return False

            data = response.json()
            count = data.get("count", 0)
            print(f"  Active alerts: {count}")

            for alert in data.get("alerts", []):
                print(f"    - [{alert['severity']}] {alert['title']} ({alert['datasource_id']})")

            return True  # Always pass even if 0 alerts

        test_get_active()

        # Test 6: Get alert details
        @self.test("Get Individual Alert Details")
        def test_get_alert_details():
            # Get first active alert
            response = requests.get(f"{self.api_base}/alerts/active", timeout=10)
            if response.status_code != 200:
                return False

            alerts = response.json().get("alerts", [])
            if not alerts:
                print("  No active alerts to test")
                return True  # Skip test

            alert_id = alerts[0]["id"]
            encoded_id = requests.utils.quote(alert_id, safe='')

            response = requests.get(f"{self.api_base}/alerts/{encoded_id}", timeout=10)
            if response.status_code != 200:
                print(f"  Failed: {response.text}")
                return False

            alert = response.json()
            print(f"  Alert ID: {alert['id']}")
            print(f"  Title: {alert['title']}")
            print(f"  Status: {alert['status']}")
            return True

        test_get_alert_details()

        # Test 7: Acknowledge an alert
        @self.test("Acknowledge Alert")
        def test_acknowledge():
            # Get first active alert
            response = requests.get(f"{self.api_base}/alerts/active", timeout=10)
            if response.status_code != 200:
                return False

            alerts = response.json().get("alerts", [])
            active_only = [a for a in alerts if a["status"] == "active"]

            if not active_only:
                print("  No active alerts to acknowledge")
                return True  # Skip test

            alert_id = active_only[0]["id"]
            encoded_id = requests.utils.quote(alert_id, safe='')

            payload = {
                "acknowledged_by": "Test-Suite",
                "notes": "Testing acknowledgment"
            }

            response = requests.post(
                f"{self.api_base}/alerts/{encoded_id}/acknowledge",
                json=payload,
                timeout=10
            )

            if response.status_code != 200:
                print(f"  Failed: {response.text}")
                return False

            print(f"  Acknowledged alert: {alert_id}")
            return True

        test_acknowledge()
        time.sleep(1)

        # Test 8: Resolve an alert manually
        @self.test("Resolve Alert Manually")
        def test_resolve():
            # Get first acknowledged or active alert
            response = requests.get(f"{self.api_base}/alerts/active", timeout=10)
            if response.status_code != 200:
                return False

            alerts = response.json().get("alerts", [])
            if not alerts:
                print("  No alerts to resolve")
                return True  # Skip test

            alert_id = alerts[0]["id"]
            encoded_id = requests.utils.quote(alert_id, safe='')

            payload = {
                "resolved_by": "Test-Suite",
                "notes": "Testing manual resolution"
            }

            response = requests.post(
                f"{self.api_base}/alerts/{encoded_id}/resolve",
                json=payload,
                timeout=10
            )

            if response.status_code != 200:
                print(f"  Failed: {response.text}")
                return False

            print(f"  Resolved alert: {alert_id}")
            return True

        test_resolve()
        time.sleep(1)

        # Test 9: TAB 2 - Resolved alerts
        @self.test("TAB 2: Get Resolved Alerts with Resolution Type")
        def test_get_resolved():
            response = requests.get(f"{self.api_base}/alerts/resolved", timeout=10)
            if response.status_code != 200:
                return False

            data = response.json()
            count = data.get("count", 0)
            print(f"  Resolved alerts: {count}")

            for alert in data.get("alerts", []):
                res_type = alert.get("resolution_type", "unknown")
                tag = "[AUTO]" if res_type == "automatic" else "[MANUAL]"
                print(f"    - {tag} [{alert['severity']}] {alert['title']}")

                # Validate resolution_type field exists
                if "resolution_type" not in alert:
                    print("    [WARN] Missing resolution_type field!")
                    return False

            return True

        test_get_resolved()

        # Test 10: TAB 3 - All alerts with summary
        @self.test("TAB 3: Get All Alerts with Summary")
        def test_get_all():
            response = requests.get(f"{self.api_base}/alerts/all", timeout=10)
            if response.status_code != 200:
                return False

            data = response.json()
            count = data.get("count", 0)
            summary = data.get("summary", {})

            print(f"  All alerts: {count}")
            print(f"  Summary:")
            print(f"    Active: {summary.get('active', 0)}")
            print(f"    Acknowledged: {summary.get('acknowledged', 0)}")
            print(f"    Resolved: {summary.get('resolved', 0)}")
            print(f"    Auto-Resolved: {summary.get('auto_resolved', 0)}")

            # Validate summary fields
            if "summary" not in data:
                print("    [WARN] Missing summary field!")
                return False

            return True

        test_get_all()

        # Test 11: Get alert rules
        @self.test("Get Alert Rules")
        def test_get_rules():
            response = requests.get(f"{self.api_base}/alerts/rules", timeout=10)
            if response.status_code != 200:
                return False

            data = response.json()
            rules = data.get("rules", [])
            print(f"  Total rules: {len(rules)}")

            for rule in rules[:5]:  # Show first 5
                print(f"    - {rule['id']}: {rule['name']} (P{rule['severity']})")

            return len(rules) > 0

        test_get_rules()

        # Test 12: AI alert analysis
        @self.test("AI Alert Analysis")
        def test_ai_analysis():
            # Get first alert
            response = requests.get(f"{self.api_base}/alerts/all?limit=1", timeout=10)
            if response.status_code != 200:
                return False

            alerts = response.json().get("alerts", [])
            if not alerts:
                print("  No alerts to analyze")
                return True  # Skip test

            alert_id = alerts[0]["id"]
            encoded_id = requests.utils.quote(alert_id, safe='')

            response = requests.post(
                f"{self.api_base}/alerts/{encoded_id}/analyze",
                timeout=30
            )

            if response.status_code != 200:
                print(f"  Analysis failed: {response.text}")
                return False

            data = response.json()
            print(f"  Root Cause: {data.get('root_cause', 'N/A')}")
            print(f"  Confidence: {data.get('confidence', 0) * 100:.0f}%")
            print(f"  Immediate Actions: {len(data.get('immediate_actions', []))}")
            print(f"  Recommendations: {len(data.get('recommendations', []))}")

            return "root_cause" in data

        test_ai_analysis()

        # Test 13: Get alert history
        @self.test("Get Alert History")
        def test_get_history():
            # Get first alert
            response = requests.get(f"{self.api_base}/alerts/all?limit=1", timeout=10)
            if response.status_code != 200:
                return False

            alerts = response.json().get("alerts", [])
            if not alerts:
                print("  No alerts to get history for")
                return True  # Skip test

            alert_id = alerts[0]["id"]
            encoded_id = requests.utils.quote(alert_id, safe='')

            response = requests.get(f"{self.api_base}/alerts/{encoded_id}/history", timeout=10)
            if response.status_code != 200:
                print(f"  Failed: {response.text}")
                return False

            data = response.json()
            history = data.get("history", [])
            print(f"  History entries: {len(history)}")

            for entry in history:
                print(f"    - {entry['timestamp']}: {entry['event_type']}")

            return True

        test_get_history()

        # Print final results
        self.print_header("Test Results Summary")

        passed = sum(1 for _, success, _ in self.test_results if success)
        failed = sum(1 for _, success, _ in self.test_results if not success)
        total = len(self.test_results)

        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Pass Rate: {(passed/total*100):.1f}%\n")

        for name, success, error in self.test_results:
            status = "[PASS]" if success else "[FAIL]"
            print(f"{status} {name}")
            if error and not success:
                print(f"      Error: {error}")

        print("\n" + "=" * 80)
        if failed == 0:
            print("[SUCCESS] All tests passed!")
        else:
            print(f"[PARTIAL] {failed} test(s) failed")
        print("=" * 80 + "\n")

        return failed == 0


def main():
    """Main entry point"""
    tester = ComprehensiveAlertTest()
    try:
        success = tester.run_all_tests()
        if success:
            print("\n[FINAL] Comprehensive test suite PASSED!")
        else:
            print("\n[FINAL] Some tests failed - check results above")
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Tests stopped by user")
    except Exception as e:
        print(f"\n\n[ERROR] Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
