"""
Demo Alert Data Generator

This script generates realistic alert scenarios by:
1. Creating a test datasource (PostgreSQL)
2. Starting monitoring to generate alerts
3. Displaying active alerts

Alert Scenarios:
- P1: Database connection failures (high severity)
- P1: High deadlock rate (critical)
- P2: Slow query performance (warning)
- P2: High table bloat (maintenance needed)
- P3: Connection pool saturation (info)
"""

import requests
import time

API_BASE = "http://127.0.0.1:8000"

# Demo datasource configuration
DEMO_DATASOURCE = {
    "id": "demo-postgres",
    "engine": "postgres",
    "dsn": "postgresql://postgres:postgres@localhost:5432/UniversityDB"
}


def create_datasource():
    """Create demo datasource if it doesn't exist"""
    print("[Step 1] Creating demo datasource...")

    # Check if datasource already exists
    try:
        response = requests.get(f"{API_BASE}/datasources")
        datasources = response.json()

        if DEMO_DATASOURCE["id"] in datasources:
            print(f"   [OK] Datasource '{DEMO_DATASOURCE['id']}' already exists")
            return True

        # Create datasource
        response = requests.post(f"{API_BASE}/datasources", json=DEMO_DATASOURCE)
        if response.status_code == 200:
            print(f"   [OK] Created datasource: {DEMO_DATASOURCE['id']}")
            return True
        else:
            print(f"   [ERROR] Failed to create datasource: {response.text}")
            return False
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        print("   [INFO] Make sure backend is running: python run.py")
        return False


def start_monitoring():
    """Start monitoring for the demo datasource"""
    print("\n[Step 2] Starting alert monitoring...")

    ds_id = DEMO_DATASOURCE["id"]

    try:
        response = requests.post(f"{API_BASE}/alerts/monitoring/{ds_id}/start")

        if response.status_code == 200:
            result = response.json()
            print(f"   [OK] Monitoring started")
            print(f"        Interval: {result.get('interval_seconds', 60)}s")
            print(f"        Active rules: {len(result.get('active_rules', []))}")
            return True
        else:
            print(f"   [ERROR] Failed to start monitoring: {response.text}")
            return False
    except Exception as e:
        print(f"   [ERROR] Error starting monitoring: {e}")
        return False


def trigger_demo_alerts():
    """Manually trigger alerts by evaluating rules"""
    print("\n[Step 3] Triggering demo alerts...")

    ds_id = DEMO_DATASOURCE["id"]

    try:
        # Call evaluate endpoint to check alert rules
        response = requests.post(f"{API_BASE}/alerts/evaluate/{ds_id}")

        if response.status_code == 200:
            result = response.json()
            alerts_triggered = result.get("alerts_triggered", 0)

            print(f"   [OK] Evaluation complete")
            print(f"        Alerts triggered: {alerts_triggered}")
            return True
        else:
            print(f"   [INFO] Evaluate endpoint returned: {response.status_code}")
            print("        This is expected if no metrics exceed thresholds")
            return True

    except Exception as e:
        print(f"   [ERROR] Error triggering alerts: {e}")
        return False


def check_active_alerts():
    """Check and display active alerts"""
    print("\n[Step 4] Checking active alerts...")

    try:
        response = requests.get(f"{API_BASE}/alerts/active")

        if response.status_code == 200:
            result = response.json()
            alerts = result.get("alerts", [])

            if alerts:
                print(f"   [OK] Found {len(alerts)} active alerts:")

                for alert in alerts:
                    severity = alert.get("severity", "P3")
                    title = alert.get("title", "Unknown")
                    ds_id = alert.get("datasource_id", "Unknown")

                    severity_label = "[CRITICAL]" if severity == "P1" else "[WARNING]" if severity == "P2" else "[INFO]"
                    print(f"        {severity_label} [{severity}] {title} ({ds_id})")
            else:
                print("   [INFO] No active alerts found")
                print("          This is expected if:")
                print("          - Alert conditions haven't been met yet")
                print("          - Monitoring hasn't run evaluation cycle")
                print("          - Database metrics are all within thresholds")

            return True
        else:
            print(f"   [ERROR] Failed to fetch alerts: {response.status_code}")
            return False

    except Exception as e:
        print(f"   [ERROR] Error fetching alerts: {e}")
        return False


