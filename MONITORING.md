# AI DB Advisor - Monitoring Setup

Complete monitoring setup with Prometheus, Grafana, and custom metrics for all services.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Prometheus                             │
│              (Metrics Collection & Storage)                  │
│                   http://localhost:9090                      │
└───────────┬─────────────────────────────────────────────────┘
            │
            │ Scrapes Metrics From:
            │
    ┌───────┴────────┬─────────────┬──────────────┬────────────┐
    │                │             │              │            │
┌───▼────┐  ┌───────▼──────┐  ┌──▼──────┐  ┌───▼─────┐  ┌───▼──────┐
│FastAPI │  │  MCP Bridge  │  │PostgreSQL│  │Grafana  │  │Prometheus│
│Backend │  │              │  │ Exporter │  │         │  │  Itself  │
│:8000   │  │    :3000     │  │  :9187   │  │  :3000  │  │  :9090   │
└────────┘  └──────────────┘  └──────────┘  └─────────┘  └──────────┘
```

## Services Overview

### 1. **Prometheus** (Port 9090)
- **Purpose**: Time-series database for metrics
- **URL**: http://localhost:9090
- **Data Retention**: 15 days (default)
- **Scrape Interval**: 10-15 seconds

### 2. **Grafana** (Port 3001)
- **Purpose**: Metrics visualization and dashboards
- **URL**: http://localhost:3001
- **Login**: `admin` / `admin123`
- **Features**:
  - Custom dashboards
  - Alert notifications
  - Data source: Prometheus

### 3. **AlertManager** (Port 9093)
- **Purpose**: Alert routing and notifications
- **URL**: http://localhost:9093
- **Config**: `monitoring/alertmanager.yml`

### 4. **PostgreSQL Exporter** (Port 9187)
- **Purpose**: PostgreSQL database metrics
- **URL**: http://localhost:9187/metrics
- **Database**: UniversityDB
- **Metrics**: Connections, queries, locks, etc.

## Monitored Applications

### 1. FastAPI Backend (Port 8000)

**Metrics Endpoint**: http://127.0.0.1:8000/metrics

**Available Metrics**:
- `http_requests_total` - Total HTTP requests by method, status
- `http_request_duration_seconds` - Request latency histogram
- `http_requests_inprogress` - Active requests
- `python_gc_*` - Python garbage collection stats
- `python_info` - Python version information

**Custom Application Metrics**:
- Database query performance
- AI suggestion generation time
- LLM API call duration
- Index recommendation counts

### 2. MCP HTTP Bridge (Port 3000)

**Metrics Endpoint**: http://localhost:3000/metrics

**Available Metrics**:
- `mcp_requests_total{method, status}` - Total MCP requests
- `mcp_request_duration_seconds{method}` - MCP request latency
- `mcp_tools_discovered` - Number of MCP tools available
- `mcp_server_status` - MCP server health (1=running, 0=stopped)
- `http_requests_total` - HTTP requests to bridge
- `http_request_duration_seconds` - HTTP request latency

**Methods Tracked**:
- `tools/list` - List available tools
- `tools/call` - Execute MCP tools
- `query/optimize` - Query optimization requests

### 3. PostgreSQL Database

**Metrics Source**: PostgreSQL Exporter (port 9187)

**Available Metrics**:
- `pg_up` - Database availability
- `pg_stat_database_*` - Database statistics
- `pg_locks_*` - Lock information
- `pg_stat_activity_*` - Active connections
- `pg_stat_statements_*` - Query performance (if extension enabled)

## Quick Start

### 1. Start Monitoring Stack

```bash
# Option 1: Use the startup script
start_monitoring.bat

# Option 2: Manual start
docker-compose -f docker-compose.monitoring.yml up -d
```

### 2. Start Backend Services

**Terminal 1 - FastAPI Backend**:
```bash
python run.py
```

**Terminal 2 - MCP Bridge**:
```bash
python mcp_http_bridge.py
```

### 3. Verify Services

Check all services are running:
```bash
# Check Docker services
docker-compose -f docker-compose.monitoring.yml ps

# Test metrics endpoints
curl http://127.0.0.1:8000/metrics
curl http://localhost:3000/metrics
curl http://localhost:9187/metrics
```

### 4. Access Monitoring Dashboards

1. **Prometheus**: http://localhost:9090
   - Go to **Status → Targets** to verify all services are being scraped
   - Query metrics in the **Graph** tab

2. **Grafana**: http://localhost:3001
   - Login: `admin` / `admin123`
   - Add Prometheus data source (URL: `http://prometheus:9090`)
   - Import dashboards (see below)

