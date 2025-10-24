# AI-Powered Alert System - Test Plan

## Executive Summary

This document outlines the comprehensive testing strategy for implementing an AI-powered alert and notification system within the AI DB Advisor Tauri application. The system monitors database health, performance metrics, and triggers intelligent alerts with AI-generated solutions.

---

## 1. System Architecture Overview

### Components to Build

```
┌─────────────────────────────────────────────────────────────┐
│                    Tauri Desktop App                         │
│  ┌────────────────┬────────────────┬────────────────────┐  │
│  │ Alert Panel    │ Notification   │ AI Chat for        │  │
│  │ (Real-time)    │ Center         │ Alert Resolution   │  │
│  └────────────────┴────────────────┴────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket + REST API
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI Backend (Python)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Alert Engine (New Service)                          │  │
│  │  - Rule Evaluator                                    │  │
│  │  - Metric Collector (from DB agents)                 │  │
│  │  - Threshold Manager                                 │  │
│  │  - Alert Dispatcher                                  │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  AI Alert Analyzer (New Service)                     │  │
│  │  - Context Builder (alert + DB state)                │  │
│  │  - LLM Integration (solution generation)             │  │
│  │  - Recommendation Engine                             │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  Notification Manager (New Service)                  │  │
│  │  - WebSocket Server (real-time push)                 │  │
│  │  - Alert Queue (priority-based)                      │  │
│  │  - History Storage (in-memory/Redis)                 │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                              ▼
┌──────────────────┐          ┌──────────────────┐
│ Multi-Databases  │          │  Ollama LLM      │
│ (Monitoring)     │          │  (qwen2.5:7b)    │
└──────────────────┘          └──────────────────┘
```

### New Endpoints (Backend)

**Alert Management**:
- `GET /alerts/active`: Get all active alerts
- `GET /alerts/history?ds_id={id}&severity={P1|P2|P3}&limit=100`: Alert history
- `POST /alerts/acknowledge/{alert_id}`: Acknowledge an alert
- `POST /alerts/resolve/{alert_id}`: Mark alert as resolved
- `GET /alerts/rules`: List all monitoring rules
- `POST /alerts/rules`: Create custom alert rule
- `PUT /alerts/rules/{rule_id}`: Update rule thresholds
- `DELETE /alerts/rules/{rule_id}`: Delete custom rule

**Alert Analysis**:
- `POST /alerts/{alert_id}/analyze`: Get AI analysis and solutions
- `POST /alerts/{alert_id}/chat`: Conversational follow-up questions
- `GET /alerts/{alert_id}/recommendations`: Get recommended actions

**Monitoring Control**:
- `POST /monitoring/{ds_id}/start`: Start monitoring a datasource
- `POST /monitoring/{ds_id}/stop`: Stop monitoring
- `GET /monitoring/status`: Get monitoring status for all datasources
- `PUT /monitoring/{ds_id}/config`: Update monitoring intervals/thresholds

**WebSocket**:
- `WS /ws/alerts/{client_id}`: Real-time alert stream

---

## 2. Test Strategy

### 2.1 Test Pyramid

```
                    ┌──────────────┐
                    │  E2E Tests   │  (10%)
                    │  - Tauri UI  │
                    │  - WebSocket │
                    └──────────────┘
              ┌────────────────────────┐
              │  Integration Tests     │  (30%)
              │  - API Endpoints       │
              │  - Alert Workflows     │
              │  - AI Integration      │
              └────────────────────────┘
      ┌──────────────────────────────────────┐
      │       Unit Tests                     │  (60%)
      │  - Alert Rules                       │
      │  - Metric Collection                 │
      │  - Threshold Evaluation              │
      │  - AI Prompt Generation              │
      └──────────────────────────────────────┘
```

### 2.2 Test Coverage Targets

- **Unit Tests**: 85%+ code coverage
- **Integration Tests**: All critical alert workflows (P1/P2)
- **E2E Tests**: Happy path + top 5 alert scenarios
- **Performance Tests**: Alert latency < 2s (detection to notification)

---

## 3. Test Scenarios by Priority

### 3.1 P1 (Critical) Alert Tests - Must Cover

#### Test Case 1.1: Database Down Detection
```yaml
Scenario: Primary database becomes unavailable
Given: PostgreSQL datasource "UniversityDB" is being monitored
When: Database server stops responding for 3 consecutive health checks
Then:
  - P1 alert "Primary Down" is triggered within 10 seconds
  - WebSocket notification is sent to all connected clients
  - AI analysis provides:
    - Root cause detection (connection refused, server down, network issue)
    - Immediate actions (check server status, verify network, review logs)
    - Failover recommendations (if replica available)
  - Alert history shows timestamp, severity, datasource
```