def show_usage_instructions():
    """Display instructions for testing the alert system"""
    print("\n" + "="*70)
    print("DEMO ALERTS SETUP COMPLETE!")
    print("="*70)

    print("\nHow to Test the Alert System:")
    print("\n1. View Active Alerts in UI:")
    print("   - Open Tauri app: npm run dev (in tauri-app/)")
    print("   - Click 'Alerts' button in header")
    print("   - View alerts grouped by severity (P1/P2/P3)")

    print("\n2. Test AI Analysis:")
    print("   - Click on any alert card")
    print("   - View AI-powered root cause analysis")
    print("   - See immediate actions and recommendations")

    print("\n3. Test Alert Acknowledgment:")
    print("   - Click 'Acknowledge' button on an active alert")
    print("   - Alert status changes to 'Acknowledged'")

    print("\n4. Test Alert Resolution:")
    print("   - Click 'Resolve' button on an acknowledged alert")
    print("   - Alert moves to 'Alert History' tab")

    print("\n5. Check Alert History:")
    print("   - Click 'Alert History' tab")
    print("   - View resolved and auto-resolved alerts")
    print("   - Filter by severity (P1/P2/P3)")

    print("\n6. Manual API Testing:")
    print("   - Get active alerts:")
    print("     curl http://127.0.0.1:8000/alerts/active")
    print("\n   - Analyze specific alert:")
    print("     curl -X POST http://127.0.0.1:8000/alerts/{alert_id}/analyze")
    print("\n   - Acknowledge alert:")
    print("     curl -X POST http://127.0.0.1:8000/alerts/{alert_id}/acknowledge ^")
    print("       -H \"Content-Type: application/json\" ^")
    print("       -d \"{\\\"acknowledged_by\\\":\\\"admin\\\",\\\"notes\\\":\\\"Investigating\\\"}\"")

    print("\n7. Stop Monitoring (Optional):")
    print(f"   curl -X POST http://127.0.0.1:8000/alerts/monitoring/{DEMO_DATASOURCE['id']}/stop")

    print("\n" + "="*70)


def main():
    """Main execution flow"""
    print("\n" + "="*70)
    print("AI DB Advisor - Demo Alert Generator")
    print("="*70)
    print("\nThis script will:")
    print("1. Create a demo PostgreSQL datasource")
    print("2. Start alert monitoring")
    print("3. Trigger demo alerts")
    print("4. Display active alerts")

    print("\nPrerequisites:")
    print("   - Backend running: python run.py")
    print("   - PostgreSQL running with UniversityDB")
    print("   - Ollama running (optional, for AI analysis)")

    input("\nPress Enter to continue...")

    # Execute setup steps
    success = True

    success = create_datasource() and success

    if success:
        success = start_monitoring() and success

    # Wait for monitoring to run at least one cycle
    if success:
        print("\n[INFO] Waiting 10 seconds for monitoring to evaluate rules...")
        time.sleep(10)

    if success:
        success = trigger_demo_alerts() and success

    if success:
        success = check_active_alerts() and success

    # Show usage instructions
    show_usage_instructions()

    if success:
        print("\n[SUCCESS] Demo setup completed successfully!")
    else:
        print("\n[WARNING] Demo setup completed with some warnings.")
        print("          Check the output above for details.")

    print("\n[TIP] Alerts may take up to 60 seconds to appear as monitoring")
    print("      evaluates rules on a scheduled interval.\n")


if __name__ == "__main__":
    main()
