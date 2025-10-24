@echo off
REM start_backend.bat - Run the AI DB Advisor backend with myenv Python

echo ========================================
echo AI DB Advisor Backend Startup
echo ========================================
echo.

REM Check if myenv exists
if not exist "myenv\Scripts\python.exe" (
    echo ERROR: myenv not found!
    echo Please create the virtual environment first:
    echo   python -m venv myenv
    echo   myenv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo Using myenv Python environment...
echo Python: %cd%\myenv\Scripts\python.exe
echo.

REM Run the backend with myenv Python
myenv\Scripts\python.exe run.py

pause