**Test Implementation**:
- **Unit Test**: `test_health_check_failure_triggers_p1_alert()`
- **Integration Test**: `test_db_down_alert_workflow()` (mock DB connection failure)
- **E2E Test**: `test_tauri_displays_critical_alert_banner()` (stop Docker container)

---

#### Test Case 1.2: Write Latency SLO Breach
```yaml
Scenario: Write query P99 latency exceeds 250ms SLO
Given: Monitoring enabled with P99_write_latency rule (threshold: 250ms)
When: pg_stat_statements shows writes averaging 400ms over 5min window
Then:
  - P1 alert "Write Latency SLO Breach" triggered
  - AI analysis includes:
    - Top slow write queries from pg_stat_statements
    - Wait event analysis (I/O, lock, CPU)
    - Index recommendations for slow queries
    - Configuration tuning (shared_buffers, checkpoint_timeout)
  - Recommended fixes include SQL rewrites or CREATE INDEX statements
```

**Test Implementation**:
- **Unit Test**: `test_latency_threshold_calculation()`
- **Integration Test**: `test_write_latency_alert_with_ai_analysis()`
- **Mocking Strategy**: Inject mock pg_stat_statements data with high latency

---

#### Test Case 1.3: Replication Lag > RPO
```yaml
Scenario: Standby replica falls behind primary beyond Recovery Point Objective
Given: RPO configured as 5 minutes (300 seconds)
When: pg_stat_replication shows replay_lag = 420 seconds
Then:
  - P1 alert "Replication Lag Critical" triggered
  - AI provides:
    - Lag breakdown (write_lag, flush_lag, replay_lag)
    - Bottleneck identification (network, disk I/O, CPU on standby)
    - Remediation steps:
      - Check standby resources
      - Review max_standby_streaming_delay
      - Verify wal_sender/receiver health
  - Alert includes data loss risk window (7 minutes)
```

**Test Implementation**:
- **Unit Test**: `test_replication_lag_detection()`
- **Integration Test**: `test_replication_alert_includes_context()`
- **Mock**: Simulate pg_stat_replication with high lag values

---

#### Test Case 1.4: Disk Space Critical (< 10% Free)
```yaml
Scenario: Database server disk space drops below 10%
Given: Node exporter monitoring filesystem /var/lib/postgresql
When: node_filesystem_avail_bytes shows 8% free space
Then:
  - P1 alert "Disk Space Critical" triggered
  - AI analysis includes:
    - Current usage breakdown (data files, WAL, temp, logs)
    - Growth trend (30/60/90 day projection)
    - Immediate actions:
      - Archive old WAL files
      - Clean temp files
      - Extend volume (cloud auto-scaling)
    - Long-term: partitioning, data archival strategy
  - Alert shows estimated time to full (< 30 min)
```

**Test Implementation**:
- **Unit Test**: `test_disk_space_calculation()`
- **Integration Test**: `test_disk_alert_with_growth_projection()`
- **Mock**: Inject node_exporter metrics with low free space

---

#### Test Case 1.5: Backup Policy Breach
```yaml
Scenario: Last successful backup is older than policy (24 hours)
Given: Backup policy requires daily full backups
When: Last backup timestamp is 28 hours ago
Then:
  - P1 alert "Backup Policy Breach" triggered
  - AI provides:
    - Last successful backup details
    - Failed backup attempts (if any)
    - RPO/RTO risk assessment
    - Immediate actions:
      - Trigger manual backup
      - Check backup tool logs
      - Verify storage availability
  - Alert persists until backup completes
```

**Test Implementation**:
- **Unit Test**: `test_backup_age_validation()`
- **Integration Test**: `test_backup_breach_alert_workflow()`
- **Mock**: Simulate backup metadata with old timestamp

---

### 3.2 P2 (High) Alert Tests

#### Test Case 2.1: CPU Utilization Spike (> 85% for 10min)
```yaml
Scenario: Database server CPU sustained above 85%
Given: CPU threshold configured at 85% for 10 minutes
When: node_exporter shows CPU > 90% for 12 consecutive minutes
Then:
  - P2 alert "CPU High" triggered
  - AI analysis includes:
    - Top CPU-consuming queries (pg_stat_statements)
    - Wait events (CPU-bound vs I/O-wait)
    - Recommendations:
      - Query optimization (slow queries)
      - Connection pooling (if connection storm)
      - Resource limits (cgroups/docker)
    - Expected impact on P99 latency
```

