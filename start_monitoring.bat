@echo off
REM Start all monitoring services for AI DB Advisor

echo ================================================================================
echo Starting AI DB Advisor Monitoring Stack
echo ================================================================================
echo.

REM 1. Start Docker monitoring services
echo [1/3] Starting Docker monitoring services (Prometheus, Grafana, etc.)...
docker-compose -f docker-compose.monitoring.yml up -d
if %errorlevel% neq 0 (
    echo ERROR: Failed to start Docker services
    exit /b 1
)
echo Docker services started successfully!
echo.

REM 2. Wait for services to initialize
echo [2/3] Waiting for services to initialize (10 seconds)...
timeout /t 10 /nobreak > nul
echo.

REM 3. Show service status
echo [3/3] Monitoring services status:
echo.
docker-compose -f docker-compose.monitoring.yml ps
echo.

echo ================================================================================
echo Monitoring Stack Ready!
echo ================================================================================
echo.
echo Access URLs:
echo   - Prometheus:     http://localhost:9090
echo   - Grafana:        http://localhost:3001  (admin/admin123)
echo   - AlertManager:   http://localhost:9093
echo   - PostgreSQL Exp: http://localhost:9187/metrics
echo.
echo Backend Services (Start these separately):
echo   - FastAPI:        python run.py
echo   - MCP Bridge:     python mcp_http_bridge.py
echo.
echo Backend Metrics:
echo   - FastAPI:        http://127.0.0.1:8000/metrics
echo   - MCP Bridge:     http://localhost:3000/metrics
echo.
echo ================================================================================
