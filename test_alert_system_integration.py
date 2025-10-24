"""
Comprehensive Alert System Integration Tests

Tests the complete alert system workflow:
1. Backend API endpoints
2. Alert triggering and lifecycle
3. Metric collection
4. Auto-resolution
5. AI analysis

Run with: python test_alert_system_integration.py
"""

import requests
import time
import json
from datetime import datetime


class AlertSystemTester:
    """Comprehensive alert system test suite"""

    def __init__(self, api_base_url="http://127.0.0.1:8000"):
        self.api_base = api_base_url
        self.test_results = []
        self.test_datasource_id = f"test-db-{int(time.time())}"

    def log_test(self, test_name, passed, message=""):
        """Log test result"""
        status = "[PASS]" if passed else "[FAIL]"
        result = {
            "test": test_name,
            "passed": passed,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        print(f"{status} {test_name}")
        if message:
            print(f"      {message}")

    def print_header(self, title):
        """Print section header"""
        print("\n" + "=" * 100)
        print(f"  {title}")
        print("=" * 100 + "\n")

    def test_backend_health(self):
        """Test 1: Backend Health Check"""
        try:
            response = requests.get(f"{self.api_base}/healthz", timeout=5)
            passed = response.status_code == 200
            self.log_test(
                "Backend Health Check",
                passed,
                f"Status: {response.status_code}"
            )
            return passed
        except Exception as e:
            self.log_test("Backend Health Check", False, f"Error: {e}")
            return False

    def test_datasource_registration(self):
        """Test 2: Datasource Registration"""
        try:
            payload = {
                "id": self.test_datasource_id,
                "engine": "postgres",
                "dsn": "postgresql://postgres:postgres@localhost:5432/UniversityDB"
            }

            response = requests.post(
                f"{self.api_base}/datasources",
                json=payload,
                timeout=10
            )

            passed = response.status_code in [201, 409]  # 201 = created, 409 = already exists
            self.log_test(
                "Datasource Registration",
                passed,
                f"Status: {response.status_code}, Response: {response.text}"
            )
            return passed
        except Exception as e:
            self.log_test("Datasource Registration", False, f"Error: {e}")
            return False

    def test_alert_rules_endpoint(self):
        """Test 3: Get Alert Rules"""
        try:
            response = requests.get(f"{self.api_base}/alerts/rules", timeout=10)
            passed = response.status_code == 200

            if passed:
                data = response.json()
                rule_count = data.get("count", 0)
                self.log_test(
                    "Get Alert Rules",
                    passed,
                    f"Found {rule_count} alert rules"
                )
            else:
                self.log_test("Get Alert Rules", False, f"Status: {response.status_code}")

            return passed
        except Exception as e:
            self.log_test("Get Alert Rules", False, f"Error: {e}")
            return False

    def test_manual_alert_evaluation(self):
        """Test 4: Manual Alert Evaluation"""
        try:
            response = requests.post(
                f"{self.api_base}/alerts/evaluate/{self.test_datasource_id}",
                timeout=15
            )

            passed = response.status_code == 200

            if passed:
                data = response.json()
                alerts_triggered = data.get("alerts_triggered", 0)
                metrics_collected = data.get("metrics_collected", 0)

                self.log_test(
                    "Manual Alert Evaluation",
                    passed,
                    f"Metrics: {metrics_collected}, Alerts: {alerts_triggered}"
                )

                # Store for later tests
                self.evaluation_result = data
            else:
                self.log_test(
                    "Manual Alert Evaluation",
                    False,
                    f"Status: {response.status_code}, Response: {response.text}"
                )

            return passed
        except Exception as e:
            self.log_test("Manual Alert Evaluation", False, f"Error: {e}")
            return False

    def test_get_active_alerts(self):
        """Test 5: Get Active Alerts"""
        try:
            response = requests.get(f"{self.api_base}/alerts/active", timeout=10)
            passed = response.status_code == 200

            if passed:
                data = response.json()
                alert_count = data.get("count", 0)
                alerts = data.get("alerts", [])

                self.log_test(
                    "Get Active Alerts",
                    passed,
                    f"Found {alert_count} active alert(s)"
                )

                # Store alerts for later tests
                self.active_alerts = alerts

                # Display alerts
                if alerts:
                    for idx, alert in enumerate(alerts, 1):
                        print(f"      Alert {idx}: [{alert['severity']}] {alert['title']}")
                        print(f"                  Datasource: {alert['datasource_id']}")
                        print(f"                  Status: {alert['status']}")
            else:
                self.log_test("Get Active Alerts", False, f"Status: {response.status_code}")

            return passed
        except Exception as e:
            self.log_test("Get Active Alerts", False, f"Error: {e}")
            return False

    def test_alert_details(self):
        """Test 6: Get Alert Details"""
        if not hasattr(self, 'active_alerts') or not self.active_alerts:
            self.log_test("Get Alert Details", False, "No active alerts to test")
            return False

        try:
            alert_id = self.active_alerts[0]['id']
            response = requests.get(
                f"{self.api_base}/alerts/{alert_id}",
                timeout=10
            )

            passed = response.status_code == 200

            if passed:
                data = response.json()
                self.log_test(
                    "Get Alert Details",
                    passed,
                    f"Retrieved details for alert: {alert_id}"
                )
            else:
                self.log_test("Get Alert Details", False, f"Status: {response.status_code}")

            return passed
        except Exception as e:
            self.log_test("Get Alert Details", False, f"Error: {e}")
            return False

    def test_acknowledge_alert(self):
        """Test 7: Acknowledge Alert"""
        if not hasattr(self, 'active_alerts') or not self.active_alerts:
            self.log_test("Acknowledge Alert", False, "No active alerts to test")
            return False

        try:
            alert_id = self.active_alerts[0]['id']
            payload = {
                "acknowledged_by": "test-user",
                "notes": "Testing acknowledgment"
            }

            response = requests.post(
                f"{self.api_base}/alerts/{alert_id}/acknowledge",
                json=payload,
                timeout=10
            )

            passed = response.status_code == 200

            if passed:
                data = response.json()
                self.log_test(
                    "Acknowledge Alert",
                    passed,
                    f"Acknowledged by: {data.get('acknowledged_by', 'N/A')}"
                )
            else:
                self.log_test("Acknowledge Alert", False, f"Status: {response.status_code}")

            return passed
        except Exception as e:
            self.log_test("Acknowledge Alert", False, f"Error: {e}")
            return False

    def test_ai_analysis(self):
        """Test 8: AI Analysis for P1 Alert"""
        if not hasattr(self, 'active_alerts') or not self.active_alerts:
            self.log_test("AI Analysis", False, "No active alerts to test")
            return False

        # Find a P1 alert
        p1_alerts = [a for a in self.active_alerts if a['severity'] == 'P1']

        if not p1_alerts:
            self.log_test("AI Analysis", False, "No P1 alerts available")
            return False

        try:
            alert_id = p1_alerts[0]['id']
            response = requests.post(
                f"{self.api_base}/alerts/{alert_id}/analyze",
                timeout=30  # AI analysis may take longer
            )

            passed = response.status_code == 200

            if passed:
                data = response.json()
                root_cause = data.get("root_cause", "N/A")
                confidence = data.get("confidence", 0)
                rec_count = len(data.get("recommendations", []))

                self.log_test(
                    "AI Analysis",
                    passed,
                    f"Confidence: {confidence*100:.1f}%, Recommendations: {rec_count}"
                )

                print(f"      Root Cause: {root_cause[:80]}...")
            else:
                self.log_test("AI Analysis", False, f"Status: {response.status_code}")

            return passed
        except Exception as e:
            self.log_test("AI Analysis", False, f"Error: {e}")
            return False

    def test_alert_history(self):
        """Test 9: Get Alert History"""
        try:
            response = requests.get(
                f"{self.api_base}/alerts/history?limit=10",
                timeout=10
            )

            passed = response.status_code == 200

            if passed:
                data = response.json()
                alert_count = data.get("count", 0)
                self.log_test(
                    "Get Alert History",
                    passed,
                    f"Found {alert_count} historical alert(s)"
                )
            else:
                self.log_test("Get Alert History", False, f"Status: {response.status_code}")

            return passed
        except Exception as e:
            self.log_test("Get Alert History", False, f"Error: {e}")
            return False

    def test_monitoring_status(self):
        """Test 10: Get Monitoring Status"""
        try:
            response = requests.get(
                f"{self.api_base}/alerts/monitoring/status",
                timeout=10
            )

            passed = response.status_code == 200

            if passed:
                data = response.json()
                monitored_count = data.get("total_monitored", 0)
                self.log_test(
                    "Get Monitoring Status",
                    passed,
                    f"Monitored datasources: {monitored_count}"
                )
            else:
                self.log_test("Get Monitoring Status", False, f"Status: {response.status_code}")

            return passed
        except Exception as e:
            self.log_test("Get Monitoring Status", False, f"Error: {e}")
            return False

    def test_database_down_alert(self):
        """Test 11: Database Down Alert (if DB is actually down)"""
        if not hasattr(self, 'active_alerts'):
            self.log_test("Database Down Alert", False, "No alerts retrieved")
            return False

        db_down_alerts = [
            a for a in self.active_alerts
            if a['rule_id'] == 'db_down' and a['datasource_id'] == self.test_datasource_id
        ]

        if db_down_alerts:
            alert = db_down_alerts[0]
            passed = (
                alert['severity'] == 'P1' and
                alert['status'] in ['active', 'acknowledged'] and
                alert['metric_value'] == 0
            )

            self.log_test(
                "Database Down Alert Validation",
                passed,
                f"DB Down alert found and validated (Severity: {alert['severity']}, Status: {alert['status']})"
            )
        else:
            self.log_test(
                "Database Down Alert Validation",
                True,
                "No DB down alert (database is UP)"
            )
            passed = True

        return passed

    def run_all_tests(self):
        """Run all tests"""
        self.print_header("AI DB Advisor - Comprehensive Alert System Integration Tests")

        print("[INFO] Starting test suite...")
        print(f"[INFO] API Base URL: {self.api_base}")
        print(f"[INFO] Test Datasource ID: {self.test_datasource_id}\n")

        # Run tests in order
        tests = [
            ("Backend Health", self.test_backend_health),
            ("Datasource Registration", self.test_datasource_registration),
            ("Alert Rules Endpoint", self.test_alert_rules_endpoint),
            ("Manual Alert Evaluation", self.test_manual_alert_evaluation),
            ("Get Active Alerts", self.test_get_active_alerts),
            ("Get Alert Details", self.test_alert_details),
            ("Acknowledge Alert", self.test_acknowledge_alert),
            ("AI Analysis", self.test_ai_analysis),
            ("Get Alert History", self.test_alert_history),
            ("Monitoring Status", self.test_monitoring_status),
            ("Database Down Alert", self.test_database_down_alert),
        ]

        print("=" * 100)
        print("Running Tests...")
        print("=" * 100 + "\n")

        for test_name, test_func in tests:
            try:
                test_func()
            except Exception as e:
                self.log_test(test_name, False, f"Unexpected error: {e}")

            time.sleep(0.5)  # Small delay between tests

        # Show summary
        self.show_summary()

    def show_summary(self):
        """Show test summary"""
        self.print_header("Test Summary")

        passed_count = sum(1 for r in self.test_results if r['passed'])
        failed_count = len(self.test_results) - passed_count
        pass_rate = (passed_count / len(self.test_results) * 100) if self.test_results else 0

        print(f"Total Tests: {len(self.test_results)}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {failed_count}")
        print(f"Pass Rate: {pass_rate:.1f}%\n")

        if failed_count > 0:
            print("Failed Tests:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  - {result['test']}: {result['message']}")
            print()

        print("=" * 100 + "\n")

        # Return exit code
        return 0 if failed_count == 0 else 1


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive alert system integration tests")
    parser.add_argument(
        '--api',
        type=str,
        default='http://127.0.0.1:8000',
        help='FastAPI base URL (default: http://127.0.0.1:8000)'
    )

    args = parser.parse_args()

    tester = AlertSystemTester(api_base_url=args.api)
    exit_code = tester.run_all_tests()

    exit(exit_code)


if __name__ == "__main__":
    main()
