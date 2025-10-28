# 🔔 ALERT SYSTEM ARCHITECTURE CLARIFICATION

## TWO SEPARATE ALERT SYSTEMS

Your application has **TWO COMPLETELY DIFFERENT alert systems** running independently:

---

## 🎯 SYSTEM 1: Application-Level Alerts (Tauri UI)

### What It Is
**Database health monitoring alerts shown IN the Tauri desktop application.**

### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Tauri Desktop App                         │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Query Editor │  │  Analytics   │  │  🔔 Alerts   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                             │                │
│                                             ▼                │
│                                    AlertsPanel.tsx           │
│                                    (3-tab interface)         │
└─────────────────────────────────────────────────────────────┘
                        │ HTTP REST API
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (.venv/app/)                    │
│                                                              │
│  Routers:                                                   │
│    /alerts/rules      - Get 16 predefined rules            │
│    /alerts/active     - Get currently firing alerts        │
│    /alerts/resolved   - Get resolved alerts                │
│    /alerts/all        - Get all alerts history             │
│    /alerts/{id}/acknowledge - Acknowledge alert            │
│    /alerts/{id}/resolve     - Manually resolve alert       │
│                                                              │
│  Services:                                                  │
│    alert_engine.py    - Alert evaluation engine            │
│    alert_analyzer.py  - Metric analysis                    │
│    In-memory storage  - Alert state/history               │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
                PostgreSQL Database
                (Direct connection - no exporter)
```

### How It Works

**16 Predefined Alert Rules:**
1. `db_down` (P1) - Database not responding
2. `write_latency_slo` (P1) - Write latency > 250ms
3. `read_latency_slo` (P1) - Read latency > 250ms
4. `replication_lag_critical` (P1) - Replica lag > 300s
5. `disk_space_critical` (P1) - Disk < 10% free
6. `backup_policy_breach` (P1) - No backup in 24h
7. `connection_exhaustion` (P1) - Connections > 98%
8. `deadlock_storm` (P1) - 10+ deadlocks/min
9. `cpu_high` (P2) - CPU > 85% for 10min
10. `memory_pressure` (P2) - Memory > 90% for 10min
11. `long_running_transaction` (P2) - Transaction > 30min
12. `table_bloat_high` (P2) - Table bloat > 30%
13. `slow_checkpoint` (P2) - Checkpoint > 30s
14. `storage_forecast_critical` (P3) - Disk fills in < 14 days
15. `cache_hit_degradation` (P3) - Cache hit < 95%
16. `unused_index` (P3) - Unused indexes detected

**Alert Lifecycle:**
```
1. Alert Engine polls datasource every X seconds
2. Evaluates all 16 rules against current metrics
3. If condition met → Create alert (status: active)
4. Store in memory (in-memory alert storage)
5. Auto-refresh in UI every 10 seconds
6. User can:
   - View in Tauri app "Alerts" tab
   - Acknowledge alert (status: acknowledged)
   - Manually resolve (status: resolved)
7. Auto-resolve when condition clears (status: auto_resolved)
```

**UI Features (AlertsPanel.tsx):**
- **Current Tab**: Active + acknowledged alerts
- **Resolved Tab**: Recently resolved (50 last)
- **All Tab**: Complete history (100 last) + summary
- **Auto-refresh**: Every 10 seconds
- **Actions**: Acknowledge, Resolve buttons
- **Status badges**: P1/P2/P3, active/acknowledged/resolved

**Current Status:**
```bash
curl http://localhost:8000/alerts/active
# Returns: {"alerts": [], "count": 0}
```
**→ Zero alerts because NO database is currently monitored by the alert engine**

**To Trigger Alerts:**
You need to:
1. Register a datasource via `/datasources`
2. Alert engine will poll it
3. Alerts will appear in UI "Alerts" tab

---

## 🚨 SYSTEM 2: Infrastructure-Level Alerts (Prometheus/Alertmanager)

### What It Is
**Infrastructure monitoring alerts for external notification (email, Slack, PagerDuty).**

### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│              Prometheus + Alertmanager Stack                 │
│                    (Docker Containers)                       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Prometheus (scrapes metrics every 10-30s)            │  │
│  │   - FastAPI app metrics (/metrics)                   │  │
│  │   - PostgreSQL metrics (postgres-exporter)           │  │
│  │   - MCP Bridge metrics (/metrics)                    │  │
│  │   - Grafana metrics                                  │  │
│  │                                                       │  │
│  │ Alert Rules (14 rules in alerts.yml):                │  │
│  │   - FastAPIDown, HighErrorRate, SlowAPIResponse      │  │
│  │   - PostgreSQLDown, HighDatabaseConnections          │  │
│  │   - MCPBridgeDown, MCPHighErrorRate                  │  │
│  │   - etc.                                              │  │
│  └──────────────────────────────────────────────────────┘  │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Alertmanager (routes alerts)                         │  │
│  │   - Receives alerts from Prometheus                  │  │
│  │   - Groups alerts by severity                        │  │
│  │   - Routes to receivers                              │  │
│  │   - ❌ NO RECEIVERS CONFIGURED ❌                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
                   📧 Email?  ❌ NOT CONFIGURED
                   💬 Slack?  ❌ NOT CONFIGURED
                   📟 PagerDuty?  ❌ NOT CONFIGURED
```

