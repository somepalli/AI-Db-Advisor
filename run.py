# run.py (place at repo root)
import pathlib
import sys
import uvicorn

if __name__ == "__main__":
    ROOT = pathlib.Path(__file__).parent.resolve()
    APP_DIR = ROOT / ".venv" / "app"

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
        port=8000,
        reload=True,
        reload_dirs=[str(APP_DIR)],
    )
