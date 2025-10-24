# Grafana Integration Plan for AI DB Advisor

## 📊 Overview

Integrate Grafana for comprehensive monitoring of:
1. **Database Performance** - Query times, connections, locks, cache hit ratios
2. **Application Metrics** - API response times, request rates, error rates
3. **MCP Operations** - MCP suggestions, approvals, executions
4. **AI Operations** - LLM request times, suggestion quality metrics

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Grafana Dashboards                        │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │  Database    │  Application │  AI & MCP Operations     │ │
│  │  Performance │  Metrics     │  Dashboard               │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │ Queries
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Prometheus (Time Series DB)               │
└───────────┬─────────────────────────────┬───────────────────┘
            │                             │
            ▼                             ▼
┌───────────────────────┐   ┌────────────────────────────────┐
│ FastAPI App           │   │ PostgreSQL Exporter            │
│ (Prometheus Metrics)  │   │ (Database Metrics)             │
│ - /metrics endpoint   │   │ - postgres_exporter            │
└───────────────────────┘   └────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Databases (PostgreSQL, MySQL, etc.)       │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Implementation Phases

### Phase 1: Prometheus Metrics Exporter (FastAPI)
**Goal**: Expose application metrics in Prometheus format

**Components**:
1. Install `prometheus-fastapi-instrumentator`
2. Add `/metrics` endpoint to FastAPI app
3. Export custom metrics:
   - Query execution times
   - AI suggestion generation times
   - MCP operation metrics
   - Database connection pool status
   - Error rates by endpoint

**Metrics to Export**:
```python
# Request metrics (auto-instrumented)
- http_requests_total (counter)
- http_request_duration_seconds (histogram)
- http_request_size_bytes (summary)
- http_response_size_bytes (summary)

# Custom metrics
- db_query_duration_seconds (histogram) - Per database type
- ai_suggestion_generation_seconds (histogram)
- mcp_operation_total (counter) - By operation type
- database_connections_active (gauge) - Per datasource
- ai_suggestions_generated_total (counter) - By type
- mcp_suggestions_approved_total (counter)
- mcp_suggestions_executed_total (counter)
- optimization_improvements_percentage (gauge)
```

### Phase 2: PostgreSQL Exporter Setup
**Goal**: Collect database-level metrics

**Components**:
1. Install `postgres_exporter` (Docker or binary)
2. Configure connection to each PostgreSQL database
3. Expose metrics on port 9187

**Metrics Collected**:
- Database size and growth
- Active connections
- Transaction rates
- Cache hit ratios
- Locks and deadlocks
- Table/index sizes
- Slow queries
- Replication lag (if applicable)

### Phase 3: Prometheus Setup
**Goal**: Scrape and store metrics

**Configuration**:
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # FastAPI Application
  - job_name: 'ai-db-advisor'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'

  # PostgreSQL Databases
  - job_name: 'postgres-university'
    static_configs:
      - targets: ['localhost:9187']

  # MCP Bridge
  - job_name: 'mcp-bridge'
    static_configs:
      - targets: ['localhost:3000']
    metrics_path: '/metrics'
```

### Phase 4: Grafana Dashboards
**Goal**: Visualize all metrics

**Dashboards to Create**:

#### 1. Database Performance Dashboard
**Panels**:
- Query execution time (avg, p50, p95, p99)
- Active connections by database
- Transaction rate (commits/rollbacks per second)
- Cache hit ratio
- Table/index sizes
- Slow queries (> 1s)
- Locks and waiting queries
- Database growth trend

#### 2. Application Performance Dashboard
**Panels**:
- Request rate (requests/second)
- Response time (avg, p50, p95, p99)
- Error rate (4xx, 5xx)
- Active API endpoints usage
- Top slowest endpoints
- Request/response size distribution

#### 3. AI & MCP Operations Dashboard
**Panels**:
- AI suggestions generated (by type)
- AI suggestion generation time
- MCP suggestions requested vs generated
- MCP approval rate
- MCP execution success rate
- Average optimization improvement %
- LLM response times
- MCP tool invocation counts

#### 4. System Health Dashboard
**Panels**:
- CPU usage
- Memory usage
- Disk I/O
- Network traffic
- Process uptime
- Error logs count

### Phase 5: Alerting Rules
**Goal**: Proactive monitoring

**Alert Rules**:
```yaml
groups:
  - name: database_alerts
    rules:
      - alert: HighQueryDuration
        expr: db_query_duration_seconds{quantile="0.95"} > 5
        for: 5m
        annotations:
          summary: "Slow queries detected"

      - alert: HighDatabaseConnections
        expr: database_connections_active > 80
        for: 2m
        annotations:
          summary: "Database connection pool near limit"

      - alert: LowCacheHitRatio
        expr: pg_cache_hit_ratio < 0.90
        for: 10m
        annotations:
          summary: "PostgreSQL cache hit ratio below 90%"

  - name: application_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"

      - alert: SlowAPIResponse
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 2
        for: 5m
        annotations:
          summary: "API response time degraded"

  - name: mcp_alerts
    rules:
      - alert: MCPFailureRate
        expr: rate(mcp_operation_total{status="failed"}[5m]) > 0.1
        for: 5m
        annotations:
          summary: "MCP operations failing"
