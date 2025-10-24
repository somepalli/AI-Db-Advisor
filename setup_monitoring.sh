#!/bin/bash

# Setup Monitoring Stack for AI DB Advisor
# This script sets up Prometheus + Grafana monitoring

echo "=========================================="
echo "AI DB Advisor - Monitoring Setup"
echo "=========================================="

# Step 1: Install Python dependencies
echo ""
echo "Step 1: Installing Python dependencies..."
pip install prometheus-fastapi-instrumentator prometheus-client

# Step 2: Create alert rules
echo ""
echo "Step 2: Creating alert rules..."
cat > monitoring/alerts.yml << 'EOF'
groups:
  - name: database_alerts
    rules:
      - alert: SlowDatabaseQuery
        expr: histogram_quantile(0.95, rate(db_query_duration_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow database queries detected"
          description: "95th percentile query duration is {{ $value }}s"

      - alert: HighDatabaseConnections
        expr: database_connections_active > 80
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High database connection count"
          description: "{{ $labels.datasource_id }} has {{ $value }} connections"

  - name: application_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate"
          description: "Error rate is {{ $value }} requests/sec"

      - alert: SlowAPIResponse
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow API responses"
          description: "95th percentile response time is {{ $value }}s"

  - name: mcp_alerts
    rules:
      - alert: MCPFailureRate
        expr: rate(mcp_operation_total{status="error"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "MCP operations failing"
          description: "MCP error rate is {{ $value }} operations/sec"
EOF

# Step 3: Create Grafana datasource provisioning
echo "Step 3: Creating Grafana datasource configuration..."
cat > monitoring/grafana/provisioning/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: "15s"
EOF

# Step 4: Create Grafana dashboard provisioning
echo "Step 4: Creating Grafana dashboard configuration..."
cat > monitoring/grafana/provisioning/dashboards/dashboards.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'AI DB Advisor Dashboards'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /var/lib/grafana/dashboards
EOF

# Step 5: Create Alertmanager configuration
echo "Step 5: Creating Alertmanager configuration..."
cat > monitoring/alertmanager.yml << 'EOF'
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'

receivers:
  - name: 'default'
    # Add your notification channels here
    # email_configs:
    # - to: 'alerts@example.com'
    #   from: 'alertmanager@example.com'
    #   smarthost: smtp.example.com:587
    #   auth_username: 'alertmanager@example.com'
    #   auth_password: 'password'
EOF

echo ""
echo "=========================================="
echo "✅ Monitoring setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Start monitoring stack:"
echo "   docker-compose -f docker-compose.monitoring.yml up -d"
echo ""
echo "2. Access services:"
echo "   - Prometheus: http://localhost:9090"
echo "   - Grafana: http://localhost:3001 (admin/admin123)"
echo "   - AlertManager: http://localhost:9093"
echo ""
echo "3. Import dashboards in Grafana:"
echo "   - Dashboard ID 16110 (FastAPI Observability)"
echo "   - Dashboard ID 9628 (PostgreSQL Database)"
echo ""
echo "4. Start your application with metrics:"
echo "   python run.py"
echo ""
echo "5. Verify metrics endpoint:"
echo "   curl http://localhost:8000/metrics"
echo ""
