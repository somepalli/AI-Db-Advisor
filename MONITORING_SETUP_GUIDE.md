# Grafana Monitoring Setup Guide

## 📊 What's Been Implemented

✅ **Prometheus Metrics Exporter** - Custom metrics for DB, AI, and MCP operations
✅ **Docker Compose Stack** - Prometheus, Grafana, AlertManager, PostgreSQL Exporter
✅ **Alert Rules** - Proactive monitoring for slow queries, errors, and MCP failures
✅ **FastAPI Instrumentation** - Automatic HTTP metrics collection
✅ **Custom Metrics Module** - Track-specific operations with context managers

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- AI DB Advisor app running
- PostgreSQL database accessible

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- `prometheus-fastapi-instrumentator==7.0.0`
- `prometheus-client==0.21.0`

### Step 2: Create Configuration Files
```bash
bash setup_monitoring.sh
```

This creates:
- `monitoring/prometheus.yml` - Prometheus scrape configuration
- `monitoring/alerts.yml` - Alert rules
- `monitoring/grafana/provisioning/` - Auto-provisioning configs
- `monitoring/alertmanager.yml` - Alert routing

### Step 3: Start Monitoring Stack
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

This starts:
- **Prometheus** on `http://localhost:9090`
- **Grafana** on `http://localhost:3001`
- **PostgreSQL Exporter** on `http://localhost:9187`
- **AlertManager** on `http://localhost:9093`

### Step 4: Start Your Application
```bash
# Terminal 1: MCP Bridge
python mcp_http_bridge.py

# Terminal 2: Main App
python run.py
```

### Step 5: Verify Metrics
```bash
# Check FastAPI metrics
curl http://localhost:8000/metrics

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets
```

## 📈 Accessing Dashboards

### Grafana Login
- URL: http://localhost:3001
- Username: `admin`
- Password: `admin123`

### Import Pre-built Dashboards

1. **FastAPI Observability** (ID: 16110)
   - Go to Dashboards → Import
   - Enter ID: `16110`
   - Select Prometheus datasource
   - Click Import

2. **PostgreSQL Database** (ID: 9628)
   - Go to Dashboards → Import
   - Enter ID: `9628`
   - Select Prometheus datasource
   - Click Import

3. **Custom AI DB Advisor Dashboard**
   - Create new dashboard
   - Add panels using queries below

## 📊 Custom Dashboard Queries

### Database Performance Panel
```promql
# Average query duration by database type
rate(db_query_duration_seconds_sum[5m]) / rate(db_query_duration_seconds_count[5m])

# 95th percentile query duration
histogram_quantile(0.95, rate(db_query_duration_seconds_bucket[5m]))

# Query rate by database
rate(db_queries_total[5m])
```

### AI Operations Panel
```promql
# AI suggestions generated per minute
rate(ai_suggestions_generated_total[1m]) * 60

# AI generation time (p95)
histogram_quantile(0.95, rate(ai_suggestion_generation_seconds_bucket[5m]))

# AI suggestions by type
sum by (suggestion_type) (rate(ai_suggestions_generated_total[5m]))
```

### MCP Operations Panel
```promql
# MCP approval rate
rate(mcp_suggestions_approved_total[5m]) / rate(mcp_operation_total{operation_type="suggest"}[5m])

# MCP execution success rate
rate(mcp_suggestions_executed_total{execution_status="success"}[5m]) / rate(mcp_suggestions_executed_total[5m])

# MCP operations by type
sum by (operation_type) (rate(mcp_operation_total[5m]))
```

### API Performance Panel
```promql
# Request rate
rate(http_requests_total[5m])

# Response time (p95)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m])
```

## 🔔 Alert Configuration

Alerts are automatically loaded from `monitoring/alerts.yml`.

### View Active Alerts
1. Prometheus: http://localhost:9090/alerts
2. Grafana: Alerting → Alert rules

### Configure Notifications

Edit `monitoring/alertmanager.yml`:

```yaml
receivers:
  - name: 'email'
    email_configs:
    - to: 'your-email@example.com'
      from: 'alerts@ai-db-advisor.com'
      smarthost: 'smtp.gmail.com:587'
      auth_username: 'your-email@gmail.com'
      auth_password: 'your-app-password'

  - name: 'slack'
    slack_configs:
    - api_url: 'YOUR_SLACK_WEBHOOK_URL'
      channel: '#alerts'
```

