# AI DB Advisor - Monitoring Setup

Complete monitoring setup with Prometheus, Grafana, and custom metrics for all services.

The monitoring stack is part of the main `docker-compose.yml` under the `monitoring`
profile, so it shares a network with the app and scrapes the backend directly:

```bash
cp .env.docker.example .env
docker compose --profile monitoring up --build
```

| Service        | URL                          | Notes                              |
| -------------- | ---------------------------- | ---------------------------------- |
| Grafana        | http://localhost:3001        | `admin` / `admin123` (overridable) |
| Prometheus     | http://localhost:9090        | scrapes `backend:8095/metrics`     |
| PG Exporter    | http://localhost:9187/metrics| `PG_EXPORTER_DSN`                  |
| Alertmanager   | http://localhost:9093        | `monitoring/alertmanager.yml`      |

Grafana's Prometheus datasource and dashboards are **auto-provisioned** — no manual
setup needed. The sections below document the metrics and queries in more detail.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Prometheus                             │
│              (Metrics Collection & Storage)                  │
│                   http://localhost:9090                      │
└───────────┬─────────────────────────────────────────────────┘
            │
            │ Scrapes Metrics From (over the compose network):
            │
    ┌───────┴────────┬──────────────┬───────────────┐
    │                │              │               │
┌───▼─────────┐  ┌───▼──────────┐  ┌▼─────────┐  ┌──▼───────┐
│FastAPI       │  │PostgreSQL    │  │Grafana   │  │Prometheus│
│Backend       │  │ Exporter     │  │          │  │  Itself  │
│backend:8095  │  │ :9187        │  │ :3000    │  │  :9090   │
└──────────────┘  └──────────────┘  └──────────┘  └──────────┘
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
- **Database**: set via `PG_EXPORTER_DSN` (defaults to the sample UniversityDB on the host)
- **Metrics**: Connections, queries, locks, etc.

## Monitored Applications

### 1. FastAPI Backend (scraped at `backend:8095`)

**Metrics Endpoint**: `http://backend:8095/metrics` in-network
(`http://localhost:8095/metrics` from the host, since the port is published for debugging)

**Available Metrics**:
- `http_requests_total` - Total HTTP requests by method, status
- `http_request_duration_seconds` - Request latency histogram
- `http_requests_inprogress` - Active requests
- `python_gc_*` - Python garbage collection stats
- `python_info` - Python version information

**Custom Application Metrics** (defined in `backend/monitoring/metrics.py`):
- `db_query_duration_seconds` / `db_queries_total` - database query performance
- `ai_suggestion_generation_seconds` / `ai_suggestions_generated_total` - AI suggestion timing
- `llm_api_response_seconds` - LLM API call duration
- `mcp_operation_total` - in-process MCP operations
- `index_recommendations_applied_total` / `query_rewrites_applied_total` - optimization actions

> The standalone MCP HTTP bridge is not part of this stack (MCP runs in-process and
> is off by default), so it is no longer a Prometheus scrape target. MCP activity is
> captured by the backend's own `mcp_*` metrics above.

### 2. PostgreSQL Database

**Metrics Source**: PostgreSQL Exporter (port 9187)

**Available Metrics**:
- `pg_up` - Database availability
- `pg_stat_database_*` - Database statistics
- `pg_locks_*` - Lock information
- `pg_stat_activity_*` - Active connections
- `pg_stat_statements_*` - Query performance (if extension enabled)

## Quick Start

### 1. Start the stack with monitoring

```bash
cp .env.docker.example .env          # first time only
docker compose --profile monitoring up --build
```

This brings up the backend, frontend, Prometheus, Grafana, the PostgreSQL
exporter, and Alertmanager on one network. Omit `--profile monitoring` to run
just the app.

### 2. Verify services

```bash
# Container status
docker compose --profile monitoring ps

# Metrics endpoints (from the host)
curl http://localhost:8095/metrics    # backend (published for debugging)
curl http://localhost:9187/metrics    # postgres exporter
```

Inside the network, Prometheus reaches the backend at `backend:8095` — the app
does not need to be published for scraping to work.

### 3. Access dashboards

1. **Prometheus**: http://localhost:9090
   - **Status → Targets** should show `ai-db-advisor-app` (backend) and
     `postgres-universitydb` as **UP**.

2. **Grafana**: http://localhost:3001 (`admin` / `admin123`)
   - The Prometheus datasource and the bundled dashboards are **auto-provisioned**
     from `monitoring/grafana/provisioning` — no manual setup required.

## Grafana provisioning

Everything under `monitoring/grafana/provisioning` is loaded on startup:

- **Datasource** (`datasources/prometheus.yml`): Prometheus at `http://prometheus:9090`,
  pinned to `uid: prometheus` and marked default. Dashboards reference this uid so
  their panels bind automatically.
- **Dashboards** (`dashboards/dashboards.yml` → `monitoring/grafana/dashboards/`):
  the FastAPI backend dashboard is active. (The MCP and ClickHouse dashboards ship
  but stay empty — those components are not part of this stack.)

To add your own dashboard, drop its JSON into `monitoring/grafana/dashboards/`
(set each panel's datasource uid to `prometheus`) and restart Grafana. To import a
community dashboard such as the PostgreSQL one (ID **9628**), use **Dashboards →
Import** in the UI and pick the Prometheus datasource.

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
1. The provisioned datasource already uses `http://prometheus:9090` (service name, not localhost)
2. Verify Prometheus is running: `docker compose --profile monitoring ps`
3. Test from the Grafana container: `docker compose exec grafana wget -qO- http://prometheus:9090/-/healthy`

### Backend target shows DOWN in Prometheus

**Problem**: The `ai-db-advisor-app` target is DOWN.

**Solution**:
1. Confirm the backend is healthy: `docker compose ps` (should be `healthy`).
2. Prometheus scrapes `backend:8095` over the compose network — both must be in the
   same project/network. Start them together: `docker compose --profile monitoring up`.
3. Check the endpoint from Prometheus's container:
   `docker compose exec prometheus wget -qO- http://backend:8095/metrics | head`

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
1. Check logs: `docker compose --profile monitoring logs -f prometheus grafana`
2. Verify configuration files in `monitoring/` directory
3. Test individual services with curl commands
4. Review Prometheus targets: http://localhost:9090/targets