**Test Implementation**:
- **Unit Test**: `test_cpu_threshold_sustained_duration()`
- **Integration Test**: `test_cpu_alert_with_query_correlation()`

---

#### Test Case 2.2: Long-Running Transaction (> 30min)
```yaml
Scenario: Transaction open for extended period blocking autovacuum
Given: Long transaction threshold = 30 minutes
When: pg_stat_activity shows xact_start 45 minutes ago
Then:
  - P2 alert "Long Running Transaction" triggered
  - AI provides:
    - Transaction details (PID, user, query)
    - Blocking/blocked sessions
    - Impact on vacuum, bloat, replication slots
    - Actions:
      - Contact application team
      - Consider kill -SIGTERM <pid> if idle
      - Review application transaction management
```

**Test Implementation**:
- **Unit Test**: `test_long_transaction_detection()`
- **Integration Test**: `test_long_txn_alert_with_impact_analysis()`

---

#### Test Case 2.3: Table Bloat Detection (> 30%)
```yaml
Scenario: Table accumulates significant bloat
Given: Bloat threshold = 30% for production tables
When: students table shows 42% bloat (dead tuples / total)
Then:
  - P2 alert "Table Bloat High" triggered
  - AI provides:
    - Current bloat metrics (bytes, percentage)
    - Autovacuum history for table
    - Recommendations:
      - VACUUM FULL (requires table lock)
      - pg_repack (online reorganization)
      - Adjust autovacuum_vacuum_scale_factor
    - Estimated reclaim space (1.2 GB)
```

**Test Implementation**:
- **Unit Test**: `test_bloat_calculation()`
- **Integration Test**: `test_bloat_alert_with_vacuum_recommendations()`

---

### 3.3 P3 (Medium) Alert Tests

#### Test Case 3.1: Storage Forecast (< 14 days to full)
```yaml
Scenario: Storage growth trend predicts exhaustion
Given: Historical growth rate 5 GB/day, 60 GB free
When: Linear projection shows < 12 days to full
Then:
  - P3 alert "Storage Forecast Critical" triggered
  - AI provides:
    - Growth trend chart (30/60/90 day)
    - Top growing tables
    - Recommendations:
      - Partition large tables
      - Archive old data
      - Enable compression
      - Plan capacity upgrade
  - Alert updates daily with revised forecast
```

**Test Implementation**:
- **Unit Test**: `test_storage_growth_projection()`
- **Integration Test**: `test_forecast_alert_updates_daily()`

---

#### Test Case 3.2: Unused Index Detection
```yaml
Scenario: Index not used in 7+ days
Given: idx_scan monitoring enabled
When: pg_stat_user_indexes shows idx_scan = 0 for 10 days
Then:
  - P3 alert "Unused Index" triggered
  - AI provides:
    - Index details (size, table, columns)
    - Historical usage (if any)
    - Cost analysis (write overhead)
    - Recommendations:
      - Safe to drop (with DROP INDEX statement)
      - Consider monitoring 30 days first
  - Alert batches multiple unused indexes
```

**Test Implementation**:
- **Unit Test**: `test_unused_index_tracking()`
- **Integration Test**: `test_batch_unused_index_alert()`

---

## 4. Test Implementation Structure

### 4.1 Backend Unit Tests (pytest)

**File**: `.venv/app/tests/test_alert_engine.py`