Then restart AlertManager:
```bash
docker-compose -f docker-compose.monitoring.yml restart alertmanager
```

## 🛠️ Custom Metrics Usage

### In Your Code

```python
from monitoring.metrics import (
    track_query_time,
    track_ai_suggestion_generation,
    track_mcp_operation,
    record_mcp_approval
)

# Track database query
with track_query_time("postgres", "select"):
    result = execute_query(sql)

# Track AI suggestion generation
with track_ai_suggestion_generation("ollama", "index"):
    suggestion = generate_suggestion(query)

# Track MCP operation
with track_mcp_operation("suggest", "query_optimizer"):
    mcp_result = mcp_client.generate_suggestion(...)

# Record MCP approval
record_mcp_approval("query_optimizer", "low")
```

## 📋 Metrics Reference

### Auto-Instrumented Metrics (FastAPI)
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request duration histogram
- `http_request_size_bytes` - Request size
- `http_response_size_bytes` - Response size
- `http_requests_inprogress` - Currently processing requests

### Custom Database Metrics
- `db_query_duration_seconds` - Query execution time
- `database_connections_active` - Active connections
- `db_queries_total` - Total queries executed
- `database_size_bytes` - Database size

### Custom AI Metrics
- `ai_suggestion_generation_seconds` - AI generation time
- `ai_suggestions_generated_total` - Total suggestions
- `ai_suggestions_validated_total` - Validated suggestions
- `llm_api_response_seconds` - LLM API response time

### Custom MCP Metrics
- `mcp_operation_total` - Total MCP operations
- `mcp_suggestion_duration_seconds` - MCP suggestion time
- `mcp_suggestions_approved_total` - Approved suggestions
- `mcp_suggestions_executed_total` - Executed suggestions
- `mcp_suggestions_rejected_total` - Rejected suggestions

### Custom Optimization Metrics
- `optimization_improvement_percentage` - Optimization gains
- `index_recommendations_applied_total` - Applied index recommendations
- `query_rewrites_applied_total` - Applied query rewrites

## 🔧 Troubleshooting

### Metrics Not Showing
1. Check `/metrics` endpoint: `curl http://localhost:8000/metrics`
2. Verify Prometheus targets: http://localhost:9090/targets
3. Check Docker logs: `docker-compose -f docker-compose.monitoring.yml logs prometheus`

### Grafana Can't Connect to Prometheus
1. Check network: `docker network ls`
2. Verify Prometheus URL in Grafana datasource
3. Test connection: Settings → Data Sources → Prometheus → Save & Test

### PostgreSQL Exporter Failing
1. Check connection string in `docker-compose.monitoring.yml`
2. Verify PostgreSQL is accessible from Docker
3. Check exporter logs: `docker logs ai-db-advisor-postgres-exporter`

## 📊 Dashboard Recommendations

### 1. Executive Dashboard
- Total requests/day
- Average response time
- Error rate
- Database size growth
- AI suggestions generated
- MCP approval rate

### 2. Performance Dashboard
- Query duration (p50, p95, p99)
- API response time
- Active connections
- Cache hit ratio
- Slow queries

### 3. Operations Dashboard
- MCP operations funnel
- AI suggestion breakdown
- Optimization improvements
- Alert history
- System health

## 🎯 Next Steps

1. **Customize Dashboards**: Add panels specific to your use cases
2. **Set Alert Thresholds**: Adjust based on your baselines
3. **Configure Notifications**: Set up email/Slack alerts
4. **Add More Exporters**: MySQL, MongoDB exporters as needed
5. **Enable Long-term Storage**: Configure Prometheus remote write

## 📚 Resources

- **Prometheus Docs**: https://prometheus.io/docs/
- **Grafana Docs**: https://grafana.com/docs/
- **FastAPI Instrumentator**: https://github.com/trallnag/prometheus-fastapi-instrumentator
- **PostgreSQL Exporter**: https://github.com/prometheus-community/postgres_exporter
- **PromQL Cheatsheet**: https://promlabs.com/promql-cheat-sheet/

---

**Status**: ✅ Ready for deployment!

All configuration files are in place. Run the commands above to start monitoring your AI DB Advisor system!
