# Alert Testing Guide - AlertManager & Grafana

Complete guide to triggering, viewing, and managing alerts in your AI DB Advisor monitoring stack.

## Table of Contents
- [Alert Overview](#alert-overview)
- [Quick Start](#quick-start)
- [Triggering Alerts](#triggering-alerts)
- [Viewing Alerts](#viewing-alerts)
- [Alert Scenarios](#alert-scenarios)
- [Grafana Alert Integration](#grafana-alert-integration)

---

## Alert Overview

Your monitoring stack includes **15 alert rules** across 4 categories:

### FastAPI Backend Alerts (5 alerts)
| Alert | Severity | Threshold | Fire After |
|-------|----------|-----------|------------|
| **HighErrorRate** | Critical | >5% error rate | 2 minutes |
| **SlowAPIResponse** | Warning | p95 > 2s | 3 minutes |
| **HighRequestLoad** | Warning | >100 req/sec | 2 minutes |
| **TooManyActiveRequests** | Warning | >50 concurrent | 1 minute |
| **FastAPIDown** | Critical | Service down | 1 minute |

### MCP Bridge Alerts (5 alerts)
| Alert | Severity | Threshold | Fire After |
|-------|----------|-----------|------------|
| **MCPServerDown** | Critical | Server down | 1 minute |
| **MCPHighErrorRate** | Warning | >10% error rate | 2 minutes |
| **MCPSlowResponses** | Warning | p95 > 3s | 3 minutes |
| **MCPNoToolsDiscovered** | Warning | 0 tools | 2 minutes |
| **MCPBridgeDown** | Critical | Service down | 1 minute |

### PostgreSQL Alerts (3 alerts)
| Alert | Severity | Threshold | Fire After |
|-------|----------|-----------|------------|
| **PostgreSQLDown** | Critical | DB down | 1 minute |
| **HighDatabaseConnections** | Warning | >80 connections | 3 minutes |
| **TooManyDatabaseLocks** | Warning | >100 locks | 2 minutes |

### System Alerts (2 alerts)
| Alert | Severity | Threshold | Fire After |
|-------|----------|-----------|------------|
| **HighPythonGCActivity** | Info | >10 GC/sec | 5 minutes |

---

## Quick Start

### Step 1: Verify All Services Are Running

```bash
# Check Docker services
docker-compose -f docker-compose.monitoring.yml ps

# Should show: Prometheus, Grafana, AlertManager, PostgreSQL Exporter all UP

# Check Python services (in separate terminals)
# Terminal 1: FastAPI backend should be running (python run.py)
# Terminal 2: MCP bridge should be running (python mcp_http_bridge.py)
```

### Step 2: Verify Alert Rules Are Loaded

1. Open Prometheus: http://localhost:9090
2. Click **Status** → **Rules**
3. You should see 4 groups:
   - `fastapi_alerts` (5 rules)
   - `mcp_alerts` (5 rules)
   - `postgres_alerts` (3 rules)
   - `system_alerts` (2 rules)

### Step 3: Check Current Alerts

1. Open Prometheus: http://localhost:9090/alerts
2. You should see all alerts in "Inactive" state (green)

### Step 4: Trigger Your First Alert

```bash
# Run the alert trigger script
python trigger_alerts.py --scenario errors --duration 180
```

---

## Triggering Alerts

### Method 1: Using the Automated Script

The easiest way to trigger alerts is using `trigger_alerts.py`:

```bash
# List all scenarios
python trigger_alerts.py --list

# Trigger high error rate (runs for 3 minutes)
python trigger_alerts.py --scenario errors --duration 180

# Trigger high load (runs for 2 minutes)
python trigger_alerts.py --scenario load --duration 120

# Trigger slow responses
python trigger_alerts.py --scenario slow --duration 240

# Run all scenarios sequentially
python trigger_alerts.py --scenario all
```

### Method 2: Manual Triggering

#### Trigger HighErrorRate Alert

```bash
# Generate many 404 errors
for i in {1..1000}; do
  curl -s http://127.0.0.1:8000/non-existent-endpoint-$i > /dev/null
  sleep 0.1
done
```

**Expected**: Alert fires after 2 minutes when error rate >5%

#### Trigger HighRequestLoad Alert

```bash
# Use Apache Bench or similar tool
# Windows: Install Apache Bench or use Python script
python -c "
import requests
import threading
import time

def make_requests():
    for i in range(1000):
        try:
            requests.get('http://127.0.0.1:8000/healthz', timeout=5)
        except:
            pass
        time.sleep(0.01)

threads = [threading.Thread(target=make_requests) for _ in range(20)]
for t in threads:
    t.start()
for t in threads:
    t.join()
"
```

**Expected**: Alert fires after 2 minutes when request rate >100 req/sec

#### Trigger FastAPIDown Alert

```bash
# Stop the FastAPI backend
# Press Ctrl+C in the terminal running "python run.py"
# Wait 1 minute
```

**Expected**: Alert fires after 1 minute

#### Trigger MCPBridgeDown Alert

```bash
# Stop the MCP bridge
# Press Ctrl+C in the terminal running "python mcp_http_bridge.py"
# Wait 1 minute
```

**Expected**: Alert fires after 1 minute

#### Trigger PostgreSQLDown Alert

```bash
# Stop PostgreSQL service (be careful!)
# Windows: Stop PostgreSQL service from Services
# Or stop docker postgres if using containerized version

# Better: Simulate by stopping postgres exporter
docker stop ai-db-advisor-postgres-exporter
```

**Expected**: Alert fires after 1 minute

---

## Viewing Alerts

### In Prometheus

1. **Open Prometheus Alerts Page**:
   - URL: http://localhost:9090/alerts
   - Shows all configured alerts and their current state

2. **Alert States**:
   - **Inactive** (Green): No issue detected
   - **Pending** (Yellow): Condition met, waiting for "for" duration
   - **Firing** (Red): Alert is active and sent to AlertManager

3. **Alert Details**:
   - Click on an alert to see:
     - Current value
     - Labels
     - Annotations
     - Active since time

### In AlertManager

1. **Open AlertManager**:
   - URL: http://localhost:9093
   - Shows currently firing alerts

2. **Alert Features**:
   - **Alerts** tab: View all active alerts
   - **Silences** tab: Temporarily mute alerts
   - **Status** tab: View AlertManager configuration

3. **Creating Silences**:
   - Click **New Silence**
   - Add matchers: `alertname=HighErrorRate`
   - Set duration: 1 hour
   - Add comment: "Maintenance window"
   - Click **Create**

### In Grafana

Grafana can display alerts from Prometheus/AlertManager in several ways:

#### Method 1: Alert List Panel

1. Open Grafana: http://localhost:3001
2. Create a new dashboard or edit existing
3. Click **Add** → **Visualization**
4. Select **Alert list** as panel type
5. Configure:
   - **Show**: `Current state`
   - **Max alerts**: `10`
   - **Alert name**: Leave empty (shows all)
   - **Dashboard tags**: Leave empty
   - **State filter**: Select all (Normal, Pending, Alerting)
6. Click **Apply**

This creates a live list of all alerts!

#### Method 2: Using Prometheus Data Source

1. Create a new panel
2. Select **Prometheus** as data source
3. Query:
   ```promql
   ALERTS{alertstate="firing"}
   ```
4. Panel type: **Table**
5. This shows all currently firing alerts

#### Method 3: Configure Alerting in Grafana

1. Click **Alerting** (bell icon) in left sidebar
2. Click **Alert rules**
3. Click **New alert rule**
4. Configure:
   - **Rule name**: High Error Rate
   - **Query**:
     ```promql
     (sum(rate(http_requests_total{job="ai-db-advisor-app",status=~"5.."}[5m])) / sum(rate(http_requests_total{job="ai-db-advisor-app"}[5m]))) > 0.05
     ```
   - **Threshold**: `0.05` (5%)
   - **Evaluation interval**: `1m`
   - **For**: `2m`
5. Add notification channel
6. Click **Save**

#### Method 4: Import Alert Dashboard

Create a dedicated alerts dashboard:

1. Click **+ icon** → **Dashboard**
2. Add multiple panels:

**Panel 1: Active Alerts Count**
- Type: **Stat**
- Query: `count(ALERTS{alertstate="firing"})`
- Title: Active Alerts

**Panel 2: Alerts by Severity**
- Type: **Stat** or **Bar gauge**
- Query A: `count(ALERTS{alertstate="firing",severity="critical"})`
- Query B: `count(ALERTS{alertstate="firing",severity="warning"})`
- Query C: `count(ALERTS{alertstate="firing",severity="info"})`

**Panel 3: Alert Timeline**
- Type: **State timeline**
- Query: `ALERTS{}`
- Shows alert state changes over time

**Panel 4: Alert Details Table**
- Type: **Table**
- Query: `ALERTS{alertstate="firing"}`
- Shows all firing alerts with details

---

## Alert Scenarios

### Scenario 1: High Error Rate Alert

**Goal**: Trigger and observe the HighErrorRate alert

**Steps**:

1. **Trigger the alert**:
   ```bash
   python trigger_alerts.py --scenario errors --duration 180
   ```

2. **Monitor in Prometheus** (http://localhost:9090/alerts):
   - Initially: HighErrorRate shows as **Inactive** (green)
   - After ~1 minute: Changes to **Pending** (yellow)
   - After 2 minutes: Changes to **Firing** (red)

3. **Check AlertManager** (http://localhost:9093):
   - Alert appears in "Alerts" tab
   - Shows:
     - Alert name: HighErrorRate
     - Severity: critical
     - Service: fastapi
     - Description: Error rate percentage

4. **View in Grafana** (http://localhost:3001):
   - Open FastAPI dashboard
   - See spike in HTTP Status Codes panel (red area for 5xx errors)
   - If you added Alert List panel, alert appears there

5. **Resolution**:
   - Stop the script (Ctrl+C) or let it complete
   - Wait 5 minutes for error rate to drop
   - Alert auto-resolves (returns to Inactive)
   - AlertManager removes it from active alerts

**Expected Timeline**:
```
0:00 - Start script
0:30 - Error rate rises above 5%
2:00 - Alert fires (sent to AlertManager)
3:00 - Script ends
5:00 - Error rate drops below threshold
7:00 - Alert resolves
```

### Scenario 2: High Load Alert

**Goal**: Trigger HighRequestLoad alert

**Steps**:

1. **Trigger the alert**:
   ```bash
   python trigger_alerts.py --scenario load --duration 120
   ```

2. **Monitor**:
   - Prometheus: Watch HighRequestLoad alert
   - Grafana FastAPI Dashboard: See request rate spike in "Request Rate" panel

3. **Observe**:
   - Request rate climbs above 100 req/sec
   - Alert pending after 1 minute
   - Alert fires after 2 minutes
   - Auto-resolves after load stops

### Scenario 3: Service Down Alert

**Goal**: Trigger FastAPIDown alert

**Steps**:

1. **Stop FastAPI backend**:
   - Go to terminal running `python run.py`
   - Press `Ctrl+C`

2. **Monitor**:
   - Prometheus: Watch FastAPIDown alert
   - Alert fires within 1 minute

3. **Check AlertManager**:
   - Critical severity alert appears
   - Description: "FastAPI service is not responding"

4. **Resolution**:
   - Restart FastAPI: `python run.py`
   - Alert resolves within 1-2 minutes

### Scenario 4: Multiple Alerts

**Goal**: Trigger multiple alerts simultaneously

**Steps**:

1. **Terminal 1** - High error rate:
   ```bash
   python trigger_alerts.py --scenario errors --duration 300
   ```

2. **Terminal 2** - High load:
   ```bash
   python trigger_alerts.py --scenario load --duration 300
   ```

3. **Observe**:
   - Multiple alerts fire in Prometheus
   - All appear in AlertManager
   - Grafana shows multiple active alerts

4. **Check Alert List in Grafana**:
   - Create Alert List panel (see instructions above)
   - See both alerts listed

---

## Grafana Alert Integration

### Setting Up Alert Notifications

#### Step 1: Add Notification Channel

1. Go to **Alerting** → **Contact points**
2. Click **New contact point**
3. Choose notification type:

**Email**:
- Name: `Email Admins`
- Type: `Email`
- Addresses: `admin@example.com`

**Slack** (if you have Slack):
- Name: `Slack Alerts`
- Type: `Slack`
- Webhook URL: Your Slack webhook
- Channel: `#alerts`

**Webhook**:
- Name: `Custom Webhook`
- Type: `Webhook`
- URL: `http://your-webhook-url`

4. Click **Test** to verify
5. Click **Save contact point**

#### Step 2: Create Notification Policy

1. Go to **Alerting** → **Notification policies**
2. Click **New policy**
3. Configure:
   - **Matching labels**: `severity=critical`
   - **Contact point**: Select your email/Slack
   - **Group by**: `alertname`
   - **Group interval**: `5m`
   - **Repeat interval**: `4h`
4. Click **Save policy**

Now critical alerts will be sent to your notification channel!

### Creating a Custom Alert Dashboard

Create a dedicated dashboard for monitoring alerts:

**Dashboard Name**: `AI DB Advisor - Alerts Overview`

**Panels**:

1. **Total Active Alerts** (Stat panel):
   ```promql
   count(ALERTS{alertstate="firing"})
   ```

2. **Critical Alerts** (Stat panel, red):
   ```promql
   count(ALERTS{alertstate="firing",severity="critical"})
   ```

3. **Warning Alerts** (Stat panel, yellow):
   ```promql
   count(ALERTS{alertstate="firing",severity="warning"})
   ```

4. **Alert Timeline** (State timeline):
   ```promql
   ALERTS{}
   ```

5. **Firing Alerts Table** (Table):
   ```promql
   ALERTS{alertstate="firing"}
   ```
   Transform: Format table columns to show alertname, severity, summary

6. **Alert History** (Time series):
   ```promql
   changes(ALERTS{alertstate="firing"}[5m])
   ```

### Alert Annotations in Dashboards

Add alert annotations to see when alerts fired:

1. Edit any dashboard
2. Click **Dashboard settings** (gear icon)
3. Go to **Annotations**
4. Click **Add annotation query**
5. Configure:
   - **Name**: `Prometheus Alerts`
   - **Data source**: `Prometheus`
   - **Query**: `ALERTS{alertstate="firing"}`
   - **Title**: `{{alertname}}`
   - **Tags**: `{{severity}}`
   - **Text**: `{{summary}}`
6. Click **Add**
7. Save dashboard

Now you'll see vertical lines on graphs when alerts fire!

---

## Troubleshooting

### Alerts Not Firing

**Problem**: Alert conditions are met but alert doesn't fire

**Solutions**:

1. Check Prometheus Rules:
   - Go to http://localhost:9090/rules
   - Verify rules are loaded
   - Check for syntax errors (shown in red)

2. Reload Prometheus:
   ```bash
   docker exec ai-db-advisor-prometheus kill -HUP 1
   ```

3. Check evaluation interval:
   - Alerts are evaluated every 30 seconds
   - "for" duration must pass before firing

4. Verify metrics exist:
   - Go to Prometheus Graph tab
   - Run the alert query manually
   - Check if it returns data

### AlertManager Not Receiving Alerts

**Problem**: Alerts fire in Prometheus but don't appear in AlertManager

**Solutions**:

1. Check Prometheus AlertManager config:
   ```bash
   docker exec ai-db-advisor-prometheus cat /etc/prometheus/prometheus.yml | grep -A 5 alerting
   ```

2. Verify AlertManager is accessible:
   ```bash
   curl http://localhost:9093
   ```

3. Check Prometheus logs:
   ```bash
   docker-compose -f docker-compose.monitoring.yml logs prometheus | grep alert
   ```

### Alerts Not Visible in Grafana

**Problem**: Alerts fire but don't show in Grafana

**Solutions**:

1. Verify Prometheus data source is connected:
   - Go to **Configuration** → **Data sources**
   - Test connection to Prometheus

2. Check query syntax:
   - Query: `ALERTS{alertstate="firing"}`
   - Should return results if alerts are active

3. Try creating Alert List panel:
   - Use Alert List visualization type
   - Shows alerts from Grafana's built-in alerting

---

## Best Practices

### 1. Start with Simple Alerts

Test one alert at a time:
```bash
python trigger_alerts.py --scenario errors --duration 180
```

### 2. Monitor Alert Latency

Track how long it takes for alerts to fire after conditions are met.

### 3. Use Silences for Maintenance

When doing planned maintenance:
1. Go to AlertManager
2. Create silence for maintenance window
3. Prevents alert fatigue

### 4. Set Up Notification Channels

Configure email/Slack so you're notified of critical alerts.

### 5. Create Alert Runbooks

Document what to do when each alert fires:
- HighErrorRate: Check application logs, restart service
- FastAPIDown: Restart backend, check dependencies
- PostgreSQLDown: Check database status, disk space

### 6. Test Regularly

Run alert tests monthly to ensure alerting is working.

### 7. Review and Tune Thresholds

After monitoring for a week, adjust thresholds based on actual patterns.

---

## Complete Testing Workflow

Follow this workflow to test your entire alerting setup:

### Phase 1: Verify Setup (5 minutes)

1. Check all services are running
2. Open Prometheus: http://localhost:9090/alerts
3. Open AlertManager: http://localhost:9093
4. Open Grafana: http://localhost:3001
5. Verify all alerts show as "Inactive"

### Phase 2: Trigger First Alert (10 minutes)

1. Run: `python trigger_alerts.py --scenario errors --duration 180`
2. Watch Prometheus alerts page
3. Wait for alert to go: Inactive → Pending → Firing
4. Check AlertManager shows the alert
5. View in Grafana (if configured)

### Phase 3: Test Multiple Alerts (15 minutes)

1. Keep first script running
2. In new terminal: `python trigger_alerts.py --scenario load --duration 180`
3. Watch both alerts fire
4. Check AlertManager shows both

### Phase 4: Test Resolution (10 minutes)

1. Stop both scripts (Ctrl+C)
2. Wait 5 minutes
3. Watch alerts resolve in Prometheus
4. Verify they disappear from AlertManager

### Phase 5: Test Critical Alert (5 minutes)

1. Stop FastAPI backend (Ctrl+C)
2. Wait 1 minute
3. See FastAPIDown alert fire
4. Restart backend
5. Watch alert resolve

**Total Time**: ~45 minutes for complete test

---

## Next Steps

1. ✅ Test alerts using `trigger_alerts.py`
2. ✅ Configure notification channels in Grafana
3. ✅ Create custom alert dashboard
4. ✅ Set up alert annotations
5. ✅ Document runbooks for each alert
6. ✅ Schedule regular alert testing

Your alerting system is now fully configured and ready! 🎉
