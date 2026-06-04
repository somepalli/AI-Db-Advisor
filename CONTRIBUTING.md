# Contributing to AI DB Advisor

Thanks for your interest in contributing! This guide covers setting up a dev
environment, running the app and tests, and submitting changes.

## Project layout

```
ai-db-advisor/
├── backend/          # FastAPI backend (the canonical, runnable backend package)
│   ├── routers/      # API endpoints (datasources, analyze, suggestions, alerts, analytics, mcp, ...)
│   ├── services/     # DB agents, AI client, advisors, monitoring, metrics, notifications
│   ├── utils/        # SQL parsing, plan diffing
│   ├── tests/        # pytest suite
│   ├── main.py       # FastAPI app
│   └── config.py     # Settings (env-driven)
├── tauri-app/        # Tauri v2 + React + TypeScript desktop UI
├── run.py            # Entry point: serves backend.main:app
└── requirements.txt
```

> The app is run via `python run.py`, which serves `backend.main:app`. (Earlier
> revisions ran from an untracked `.venv/app/` copy — that is no longer the case.)

## Backend dev setup

```bash
python -m venv .venv-app
# Windows:
.venv-app\Scripts\activate
# macOS/Linux:
source .venv-app/bin/activate

pip install -r requirements.txt
cp .env.example .env            # then edit .env with your own values
python run.py                   # http://127.0.0.1:8095  (docs at /docs)
```

You also need [Ollama](https://ollama.ai) for AI suggestions:

```bash
ollama pull qwen2.5:7b-instruct
```

## Frontend dev setup

```bash
cd tauri-app
npm install
npm run dev            # Vite dev server (browser) at http://localhost:5173
npm run tauri dev      # native desktop window (requires the Rust toolchain)
```

Configure the backend URL via `tauri-app/.env.local` (`VITE_API_BASE_URL`); see
`tauri-app/.env.example`.

## Running tests

```bash
# Backend (from repo root)
python -m pytest backend/tests

# Frontend type-check / build
cd tauri-app && npm run build
```

Integration tests that require live external services (MCP bridge, Google API) are
marked `integration` and skip automatically when those services/credentials aren't
configured. The default `pytest` run is offline-friendly.

## Security

Never commit secrets. Real `.env*` files are git-ignored; only `*.example` templates
are tracked. Credentials read from the environment (no hardcoded defaults). See
[`docs/SECURITY_REMEDIATION.md`](docs/SECURITY_REMEDIATION.md).

## Submitting changes

1. Branch off `master`: `git checkout -b feature/my-change`
2. Keep changes focused; match the surrounding code style.
3. Run backend tests and the frontend build before pushing.
4. Open a PR describing the change and how you verified it.

## Adding a new database engine

See the "Adding New Database Engines" section in `backend/CLAUDE.md` — implement the
`BaseAgent` interface, register in `registry.py`, and add the engine to the
`/datasources/engines` listing and DSN docs.