```

### Phase 6: Notification Channels
**Integrations**:
- Email notifications
- Slack/Discord webhooks
- PagerDuty (for critical alerts)

## 🚀 Implementation Steps

### Step 1: Install Dependencies
```bash
# Python dependencies
pip install prometheus-fastapi-instrumentator
pip install prometheus-client

# Docker services (Prometheus + Grafana)
# OR install binaries
```

### Step 2: Update FastAPI App
Add Prometheus instrumentation to main.py

### Step 3: Deploy Prometheus
Create docker-compose.yml with Prometheus configuration

### Step 4: Deploy Grafana
Add Grafana to docker-compose.yml with volume mounts

### Step 5: Configure Data Sources
- Add Prometheus data source in Grafana
- Add PostgreSQL direct connection (optional)

### Step 6: Import Dashboards
- Use pre-built community dashboards
- Customize for AI DB Advisor specifics

### Step 7: Configure Alerts
- Import alert rules
- Set up notification channels

### Step 8: Test & Validate
- Generate load
- Verify metrics collection
- Test alert triggers

## 📦 Required Files

1. **`prometheus.yml`** - Prometheus configuration
2. **`docker-compose.yml`** - Prometheus + Grafana stack
3. **`grafana/dashboards/*.json`** - Dashboard definitions
4. **`grafana/provisioning/`** - Auto-provisioning configs
5. **`alerts.yml`** - Alert rules
6. **`monitoring/metrics.py`** - Custom metrics helpers
7. **Updated `main.py`** - With Prometheus instrumentation

## 📊 Dashboard Panels Examples

### Database Query Performance
```
Panel: Query Execution Time (p95)
Query: histogram_quantile(0.95, rate(db_query_duration_seconds_bucket[5m]))
Visualization: Graph (time series)
Thresholds: Warning > 1s, Critical > 5s
```

### AI Suggestion Success Rate
```
Panel: AI Suggestions Generated
Query: rate(ai_suggestions_generated_total[5m])
Visualization: Stat panel
Unit: ops/sec
```

### MCP Approval Flow
```
Panel: MCP Approval Funnel
Queries:
  - mcp_suggestions_generated_total (Requested)
  - mcp_suggestions_approved_total (Approved)
  - mcp_suggestions_executed_total (Executed)
Visualization: Bar gauge
Shows: Conversion rates through approval workflow
```

## 🎯 Success Metrics

After implementation, you'll have:

✅ Real-time database performance monitoring
✅ Application health visibility
✅ AI/MCP operations tracking
✅ Proactive alerting on issues
✅ Historical trend analysis
✅ Capacity planning insights
✅ Optimization impact measurement

## 🔧 Maintenance

**Regular Tasks**:
- Review alert thresholds monthly
- Archive old metrics (retention policy)
- Update dashboards as features evolve
- Test backup/restore procedures

## 📚 Resources

- Prometheus FastAPI Instrumentator: https://github.com/trallnag/prometheus-fastapi-instrumentator
- Grafana Dashboards: https://grafana.com/grafana/dashboards/
- PostgreSQL Exporter: https://github.com/prometheus-community/postgres_exporter
- Pre-built FastAPI Dashboard: https://grafana.com/grafana/dashboards/16110

---

**Estimated Time**: 4-6 hours for full implementation
**Difficulty**: Medium
**Priority**: High (Production monitoring essential)

Ready to start implementation?
