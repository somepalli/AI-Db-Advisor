@echo off
REM Setup Monitoring Stack for AI DB Advisor (Windows)

echo ==========================================
echo AI DB Advisor - Monitoring Setup
echo ==========================================

REM Step 1: Install Python dependencies
echo.
echo Step 1: Installing Python dependencies...
pip install prometheus-fastapi-instrumentator prometheus-client

REM Step 2: Create monitoring directories
echo.
echo Step 2: Creating monitoring directories...
if not exist "monitoring" mkdir monitoring
if not exist "monitoring\grafana" mkdir monitoring\grafana
if not exist "monitoring\grafana\provisioning" mkdir monitoring\grafana\provisioning
if not exist "monitoring\grafana\provisioning\datasources" mkdir monitoring\grafana\provisioning\datasources
if not exist "monitoring\grafana\provisioning\dashboards" mkdir monitoring\grafana\provisioning\dashboards
if not exist "monitoring\grafana\dashboards" mkdir monitoring\grafana\dashboards

REM Step 3: Create alert rules
echo.
echo Step 3: Creating alert rules...
(
echo groups:
echo   - name: database_alerts
echo     rules:
echo       - alert: SlowDatabaseQuery
echo         expr: histogram_quantile^(0.95, rate^(db_query_duration_seconds_bucket[5m]^)^) ^> 5
echo         for: 5m
echo         labels:
echo           severity: warning
echo         annotations:
echo           summary: "Slow database queries detected"
echo           description: "95th percentile query duration is {{ $value }}s"
echo.
echo       - alert: HighDatabaseConnections
echo         expr: database_connections_active ^> 80
echo         for: 2m
echo         labels:
echo           severity: warning
echo         annotations:
echo           summary: "High database connection count"
echo           description: "{{ $labels.datasource_id }} has {{ $value }} connections"
echo.
echo   - name: application_alerts
echo     rules:
echo       - alert: HighErrorRate
echo         expr: rate^(http_requests_total{status=~"5.."}[5m]^) ^> 0.05
echo         for: 5m
echo         labels:
echo           severity: critical
echo         annotations:
echo           summary: "High API error rate"
echo           description: "Error rate is {{ $value }} requests/sec"
echo.
echo       - alert: SlowAPIResponse
echo         expr: histogram_quantile^(0.95, rate^(http_request_duration_seconds_bucket[5m]^)^) ^> 2
echo         for: 5m
echo         labels:
echo           severity: warning
echo         annotations:
echo           summary: "Slow API responses"
echo           description: "95th percentile response time is {{ $value }}s"
echo.
echo   - name: mcp_alerts
echo     rules:
echo       - alert: MCPFailureRate
echo         expr: rate^(mcp_operation_total{status="error"}[5m]^) ^> 0.1
echo         for: 5m
echo         labels:
echo           severity: warning
echo         annotations:
echo           summary: "MCP operations failing"
echo           description: "MCP error rate is {{ $value }} operations/sec"
) > monitoring\alerts.yml

REM Step 4: Create Grafana datasource provisioning
echo.
echo Step 4: Creating Grafana datasource configuration...
(
echo apiVersion: 1
echo.
echo datasources:
echo   - name: Prometheus
echo     type: prometheus
echo     access: proxy
echo     url: http://prometheus:9090
echo     isDefault: true
echo     editable: true
echo     jsonData:
echo       timeInterval: "15s"
) > monitoring\grafana\provisioning\datasources\prometheus.yml

REM Step 5: Create Grafana dashboard provisioning
echo.
echo Step 5: Creating Grafana dashboard configuration...
(
echo apiVersion: 1
echo.
echo providers:
echo   - name: 'AI DB Advisor Dashboards'
echo     orgId: 1
echo     folder: ''
echo     type: file
echo     disableDeletion: false
echo     editable: true
echo     options:
echo       path: /var/lib/grafana/dashboards
) > monitoring\grafana\provisioning\dashboards\dashboards.yml

REM Step 6: Create Alertmanager configuration
echo.
echo Step 6: Creating Alertmanager configuration...
(
echo global:
echo   resolve_timeout: 5m
echo.
echo route:
echo   group_by: ['alertname', 'cluster']
echo   group_wait: 10s
echo   group_interval: 10s
echo   repeat_interval: 12h
echo   receiver: 'default'
echo.
echo receivers:
echo   - name: 'default'
echo     # Add your notification channels here
echo     # email_configs:
echo     # - to: 'alerts@example.com'
) > monitoring\alertmanager.yml

echo.
echo ==========================================
echo Setup complete!
echo ==========================================
echo.
echo Next steps:
echo 1. Install Docker Desktop for Windows if not installed
echo    Download from: https://www.docker.com/products/docker-desktop/
echo.
echo 2. Start the app + monitoring stack (one command):
echo    docker compose --profile monitoring up --build
echo.
echo 3. Access services:
echo    - Prometheus: http://localhost:9090
echo    - Grafana: http://localhost:3001 (admin/admin123)
echo    - AlertManager: http://localhost:9093
echo.
echo 4. Grafana's Prometheus datasource and dashboards are auto-provisioned.
echo    (For community dashboards like ID 9628, use Dashboards ^> Import.)
echo.
echo 5. Verify the backend metrics endpoint:
echo    curl http://localhost:8095/metrics
echo.
echo Press any key to exit...
pause >nul