### How It Works

**14 Infrastructure Alert Rules:**
1. `FastAPIDown` - API not responding
2. `HighErrorRate` - >5% error rate
3. `SlowAPIResponse` - p95 latency > 2s
4. `HighRequestLoad` - >100 req/sec
5. `TooManyActiveRequests` - >50 concurrent
6. `MCPServerDown` - MCP status = 0
7. `MCPHighErrorRate` - >10% error rate
8. `MCPSlowResponses` - p95 latency > 3s
9. `MCPNoToolsDiscovered` - 0 tools
10. `MCPBridgeDown` - MCP not responding
11. `PostgreSQLDown` - pg_up = 0
12. `HighDatabaseConnections` - >80 connections
13. `TooManyDatabaseLocks` - >100 locks
14. `HighPythonGCActivity` - High GC rate

**Alert Flow:**
```
1. Prometheus scrapes metrics every 10-30s
2. Evaluates alert rules every 15s
3. If condition met for duration (e.g., 1-3 min) → Alert FIRES
4. Prometheus sends to Alertmanager
5. Alertmanager receives alert
6. Routes to configured receivers
7. ❌ NO RECEIVERS → Alert goes NOWHERE
```

**Current Status:**
```bash
curl http://localhost:9090/api/v1/alerts
# Returns 2 FIRING alerts:
# - PostgreSQLDown (firing 7+ minutes)
# - MCPBridgeDown (firing 9+ hours)
```
**→ Alerts ARE FIRING but NO ONE IS NOTIFIED**

**Alertmanager Status:**
```bash
curl http://localhost:9093/api/v2/alerts
# Returns: 2 alerts in Alertmanager
# But receivers = ["default"] with NO notification channels
```

---

## 🔍 KEY DIFFERENCES

| Feature | System 1 (App Alerts) | System 2 (Infra Alerts) |
|---------|----------------------|-------------------------|
| **Purpose** | Database health monitoring | Infrastructure monitoring |
| **Visibility** | In Tauri app UI | External notifications |
| **Target Audience** | DBAs using the app | On-call engineers |
| **Alert Rules** | 16 rules (DB-specific) | 14 rules (infrastructure) |
| **Metrics Source** | Direct DB queries | Prometheus exporters |
| **Storage** | In-memory (app backend) | Prometheus TSDB |
| **Notification** | UI only | Email/Slack/PagerDuty |
| **Auto-resolution** | Yes (built-in) | Yes (when metric clears) |
| **Current Status** | Working, 0 alerts (no DS) | **BROKEN - no notifications** |
| **User Interaction** | Acknowledge/Resolve buttons | Silence/Resolve via Alertmanager UI |

---

## 🎯 WHICH SYSTEM HAS THE PROBLEM?

### System 1 (App Alerts) - ✅ WORKING
**Status:** Fully functional
**Evidence:**
- API endpoints responding: `/alerts/active`, `/alerts/rules`
- 16 rules loaded and ready
- UI component (AlertsPanel.tsx) properly integrated
- Alert lifecycle working (active → acknowledged → resolved)

**Why Zero Alerts?**
Because NO datasources are registered with the alert engine.

**To Test:**
```bash
# 1. Register a datasource
curl -X POST http://localhost:8000/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-db",
    "engine": "postgres",
    "dsn": "postgresql://postgres:postgres@localhost:5432/UniversityDB"
  }'

# 2. Wait 10-30 seconds for alert engine to poll

# 3. Check active alerts
curl http://localhost:8000/alerts/active

# 4. Open Tauri app → Click "🔔 Alerts" button
# Should see alerts if any rules triggered
```

---

### System 2 (Infra Alerts) - ❌ BROKEN
**Status:** Alerts firing, notifications NOT configured
**Evidence:**
- Prometheus: 2 critical alerts FIRING right now
- Alertmanager: Receiving alerts
- Notification receivers: EMPTY (no email/Slack/PagerDuty)

**Problem:**
`monitoring/alertmanager.yml` has no notification channels:
```yaml
receivers:
  - name: 'default'
    # All notification configs commented out!
```

