# Running AI DB Advisor with Docker

Run the whole app — backend API + web UI — with one command. No Python, Node, or
Rust toolchains required.

## Quick start

```bash
cp .env.docker.example .env     # then edit .env to choose your LLM (see below)
docker compose up --build
```

Open **http://localhost:8080** in your browser.

> If port 8080 is already in use, pick another: `WEB_PORT=8088 docker compose up --build`
> (then open http://localhost:8088).

That's it. The web UI is the same interface as the desktop app; nginx serves it and
reverse-proxies API calls to the backend, so there's nothing else to configure.

## Choose your LLM

AI suggestions need a language model. Edit `.env` and pick **one**:

| Option | `.env` settings | How to run |
|--------|-----------------|------------|
| **Bundled local Ollama** (offline, no key) | `LLM_PROVIDER=ollama`, `LLM_ENDPOINT=http://ollama:11434` | `docker compose --profile ollama up --build`, then `docker compose exec ollama ollama pull qwen2.5:7b-instruct` |
| **Your own host Ollama** | `LLM_PROVIDER=ollama`, `LLM_ENDPOINT=http://host.docker.internal:11434` | `docker compose up --build` |
| **OpenAI / OpenAI-compatible** | `LLM_PROVIDER=openai`, `LLM_ENDPOINT=https://api.openai.com`, `LLM_MODEL=…`, `LLM_API_KEY=…` | `docker compose up --build` |
| **Anthropic (Claude)** | `LLM_PROVIDER=anthropic`, `LLM_ENDPOINT=https://api.anthropic.com`, `LLM_MODEL=claude-…`, `LLM_API_KEY=…` | `docker compose up --build` |

`openai` also covers OpenAI-compatible local servers (LM Studio, llama.cpp, vLLM) and
gateways — just point `LLM_ENDPOINT` at them.

## What runs

| Service | Port | Notes |
|---------|------|-------|
| `frontend` (nginx + web UI) | `8080` | The URL you open. Proxies `/api/*` → backend. |
| `backend` (FastAPI) | `8095` | Exposed for debugging; the UI uses it via the proxy. |
| `ollama` *(profile `ollama`)* | `11434` | Optional bundled LLM, off by default. |
| `prometheus` *(profile `monitoring`)* | `9090` | Scrapes `backend:8095/metrics`. |
| `grafana` *(profile `monitoring`)* | `3001` | Dashboards, auto-provisioned. `admin`/`admin123`. |
| `postgres-exporter` *(profile `monitoring`)* | `9187` | DB metrics via `PG_EXPORTER_DSN`. |
| `alertmanager` *(profile `monitoring`)* | `9093` | Alert routing. |

ClickHouse and the MCP Toolbox are **not** bundled.

### Monitoring

Prometheus + Grafana are folded into this stack under the `monitoring` profile
(off by default). Bring them up alongside the app with:

```bash
docker compose --profile monitoring up --build
```

Grafana opens at http://localhost:3001 (`admin`/`admin123`) with the Prometheus
datasource and backend dashboard already provisioned. Profiles compose, so you can
combine them: `docker compose --profile ollama --profile monitoring up --build`.
See **[MONITORING.md](MONITORING.md)** for metrics and queries.

## Data & persistence

State is stored on the `appdata` Docker volume (`/data` in the backend container):
registered datasources (`datasources.json`), chat history (`chroma_db/`), audit logs,
and the embedding-model cache. It survives `docker compose down`; remove it with
`docker compose down -v`.

## Database drivers

The default image supports **PostgreSQL, MySQL/MariaDB, SQLite, DuckDB, ClickHouse,
MongoDB, and Redis**. SQL Server (`pyodbc`), Oracle (`oracledb`), and Cassandra
(`cassandra-driver`) need a compiler/system packages and are opt-in:

```bash
docker compose build --build-arg OPTIONAL_DB_DRIVERS=1
```

## Connecting to your databases

A database running on **your machine** can't be reached as `localhost` from inside the
container — there, `localhost` means the container itself. By default this stack sets
`REWRITE_LOCALHOST_DSN=true`, so you can register datasources with the natural host and
the backend rewrites it to `host.docker.internal` (your machine) at connect time:

```
postgresql://user:pass@localhost:5432/db      # works — auto-rewritten
postgresql://user:pass@host.docker.internal:5432/db   # also works (explicit)
```

This applies to every engine (MySQL, Mongo, Redis, etc.). Note that registering a
datasource only *stores* the DSN — the connection isn't opened until you load a schema or
run analysis, so an unreachable host only surfaces an error at that point, not at register
time. To disable the rewrite (e.g. all your databases are remote), set
`REWRITE_LOCALHOST_DSN=false` in `.env`.

## Security note

In the browser, database connection secrets fall back to **localStorage** (not encrypted
at rest) because the OS keyring is only available in the native desktop build. For
production use with sensitive credentials, prefer the native Tauri desktop app, or run
this stack only on a trusted host/network.

## Useful commands

```bash
docker compose up --build -d         # start in background
docker compose logs -f backend       # tail backend logs
docker compose ps                    # status
docker compose down                  # stop (keep data)
docker compose down -v               # stop and delete volumes (wipes data)
curl http://localhost:8080/api/healthz   # -> {"ok":true} (via proxy)
```