```python
import pytest
from datetime import datetime, timedelta
from services.alert_engine import AlertEngine, AlertRule, MetricSnapshot
from services.alert_analyzer import AlertAnalyzer

class TestAlertRuleEvaluation:
    """Test alert rule threshold evaluation"""

    def test_simple_threshold_breach(self):
        """Test basic threshold comparison"""
        rule = AlertRule(
            id="cpu_high",
            metric="cpu_percent",
            operator=">=",
            threshold=85.0,
            duration_minutes=10,
            severity="P2"
        )

        # Simulate 12 minutes of high CPU
        snapshots = [
            MetricSnapshot(timestamp=datetime.now() - timedelta(minutes=i),
                          metric="cpu_percent", value=92.0)
            for i in range(12, 0, -1)
        ]

        engine = AlertEngine()
        alert = engine.evaluate_rule(rule, snapshots)

        assert alert is not None
        assert alert.severity == "P2"
        assert alert.rule_id == "cpu_high"
        assert "sustained" in alert.message.lower()

    def test_insufficient_duration_no_alert(self):
        """Test that brief spikes don't trigger sustained alerts"""
        rule = AlertRule(
            id="cpu_high",
            metric="cpu_percent",
            operator=">=",
            threshold=85.0,
            duration_minutes=10,
            severity="P2"
        )

        # Only 5 minutes of high CPU
        snapshots = [
            MetricSnapshot(timestamp=datetime.now() - timedelta(minutes=i),
                          metric="cpu_percent", value=92.0)
            for i in range(5, 0, -1)
        ]

        engine = AlertEngine()
        alert = engine.evaluate_rule(rule, snapshots)

        assert alert is None

    def test_replication_lag_complex_rule(self):
        """Test multi-condition rule (lag > RPO AND sync_state != 'sync')"""
        rule = AlertRule(
            id="replication_lag",
            conditions=[
                {"metric": "replay_lag_seconds", "operator": ">", "value": 300},
                {"metric": "sync_state", "operator": "!=", "value": "sync"}
            ],
            severity="P1"
        )

        snapshots = {
            "replay_lag_seconds": MetricSnapshot(value=420),
            "sync_state": MetricSnapshot(value="async")
        }

        engine = AlertEngine()
        alert = engine.evaluate_rule(rule, snapshots)

        assert alert is not None
        assert alert.severity == "P1"
        assert "replication" in alert.title.lower()

    def test_disk_space_projection(self):
        """Test runway calculation for disk space"""
        from services.alert_engine import calculate_runway

        # 100 GB free, growing 5 GB/day
        free_space_gb = 100
        daily_growth_gb = 5

        runway_days = calculate_runway(free_space_gb, daily_growth_gb)

        assert runway_days == 20

        # Should trigger P1 if < 1 day (10% free ~= 30 min)
        free_space_gb = 10
        runway_hours = calculate_runway(free_space_gb, daily_growth_gb, unit='hours')

        assert runway_hours < 24 * 2  # Less than 2 days


class TestAlertAnalyzer:
    """Test AI-powered alert analysis"""

    @pytest.fixture
    def mock_llm_client(self, monkeypatch):
        """Mock Ollama LLM responses"""
        def mock_chat(messages, **kwargs):
            # Return canned AI response based on alert type
            alert_type = messages[1]['content']

            if "Write Latency" in alert_type:
                return {
                    "root_cause": "High I/O wait on pg_wal writes",
                    "immediate_actions": [
                        "Check pg_stat_statements for slow INSERT/UPDATE queries",
                        "Review checkpoint_timeout and checkpoint_completion_target",
                        "Verify disk I/O latency with iostat"
                    ],
                    "recommendations": [
                        {
                            "type": "config",
                            "summary": "Increase checkpoint_timeout to reduce write stalls",
                            "sql": "ALTER SYSTEM SET checkpoint_timeout = '15min';"
                        },
                        {
                            "type": "index",
                            "summary": "Add index on enrollments(student_id, semester)",
                            "sql": "CREATE INDEX idx_enrollments_lookup ON enrollments(student_id, semester);"
                        }
                    ],
                    "expected_improvement": "30-40% reduction in P99 write latency"
                }

            return {"error": "Unknown alert type"}

        monkeypatch.setattr("services.ai_client.AIClient.chat", mock_chat)

    def test_ai_analysis_includes_context(self, mock_llm_client):
        """Test that AI receives full alert context"""
        from services.alert_analyzer import build_ai_context

        alert = Alert(
            id="alert_123",
            severity="P1",
            title="Write Latency SLO Breach",
            metric_value=450.0,
            threshold=250.0,
            datasource_id="pg_university"
        )

        context = build_ai_context(alert, include_schema=True)

        assert "Write Latency" in context
        assert "450" in context
        assert "threshold: 250" in context.lower()
        assert "pg_university" in context

    def test_ai_recommendations_parsed_correctly(self, mock_llm_client):
        """Test parsing of AI recommendations"""
        analyzer = AlertAnalyzer()

        alert = Alert(
            severity="P1",
            title="Write Latency SLO Breach",
            datasource_id="pg_university"
        )

        analysis = analyzer.analyze(alert)

        assert analysis.root_cause is not None
        assert len(analysis.immediate_actions) > 0
        assert len(analysis.recommendations) == 2
        assert analysis.recommendations[0].type == "config"
        assert "ALTER SYSTEM" in analysis.recommendations[0].sql


class TestMetricCollection:
    """Test metric collection from database agents"""

    def test_postgres_health_metrics(self, mock_postgres_agent):
        """Test collecting health metrics from PostgreSQL"""
        from services.metric_collector import collect_health_metrics

        metrics = collect_health_metrics("pg_university")

        assert metrics["db_up"] == 1
        assert "numbackends" in metrics
        assert "conflicts" in metrics
        assert "deadlocks" in metrics

    def test_replication_metrics(self, mock_postgres_agent):
        """Test replication lag metrics"""
        from services.metric_collector import collect_replication_metrics

        metrics = collect_replication_metrics("pg_university")

        assert "replay_lag_seconds" in metrics
        assert "write_lag_bytes" in metrics
        assert "sync_state" in metrics
        assert metrics["num_standbys"] >= 0

    def test_metric_collection_failure_handling(self, monkeypatch):
        """Test graceful handling of metric collection failures"""
        def mock_fail_query(*args, **kwargs):
            raise Exception("Connection timeout")

        monkeypatch.setattr("services.agents.postgres_agent.PostgresAgent.query", mock_fail_query)

        from services.metric_collector import collect_health_metrics

        metrics = collect_health_metrics("pg_university")

        # Should return partial metrics with error flag
        assert metrics["error"] == True
        assert "timeout" in metrics["error_message"].lower()
```

