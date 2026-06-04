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

ClickHouse and the MCP Toolbox are **not** bundled. The Prometheus/Grafana monitoring
stack stays separate (`docker-compose.monitoring.yml`).

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

Use `host.docker.internal` (Docker Desktop) instead of `localhost` in DSNs to reach a
database running on your host, e.g. `postgresql://user:pass@host.docker.internal:5432/db`.

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