**Impact:**
- PostgreSQL DOWN alert firing for 7+ minutes → NO ONE NOTIFIED
- MCP Bridge DOWN alert firing for 9+ hours → NO ONE NOTIFIED
- Future infrastructure issues → NO ONE WILL KNOW

**Fix Required:**
Configure at least ONE notification channel (see ALERT_SYSTEM_INCIDENT_REPORT.md for complete configs):
- Email (via SMTP)
- Slack (via webhook)
- Microsoft Teams (via webhook)
- PagerDuty (via integration key)

---

## 📊 VISUAL COMPARISON

### System 1: Where Alerts Appear
```
Tauri Desktop App
┌─────────────────────────────────────────┐
│  Query Analyzer  │  Analytics  │ 🔔 Alerts │
└─────────────────────────────────────────┘
                                      ▲
                                      │
                           Click here to see alerts
                                      │
                                      ▼
┌─────────────────────────────────────────┐
│         Alerts Dashboard                │
├─────────────────────────────────────────┤
│  Current (2) │ Resolved (5) │ All (12) │
├─────────────────────────────────────────┤
│                                         │
│  🔴 P1  active                          │
│  Primary Database Down                  │
│  postgres-main (postgres)               │
│  Database instance is not responding    │
│  Triggered: 2 minutes ago               │
│  [Acknowledge] [Resolve Manually]       │
│                                         │
│  🟠 P2  acknowledged                    │
│  CPU Utilization High                   │
│  postgres-main (postgres)               │
│  CPU sustained above 85% for 10 minutes │
│  Triggered: 15 minutes ago              │
│  Acknowledged: 5 minutes ago by User    │
│  [Resolve Manually]                     │
└─────────────────────────────────────────┘
```

### System 2: Where Alerts Should Go (NOT CONFIGURED)
```
❌ NO NOTIFICATIONS CONFIGURED ❌

Should send to:
📧 Email: oncall@company.com
💬 Slack: #ai-db-advisor-alerts
📟 PagerDuty: Create incident
📱 SMS: (via PagerDuty)
📞 Phone call: (via PagerDuty escalation)

But currently:
🚨 Alert fires in Prometheus
   ↓
✅ Routes to Alertmanager
   ↓
❌ NO receivers configured
   ↓
🔇 SILENCE (no one notified)
```

---

## 🛠️ RECOMMENDED ACTIONS

### For System 1 (App Alerts)
**Status:** No action needed - working as designed

**Optional Enhancements:**
1. Add more alert rules (custom rules for specific datasources)
2. Add alert history persistence (currently in-memory)
3. Add email/Slack notifications FROM the app
4. Add alert analytics/trends

### For System 2 (Infra Alerts)
**Status:** IMMEDIATE ACTION REQUIRED

**Priority 1 (15 minutes):**
1. Configure ONE notification channel in `monitoring/alertmanager.yml`
   - Recommend: Email (easiest to set up)
   - See ALERT_SYSTEM_INCIDENT_REPORT.md for exact config