---

### 4.2 Integration Tests (pytest)

**File**: `.venv/app/tests/integration/test_alert_workflows.py`

```python
import pytest
from fastapi.testclient import TestClient
from main import app
import asyncio

client = TestClient(app)

class TestAlertEndpoints:
    """Test alert API endpoints"""

    def test_get_active_alerts(self):
        """Test GET /alerts/active"""
        response = client.get("/alerts/active")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["alerts"], list)
        assert "count" in data

        if data["count"] > 0:
            alert = data["alerts"][0]
            assert "id" in alert
            assert "severity" in alert
            assert "title" in alert
            assert "timestamp" in alert

    def test_acknowledge_alert(self):
        """Test POST /alerts/acknowledge/{alert_id}"""
        # First create a test alert
        # (In real tests, this would be triggered by monitoring)

        response = client.post("/alerts/acknowledge/test_alert_123", json={
            "acknowledged_by": "test_user",
            "notes": "Investigating disk space issue"
        })

        assert response.status_code == 200
        data = response.json()

        assert data["acknowledged"] == True
        assert data["acknowledged_by"] == "test_user"

    def test_ai_analysis_endpoint(self):
        """Test POST /alerts/{alert_id}/analyze"""
        response = client.post("/alerts/test_alert_456/analyze")

        assert response.status_code == 200
        data = response.json()

        assert "root_cause" in data
        assert "immediate_actions" in data
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)

    def test_alert_history_filtering(self):
        """Test GET /alerts/history with filters"""
        response = client.get("/alerts/history", params={
            "ds_id": "pg_university",
            "severity": "P1",
            "limit": 10
        })

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["alerts"], list)
        assert len(data["alerts"]) <= 10

        # Verify all alerts are P1
        for alert in data["alerts"]:
            assert alert["severity"] == "P1"


class TestAlertWorkflows:
    """Test end-to-end alert workflows"""

    @pytest.mark.asyncio
    async def test_disk_space_alert_workflow(self, mock_node_exporter):
        """Test complete workflow: metric collection → alert → AI analysis"""
        from services.alert_engine import AlertEngine
        from services.metric_collector import collect_disk_metrics

        # 1. Collect metrics (mocked to show 8% free)
        metrics = collect_disk_metrics("pg_university")
        assert metrics["disk_free_percent"] == 8

        # 2. Evaluate rules
        engine = AlertEngine()
        alerts = engine.evaluate_all_rules("pg_university", metrics)

        # Should trigger P1 disk space alert
        disk_alerts = [a for a in alerts if "disk" in a.title.lower()]
        assert len(disk_alerts) == 1
        assert disk_alerts[0].severity == "P1"

        # 3. AI analysis
        from services.alert_analyzer import AlertAnalyzer
        analyzer = AlertAnalyzer()
        analysis = await analyzer.analyze_async(disk_alerts[0])

        assert analysis.root_cause is not None
        assert len(analysis.recommendations) > 0

        # Should recommend immediate actions
        actions = [a.lower() for a in analysis.immediate_actions]
        assert any("archive" in a or "clean" in a or "extend" in a for a in actions)

    @pytest.mark.asyncio
    async def test_replication_lag_alert_with_recovery(self):
        """Test replication alert that auto-resolves"""
        from services.alert_engine import AlertEngine
        from services.metric_collector import collect_replication_metrics

        # Initial state: high lag
        metrics_high_lag = {
            "replay_lag_seconds": 450,
            "sync_state": "async"
        }

        engine = AlertEngine()
        alerts = engine.evaluate_all_rules("pg_university", metrics_high_lag)

        rep_alerts = [a for a in alerts if "replication" in a.title.lower()]
        assert len(rep_alerts) == 1
        alert_id = rep_alerts[0].id

        # Later: lag recovers
        metrics_recovered = {
            "replay_lag_seconds": 120,
            "sync_state": "async"
        }

        alerts_after = engine.evaluate_all_rules("pg_university", metrics_recovered)
        rep_alerts_after = [a for a in alerts_after if a.id == alert_id]

        # Alert should auto-resolve
        assert len(rep_alerts_after) == 0

        # Check alert history shows resolution
        response = client.get(f"/alerts/history", params={"alert_id": alert_id})
        data = response.json()

        assert data["alerts"][0]["status"] == "resolved"
        assert data["alerts"][0]["auto_resolved"] == True
```

