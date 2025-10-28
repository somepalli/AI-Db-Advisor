"""
Test script to verify alert generation flow manually.

This script simulates what the monitoring service does:
1. Collects metrics (with db_up=False since PostgreSQL is stopped)
2. Calls alert_engine.evaluate_all_rules()
3. Checks if alerts were generated
"""

import sys
import os

# Add .venv/app to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.venv', 'app'))

from services.alert_engine import AlertEngine

# Create alert engine (will auto-register all default rules)
alert_engine = AlertEngine()

print(f"Alert engine initialized with {len(alert_engine.rules)} rules")
print(f"Rules: {list(alert_engine.rules.keys())}")

# Simulate metrics with database down
metrics_dict = {
    "db_up": 0,  # <- This is the key metric for db_down rule
    "connection_count": 0,
    "db_size_mb": 0,
    "table_count": 0,
    "lock_count": 0,
    "blocking_locks": 0
}

print(f"\nSimulated metrics: {metrics_dict}")

# Evaluate all rules
triggered_alerts = alert_engine.evaluate_all_rules(
    datasource_id="Demo-DB-Post",
    engine="postgres",
    metrics=metrics_dict
)

print(f"\nTriggered alerts: {len(triggered_alerts)}")
for alert in triggered_alerts:
    print(f"  - {alert.rule_id} ({alert.severity}): {alert.message}")
    print(f"    Alert ID: {alert.id}")
    print(f"    Datasource: {alert.datasource_id}")
    print(f"    Status: {alert.status}")

# Check active alerts
active_alerts = alert_engine.get_active_alerts()
print(f"\nActive alerts in engine: {len(active_alerts)}")
for alert in active_alerts:
    print(f"  - {alert.rule_id} ({alert.severity}): {alert.message}")
    print(f"    Alert ID: {alert.id}")
