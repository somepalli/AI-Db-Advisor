@echo off
echo ================================================================================
echo Starting MCP HTTP Bridge
echo ================================================================================
echo.
echo This will start the MCP bridge on http://localhost:3000
echo The bridge connects to PostgreSQL MCP server for UniversityDB
echo.
echo Keep this window open - it will show MCP activity
echo Press Ctrl+C to stop
echo.
echo ================================================================================
echo.

cd /d "%~dp0"
python mcp_http_bridge.py

pause