---

### 4.3 End-to-End Tests (Playwright for Tauri)

**File**: `tauri-app/tests/e2e/alerts.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { _electron as electron } from 'playwright';

test.describe('Alert System E2E', () => {
  let electronApp;
  let window;

  test.beforeAll(async () => {
    // Launch Tauri app
    electronApp = await electron.launch({
      args: ['tauri-app/src-tauri/target/release/ai-db-advisor.exe']
    });
    window = await electronApp.firstWindow();
  });

  test.afterAll(async () => {
    await electronApp.close();
  });

  test('should display critical alert banner when database goes down', async () => {
    // 1. Add datasource
    await window.click('button:has-text("Add Connection")');
    await window.fill('input[placeholder="Connection ID"]', 'test_pg');
    await window.selectOption('select[name="engine"]', 'postgres');
    await window.fill('input[placeholder="DSN"]',
      'postgresql://postgres:postgres@localhost:5432/UniversityDB');
    await window.click('button:has-text("Connect")');

    // 2. Verify monitoring started
    await expect(window.locator('.monitoring-status')).toContainText('Active');

    // 3. Simulate database failure (stop Docker container)
    // (This would be done via test setup script)

    // 4. Wait for alert banner (should appear within 10 seconds)
    const alertBanner = window.locator('.alert-banner.p1');
    await expect(alertBanner).toBeVisible({ timeout: 15000 });
    await expect(alertBanner).toContainText('Primary Down');

    // 5. Click on alert to view details
    await alertBanner.click();

    // 6. Verify AI analysis panel opens
    const analysisPanel = window.locator('.alert-analysis-panel');
    await expect(analysisPanel).toBeVisible();
    await expect(analysisPanel.locator('.root-cause')).toBeVisible();
    await expect(analysisPanel.locator('.recommendations')).toBeVisible();

    // 7. Verify recommended actions include "check server status"
    const actions = analysisPanel.locator('.immediate-actions li');
    const actionTexts = await actions.allTextContents();
    expect(actionTexts.some(a => a.toLowerCase().includes('server'))).toBe(true);
  });

  test('should show real-time WebSocket notifications', async () => {
    // 1. Monitor WebSocket connection
    const wsMessages = [];
    window.on('websocket', ws => {
      ws.on('framereceived', event => {
        wsMessages.push(JSON.parse(event.payload));
      });
    });

    // 2. Trigger backend alert (via API)
    await fetch('http://127.0.0.1:8000/test/trigger_alert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        severity: 'P2',
        title: 'CPU High',
        datasource_id: 'test_pg'
      })
    });

    // 3. Verify WebSocket message received
    await window.waitForTimeout(2000);
    expect(wsMessages.length).toBeGreaterThan(0);
    expect(wsMessages[0].severity).toBe('P2');
    expect(wsMessages[0].title).toBe('CPU High');

    // 4. Verify UI updated
    const alertCount = window.locator('.alert-count-badge');
    await expect(alertCount).toHaveText('1');
  });

  test('should support conversational AI chat for alerts', async () => {
    // 1. Open an existing alert
    await window.click('.alert-item:first-child');

    // 2. Navigate to AI Chat tab
    await window.click('button:has-text("AI Chat")');

    // 3. Ask follow-up question
    const chatInput = window.locator('textarea[placeholder*="Ask"]');
    await chatInput.fill('What specific queries are causing this latency issue?');
    await window.click('button:has-text("Send")');

    // 4. Wait for AI response
    const aiResponse = window.locator('.chat-message.ai:last-child');
    await expect(aiResponse).toBeVisible({ timeout: 10000 });

    // 5. Verify response includes query details
    const responseText = await aiResponse.textContent();
    expect(responseText.toLowerCase()).toContain('query');
  });
});
```

---

## 5. Performance Tests

### 5.1 Alert Latency Benchmark

**Target**: Alert detection → UI notification in < 2 seconds

