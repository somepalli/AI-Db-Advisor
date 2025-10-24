# Grafana Dashboard Troubleshooting Guide

## Issue: "No data" showing in Grafana dashboards

This guide helps you diagnose and fix the "No data" issue in Grafana dashboards for AI DB Advisor.

## Root Causes

### 1. **Metric Name Mismatch** ✅ FIXED
The dashboards were using incorrect metric names that don't match what the applications expose.

**Fixed in**: `monitoring/grafana/dashboards/fastapi-dashboard.json`

**Change**:
- Dashboard was using: `http_request_duration_seconds_bucket`
- Actual metric name: `http_request_duration_highr_seconds_bucket`

### 2. **Prometheus Not Scraping Targets**
Prometheus must be able to reach the application metrics endpoints.

## Verification Steps

### Step 1: Check if services are exposing metrics

```bash
# Check FastAPI backend metrics
curl http://127.0.0.1:8000/metrics

# Check MCP Bridge metrics
curl http://127.0.0.1:3000/metrics
```

**Expected**: You should see Prometheus-format metrics output

### Step 2: Check Prometheus targets

1. Open Prometheus UI: http://localhost:9090/targets
2. Look for these jobs:
   - `ai-db-advisor-app` → should scrape `host.docker.internal:8000`
   - `mcp-bridge` → should scrape `host.docker.internal:3000`

**Expected Status**: All targets should be **UP** (green)

**Common Issues**:
- **DOWN (red)**: Can't reach the target
  - Solution: Ensure FastAPI/MCP servers are running
  - Check if `host.docker.internal` resolves correctly (Docker Desktop feature)
  - Try using `host.docker.internal` instead of `localhost` in prometheus.yml

### Step 3: Query metrics in Prometheus

1. Open Prometheus UI: http://localhost:9090/graph
2. Try these queries:

```promql
# FastAPI metrics
http_requests_total{job="ai-db-advisor-app"}
http_request_duration_highr_seconds_bucket{job="ai-db-advisor-app"}

# MCP Bridge metrics
mcp_server_status{job="mcp-bridge"}
mcp_requests_total{job="mcp-bridge"}
```

**Expected**: You should see data points with values

### Step 4: Check Grafana data source

1. Open Grafana: http://localhost:3001
2. Go to: Configuration → Data Sources → Prometheus
3. Click "Test" button

**Expected**: "Data source is working" message

## Available Metrics

### FastAPI Backend (`job="ai-db-advisor-app"`)

| Metric Name | Type | Description |
|-------------|------|-------------|
| `http_requests_total` | counter | Total HTTP requests by method, handler, status |
| `http_requests_inprogress` | gauge | Current active requests |
| `http_request_duration_highr_seconds` | histogram | Request latency (high resolution) |
| `http_request_size_bytes` | summary | Request body sizes |
| `http_response_size_bytes` | summary | Response body sizes |
| `python_gc_objects_collected_total` | counter | Python GC statistics |

**Labels**:
- `method`: HTTP method (GET, POST, etc.)
- `handler`: Endpoint path (e.g., `/analyze/{ds_id}/schema`)
- `status`: Status code group (`2xx`, `4xx`, `5xx`)

### MCP Bridge (`job="mcp-bridge"`)

| Metric Name | Type | Description |
|-------------|------|-------------|
| `mcp_server_status` | gauge | MCP server status (0=DOWN, 1=UP) |
| `mcp_tools_discovered` | gauge | Number of MCP tools discovered |
| `mcp_requests_total` | counter | Total MCP requests by method and status |
| `mcp_request_duration_seconds` | histogram | MCP request latency |
| `http_requests_total` | counter | HTTP requests to bridge |
| `http_request_duration_highr_seconds` | histogram | HTTP request latency |

**Labels**:
- `method`: MCP method name (e.g., `tools/call`, `tools/list`)
- `status`: Request status (`success`, `error`)

## Dashboard Query Examples

### Request Rate (req/sec)
```promql
rate(http_requests_total{job="ai-db-advisor-app"}[5m])
```

### Active Requests
```promql
http_requests_inprogress{job="ai-db-advisor-app"}
```

### P95 Latency
```promql
histogram_quantile(0.95, rate(http_request_duration_highr_seconds_bucket{job="ai-db-advisor-app"}[5m]))
```

