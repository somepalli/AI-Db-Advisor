# 🤖 AI DB Advisor

**Multi-Database Performance Advisor with an AI Chat Assistant and an Autonomous, Guardrail-Gated DBA Agent**

AI DB Advisor combines rule-based query analysis, AI-powered chat/optimization, and a bounded autonomous "agent" loop that proactively scans your databases, proposes fixes, and routes anything impactful through a human-in-the-loop (HITL) approval queue — never executing a destructive statement on its own. The desktop/web UI is built with Tauri, React, Tailwind, and Radix UI; the backend is FastAPI.

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg)
![Tauri](https://img.shields.io/badge/Tauri-v2-FFC131.svg)
![React](https://img.shields.io/badge/React-18-61DAFB.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## 🚀 Run with Docker (fastest)

No toolchains needed — run the backend + web UI with one command:

```bash
cp .env.docker.example .env     # choose your LLM (Ollama / OpenAI / Anthropic)
docker compose up --build       # then open http://localhost:8080
```

See **[DOCKER.md](DOCKER.md)** for LLM options, persistence, and database-driver notes,
**[MONITORING.md](MONITORING.md)** for the optional Prometheus/Grafana stack, and
**[INSTALL.md](INSTALL.md)** for native/desktop development.

---

## ✨ Features

### 🗄️ Multi-Database Support (10 Database Types)

**SQL Databases:** PostgreSQL · MySQL/MariaDB · SQL Server · Oracle · SQLite
**NoSQL Databases:** MongoDB (document) · Redis (key-value) · Apache Cassandra (wide-column)
**Analytical Databases:** DuckDB · ClickHouse

Every engine implements the same `BaseAgent` contract (`get_schema`, `explain`, `stats`,
`locks`, `get_top_queries`, `get_existing_indexes`), so schema browsing, EXPLAIN plans,
and rule-based advisors work uniformly across all 10. See
**[Database Support Matrix](#-database-support-matrix)** below for exactly which
AI/agent capabilities are live per engine vs. still planned.

### 🤖 Agentic DBA Mode (autonomous, guardrail-gated)

A bounded, metadata-only investigation loop that behaves like a junior DBA who reads
but never touches data and never executes anything destructive:

- **Proactive scanning** — `POST /agent/scan-all` fans out a tailored health-audit goal
  (missing/unused indexes, stale stats, lock contention, cache hit ratio, expensive
  queries, plus engine-specific checks) across every registered datasource in the
  background; `GET /agent/scan/status` and `/agent/scan/results` poll progress.
- **Metadata-only, capped loop** — the agent can only call read tools that return
  schema/index/lock/stat metadata (`agent_tool_policy.py`); EXPLAIN is always run
  **without** `ANALYZE`; sample-row inclusion is hard-forced off; the loop is bounded
  by `max_iters` and a token budget, with "decide now" pressure after enough reads.
- **The guardrail wall (`agent_guardrails.py`)** — a single `evaluate()` decision point
  classifies every proposed statement as `metadata_read` / `safe_write` /
  `impactful_write` / `destructive` / `unknown`. **Destructive or unrecognized
  statements are hard-denied before they ever reach a human** — DROP TABLE/DATABASE/
  SCHEMA/VIEW/TABLESPACE/ROLE/USER, TRUNCATE, DELETE, unqualified UPDATE/DELETE,
  `CASCADE`, `ALTER TABLE ... DROP COLUMN`, Redis `FLUSHALL`, Cassandra
  `DROP KEYSPACE`, and more. A blocked proposal raises exactly one out-of-band
  `DESTRUCTIVE_BLOCKED` alert and one immutable audit event — it is never queued.
- **Safe proposals are queued, not executed** — `CREATE INDEX [CONCURRENTLY]`,
  `ANALYZE <table>`, and `SET <param>` style fixes are screened, then submitted to the
  existing HITL **approval workflow** as `pending`. A human reviews and approves/rejects
  from the UI; nothing is applied automatically.
- **Institutional memory** — each scan's top finding, approvals, and blocked count are
  persisted (`approval_store.record_scan_finding` / `get_scan_findings`) and re-injected
  into the next scan's warm-start context, so the agent doesn't re-propose changes that
  were already approved or re-flag the same issue without escalating.
- **Full audit trail** — `GET /agent/audit` (cross-datasource) and
  `/agent/{ds_id}/approvals/{id}/audit` return an immutable log of every scan start/
  completion/failure, investigation, approval, and destructive-blocked event.
- **🤖 Agent tab in the UI** (`AgentPanel.tsx`) — live per-datasource scan progress, rich
  approval cards with the proposed SQL + generated rollback SQL + typed-confirmation for
  higher-risk classes, a destructive-alerts feed, and an Audit Log view.

### 💬 AI-Powered SQL Chat Assistant
- **Conversational query generation** from natural language, with multi-turn context
- **Provider-trust gated data access** for hosted LLMs (see below) — currently Postgres,
  MySQL, and SQL Server route through the restricted, read-only tool layer; other
  engines use the legacy context builder (full schema + sample rows) regardless of trust
- **Persistent chat history** with ChromaDB-backed semantic search across sessions

### 🔍 Performance Analysis
- EXPLAIN plans, index recommendations (rule-based + AI), query rewrite suggestions,
  database statistics, lock/top-query inspection — for all 10 engines
- 3-layer index-suggestion deduplication against existing indexes

### 📊 Analytics Dashboard (DuckDB-backed)
- Sync tables/whole databases from a live PostgreSQL source into DuckDB
  (`services/data_sync.py`) for fast OLAP-style queries
- Pre-built KPI/dashboard endpoints: enrollment trends, fee collection, library usage,
  hostel occupancy, course popularity, grade distribution, comparative analysis

### 🔔 Alerting & Monitoring
- Rule-based alert engine (`alert_engine.py`) with active/resolved/history views,
  AI-assisted alert analysis, and per-datasource monitoring start/stop
- Optional Prometheus + Grafana stack (`docker compose --profile monitoring`) — see
  **[MONITORING.md](MONITORING.md)**

### 🖥️ Modern Desktop/Web UI
- **Tauri v2** desktop shell (or plain browser via Vite) — React 18 + TypeScript +
  Tailwind + Radix UI primitives + Recharts
- Tabs: **Query Analyzer** (connections, schema explorer, SQL editor + AI chat),
  **📊 Analytics**, **🔔 Alerts**, **🤖 Agent**
- SQL autocomplete, real-time syntax validation, session management

### 🔐 Provider-Trust Data Gating (Postgres / MySQL / SQL Server AI chat path)
Keeps real row data away from hosted LLMs while local models keep full access:
- **Trust derived from provider**: `ollama` → **local** (trusted); OpenAI/Anthropic →
  **hosted** (untrusted); UI override available.
- **Tool gating**: a registry tags every read-only tool `metadata` (always allowed) or
  `data` (local-trust only). On the hosted path, data tools are never selected and
  their output never reaches the model.
- **Restricted execution**: the Postgres path routes through **Postgres MCP Pro**
  in-process (`SafeSqlDriver`, RESTRICTED read-only + capped, for hosted models; plain
  `SqlDriver` for local). MySQL uses `SET SESSION TRANSACTION READ ONLY`. SQL Server's
  executor is implemented but has not yet been verified against a live container in
  this environment (Microsoft's container registry was unreachable during testing).
- **Sanitization**: metadata outputs pass through `normalize_sql` / `drop_value_arrays`
  / `strip_query_text`; schema is names-only; both the user's question and editor SQL
  are scrubbed of literal values before reaching a hosted model.

### ⚙️ Runtime-Configurable LLM
- Switch provider/model/endpoint/key from the UI — no `.env` edits or restart required
- Overrides persist to `llm_settings.json`, overlaid onto settings at startup
- LLM status badge → settings dialog with **Test** (lists installed models) and a
  **Data access** override selector

---

## 🧭 Database Support Matrix

Legend: ✅ implemented & covered by the test suite · ⚠️ implemented, not yet verified
against a live instance/UI · ❌ not yet wired (falls back to a more permissive default)

| Engine | Core analyze/advise (schema, EXPLAIN, index/rewrite) | Agentic autonomous scan (read-only, guardrail-gated) | Provider-trust gated AI chat (restricted hosted access) | Approval → Apply execution |
|---|---|---|---|---|
| PostgreSQL | ✅ | ✅ | ✅ (live-tested) | ✅ |
| MySQL / MariaDB | ✅ | ✅ | ✅ (live-tested) | ✅ |
| SQL Server | ✅ | ✅ | ⚠️ code complete, unit-tested, live-DB check pending | ✅ |
| Oracle | ✅ | ✅ | ❌ not yet wired | ✅ |
| SQLite | ✅ | ✅ | ❌ not yet wired | ✅ |
| MongoDB | ✅ | ✅ | ❌ not yet wired | ❌ not yet wired |
| Redis | ✅ | ✅ | ❌ not yet wired | ❌ not yet wired |
| Cassandra | ✅ | ✅ | ❌ not yet wired | ❌ not yet wired |
| DuckDB | ✅ | ✅ | ❌ not yet wired | ❌ not yet wired |
| ClickHouse | ✅ | ✅ | ❌ not yet wired | ❌ not yet wired |

Notes on what "✅" means here, so this table stays honest:

- **Core analyze/advise** — all 10 agents implement the full `BaseAgent` interface and
  are exercised by the 362-test backend suite (`python -m pytest backend/tests`, all
  passing). Those tests are written against mocked/fake agents to validate the API and
  service layer, not against live drivers for every engine — DuckDB and ClickHouse in
  particular have no dedicated test file yet, only the registry wiring.
- **Agentic autonomous scan** — `agent_loop.py` is engine-agnostic by construction (it
  only calls the universal `BaseAgent` read methods), and the guardrail wall has
  explicit destructive-pattern coverage for Redis (`FLUSHALL`) and Cassandra
  (`DROP KEYSPACE`) in addition to standard SQL DDL/DML. All 10 engines can run a scan
  and have proposals screened; this is tested with generic/Postgres-flavored fixtures,
  not one test per real engine.
- **Approval → Apply execution** — actually running an *approved* fix (`apply.py`) uses
  a DB-API `cursor()` + transaction pattern keyed to `postgres` / `mysql` / `sqlserver` /
  `oracle` / `sqlite`. MongoDB, Redis, Cassandra, DuckDB, and ClickHouse can be
  investigated and can have proposals queued, but there is no engine-specific apply path
  for them yet — this is the next gap to close, not a missing feature in the loop itself.
- **Provider-trust gated AI chat** — only engines in `GATED_ENGINES`
  (`gated_context.py`) get the restricted-tool / read-only / sanitized hosted-LLM path.
  Every other engine's chat falls back to the legacy context builder, which **does**
  include sample row data regardless of hosted/local trust — a known gap, tracked in
  the roadmap below.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Tauri / Web App (React + TS)                │
│   Query Analyzer · 📊 Analytics · 🔔 Alerts · 🤖 Agent             │
└───────────────────────────────┬────────────────────────────────────┘
                                 │ HTTP REST API
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend (Python)                     │
│  Routers: /datasources /analyze /ai-chat /agent /mcp /analytics   │
│           /alerts /llm                                            │
│  ┌────────────────────────────┐  ┌──────────────────────────────┐│
│  │ Agentic DBA loop            │  │ AI chat / suggestion path     ││
│  │ agent_loop → agent_         │  │ context_builder /             ││
│  │ guardrails (WALL) →         │  │ gated_context (PG/MySQL/      ││
│  │ approval_workflow (GATE)    │  │ SQL Server only) → ai_client  ││
│  └────────────────────────────┘  └──────────────────────────────┘│
│  Native per-DB agents (10 engines) implementing BaseAgent          │
└───────────────────────────────┬────────────────────────────────────┘
                                 │
        ┌────────────────────────┼─────────────────────────┐
        ▼                        ▼                          ▼
┌──────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│ 10 Database types │   │ LLM (configurable)    │   │ DuckDB analytics +   │
│ PG/MySQL/MSSQL/   │   │ Ollama / OpenAI /     │   │ Prometheus/Grafana   │
│ Oracle/SQLite/    │   │ Anthropic + ChromaDB  │   │ (optional)            │
│ Mongo/Redis/      │   └──────────────────────┘   └──────────────────────┘
│ Cassandra/DuckDB/ │
│ ClickHouse        │
└──────────────────┘
```

> **Three data-access paths.** `/analyze/*` and the agentic loop use the native
> per-database agents directly (metadata-only for the agent loop). The AI chat path
> routes through the provider-trust gated layer for Postgres/MySQL/SQL Server, and the
> legacy (ungated) context builder for everything else. See
> [Database Support Matrix](#-database-support-matrix) and
> [Provider-Trust Data Gating](#-provider-trust-data-gating-postgres--mysql--sql-server-ai-chat-path).

---

## 🆚 How this compares to DBeaver (Community Edition)

[DBeaver CE](https://dbeaver.io/) is a mature, free, open-source universal database GUI
with broad JDBC-driver support, ER diagrams, a data editor/exporter, and a SQL editor —
it's a much more general-purpose, polished desktop tool than this project, and it
supports far more database engines out of the box. It is **not** trying to be the same
kind of product as AI DB Advisor, so this is a feature-overlap comparison, not a "better
than" claim.

| Capability | AI DB Advisor | DBeaver Community Edition |
|---|---|---|
| Universal SQL editor + schema browser | ✅ | ✅ (more mature, more engines) |
| Breadth of supported databases | 10 engines | 80+ via JDBC drivers |
| ER diagrams / data editor / import-export | ❌ | ✅ |
| EXPLAIN / execution plan viewer | ✅ (text + AI explanation) | ✅ (visual plan viewer) |
| Natural-language → SQL chat | ✅ | ❌ (AI features are Ultimate/paid-only) |
| AI-generated index & rewrite suggestions | ✅ | ❌ |
| Autonomous proactive health-audit agent | ✅ (guardrail-gated, see above) | ❌ |
| Destructive-action guardrail wall + HITL approval queue | ✅ | ❌ (manual execution, no agent to gate) |
| Local-LLM-first / provider-trust data gating | ✅ | ❌ |
| Built-in alerting + Prometheus/Grafana monitoring | ✅ | ❌ |
| DuckDB-backed cross-DB analytics dashboards | ✅ | ❌ |
| Maturity / plugin ecosystem / desktop polish | growing | large, established |

In short: DBeaver CE is the better choice if you want one tool to browse/query dozens of
database engines with rich data-editing and ER tooling. AI DB Advisor is narrower in
database breadth but adds an entire AI/agentic layer — chat-driven query generation,
AI optimization suggestions, and a bounded autonomous DBA agent with a hard guardrail
wall and approval workflow — that DBeaver's free Community Edition doesn't attempt.

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.13+**
- **Node.js 18+** and npm
- **Ollama** (for local AI features)
- **Rust** (for the Tauri desktop app, optional)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ai-db-advisor.git
cd ai-db-advisor
```

### 2. Backend Setup

```bash
pip install -r requirements.txt
python run.py
```

Server runs on `http://127.0.0.1:8000` (Docker Compose uses port `8095` internally,
proxied to `8080` — see [DOCKER.md](DOCKER.md)).
- API Docs: http://127.0.0.1:8000/docs
- Health Check: http://127.0.0.1:8000/healthz

### 3. Frontend Setup (Web Interface)

```bash
cd tauri-app
npm install
npm run dev
```

Opens on `http://localhost:5173`

### 4. Desktop App (Optional)

```bash
# Install Rust (if not already installed)
# Windows: winget install Rustlang.Rustup
# macOS/Linux: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

npm run tauri dev
```

### 5. Setup Ollama (AI Features)

```bash
# https://ollama.ai
ollama pull qwen2.5:7b-instruct
curl http://127.0.0.1:11434/api/tags   # verify it's running
```

---

## 📖 Usage

### Connecting to a Database

**PostgreSQL Example:**
```
ID: my-postgres-db
Engine: postgres
DSN: postgresql://user:password@localhost:5432/database
```

**Supported DSN Formats:**
- **PostgreSQL**: `postgresql://user:pass@host:5432/db`
- **MySQL**: `mysql://user:pass@host:3306/db`
- **SQL Server**: `mssql://user:pass@host:1433/db`
- **Oracle**: `oracle://user:pass@host:1521/service`
- **MongoDB**: `mongodb://user:pass@host:27017/db`
- **Redis**: `redis://host:6379/0`
- **SQLite**: `sqlite:///path/to/database.db`
- **Cassandra**: `cassandra://host:9042/keyspace`
- **DuckDB**: `duckdb:///path/to/database.duckdb`
- **ClickHouse**: `clickhouse://user:pass@host:8123/db`

### Using the AI Chat Assistant

```
User: "Show all students enrolled in 2020"
AI: Generates → SELECT * FROM students WHERE enrollment_year = 2020

User: "Optimize this query: SELECT * FROM students"
AI: Suggests → use specific columns, add a WHERE clause, create an index

User: "Why is this query slow?"
AI: Analyzes the EXPLAIN plan and suggests improvements
```

### Using the Agent Tab

1. Open the **🤖 Agent** tab and click **Scan All** to kick off a background,
   metadata-only health audit across every registered datasource.
2. Watch live per-datasource progress and the top finding for each scan.
3. Review proposed fixes as **approval cards** — each shows the proposed SQL, the
   auto-generated rollback SQL, and (for higher-risk classes) requires typed
   confirmation before you approve.
4. Anything destructive never reaches this queue — it's rejected at the guardrail wall
   and shows up instead in the **destructive-alerts** feed with an audit entry.
5. Check the **Audit Log** view for a full, immutable history of scans, investigations,
   approvals, and blocked actions.

### Chat History

- **View Past Sessions**: click the 💬 icon to see all chat sessions
- **Session Titles**: auto-generated from the first message
- **Semantic Search**: search across all conversations (ChromaDB embeddings)
- **Session Switching**: load previous conversations with full history, persisted per
  datasource in `localStorage`

---

## 🔧 Configuration

### Configure from the UI (recommended)

Click the **LLM status badge** to open the settings dialog and switch
provider/endpoint/model/API key at runtime. **Test** lists installed models, **Save**
applies immediately (no restart). A **Data access** selector overrides the
provider-trust default.

### Environment Variables

Create a `.env` file in the root directory (see `.env.docker.example`):

```env
# LLM Configuration
LLM_PROVIDER=ollama                      # ollama | openai | anthropic
LLM_MODEL=qwen2.5:7b-instruct
LLM_ENDPOINT=http://127.0.0.1:11434
LLM_API_KEY=                             # required for hosted providers

# Provider-trust override for the gated AI chat path (Postgres/MySQL/SQL Server)
# local = full data access, hosted = read-only sanitized metadata only.
# Leave unset to derive automatically (ollama=local, else hosted).
LLM_PROVIDER_TRUST=

# Where UI overrides are persisted
LLM_SETTINGS_FILE=llm_settings.json

# Backend port (docker-compose default; CLAUDE.md elsewhere may say 8000 — that's stale)
API_PORT=8095

ENV=dev
```

### Supported LLM Providers & Models

- **Ollama (local)** — `qwen2.5:7b-instruct` (default, recommended), `llama3.1:8b`, `mistral:7b`, `codellama:7b`
- **OpenAI (hosted)** — e.g. `gpt-4o` (requires `LLM_API_KEY`)
- **Anthropic (hosted)** — e.g. `claude-sonnet-4-6` (requires `LLM_API_KEY`)

> Hosted providers are automatically treated as **untrusted**. For Postgres, MySQL, and
> SQL Server that means restricted, read-only, sanitized context unless overridden via
> `LLM_PROVIDER_TRUST`. For the other 7 engines, the chat path does not yet enforce this
> distinction — see the [Database Support Matrix](#-database-support-matrix).

---

## 📊 Key Components

### Backend (FastAPI)

**Agentic DBA mode:**
- `agent_loop.py`: bounded plan→read→propose investigation loop, proactive scan goals
- `agent_guardrails.py`: the WALL — `evaluate()` classifies/denies destructive actions
- `agent_tool_policy.py`: metadata-only toolset + forced `include_sample_data=False`
- `agent_scan_store.py`: live per-datasource scan state/progress
- `approval_workflow.py` / `approval_store.py`: HITL approval queue, audit log,
  scan-finding institutional memory
- `destructive_alerts.py`: out-of-band alert + notifier on every blocked action

**AI chat / suggestions:**
- `context_builder.py`: relevance-scored schema/sample-data context (legacy path)
- `gated_context.py` / `tool_registry.py`: provider-trust gated context (PG/MySQL/MSSQL)
- `postgres_mcp_executor.py`, `mysql_mcp_executor.py`, `mssql_mcp_executor.py`: per-engine
  restricted/read-only executors for the gated path
- `ai_client.py`: LLM client wrapper (Ollama / OpenAI / Anthropic)
- `advisor.py` / `super_agent.py`: rule-based + AI suggestion orchestration
- `chat_history.py`: ChromaDB-based chat persistence with semantic search

**Analytics & monitoring:**
- `data_sync.py`: Postgres → DuckDB table/database sync for analytics
- `alert_engine.py`: rule-based alerting, monitoring start/stop per datasource
- `metrics_collector.py`: Prometheus metrics

**Database Agents** (all implement `BaseAgent`):
`postgres_agent.py` · `mysql_agent.py` · `sqlserver_agent.py` · `oracle_agent.py` ·
`sqlite_agent.py` · `mongodb_agent.py` · `redis_agent.py` · `cassandra_agent.py` ·
`duckdb_agent.py` · `clickhouse_agent.py`

**API Endpoints (selected):**
- `/datasources` — manage database connections
- `/analyze/{ds_id}/*` — query analysis and rule-based/AI optimization
- `/agent/scan-all`, `/agent/scan/status`, `/agent/scan/results` — autonomous scans
- `/agent/{ds_id}/investigate` — single-datasource agent investigation
- `/agent/audit`, `/agent/{ds_id}/approvals/{id}/audit` — audit log
- `/agent/{ds_id}/destructive-alerts` — blocked-action feed
- `/ai-chat/chat`, `/ai-chat/validate-query` — conversational assistant
- `/analytics/*` — DuckDB sync + dashboard KPIs
- `/alerts/*` — alert rules, monitoring start/stop
- `/llm/config`, `/llm/test` — runtime LLM settings

### Frontend (React + Tauri)

**Components (selected):** `AgentPanel.tsx` · `AnalyticsDashboard.tsx` · `AlertPanel.tsx`
/ `AlertRulesPanel.tsx` / `AlertsPanel.tsx` · `ConnectionPanel.tsx` · `DBExplorer.tsx` ·
`SQLAssistant.tsx` · `AIAssistant.tsx` · `QueryAnalyzer.tsx` · `MCPSuggestionsPanel.tsx` ·
`SuggestionCard.tsx` · `LLMSettingsDialog.tsx` / `LLMStatusBadge.tsx` · `ui/` (Radix-based
primitives: dialogs, tabs, accordion, dropdowns, etc.)

---

## 🧪 Testing

```bash
# Backend tests (from repo root) — 362 tests, all passing as of this writing
python -m pytest backend/tests

# Frontend tests
cd tauri-app
npm run test
```

The backend suite validates the API/service layer with mocked/fake agents; it does not
run live driver integration tests per database engine (see the
[Database Support Matrix](#-database-support-matrix) notes for what that does and
doesn't cover).

---

## 📦 Database-Specific Requirements

### PostgreSQL
- **Extension** (recommended): `pg_stat_statements`, falls back to `pg_stat_activity`

### SQL Server
- **ODBC Driver 17/18** for SQL Server, DMV access permissions

### Oracle Database
- **Oracle Instant Client** required, V$ view permissions

### MongoDB / Redis / Cassandra
- No special requirements; enable Redis slowlog for query-performance tracking

### DuckDB / ClickHouse
- No special requirements; DuckDB is typically used as the analytics sink for
  `/analytics/*`, ClickHouse as a direct OLAP datasource

---

## 🛠️ Development

### Project Structure

```
ai-db-advisor/
├── backend/
│   ├── routers/        # datasources, analyze, ai_chat, agent, mcp, analytics, alerts, llm
│   ├── services/        # agents, agentic loop + guardrails, gated context, advisors, …
│   ├── tests/            # pytest suite (362 tests)
│   └── utils/
├── tauri-app/
│   ├── src/
│   │   ├── components/  # AgentPanel, AnalyticsDashboard, AlertPanel, SQLAssistant, …
│   │   ├── api/          # API client
│   │   └── types/
│   └── src-tauri/        # Rust backend
├── requirements.txt
├── run.py
└── README.md
```

### Adding New Database Support

1. Create an agent class inheriting from `BaseAgent`, implement all required methods
2. Add the driver to `requirements.txt`
3. Register in `registry.py`
4. If it should join the agentic autonomous scan: nothing extra — it works automatically
   via the `BaseAgent` contract
5. If it should support guardrailed *apply* of approved fixes: add a transaction branch
   in `apply.py`
6. If it should get the provider-trust gated AI chat path: follow the pattern in
   `gated_context.py` (`GATED_ENGINES`) — see the in-repo notes on adding an engine to
   the gated tool layer
7. Update the frontend engine dropdown and DSN documentation

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for details.

---

## 📝 License

MIT License — see the LICENSE file for details.

---

## 🙏 Acknowledgments

- **FastAPI** · **Ollama** · **Tauri** · **ChromaDB** · **Sentence Transformers** ·
  **SQLGlot** · **DuckDB** · **Postgres MCP Pro**

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/ai-db-advisor/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/ai-db-advisor/discussions)

---

## 🗺️ Roadmap

**Recently shipped**
- [x] Agentic DBA mode: proactive scan-all, guardrail wall, HITL approval queue,
      destructive-action alerts, institutional memory, full audit log, Agent UI tab
- [x] DuckDB + ClickHouse support (10 engines total)
- [x] DuckDB-backed analytics dashboards with Postgres data sync
- [x] Rule-based alert engine + Prometheus/Grafana monitoring stack
- [x] Provider-trust gated AI chat extended from Postgres to MySQL
- [x] Multiple LLM providers (Ollama, OpenAI, Anthropic) with runtime UI configuration
- [x] One-command Docker deployment (backend + web UI)

**Planned**
- [ ] Verify the SQL Server gated-chat executor against a live container (blocked
      previously by Microsoft container-registry reachability — retry pending)
- [ ] Extend provider-trust gating to Oracle, then SQLite, then MongoDB/Redis/Cassandra
- [ ] Wire Approval → Apply execution for MongoDB, Redis, Cassandra, DuckDB, ClickHouse
- [ ] Per-engine live integration tests (currently the suite is mock/fake-agent based)
- [ ] Export optimization reports / migration scripts
- [ ] Multi-language support, dark mode UI

---

**Made with ❤️ by the AI DB Advisor Team**
