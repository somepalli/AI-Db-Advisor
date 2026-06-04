# syntax=docker/dockerfile:1
# ----------------------------------------------------------------------------
# AI DB Advisor — FastAPI backend image (multi-stage)
# ----------------------------------------------------------------------------

# ---- Builder: install Python deps into a venv -------------------------------
FROM python:3.13-slim AS builder

ARG OPTIONAL_DB_DRIVERS=0

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Build deps for psycopg/cassandra etc. (libpq for psycopg, build-essential for C exts)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV"

WORKDIR /app
COPY requirements.txt requirements-optional.txt ./

# Install CPU-only torch first so sentence-transformers doesn't pull the ~5GB CUDA build.
# Unpinned so pip resolves a wheel compatible with this Python (e.g. cp313).
RUN pip install --upgrade pip \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

# Optionally add pyodbc/oracledb (their system libs are added in the runtime stage too).
RUN if [ "$OPTIONAL_DB_DRIVERS" = "1" ]; then pip install -r requirements-optional.txt; fi

# ---- Runtime ---------------------------------------------------------------
FROM python:3.13-slim AS runtime

ARG OPTIONAL_DB_DRIVERS=0

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    API_HOST=0.0.0.0 \
    API_PORT=8095 \
    RELOAD=false \
    HF_HOME=/home/app/.cache/huggingface

# libpq for psycopg at runtime; curl for the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Optional: SQL Server ODBC driver when OPTIONAL_DB_DRIVERS=1 (best-effort; skipped otherwise).
RUN if [ "$OPTIONAL_DB_DRIVERS" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends unixodbc gnupg curl ca-certificates \
        && rm -rf /var/lib/apt/lists/* ; \
    fi

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# Backend package + entrypoint (see .dockerignore for what's excluded).
COPY backend ./backend
COPY run.py ./run.py

# Non-root user; /data holds persistent state (chroma_db, datasources.json, logs)
# via CHROMA_DB_DIR / DATASOURCES_FILE / LOG_DIR env (set in docker-compose).
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data /home/app/.cache/huggingface \
    && chown -R app:app /app /data /home/app
USER app

EXPOSE 8095

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${API_PORT}/healthz" || exit 1

# Run uvicorn directly (no reload) for production.
CMD ["sh", "-c", "uvicorn backend.main:app --host ${API_HOST} --port ${API_PORT}"]