```python
# File: .venv/app/tests/performance/test_alert_latency.py

import pytest
import time
from datetime import datetime

class TestAlertLatency:
    """Measure end-to-end alert latency"""

    def test_p1_alert_latency(self, benchmark):
        """Measure time from metric breach to alert trigger"""
        from services.alert_engine import AlertEngine
        from services.metric_collector import MetricSnapshot

        def trigger_alert():
            engine = AlertEngine()

            # Simulate metric breach
            snapshot = MetricSnapshot(
                timestamp=datetime.now(),
                metric="cpu_percent",
                value=95.0
            )

            start = time.time()
            alert = engine.evaluate_instant_rule("cpu_critical", snapshot)
            latency = (time.time() - start) * 1000  # milliseconds

            return latency

        # Run benchmark
        result = benchmark(trigger_alert)

        # Assert latency < 100ms for rule evaluation
        assert result < 100

    @pytest.mark.asyncio
    async def test_websocket_delivery_latency(self):
        """Measure WebSocket message delivery time"""
        from services.notification_manager import NotificationManager
        import asyncio

        manager = NotificationManager()

        # Connect mock client
        client_id = "test_client_123"
        received_at = None

        async def mock_client():
            nonlocal received_at
            async with manager.connect(client_id) as websocket:
                message = await websocket.receive_json()
                received_at = time.time()

        # Start client listener
        client_task = asyncio.create_task(mock_client())
        await asyncio.sleep(0.1)  # Let client connect

        # Send alert
        sent_at = time.time()
        await manager.broadcast_alert({
            "severity": "P1",
            "title": "Test Alert"
        })

        # Wait for delivery
        await client_task

        latency_ms = (received_at - sent_at) * 1000

        # Assert WebSocket delivery < 50ms
        assert latency_ms < 50
```

---

## 6. Test Data & Mocking Strategy

### 6.1 Mock Database Metrics

```python
# File: .venv/app/tests/conftest.py

import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_postgres_agent(monkeypatch):
    """Mock PostgresAgent for testing without real DB"""

    mock_agent = MagicMock()

    # Health metrics
    mock_agent.query.return_value = [
        {"numbackends": 15, "conflicts": 0, "deadlocks": 0}
    ]

    # Replication metrics
    mock_agent.get_replication_status.return_value = {
        "standbys": [
            {
                "client_addr": "192.168.1.10",
                "sync_state": "async",
                "replay_lag_seconds": 120,
                "write_lag_bytes": 1024000
            }
        ]
    }

    # Top queries
    mock_agent.get_top_queries.return_value = [
        {
            "query": "SELECT * FROM students WHERE department_id = $1",
            "calls": 1500,
            "mean_time_ms": 450.5,
            "total_time_ms": 675750
        }
    ]

    monkeypatch.setattr("services.agents.postgres_agent.PostgresAgent",
                        lambda *args: mock_agent)

    return mock_agent

@pytest.fixture
def mock_node_exporter():
    """Mock node_exporter filesystem metrics"""
    return {
        "node_filesystem_avail_bytes": 8_000_000_000,  # 8 GB
        "node_filesystem_size_bytes": 100_000_000_000,  # 100 GB
        "disk_free_percent": 8
    }
```

---

## 7. Test Execution Plan

### 7.1 Development Phase

```bash
# Run unit tests with coverage
cd .venv/app
pytest tests/ --cov=services --cov-report=html

# Target: 85%+ coverage
# Focus areas:
# - services/alert_engine.py
# - services/alert_analyzer.py
# - services/metric_collector.py
```

### 7.2 Integration Phase

```bash
# Run integration tests (requires backend running)
pytest tests/integration/ -v

# Test categories:
# - API endpoints
# - Alert workflows
# - WebSocket connections
```

### 7.3 E2E Phase

```bash
# Build Tauri app for testing
cd tauri-app
npm run tauri build

# Run Playwright tests
npx playwright test tests/e2e/alerts.spec.ts
```

### 7.4 Performance Phase

```bash
# Run performance benchmarks
pytest tests/performance/ --benchmark-only

# Generate performance report
pytest-benchmark compare
```

---

## 8. Success Criteria

### 8.1 Functional Requirements

- [ ] All P1 alert scenarios detect and trigger within 10 seconds
- [ ] AI analysis provides actionable recommendations for 90%+ of alerts
- [ ] WebSocket notifications deliver to UI in < 2 seconds
- [ ] Alert history persists and filters correctly
- [ ] Users can acknowledge/resolve alerts
- [ ] Conversational AI chat works for follow-up questions

### 8.2 Quality Requirements

- [ ] Unit test coverage ≥ 85%
- [ ] All integration tests pass
- [ ] E2E tests cover top 5 alert scenarios
- [ ] Zero false positives in 24-hour monitoring test
- [ ] Alert fatigue prevention (max 10 alerts/hour unless genuine incidents)