## Setting Up Grafana

### Step 1: Add Prometheus Data Source

1. Open http://localhost:3001
2. Login with `admin` / `admin123`
3. Go to **Configuration → Data Sources**
4. Click **Add data source**
5. Select **Prometheus**
6. Settings:
   - Name: `Prometheus`
   - URL: `http://prometheus:9090`
   - Access: `Server (default)`
7. Click **Save & Test**

### Step 2: Import Dashboards

#### PostgreSQL Dashboard
1. Go to **Dashboards → Import**
2. Enter ID: **9628**
3. Select Prometheus data source
4. Click **Import**

#### FastAPI/MCP Custom Dashboard
Create a new dashboard with panels for:
- Request rate: `rate(http_requests_total[5m])`
- Request duration: `http_request_duration_seconds`
- MCP tool calls: `rate(mcp_requests_total[5m])`
- MCP latency: `mcp_request_duration_seconds`

## Useful Prometheus Queries

### Backend Performance
```promql
# Request rate per endpoint
rate(http_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m])
```

### MCP Bridge
```promql
# MCP requests per method
rate(mcp_requests_total[5m])

# MCP error rate
rate(mcp_requests_total{status="error"}[5m])

# Number of tools
mcp_tools_discovered

# MCP server health
mcp_server_status
```

### PostgreSQL
```promql
# Database is up
pg_up

# Active connections
pg_stat_database_numbackends

# Query execution time
rate(pg_stat_statements_total_time[5m])
```

## Alert Rules

Alert rules are defined in `monitoring/alerts.yml`. Examples:

### High Error Rate
```yaml
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High error rate detected"
```

### Database Down
```yaml
- alert: PostgreSQLDown
  expr: pg_up == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "PostgreSQL database is down"
```

## Troubleshooting

### Metrics endpoint returns 404

**Problem**: `/metrics` endpoint not found

**Solution**:
1. Restart the application to load Prometheus instrumentation
2. Verify `prometheus_fastapi_instrumentator` is installed
3. Check application logs for errors

### Prometheus can't scrape targets

**Problem**: Targets show as "DOWN" in Prometheus

**Solution**:
1. Verify services are running: `curl http://host:port/metrics`
2. Check Docker network connectivity
3. For Windows: Ensure `host.docker.internal` resolves correctly
4. Check firewall rules

### Grafana can't connect to Prometheus

**Problem**: "Error reading Prometheus" in Grafana

**Solution**:
1. Use URL: `http://prometheus:9090` (container name, not localhost)
2. Verify Prometheus is running: `docker ps`
3. Test from Grafana container: `docker exec -it ai-db-advisor-grafana curl http://prometheus:9090`

### MCP Bridge metrics not updating

**Problem**: Metrics show old data or zeros

**Solution**:
1. Restart MCP bridge: Stop and run `python mcp_http_bridge.py`
2. Make a test request: `curl http://localhost:3000/tools`
3. Check metrics: `curl http://localhost:3000/metrics`

## Production Considerations

### Security
- [ ] Change default Grafana password
- [ ] Enable authentication on Prometheus
- [ ] Use HTTPS for all endpoints
- [ ] Restrict access to metrics endpoints

### Performance
- [ ] Adjust scrape intervals based on load
- [ ] Configure retention policies
- [ ] Set up metric aggregation
- [ ] Enable remote storage for long-term retention

### High Availability
- [ ] Run multiple Prometheus instances
- [ ] Configure AlertManager HA
- [ ] Set up Grafana with external database
- [ ] Implement backup strategy

## Architecture Decisions

### Why Prometheus?
- Industry standard for metrics
- Powerful query language (PromQL)
- Excellent ecosystem (exporters, Grafana, etc.)
- Pull-based model works well with microservices

### Why Grafana?
- Best-in-class visualization
- Wide data source support
- Alerting capabilities
- Large community and dashboard library

### Metrics Instrumentation
- FastAPI: `prometheus_fastapi_instrumentator` for automatic HTTP metrics
- Custom metrics: `prometheus_client` for application-specific metrics
- PostgreSQL: Official `postgres_exporter` for database metrics

## Useful Links

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PostgreSQL Exporter](https://github.com/prometheus-community/postgres_exporter)
- [FastAPI Instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)

## Support

For issues or questions:
1. Check application logs: `docker-compose -f docker-compose.monitoring.yml logs`
2. Verify configuration files in `monitoring/` directory
3. Test individual services with curl commands
4. Review Prometheus targets: http://localhost:9090/targets
