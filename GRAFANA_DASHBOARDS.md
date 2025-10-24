# Creating Custom Grafana Dashboards

Complete guide to creating and importing custom Grafana dashboards for FastAPI and MCP metrics.

## Table of Contents
- [Quick Start: Import Pre-built Dashboards](#quick-start-import-pre-built-dashboards)
- [Method 1: Import Dashboard JSON Files](#method-1-import-dashboard-json-files)
- [Method 2: Create Dashboards Manually](#method-2-create-dashboards-manually)
- [Dashboard Panels Explained](#dashboard-panels-explained)
- [Useful PromQL Queries](#useful-promql-queries)

---

## Quick Start: Import Pre-built Dashboards

I've created two pre-configured dashboard JSON files ready to import:

1. **`monitoring/grafana/dashboards/fastapi-dashboard.json`** - FastAPI Backend Dashboard
2. **`monitoring/grafana/dashboards/mcp-dashboard.json`** - MCP Bridge Dashboard

---

## Method 1: Import Dashboard JSON Files

### Step 1: Access Grafana

1. Open http://localhost:3001
2. Login with `admin` / `admin123`

### Step 2: Add Prometheus Data Source (First Time Only)

1. Click the **gear icon (⚙️)** on the left sidebar → **Data sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Configure:
   - **Name**: `Prometheus`
   - **URL**: `http://prometheus:9090`
   - Leave other settings as default
5. Click **Save & Test** (should show green checkmark)

### Step 3: Import FastAPI Dashboard

1. Click the **+ icon** on the left sidebar → **Import dashboard**
2. Click **Upload JSON file**
3. Select `monitoring/grafana/dashboards/fastapi-dashboard.json`
4. On the import screen:
   - **Name**: `AI DB Advisor - FastAPI Backend` (or customize)
   - **Folder**: Select a folder or leave as default
   - **UID**: Leave as is or change
   - **Prometheus**: Select your Prometheus data source
5. Click **Import**

### Step 4: Import MCP Dashboard

1. Repeat the same process with `monitoring/grafana/dashboards/mcp-dashboard.json`
2. Click **+ icon** → **Import dashboard**
3. Upload `mcp-dashboard.json`
4. Configure and click **Import**

### Step 5: View Your Dashboards

1. Click the **four squares icon** on the left sidebar (Dashboards)
2. You should see:
   - **AI DB Advisor - FastAPI Backend**
   - **AI DB Advisor - MCP Bridge**
3. Click on each to view real-time metrics

---

## Method 2: Create Dashboards Manually

If you prefer to create dashboards from scratch or customize them, follow these steps.

### Creating the FastAPI Dashboard

#### Step 1: Create New Dashboard

1. Click **+ icon** → **Dashboard**
2. Click **Add visualization**
3. Select **Prometheus** as data source

#### Step 2: Add Request Rate Panel

1. **Panel Type**: Time series
2. **Title**: Request Rate (req/sec)
3. **Query**:
   ```promql
   rate(http_requests_total{job="ai-db-advisor-app"}[5m])
   ```
4. **Legend**: `{{method}} {{handler}}`
5. **Unit**: `reqps` (requests per second)
6. Click **Apply**

#### Step 3: Add Active Requests Panel

1. Click **Add** → **Visualization**
2. **Panel Type**: Stat
3. **Title**: Active Requests
4. **Query**:
   ```promql
   http_requests_inprogress{job="ai-db-advisor-app"}
   ```
5. **Thresholds**:
   - Green: 0-10
   - Yellow: 10-50
   - Red: >50
6. Click **Apply**

#### Step 4: Add Total Requests Panel

1. **Panel Type**: Stat
2. **Title**: Total Requests
3. **Query**:
   ```promql
   sum(http_requests_total{job="ai-db-advisor-app"})
   ```
4. Click **Apply**

#### Step 5: Add Request Duration Panel

1. **Panel Type**: Time series
2. **Title**: Request Duration (Latency)
3. **Queries**:
   ```promql
   # Query A - 95th percentile
   histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="ai-db-advisor-app"}[5m]))

   # Query B - 50th percentile (median)
   histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{job="ai-db-advisor-app"}[5m]))
   ```
4. **Legends**:
   - Query A: `p95 - {{method}} {{handler}}`
   - Query B: `p50 - {{method}} {{handler}}`
5. **Unit**: `s` (seconds)
6. Click **Apply**

#### Step 6: Add HTTP Status Codes Panel

1. **Panel Type**: Time series
2. **Title**: HTTP Status Codes
3. **Queries**:
   ```promql
   # Query A - Success (2xx)
   rate(http_requests_total{job="ai-db-advisor-app",status=~"2.."}[5m])

   # Query B - Client Errors (4xx)
   rate(http_requests_total{job="ai-db-advisor-app",status=~"4.."}[5m])

   # Query C - Server Errors (5xx)
   rate(http_requests_total{job="ai-db-advisor-app",status=~"5.."}[5m])
   ```
4. **Legends**:
   - Query A: `2xx Success`
   - Query B: `4xx Client Error`
   - Query C: `5xx Server Error`
5. **Colors**:
   - Query A: Green
   - Query B: Yellow
   - Query C: Red
6. **Stack**: Enable stacking
7. Click **Apply**

#### Step 7: Add Python GC Panel

1. **Panel Type**: Time series
2. **Title**: Python GC Collections
3. **Query**:
   ```promql
   python_gc_objects_collected_total{job="ai-db-advisor-app"}
   ```
4. **Legend**: `Generation {{generation}}`
5. Click **Apply**

#### Step 8: Add Top Endpoints Panel

1. **Panel Type**: Bar gauge
2. **Title**: Top 10 Endpoints by Requests
3. **Query**:
   ```promql
   topk(10, sum by(handler) (http_requests_total{job="ai-db-advisor-app"}))
   ```
4. **Legend**: `{{handler}}`
5. **Orientation**: Horizontal
6. Click **Apply**

#### Step 9: Save Dashboard

1. Click the **save icon** (💾) at the top
2. **Name**: `AI DB Advisor - FastAPI Backend`
3. **Folder**: Select or create a folder
4. Click **Save**

---

### Creating the MCP Dashboard

#### Step 1: Create New Dashboard

1. Click **+ icon** → **Dashboard**

#### Step 2: Add MCP Server Status Panel

1. **Panel Type**: Stat
2. **Title**: MCP Server Status
3. **Query**:
   ```promql
   mcp_server_status{job="mcp-bridge"}
   ```
4. **Value Mappings**:
   - `0` → `DOWN` (red)
   - `1` → `UP` (green)
5. **Color Mode**: Background
6. Click **Apply**

#### Step 3: Add Tools Discovered Panel

1. **Panel Type**: Stat
2. **Title**: MCP Tools Discovered
3. **Query**:
   ```promql
   mcp_tools_discovered{job="mcp-bridge"}
   ```
4. **Color**: Blue
5. Click **Apply**

#### Step 4: Add Total MCP Requests Panel

1. **Panel Type**: Stat
2. **Title**: Total MCP Requests
3. **Query**:
   ```promql
   sum(mcp_requests_total{job="mcp-bridge"})
   ```
4. Click **Apply**

#### Step 5: Add MCP Request Errors Panel

1. **Panel Type**: Stat
2. **Title**: MCP Request Errors
3. **Query**:
   ```promql
   sum(mcp_requests_total{job="mcp-bridge",status="error"})
   ```
4. **Thresholds**:
   - Green: 0
   - Yellow: >5
   - Red: >10
5. Click **Apply**

#### Step 6: Add MCP Request Rate Panel

1. **Panel Type**: Time series
2. **Title**: MCP Request Rate by Method
3. **Queries**:
   ```promql
   # Query A - Success
   rate(mcp_requests_total{job="mcp-bridge",status="success"}[5m])

   # Query B - Error
   rate(mcp_requests_total{job="mcp-bridge",status="error"}[5m])
   ```
4. **Legends**:
   - Query A: `{{method}} - Success`
   - Query B: `{{method}} - Error`
5. Click **Apply**

#### Step 7: Add MCP Request Duration Panel

1. **Panel Type**: Time series
2. **Title**: MCP Request Duration (Latency)
3. **Queries**:
   ```promql
   # Query A - 95th percentile
   histogram_quantile(0.95, rate(mcp_request_duration_seconds_bucket{job="mcp-bridge"}[5m]))

   # Query B - 50th percentile
   histogram_quantile(0.50, rate(mcp_request_duration_seconds_bucket{job="mcp-bridge"}[5m]))
   ```
4. **Legends**:
   - Query A: `p95 - {{method}}`
   - Query B: `p50 - {{method}}`
5. **Unit**: `s` (seconds)
6. Click **Apply**

#### Step 8: Add HTTP Request Rate Panel

1. **Panel Type**: Time series
2. **Title**: HTTP Request Rate
3. **Query**:
   ```promql
   rate(http_requests_total{job="mcp-bridge"}[5m])
   ```
4. **Legend**: `{{method}} {{handler}}`
5. Click **Apply**

#### Step 9: Add MCP Requests Table

1. **Panel Type**: Table
2. **Title**: MCP Requests by Method & Status
3. **Query**:
   ```promql
   sum by(method, status) (mcp_requests_total{job="mcp-bridge"})
   ```
4. **Format**: Table
5. **Instant**: Enable
6. **Transformations**:
   - Add transformation: **Organize fields**
   - Hide: `Time`, `job`
   - Rename: `method` → `Method`, `status` → `Status`, `Value` → `Count`
7. Click **Apply**

#### Step 10: Save Dashboard

1. Click **save icon** (💾)
2. **Name**: `AI DB Advisor - MCP Bridge`
3. Click **Save**

---

## Dashboard Panels Explained

### FastAPI Dashboard Panels

| Panel | Description | Purpose |
|-------|-------------|---------|
| **Request Rate** | Shows requests per second for each endpoint | Monitor traffic patterns and identify busy endpoints |
| **Active Requests** | Number of requests currently being processed | Detect if server is overloaded |
| **Total Requests** | Cumulative count of all requests | Understand overall usage |
| **Request Duration** | Latency (p50 and p95) for each endpoint | Identify slow endpoints |
| **HTTP Status Codes** | Distribution of 2xx, 4xx, 5xx responses | Monitor error rates |
| **Python GC** | Garbage collection statistics | Debug memory issues |
| **Top Endpoints** | Most frequently accessed endpoints | Identify hotspots for optimization |

### MCP Dashboard Panels

| Panel | Description | Purpose |
|-------|-------------|---------|
| **MCP Server Status** | Shows if MCP server is running | Quick health check |
| **Tools Discovered** | Number of available MCP tools | Verify MCP integration |
| **Total MCP Requests** | Cumulative MCP API calls | Understand MCP usage |
| **Request Errors** | Failed MCP requests | Monitor integration reliability |
| **Request Rate** | Success/error rates by method | Identify problematic methods |
| **Request Duration** | MCP request latency | Monitor performance |
| **HTTP Request Rate** | HTTP traffic to MCP bridge | Overall bridge usage |
| **Requests Table** | Detailed breakdown by method/status | Deep dive into request patterns |

---

## Useful PromQL Queries

### FastAPI Backend Queries

#### Request Metrics
```promql
# Total requests per second
rate(http_requests_total{job="ai-db-advisor-app"}[5m])

# Requests by status code
sum by(status) (rate(http_requests_total{job="ai-db-advisor-app"}[5m]))

# Requests by endpoint
sum by(handler) (rate(http_requests_total{job="ai-db-advisor-app"}[5m]))

# Error rate (4xx and 5xx)
sum(rate(http_requests_total{job="ai-db-advisor-app",status=~"[45].."}[5m]))

# Success rate
sum(rate(http_requests_total{job="ai-db-advisor-app",status=~"2.."}[5m]))
```

#### Latency Metrics
```promql
# Average latency
rate(http_request_duration_seconds_sum{job="ai-db-advisor-app"}[5m])
/
rate(http_request_duration_seconds_count{job="ai-db-advisor-app"}[5m])

# 50th percentile (median)
histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{job="ai-db-advisor-app"}[5m]))

# 95th percentile
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="ai-db-advisor-app"}[5m]))

# 99th percentile
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{job="ai-db-advisor-app"}[5m]))

# Max latency
max(rate(http_request_duration_seconds_bucket{job="ai-db-advisor-app"}[5m]))
```

#### Application Metrics
```promql
# Active requests
http_requests_inprogress{job="ai-db-advisor-app"}

# Python version
python_info{job="ai-db-advisor-app"}

# GC collections by generation
python_gc_collections_total{job="ai-db-advisor-app"}

# GC collected objects
python_gc_objects_collected_total{job="ai-db-advisor-app"}
```

### MCP Bridge Queries

#### MCP-Specific Metrics
```promql
# MCP server status (1=up, 0=down)
mcp_server_status{job="mcp-bridge"}

# Number of tools
mcp_tools_discovered{job="mcp-bridge"}

# Total MCP requests
sum(mcp_requests_total{job="mcp-bridge"})

# MCP requests by method
sum by(method) (mcp_requests_total{job="mcp-bridge"})

# MCP success rate
sum(mcp_requests_total{job="mcp-bridge",status="success"})
/
sum(mcp_requests_total{job="mcp-bridge"})

# MCP error rate
sum(mcp_requests_total{job="mcp-bridge",status="error"})
/
sum(mcp_requests_total{job="mcp-bridge"})
```

#### MCP Latency
```promql
# Average MCP request duration
rate(mcp_request_duration_seconds_sum{job="mcp-bridge"}[5m])
/
rate(mcp_request_duration_seconds_count{job="mcp-bridge"}[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(mcp_request_duration_seconds_bucket{job="mcp-bridge"}[5m]))

# Latency by method
histogram_quantile(0.95, sum by(method, le) (rate(mcp_request_duration_seconds_bucket{job="mcp-bridge"}[5m])))
```

### Combined Queries

#### Overall System Health
```promql
# All services up
up{job=~"ai-db-advisor-app|mcp-bridge|postgres-universitydb"}

# Total requests across all services
sum(rate(http_requests_total[5m]))

# Error rate across all services
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

---

## Dashboard Customization Tips

### 1. Adjust Time Range
- Default: Last 30 minutes
- Change at top-right: Last 1h, 6h, 24h, 7d, etc.
- Enable auto-refresh (5s, 10s, 30s)

### 2. Add Variables (Template)
Create dynamic dashboards with variables:

1. Click **Dashboard settings** (gear icon at top)
2. Go to **Variables**
3. Click **Add variable**
4. Example: Create `interval` variable
   - **Type**: Interval
   - **Values**: `1m,5m,10m,30m,1h`
5. Use in queries: `rate(http_requests_total[$interval])`

### 3. Set Alert Rules

1. Edit any panel
2. Go to **Alert** tab
3. Click **Create alert rule**
4. Set conditions (e.g., `when avg() of query(A) is above 100`)
5. Configure notifications

### 4. Organize Panels

- **Drag and drop** panels to reorder
- **Resize** by dragging corners
- **Group** related panels together
- Use **rows** to collapse sections

### 5. Share Dashboards

1. Click **Share** icon (📤) at top
2. Options:
   - **Link**: Share URL
   - **Snapshot**: Create public snapshot
   - **Export**: Download JSON
   - **Embed**: Get iframe code

---

## Troubleshooting

### Problem: "No data" in panels

**Solutions**:
1. Check Prometheus is scraping targets:
   - Go to http://localhost:9090/targets
   - Verify all targets are **UP**
2. Verify metrics endpoint:
   - Test: `curl http://127.0.0.1:8000/metrics`
   - Test: `curl http://localhost:3000/metrics`
3. Check time range (top-right)
4. Verify job name in query matches Prometheus config

### Problem: Panels show errors

**Solutions**:
1. Check PromQL syntax in Query Inspector
2. Verify data source is connected (click data source in panel edit)
3. Check Prometheus logs: `docker-compose -f docker-compose.monitoring.yml logs prometheus`

### Problem: Dashboard doesn't update

**Solutions**:
1. Enable auto-refresh (top-right dropdown)
2. Hard refresh browser (Ctrl+F5)
3. Check if services are generating metrics (make some API requests)

---

## Next Steps

1. **Import both dashboards** (FastAPI and MCP)
2. **Make API requests** to generate metrics
3. **Watch dashboards update** in real-time
4. **Customize** panels based on your needs
5. **Create alerts** for critical metrics
6. **Export dashboards** as backups

For more advanced dashboarding, see:
- [Grafana Documentation](https://grafana.com/docs/grafana/latest/dashboards/)
- [PromQL Guide](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)
