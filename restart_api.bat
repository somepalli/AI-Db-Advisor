@echo off
REM Restart AI DB Advisor API Server

echo.
echo ========================================
echo   Restarting AI DB Advisor API
echo ========================================
echo.
echo Stopping any running instances...

REM Kill any running uvicorn/python processes for the API
taskkill /F /FI "WINDOWTITLE eq AI DB Advisor API*" 2>nul
timeout /t 2 /nobreak >nul

echo.
echo Starting API server...
echo.

REM Start the API
start "AI DB Advisor API" cmd /k python run.py

echo.
echo API server restarted!
echo Check http://localhost:8000/docs
echo.
pause
