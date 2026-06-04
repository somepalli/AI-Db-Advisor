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
    APP_DIR = ROOT / "backend"

    if not APP_DIR.exists():
        print(f"[run.py] ERROR: backend package not found at {APP_DIR}")
        sys.exit(1)

    # Ensure the repo root is importable so the `backend` package resolves
    sys.path.insert(0, str(ROOT))

    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8095"))
    # Auto-reload for local dev; disable in containers/production via RELOAD=false.
    reload = os.getenv("RELOAD", "true").lower() in ("1", "true", "yes")

    print(f"[run.py] Serving backend.main:app on http://{host}:{port} (reload={reload})")

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[str(APP_DIR)] if reload else None,
        log_level="info",
    )
