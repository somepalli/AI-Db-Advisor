from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .routers import datasources, analyze, suggestions, ai_chat, chat_history
from .routers.ui import ui
from .config import settings
import logging

logger = logging.getLogger(__name__)
app = FastAPI(title="AI DB Advisor (FastAPI)")

# Add CORS middleware to allow Tauri desktop app and Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "https://tauri.localhost",
        "http://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # Log the error for debugging
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    # In dev mode, return more details; in production, hide details
    if settings.ENV == "dev":
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal error", "error": str(exc), "type": type(exc).__name__}
        )
    return JSONResponse(status_code=500, content={"detail": "Internal error"})

@app.get("/healthz")
def healthz():
    return {"ok": True}

app.include_router(datasources.router)
app.include_router(analyze.router)
app.include_router(suggestions.router)
app.include_router(ai_chat.router)
app.include_router(chat_history.router)
app.include_router(ui)

@app.get("/")
def root():
    return {"ok": True, "service": "ai-db-advisor", "ui": "/ui"}

