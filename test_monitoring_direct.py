"""
Test monitoring service directly to see if loops execute.
"""

import sys
import os
import asyncio
import logging

# Add .venv/app to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.venv', 'app'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from services.alert_engine import AlertEngine
from services.monitoring_service import MonitoringService

async def main():
    print("Creating alert engine...")
    alert_engine = AlertEngine()
    print(f"Alert engine has {len(alert_engine.rules)} rules")

    print("\nCreating monitoring service...")
    monitoring_service = MonitoringService(alert_engine)

    print(f"Monitoring service created, self.running={monitoring_service.running}")

    print("\nStarting monitoring (this should start async tasks)...")
    await monitoring_service.start()

    print(f"Monitoring started, self.running={monitoring_service.running}")
    print(f"Active tasks: {len(monitoring_service.monitoring_tasks)}")
    print(f"Task IDs: {list(monitoring_service.monitoring_tasks.keys())}")

    print("\nWaiting 35 seconds for monitoring loops to execute...")
    await asyncio.sleep(35)

    print("\nChecking active alerts...")
    active_alerts = alert_engine.get_active_alerts()
    print(f"Active alerts: {len(active_alerts)}")
    for alert in active_alerts:
        print(f"  - {alert.rule_id} ({alert.severity}): {alert.message}")

    print("\nStopping monitoring service...")
    await monitoring_service.stop()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
