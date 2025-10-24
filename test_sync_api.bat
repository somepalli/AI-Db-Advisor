@echo off
REM test_sync_api.bat - Test the DuckDB sync API

echo ========================================
echo Testing DuckDB Sync API
echo ========================================
echo.

echo Testing sync/all endpoint...
echo.

curl -X POST http://127.0.0.1:8000/analytics/sync/all ^
  -H "Content-Type: application/json" ^
  -d "{\"pg_ds_id\": \"Demo-DB-Post\", \"ch_ds_id\": \"duckdb-analytics\"}"

echo.
echo.
echo ========================================
echo Test complete!
echo ========================================

pause
