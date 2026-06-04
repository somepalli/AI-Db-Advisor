@echo off
REM start_backend.bat - Run the AI DB Advisor backend
REM Prefers a local virtual environment if present, otherwise falls back to the
REM Python on PATH. Create a venv with:
REM   python -m venv .venv-app
REM   .venv-app\Scripts\pip install -r requirements.txt

echo ========================================
echo AI DB Advisor Backend Startup
echo ========================================
echo.

if exist ".venv-app\Scripts\python.exe" (
    echo Using .venv-app Python environment...
    .venv-app\Scripts\python.exe run.py
) else if exist "myenv\Scripts\python.exe" (
    echo Using myenv Python environment...
    myenv\Scripts\python.exe run.py
) else (
    echo No local virtual environment found - using Python on PATH...
    python run.py
)

pause