### Total Requests
```promql
sum(http_requests_total{job="ai-db-advisor-app"})
```

### HTTP Status Codes (by rate)
```promql
# 2xx Success
rate(http_requests_total{job="ai-db-advisor-app",status=~"2.."}[5m])

# 4xx Client Errors
rate(http_requests_total{job="ai-db-advisor-app",status=~"4.."}[5m])

# 5xx Server Errors
rate(http_requests_total{job="ai-db-advisor-app",status=~"5.."}[5m])
```

## Common Fixes

### Fix 1: Restart monitoring stack

```bash
cd monitoring
docker-compose down
docker-compose up -d
```

### Fix 2: Check Docker network connectivity

```bash
# From inside Prometheus container
docker exec -it prometheus ping host.docker.internal

# From inside Grafana container
docker exec -it grafana curl http://prometheus:9090/-/healthy
```

### Fix 3: Force Prometheus to reload targets

```bash
# Send SIGHUP to reload configuration
docker exec prometheus kill -HUP 1

# Or restart Prometheus
docker restart prometheus
```

### Fix 4: Verify Grafana can query Prometheus

```bash
# From Grafana container
docker exec -it grafana curl http://prometheus:9090/api/v1/query?query=up
```

### Fix 5: Check if services are generating metrics

```bash
# Make some API requests to generate metrics
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/datasources
curl http://127.0.0.1:3000/health

# Then check metrics again
curl http://127.0.0.1:8000/metrics | grep http_requests_total
curl http://127.0.0.1:3000/metrics | grep mcp_requests_total
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Applications                           │
│                                                          │
│  FastAPI Backend          MCP Bridge                     │
│  :8000/metrics           :3000/metrics                  │
└────────────┬──────────────────┬─────────────────────────┘
             │                  │
             │ (scrape every    │ (scrape every 15s)
             │  10s)            │
             ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│              Prometheus (port 9090)                      │
│  - Scrapes metrics from targets                          │
│  - Stores time-series data                               │
│  - Provides PromQL query interface                       │
└────────────────────────┬────────────────────────────────┘
                         │
                         │ (query via PromQL)
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Grafana (port 3001)                         │
│  - Visualizes metrics in dashboards                      │
│  - Uses Prometheus as data source                        │
└─────────────────────────────────────────────────────────┘
```

## Debugging Checklist

- [ ] FastAPI backend is running on port 8000
- [ ] MCP bridge is running on port 3000
- [ ] `/metrics` endpoints are accessible
- [ ] Prometheus is running and can scrape targets
- [ ] Prometheus targets are UP (check /targets page)
- [ ] Grafana is running on port 3001
- [ ] Grafana data source (Prometheus) is configured and tested
- [ ] Dashboard queries use correct metric names
- [ ] At least some API requests have been made (to generate metrics)

## Testing the Fix

### 1. Generate some traffic
```bash
# Make requests to FastAPI
for i in {1..10}; do curl -s http://127.0.0.1:8000/healthz > /dev/null; done

# Make requests to MCP Bridge
for i in {1..5}; do curl -s http://127.0.0.1:3000/health > /dev/null; done
```

### 2. Wait for Prometheus to scrape (10-15 seconds)

### 3. Check Grafana dashboard
- Open: http://localhost:3001/d/fastapi-backend
- You should now see:
  - Request Rate graph showing activity
  - Active Requests showing numbers
  - Total Requests counter increasing
  - Latency graphs (if queries are slow enough)

### 4. Check MCP dashboard
- Open: http://localhost:3001/d/mcp-bridge
- You should see:
  - MCP Server Status (green if UP)
  - MCP Tools Discovered (number of tools)
  - Request rates and latencies

## Configuration Files

- **Prometheus config**: `monitoring/prometheus.yml`
- **FastAPI dashboard**: `monitoring/grafana/dashboards/fastapi-dashboard.json`
- **MCP dashboard**: `monitoring/grafana/dashboards/mcp-dashboard.json`
- **Grafana datasource**: `monitoring/grafana/provisioning/datasources/prometheus.yml`

## Support

If dashboards still show "No data":
1. Check Prometheus logs: `docker logs prometheus`
2. Check Grafana logs: `docker logs grafana`
3. Verify all services are running: `docker ps`
4. Check network connectivity between containers
5. Review this troubleshooting guide from the beginning
