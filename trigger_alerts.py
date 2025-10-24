"""
Alert Testing Script - Trigger various alerts for demonstration

This script generates different types of load to trigger AlertManager alerts.
"""
import requests
import time
import threading
import argparse
from typing import Callable

# API endpoints
FASTAPI_URL = "http://127.0.0.1:8000"
MCP_URL = "http://localhost:3000"


class AlertTrigger:
    """Base class for triggering alerts"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.running = False

    def execute(self, duration: int = 180):
        """Execute the alert trigger for specified duration (seconds)"""
        raise NotImplementedError


class HighErrorRateTrigger(AlertTrigger):
    """Trigger HighErrorRate alert by making requests to non-existent endpoints"""

    def __init__(self):
        super().__init__(
            "High Error Rate",
            "Triggers 5xx errors by requesting non-existent endpoints"
        )

    def execute(self, duration: int = 180):
        print(f"\n[TRIGGER] {self.name}")
        print(f"   Description: {self.description}")
        print(f"   Duration: {duration}s")
        print(f"   Expected Alert: HighErrorRate (after 2 minutes)")
        print(f"   Threshold: >5% error rate\n")

        self.running = True
        start_time = time.time()
        errors = 0
        successes = 0

        while time.time() - start_time < duration and self.running:
            try:
                # Make some successful requests
                response = requests.get(f"{FASTAPI_URL}/healthz", timeout=5)
                if response.status_code == 200:
                    successes += 1

                # Make many error requests to non-existent endpoints
                for i in range(5):
                    try:
                        requests.get(f"{FASTAPI_URL}/non-existent-endpoint-{i}", timeout=5)
                    except:
                        pass
                    errors += 1

                # Print progress every 10 seconds
                elapsed = time.time() - start_time
                if int(elapsed) % 10 == 0:
                    total = errors + successes
                    error_rate = (errors / total * 100) if total > 0 else 0
                    print(f"   [{int(elapsed)}s] Error rate: {error_rate:.1f}% ({errors} errors, {successes} success)")

                time.sleep(0.1)  # Small delay between requests

            except Exception as e:
                print(f"   Error: {e}")
                time.sleep(1)

        print(f"\n   [DONE] Completed! Generated {errors} errors and {successes} successful requests")
        print(f"   [VIEW] Check Prometheus: http://localhost:9090/alerts")
        print(f"   [VIEW] Check Grafana: http://localhost:3001\n")


class HighLoadTrigger(AlertTrigger):
    """Trigger HighRequestLoad alert by making many concurrent requests"""

    def __init__(self):
        super().__init__(
            "High Request Load",
            "Generates >100 requests/second"
        )

    def execute(self, duration: int = 180):
        print(f"\n[TRIGGER] Triggering: {self.name}")
        print(f"   Description: {self.description}")
        print(f"   Duration: {duration}s")
        print(f"   Expected Alert: HighRequestLoad (after 2 minutes)")
        print(f"   Threshold: >100 req/sec\n")

        self.running = True
        start_time = time.time()
        request_count = 0

        def make_requests():
            nonlocal request_count
            while time.time() - start_time < duration and self.running:
                try:
                    requests.get(f"{FASTAPI_URL}/healthz", timeout=5)
                    request_count += 1
                    time.sleep(0.001)  # Very small delay
                except:
                    pass

        # Launch multiple threads
        threads = []
        num_threads = 20
        print(f"   Launching {num_threads} concurrent threads...")

        for i in range(num_threads):
            t = threading.Thread(target=make_requests)
            t.daemon = True
            t.start()
            threads.append(t)

        # Monitor progress
        last_count = 0
        while time.time() - start_time < duration and self.running:
            time.sleep(10)
            elapsed = time.time() - start_time
            current_rate = (request_count - last_count) / 10
            print(f"   [{int(elapsed)}s] Request rate: {current_rate:.1f} req/sec (Total: {request_count})")
            last_count = request_count

        self.running = False

        # Wait for threads
        for t in threads:
            t.join(timeout=2)

        total_time = time.time() - start_time
        avg_rate = request_count / total_time
        print(f"\n   [DONE] Completed! Generated {request_count} requests")
        print(f"   Average rate: {avg_rate:.1f} req/sec")
        print(f"   [VIEW] Check Prometheus: http://localhost:9090/alerts")
        print(f"   [VIEW] Check Grafana: http://localhost:3001\n")


class SlowResponseTrigger(AlertTrigger):
    """Trigger SlowAPIResponse alert by making slow requests"""

    def __init__(self):
        super().__init__(
            "Slow API Response",
            "Makes requests that take >2 seconds"
        )

    def execute(self, duration: int = 240):
        print(f"\n[TRIGGER] Triggering: {self.name}")
        print(f"   Description: {self.description}")
        print(f"   Duration: {duration}s")
        print(f"   Expected Alert: SlowAPIResponse (after 3 minutes)")
        print(f"   Threshold: p95 > 2 seconds\n")
        print(f"   Note: This requires an endpoint that processes slowly")
        print(f"   Making requests with query parameters to simulate load...\n")

        self.running = True
        start_time = time.time()
        request_count = 0

        while time.time() - start_time < duration and self.running:
            try:
                # Make requests to datasources endpoint which might be slower
                response = requests.get(f"{FASTAPI_URL}/datasources", timeout=10)
                request_count += 1

                elapsed = time.time() - start_time
                if int(elapsed) % 15 == 0:
                    print(f"   [{int(elapsed)}s] Requests made: {request_count}")

                time.sleep(0.5)  # Moderate delay

            except Exception as e:
                pass

        print(f"\n   [DONE] Completed! Made {request_count} requests")
        print(f"   [VIEW] Check Prometheus: http://localhost:9090/alerts")
        print(f"   [VIEW] Check Grafana: http://localhost:3001\n")


class ServiceDownTrigger(AlertTrigger):
    """Simulate FastAPIDown alert"""

    def __init__(self):
        super().__init__(
            "Service Down Simulation",
            "Instructions to trigger service down alerts"
        )

    def execute(self, duration: int = 60):
        print(f"\n[TRIGGER] Alert Scenario: {self.name}")
        print(f"   Description: {self.description}\n")
        print(f"   To trigger FastAPIDown alert:")
        print(f"   1. Stop the FastAPI backend (Ctrl+C)")
        print(f"   2. Wait 1 minute")
        print(f"   3. Check Prometheus: http://localhost:9090/alerts")
        print(f"   4. Check AlertManager: http://localhost:9093")
        print(f"   5. Check Grafana: http://localhost:3001")
        print(f"\n   To trigger MCPBridgeDown alert:")
        print(f"   1. Stop the MCP bridge (Ctrl+C)")
        print(f"   2. Wait 1 minute")
        print(f"   3. Check alerts as above")
        print(f"\n   To trigger PostgreSQLDown alert:")
        print(f"   1. Stop PostgreSQL service")
        print(f"   2. Wait 1 minute")
        print(f"   3. Check alerts as above\n")


def main():
    parser = argparse.ArgumentParser(
        description="Trigger AlertManager alerts for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Trigger high error rate for 3 minutes
  python trigger_alerts.py --scenario errors --duration 180

  # Trigger high load for 2 minutes
  python trigger_alerts.py --scenario load --duration 120

  # Show all scenarios
  python trigger_alerts.py --list
        """
    )

    parser.add_argument(
        '--scenario',
        choices=['errors', 'load', 'slow', 'down', 'all'],
        default='errors',
        help='Alert scenario to trigger'
    )

    parser.add_argument(
        '--duration',
        type=int,
        default=180,
        help='Duration in seconds (default: 180)'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available scenarios'
    )

    args = parser.parse_args()

    scenarios = {
        'errors': HighErrorRateTrigger(),
        'load': HighLoadTrigger(),
        'slow': SlowResponseTrigger(),
        'down': ServiceDownTrigger(),
    }

    if args.list:
        print("\n[LIST] Available Alert Scenarios:\n")
        for key, trigger in scenarios.items():
            print(f"  {key:10s} - {trigger.description}")
        print("\n")
        return

    print("=" * 80)
    print("ALERT TESTING SCRIPT")
    print("=" * 80)
    print("\n[WARNING]  This script will generate artificial load to trigger alerts")
    print("    Monitor alerts at:")
    print("    - Prometheus: http://localhost:9090/alerts")
    print("    - AlertManager: http://localhost:9093")
    print("    - Grafana: http://localhost:3001")
    print()

    if args.scenario == 'all':
        print("Running all scenarios sequentially...\n")
        for key in ['errors', 'load', 'slow']:
            scenarios[key].execute(duration=120)
            print("\n   Waiting 30 seconds before next scenario...")
            time.sleep(30)
    else:
        scenarios[args.scenario].execute(duration=args.duration)

    print("=" * 80)
    print("ALERT TESTING COMPLETE")
    print("=" * 80)
    print("\n[VIEW] Next Steps:")
    print("   1. Check Prometheus Alerts: http://localhost:9090/alerts")
    print("   2. Check AlertManager: http://localhost:9093")
    print("   3. View alerts in Grafana: http://localhost:3001")
    print("   4. Wait 2-3 minutes for alerts to fire")
    print("   5. Alerts will auto-resolve after conditions clear\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[WARNING]  Interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