### 8.3 Performance Requirements

- [ ] Alert evaluation latency < 100ms
- [ ] WebSocket delivery latency < 50ms
- [ ] AI analysis completes in < 3 seconds
- [ ] UI remains responsive during alert storms (50+ alerts/min)

---

## 9. Test Environment Setup

### 9.1 Backend Test Environment

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov pytest-benchmark

# Set environment variables
export ENV=test
export LLM_ENDPOINT=http://localhost:11434
export POSTGRES_TEST_DSN=postgresql://postgres:postgres@localhost:5432/test_db

# Run tests
pytest
```

### 9.2 Frontend Test Environment

```bash
# Install Playwright
cd tauri-app
npm install -D @playwright/test

# Initialize Playwright
npx playwright install

# Run E2E tests
npm run test:e2e
```

### 9.3 Mock Services

- **Mock Ollama**: Use VCR.py to record/replay LLM responses
- **Mock Databases**: Docker Compose with pre-seeded test data
- **Mock Monitoring**: Inject synthetic metrics via test fixtures

---

## 10. Continuous Testing

### 10.1 CI/CD Integration (GitHub Actions)

```yaml
# File: .github/workflows/test-alerts.yml

name: Alert System Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run unit tests
        run: pytest tests/ --cov=services --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - name: Run integration tests
        run: pytest tests/integration/ -v

  e2e-tests:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node
        uses: actions/setup-node@v3
      - name: Install Tauri dependencies
        run: npm install
        working-directory: tauri-app
      - name: Build Tauri app
        run: npm run tauri build
        working-directory: tauri-app
      - name: Run E2E tests
        run: npx playwright test
        working-directory: tauri-app
```

---

## 11. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **False Positives** | High (alert fatigue) | - Implement hysteresis/cooldown periods<br>- Require sustained thresholds (e.g., 10 min)<br>- A/B test thresholds in staging |
| **WebSocket Connection Drops** | Medium (missed alerts) | - Auto-reconnect with exponential backoff<br>- Fallback to polling every 30s<br>- Alert history as backup |
| **AI Hallucinations** | Medium (bad advice) | - Validate AI recommendations against known good patterns<br>- Show confidence scores<br>- Always include disclaimer |
| **Performance Overhead** | Low (monitoring impact) | - Use connection pooling<br>- Cache schema/stats (5 min TTL)<br>- Batch metric collection |

---

## 12. Next Steps After Testing

1. **Load Testing**: Simulate 100+ datasources with concurrent alerts
2. **Security Testing**: Test alert injection, XSS in alert messages
3. **Accessibility Testing**: Ensure alerts work with screen readers
4. **Mobile Responsiveness**: (If planning web version of Tauri app)
5. **Documentation**: Write user guide for configuring custom alert rules

---

## Appendix A: Alert Rule Schema

```json
{
  "id": "write_latency_p1",
  "name": "Write Latency SLO Breach",
  "severity": "P1",
  "description": "Triggers when write P99 latency exceeds 250ms",
  "enabled": true,
  "datasource_types": ["postgres", "mysql", "sqlserver"],
  "conditions": {
    "metric": "write_p99_latency_ms",
    "operator": ">",
    "threshold": 250,
    "duration_minutes": 5,
    "evaluation_interval_seconds": 30
  },
  "notification_channels": ["websocket", "email"],
  "auto_resolve": true,
  "cooldown_minutes": 15,
  "ai_analysis_enabled": true
}
```

## Appendix B: Sample AI Prompts

**System Prompt for Alert Analysis**:
```
You are an expert database administrator analyzing a critical alert.

Alert Details:
- Severity: {severity}
- Title: {title}
- Metric: {metric_name} = {value} (threshold: {threshold})
- Datasource: {datasource_id} ({engine})
- Timestamp: {timestamp}

Database Context:
- Schema sample: {schema_excerpt}
- Recent queries: {top_queries}
- Current stats: {db_stats}

Provide a structured analysis:
1. Root Cause: Identify the most likely reason for this alert
2. Immediate Actions: 3-5 urgent steps to mitigate impact
3. Recommendations: Long-term fixes with SQL/config changes
4. Expected Improvement: Quantify expected gains

Format as JSON:
{
  "root_cause": "...",
  "immediate_actions": ["...", "..."],
  "recommendations": [
    {"type": "index|config|query", "summary": "...", "sql": "..."}
  ],
  "expected_improvement": "..."
}
```

---

**End of Test Plan**

This comprehensive plan covers all aspects of testing the AI-powered alert system. Proceed with implementation following the todo list structure.
