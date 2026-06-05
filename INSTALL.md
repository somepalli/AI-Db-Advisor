# Installation Guide

End-to-end setup for AI DB Advisor (backend + desktop app).

> **Fastest path — Docker.** To run the whole app (backend + web UI) without
> installing Python/Node/Rust, see **[DOCKER.md](DOCKER.md)**:
> `cp .env.docker.example .env && docker compose up --build` → open http://localhost:8080.
> The steps below are for native/desktop development.

## Prerequisites

- **Python** 3.11+ (3.13 supported)
- **Node.js** 18+ and npm (for the desktop UI)
- **Rust toolchain** (only for building/running the native Tauri window — not needed for `npm run dev`)
- **Ollama** (for AI suggestions): https://ollama.ai
- A supported database to analyze (PostgreSQL, MySQL, SQL Server, Oracle, SQLite, MongoDB, Redis, Cassandra)

## 1. Clone

```bash
git clone <repo-url>
cd ai-db-advisor
```

## 2. Backend

```bash
python -m venv .venv-app
# Windows:
.venv-app\Scripts\activate
# macOS/Linux:
source .venv-app/bin/activate

pip install -r requirements.txt
cp .env.example .env        # edit values as needed
```

Pull the LLM model:

```bash
ollama pull qwen2.5:7b-instruct
ollama list                 # verify
```

Run the backend:

```bash
python run.py               # http://127.0.0.1:8095
```

- API docs: http://127.0.0.1:8095/docs
- Health check: http://127.0.0.1:8095/healthz

Override host/port with `API_HOST` / `API_PORT` env vars.

## 3. Desktop app

```bash
cd tauri-app
npm install

# Option A: browser dev (fastest)
npm run dev                 # http://localhost:5173

# Option B: native desktop window (requires Rust)
npm run tauri dev
```

If your backend runs on a non-default URL, set it in `tauri-app/.env.local`:

```
VITE_API_BASE_URL=http://127.0.0.1:8095
```

> Database connection secrets are stored in the OS-native credential store
> (Windows Credential Manager / macOS Keychain / Linux Secret Service) when running
> the Tauri desktop app. In plain browser dev mode they fall back to localStorage
> (a console warning is shown) — use the desktop app for secure storage.

## 4. Optional: MCP integration (PostgreSQL only)

MCP is **off by default** (the UI shows a clearly-labelled demo mode). To enable real
suggestions, see [`MCP_SETUP_GUIDE.md`](MCP_SETUP_GUIDE.md) and set the `MCP_*` values
in `.env`.

## 5. Optional: monitoring stack

Prometheus/Grafana dashboards and alerting live under `monitoring/`. See
`monitoring/` and `start_monitoring.bat` (Windows) / `docker-compose.monitoring.yml`.

## Troubleshooting

- **Backend won't start** — confirm the venv is active and `pip install -r requirements.txt` succeeded.
- **AI suggestions empty** — confirm Ollama is running and the model is pulled (`ollama list`).
- **CORS / connection errors in the UI** — confirm the backend is running and `VITE_API_BASE_URL` matches its address.
- **Tauri build fails** — install the Rust toolchain and platform build tools (see `tauri-app/CLAUDE.md`).