2. Send test alert to verify notifications work
3. Fix PostgreSQL (it's currently DOWN!)

**Priority 2 (1 hour):**
4. Add blackbox exporter for TCP health checks
5. Enhance PostgreSQL monitoring rules
6. Create runbooks for each critical alert

**Priority 3 (1 week):**
7. Set up on-call rotation
8. Implement SLO-based alerting
9. Create Grafana dashboards with alert links
10. Run disaster recovery drills

---

## 🤔 FREQUENTLY ASKED QUESTIONS

### Q1: Are these alerts shown in the Tauri app?

**A:** YES and NO - depends which system:
- **System 1 (App Alerts)**: YES - shown in Tauri app "Alerts" tab (🔔 button)
- **System 2 (Infra Alerts)**: NO - sent to external channels (email/Slack/etc.)

### Q2: Why are there two separate systems?

**A:** Different purposes:
- **System 1**: For DBAs actively using the app to monitor database health
- **System 2**: For on-call engineers to be notified of infrastructure issues 24/7

### Q3: Can I use just one system?

**A:** You NEED both:
- **System 1** monitors individual databases you add to the app
- **System 2** monitors the AI DB Advisor application itself (API, exporters, infrastructure)

Think of it like:
- System 1 = Doctor monitoring patients (databases)
- System 2 = Hospital monitoring equipment (the monitoring system itself)

### Q4: Why is System 2 not sending notifications?

**A:** `alertmanager.yml` has NO notification channels configured. All receiver configs are commented out. See ALERT_SYSTEM_INCIDENT_REPORT.md for fix.

### Q5: How do I test System 1 alerts?

**A:**
```bash
# 1. Add a datasource
curl -X POST http://localhost:8000/datasources -H "Content-Type: application/json" \
  -d '{"id":"test","engine":"postgres","dsn":"postgresql://..."}'

# 2. Stop the database to trigger "db_down" alert
net stop postgresql-x64-14

# 3. Wait 30-60 seconds

# 4. Check alerts
curl http://localhost:8000/alerts/active

# 5. Open Tauri app → Click "🔔 Alerts" button
```

### Q6: How do I test System 2 alerts?

**A:**
```bash
# 1. Configure notification channel in alertmanager.yml (REQUIRED FIRST!)

# 2. Send test alert
curl -X POST http://localhost:9093/api/v2/alerts -H "Content-Type: application/json" -d '[
  {"labels":{"alertname":"TestAlert","severity":"warning"},"annotations":{"summary":"Test"},"startsAt":"'$(date -Iseconds)'"}
]'

# 3. Check email/Slack/etc. for notification (should arrive in 1-2 minutes)
```

### Q7: Which alerts are currently firing?

**System 1:** None (no datasources registered)
**System 2:** 2 critical alerts:
- `PostgreSQLDown` (firing 7+ min) → Database is DOWN!
- `MCPBridgeDown` (firing 9+ hours) → MCP service not running (expected if not using MCP)

### Q8: Why is PostgreSQL down alert firing?

**A:** The `postgres-exporter` reports `pg_up=0`, meaning:
- PostgreSQL database is not responding to the exporter
- OR PostgreSQL service is stopped
- OR PostgreSQL is refusing connections

**Check:**
```bash
# Windows
sc query postgresql-x64-14

# Or try to connect
psql postgresql://postgres:postgres@localhost:5432/UniversityDB
```

---

## 📋 QUICK REFERENCE CHEAT SHEET

### System 1 (App Alerts) - In-App UI Alerts
```
Where:      Tauri app "Alerts" tab
API Base:   http://localhost:8000/alerts/
Rules:      16 predefined (DB health focused)
Storage:    In-memory (FastAPI backend)
Audience:   DBAs using the app
Action:     Acknowledge/Resolve in UI
Status:     ✅ WORKING (0 alerts - no datasources)
```

### System 2 (Infra Alerts) - External Notifications
```
Where:      Email/Slack/PagerDuty (NOT CONFIGURED)
API Base:   http://localhost:9090 (Prometheus)
            http://localhost:9093 (Alertmanager)
Rules:      14 predefined (infrastructure focused)
Storage:    Prometheus TSDB
Audience:   On-call engineers (24/7)
Action:     Silence/Acknowledge via Alertmanager
Status:     ❌ BROKEN (2 alerts firing, no notifications)
```

### Fix System 2 Now
```bash
# 1. Edit alertmanager config
notepad monitoring\alertmanager.yml

# 2. Add email config (or Slack/Teams/PagerDuty)
receivers:
  - name: 'default'
    email_configs:
      - to: 'your-email@company.com'
        from: 'alerts@company.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alerts@company.com'
        auth_password: 'your-app-password'

# 3. Reload Alertmanager
curl -X POST http://localhost:9093/-/reload

# 4. Send test alert
curl -X POST http://localhost:9093/api/v2/alerts -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"TestAlert","severity":"warning"},"annotations":{"summary":"Test notification"},"startsAt":"'$(date -Iseconds)'"}]'

# 5. Check email (should arrive in 1-3 minutes)
```

---

## 📚 RELATED DOCUMENTATION

- **ALERT_SYSTEM_INCIDENT_REPORT.md**: Complete fix for System 2 (100+ pages)
  - Root cause analysis
  - 4 notification channel configs (Email/Slack/Teams/PagerDuty)
  - Enhanced alert rules
  - Testing procedures
  - Runbooks

- **tauri-app/src/components/AlertsPanel.tsx**: System 1 UI component
  - 3-tab interface
  - Alert lifecycle management
  - Auto-refresh every 10s

- **.venv/app/routers/alerts.py**: System 1 API endpoints
  - `/alerts/rules`: Get alert rules
  - `/alerts/active`: Get firing alerts
  - `/alerts/{id}/acknowledge`: Acknowledge alert
  - `/alerts/{id}/resolve`: Resolve alert

- **monitoring/alerts.yml**: System 2 alert rules (Prometheus)
  - 14 infrastructure alert rules
  - PromQL expressions
  - Severity levels and durations

- **monitoring/alertmanager.yml**: System 2 routing config
  - ❌ Currently empty receivers
  - Needs notification channel configuration

---

**SUMMARY:**

✅ **System 1 (App Alerts)**: WORKING - Zero alerts because no datasources registered yet
❌ **System 2 (Infra Alerts)**: BROKEN - 2 critical alerts firing, no notifications sent

**Immediate Fix**: Configure notifications in `monitoring/alertmanager.yml` (15 minutes)

**See**: ALERT_SYSTEM_INCIDENT_REPORT.md for complete remediation plan.
