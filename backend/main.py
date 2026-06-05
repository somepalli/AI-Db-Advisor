from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from .routers import datasources, analyze, suggestions, ai_chat, ai_chat_stream, chat_history, mcp, analytics, alerts, llm
from .routers.ui import ui
from .config import settings, initialize_mcp
import logging
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import REGISTRY, generate_latest
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing logging configuration
)

logger = logging.getLogger(__name__)

# Set uvicorn and fastapi loggers to INFO
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("fastapi").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting AI DB Advisor...")

    # Initialize MCP if enabled
    mcp_client = initialize_mcp()
    if mcp_client:
        logger.info(f"MCP client initialized: {settings.MCP_ENDPOINT}")
    else:
        logger.info("MCP integration disabled or not configured")

    # Initialize Prometheus metrics
    logger.info("Initializing Prometheus metrics...")

    # Start monitoring service for continuous datasource health monitoring
    logger.info("Starting monitoring service...")
    from .services.monitoring_service import get_monitoring_service
    from .routers.alerts import alert_engine
    monitoring_service = get_monitoring_service(alert_engine)
    await monitoring_service.start()
    logger.info("Monitoring service started")

    yield

    # Shutdown
    logger.info("Shutting down AI DB Advisor...")

    # Stop monitoring service
    logger.info("Stopping monitoring service...")
    await monitoring_service.stop()
    logger.info("Monitoring service stopped")


app = FastAPI(title="AI DB Advisor (FastAPI)", lifespan=lifespan)

# Add logging middleware for all requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # Log incoming request
    logger.info(f"→ {request.method} {request.url.path}")
    if request.query_params:
        logger.info(f"  Query params: {dict(request.query_params)}")

    # Process request
    response = await call_next(request)

    # Log response
    process_time = (time.time() - start_time) * 1000
    logger.info(f"← {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.2f}ms")

    return response

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
app.include_router(ai_chat_stream.router)
app.include_router(chat_history.router)
app.include_router(mcp.router)
app.include_router(analytics.router)
app.include_router(alerts.router)
app.include_router(llm.router)
app.include_router(ui)

@app.get("/")
def root():
    return {"ok": True, "service": "ai-db-advisor", "ui": "/ui"}

# Initialize Prometheus instrumentation (must be after all routes are added)
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=False,
    should_respect_env_var=False,  # Changed to False - always enable
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics"],  # Don't track metrics endpoint itself
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True
)

# Instrument the app and expose metrics endpoint
instrumentator.instrument(app).expose(app)

