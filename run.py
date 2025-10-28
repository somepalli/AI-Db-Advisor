# run.py (place at repo root)
import pathlib
import sys
import os
import uvicorn
import logging

# Configure logging to show all API calls
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

if __name__ == "__main__":
    ROOT = pathlib.Path(__file__).parent.resolve()
    APP_DIR = ROOT / ".venv" / "app"

    # Check if myenv Python exists
    MYENV_PYTHON = ROOT / "myenv" / "Scripts" / "python.exe"

    if MYENV_PYTHON.exists():
        print(f"[run.py] Using myenv Python: {MYENV_PYTHON}")
        # Ensure we're using myenv
        if sys.executable.lower() != str(MYENV_PYTHON).lower():
            print(f"[run.py] WARNING: Not running with myenv Python!")
            print(f"[run.py] Current Python: {sys.executable}")
            print(f"[run.py] Please run with: myenv\\Scripts\\python.exe run.py")
            sys.exit(1)
    else:
        print(f"[run.py] WARNING: myenv not found at {MYENV_PYTHON}")

    if not APP_DIR.exists():
        print(f"[run.py] ERROR: app dir not found at {APP_DIR}")
        sys.exit(1)
    else:
        print(f"[run.py] Watching: {APP_DIR}")

    # Add .venv to Python path so 'app' module can be found
    sys.path.insert(0, str(ROOT / ".venv"))

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8095,
        reload=True,
        reload_dirs=[str(APP_DIR)],
        log_level="info",  # Enable INFO level logging
    )
