@echo off
REM Start both the MCP Bridge Server and the main AI DB Advisor API
REM This is the recommended way to start the application with MCP integration

echo.
echo ========================================
echo   AI DB Advisor with MCP Integration
echo ========================================
echo.
echo This will start:
echo 1. MCP Bridge Server (port 3000)
echo 2. AI DB Advisor API (port 8000)
echo.
echo Press Ctrl+C in either window to stop that service
echo.
pause

REM Start MCP bridge in a new window
start "MCP Bridge Server" cmd /k start_mcp_bridge.bat

REM Wait a moment for MCP bridge to start
timeout /t 3 /nobreak >nul

REM Start the main API
start "AI DB Advisor API" cmd /k python run.py

echo.
echo Both services started!
echo.
echo MCP Bridge: http://localhost:3000
echo API Server: http://localhost:8095
echo API Docs: http://localhost:8095/docs
echo.
echo Check the other windows for service logs
echo.
pause
