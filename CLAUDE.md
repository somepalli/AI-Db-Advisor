# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI DB Advisor** is a comprehensive multi-database performance optimization system consisting of:
- **FastAPI Backend** (.venv/app/): REST API for multi-database query analysis and AI-powered optimization
- **Tauri Desktop App** (tauri-app/): Modern desktop UI built with React/TypeScript and Tauri v2

The system analyzes SQL/NoSQL queries, provides AI-powered suggestions, index recommendations, query rewrites, and detailed execution plans using local LLMs via Ollama.

**Supported Databases (8 types):**
- **SQL Databases**: PostgreSQL, MySQL/MariaDB, SQL Server, Oracle, SQLite
- **NoSQL Databases**: MongoDB (document), Redis (key-value), Cassandra (wide-column)

**Important Notes:**
- **HypoPG is NOT used** - The system runs on Windows where HypoPG extension is not available
- **FastUI is NOT used** - The UI is the Tauri desktop application
- **Electron app is NOT used** - The active desktop app is Tauri-based
- **Multi-Database Support** - All 8 database types support AI-powered optimization

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Tauri Desktop App                      │
│              (React + TypeScript + Vite)                 │
│  ┌──────────┬──────────┬──────────┬─────────────────┐  │
│  │Connection│  DB      │   SQL    │  AI Suggestions │  │
│  │  Panel   │ Explorer │  Editor  │     Panel       │  │
│  └──────────┴──────────┴──────────┴─────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP REST API
                       ▼
┌─────────────────────────────────────────────────────────┐
│               FastAPI Backend (Python)                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Routers: /datasources, /analyze, /optimize      │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  Services: Multi-DB Agents, AI Client, Advisors  │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  Utils: SQL Parser, Plan Diff                    │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                              ▼
┌──────────────────┐          ┌──────────────────┐
│ Multi-Databases  │          │  Ollama LLM      │
│ (8 DB types)     │          │  (qwen2.5:7b)    │
└──────────────────┘          └──────────────────┘
```

## Backend Architecture (.venv/app/)

### Core Components

#### 1. Agent Layer (services/)
Database-specific agents implementing the `BaseAgent` interface:

- **`base_agent.py`**: Abstract base class defining the agent contract
  - All agents must implement: `get_db_type()`, `get_schema()`, `get_top_queries()`, `explain()`, `locks()`, `stats()`, `get_existing_indexes()`, `index_exists()`, `get_optimization_context()`

- **SQL Database Agents**:
  - **`postgres_agent.py`**: PostgreSQL implementation
    - Uses psycopg 3.2, pg_stat_statements, pg_catalog
    - EXPLAIN plans, index validation via pg_indexes
  - **`mysql_agent.py`**: MySQL/MariaDB implementation
    - Uses pymysql, INFORMATION_SCHEMA, performance_schema
    - EXPLAIN plans, index validation via statistics
  - **`sqlserver_agent.py`**: SQL Server implementation
    - Uses pyodbc, sys tables (sys.columns, sys.indexes)
    - SHOWPLAN_XML for execution plans
  - **`oracle_agent.py`**: Oracle Database implementation
    - Uses cx_Oracle, ALL_TAB_COLUMNS, V$SQL
    - EXPLAIN PLAN, index validation via ALL_INDEXES
  - **`sqlite_agent.py`**: SQLite implementation
    - Uses sqlite3 (stdlib), PRAGMA commands
    - EXPLAIN QUERY PLAN, index validation via PRAGMA index_list

- **NoSQL Database Agents**:
  - **`mongodb_agent.py`**: MongoDB implementation
    - Uses pymongo, collections instead of tables
    - explain() for query plans, index validation via index_information()
  - **`redis_agent.py`**: Redis implementation
    - Uses redis-py, key patterns instead of schema
    - SLOWLOG for performance, no traditional indexes
  - **`cassandra_agent.py`**: Cassandra implementation
    - Uses cassandra-driver, system_schema tables
    - Query tracing, secondary indexes

- **`registry.py`**: Factory pattern for instantiating agents based on engine type
  - Maps 19 engine aliases to 8 agent classes
  - Examples: "postgres", "mysql", "mongodb", "oracle", "redis", etc.

#### 2. Advisor System (services/advisor.py)
Rule-based optimization advisors:

- **`index_advice_pg()`**: Analyzes predicates and suggests indexes
  - Parses SQL using sqlglot
  - Extracts WHERE, JOIN, and ORDER BY predicates
  - Recommends B-tree indexes on filtered columns
  - **Note**: No HypoPG validation on Windows
- **`rewrite_advice()`**: Heuristic query rewrites
  - Detects `SELECT *` anti-pattern
  - Identifies inefficient OFFSET/LIMIT patterns
  - Suggests query improvements

#### 3. AI Integration (services/)

- **`ai_client.py`**: LLM client wrapper for Ollama
  - Supports Ollama's `/api/chat` endpoint
  - Enables JSON mode via `format: "json"` parameter
  - Increased token limit: `max_tokens=1500` for complete suggestions
  - Advanced JSON parsing with fallbacks:
    1. Direct JSON parse
    2. Markdown code block extraction
    3. Regex-based JSON extraction
  - Comprehensive error handling and logging

- **`ai_suggest.py`**: AI-powered query optimization
  - **System Prompt**: Detailed instructions for generating 3 types of suggestions:
    - `type: "index"`: Index recommendations with table/columns
    - `type: "rewrite"`: Query rewrite suggestions with new_sql
    - `type: "note"`: General performance advice
  - **Input Context**:
    - Database schema sample (3 tables, 6 columns each)
    - Original SQL query
    - EXPLAIN plan excerpt (Node Type, Cost, Rows, Filters)
  - **Validation**: Each suggestion is validated (or marked unvalidated on Windows)
  - **Expected Gains**: Calculated via plan cost/row comparison
  - **Comprehensive Logging**: Full request/response logging for debugging

#### 3a. MCP Integration (Model Context Protocol)

**Overview**: MCP integration enables direct database access for AI assistants through standardized protocol.

- **`mcp_client.py`**: MCP client wrapper for postgres-mcp
  - Connects to MCP bridge server (HTTP wrapper for stdio MCP servers)
  - Supports postgres-mcp tools: `query`, `list_tables`, `describe_table`, `append_insights`
  - Maps generic context to tool-specific arguments
  - Safety: Suggestion-only mode enforced, never auto-executes

- **`mcp_orchestrator.py`**: Orchestrates MCP tool invocations
  - Workflow: Request → Validate → Approve → Execute
  - Safety validation via `SafetyValidator`
  - User approval workflow via `ApprovalWorkflow`
  - Comprehensive logging and audit trail

- **`mcp_bridge_server.py`** (root directory): HTTP bridge for postgres-mcp
  - Wraps stdio MCP servers as HTTP endpoints
  - Endpoints: `/health`, `/tools`, `/tools/call`
  - JSON-RPC 2.0 protocol adapter
  - Runs on port 3000 (configurable via `MCP_BRIDGE_PORT`)
  - Auto-installs postgres-mcp via npx

- **AI Chat Integration** (`routers/ai_chat.py`):
  - Automatically fetches MCP suggestions alongside AI suggestions
  - Merges AI and MCP recommendations with `is_mcp: true` flag
  - Falls back to demo mode if MCP not configured

**Configuration** (.env):
```env
MCP_ENABLED=true
MCP_ENDPOINT=http://localhost:3000
POSTGRES_DSN=postgresql://user:password@host:5432/database
MCP_BRIDGE_PORT=3000
```

**Starting MCP Bridge**:
```bash
# Windows
start_mcp_bridge.bat

# Or start both services
start_with_mcp.bat

# Or manually
python mcp_bridge_server.py
```

**Architecture**:
```
AI Chat → MCP Client → MCP Bridge (HTTP) → postgres-mcp (stdio) → PostgreSQL
```

See `README_MCP.md` for detailed integration guide.

#### 4. SQL Analysis (utils/)

- **`sql_parse.py`**: SQL parsing utilities using sqlglot
  - Extracts predicates from WHERE clauses
  - Identifies columns in JOINs and ORDER BY
  - Supports PostgreSQL dialect

- **`plan_diff.py`**: Query plan comparison
  - Computes cost delta percentage
  - Computes row count delta percentage
  - Used for before/after optimization metrics

#### 5. API Routers (routers/)

**`datasources.py`**:
- `GET /datasources`: List all registered data sources
- `POST /datasources`: Register new database connection (any supported engine)
  - Request: `{id: string, engine: "postgres"|"mysql"|"mongodb"|..., dsn: "..."}`
  - Stores in-memory: `settings.DATASOURCES`
- `DELETE /datasources/{ds_id}`: Delete a data source
- `GET /datasources/engines`: List all supported database engines (19 aliases, 8 types)

**`analyze.py`**:
- `GET /analyze/{ds_id}/schema`: Get database schema (works for all DB types)
- `GET /analyze/{ds_id}/top`: Get top queries by execution time (DB-specific)
- `POST /analyze/{ds_id}/explain`: Get EXPLAIN plan for query (DB-specific format)
- `GET /analyze/{ds_id}/locks`: Get current database locks (DB-specific)
- `GET /analyze/{ds_id}/stats`: Get database statistics (DB-specific)
- `POST /analyze/{ds_id}/advise/index`: Get index recommendations (SQL databases)
- `POST /analyze/{ds_id}/advise/rewrite`: Get query rewrite suggestions (SQL databases)
- `POST /analyze/{ds_id}/advise/ai`: Get AI-powered suggestions (all DB types, 3 suggestions)
- `POST /analyze/{ds_id}/explain/ai`: Get AI explanation of EXPLAIN plan (all DB types)
- `POST /analyze/{ds_id}/optimize/database`: Get database-level AI optimizations
- `POST /analyze/{ds_id}/optimize/table/{table_name}`: Get table-level AI optimizations
- `POST /analyze/{ds_id}/optimize/apply`: Apply selected optimization SQL statements

All endpoints are database-agnostic and include extensive logging for debugging.

### Data Flow

1. **Connection Setup**:
   - User adds connection in Tauri UI
   - Frontend calls `POST /datasources` with DSN
   - Backend stores in `settings.DATASOURCES` (in-memory)

2. **Query Analysis**:
   - User executes SQL in Tauri SQL Editor
   - Frontend calls analysis endpoints sequentially:
     - `POST /analyze/{ds_id}/advise/ai` → AI Suggestions
     - `POST /analyze/{ds_id}/advise/rewrite` → Rewrite Advice
     - `POST /analyze/{ds_id}/advise/index` → Index Advice
     - `POST /analyze/{ds_id}/explain` → Explain Plan
   - Each endpoint:
     - Calls `resolve_agent(ds_id)` to get appropriate database agent
     - Executes database-specific analysis
     - Returns unified results format

3. **AI Suggestion Flow**:
   ```
   User SQL → Schema Context → LLM Prompt → Ollama → JSON Response
        ↓                                                    ↓
   EXPLAIN Plan                                    Parse & Validate
        ↓                                                    ↓
   Plan Excerpt                              Generate SQL/Index fixes
                                                             ↓
                                              Return 3 suggestions
   ```

### Configuration

**Environment Variables** (config.py):
- `LLM_PROVIDER`: "ollama" (default)
- `LLM_MODEL`: "qwen2.5:7b-instruct" (default)
- `LLM_ENDPOINT`: "http://127.0.0.1:11434" (default)
- `ENV`: "dev" or "prod"

**In-Memory Storage**:
- `settings.DATASOURCES`: Dict[str, DataSource] - All database connections

## Frontend Architecture (tauri-app/)

### Tech Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite 6
- **Desktop**: Tauri v2 (Rust-based, lightweight alternative to Electron)
- **HTTP Client**: Native fetch API (works with Tauri permissions)
- **Styling**: CSS-in-JS (inline styles)

### Component Structure

```
tauri-app/src/
├── main.tsx                 # App entry point
├── App.tsx                  # Root component with 4-panel layout
├── api/
│   └── client.ts            # API client (analyzeApi, datasourcesApi, healthApi)
├── components/
│   ├── ConnectionPanel.tsx          # Database connection management
│   ├── DBExplorer.tsx              # Database schema tree view
│   ├── SQLEditor.tsx               # Basic SQL editor
│   ├── SQLEditorWithAutocomplete.tsx  # SQL editor with autocomplete
│   ├── QueryAnalyzer.tsx           # AI suggestions display panel
│   └── Dashboard.tsx               # Performance dashboard (not used in main UI)
└── types/
    └── index.ts             # TypeScript type definitions
```

### Component Details

#### App.tsx
Four-panel desktop layout:
```
┌────────────────┬────────────────┬────────────────┬────────────────┐
│  Connection    │  DB Explorer   │  SQL Editor    │ AI Suggestions │
│    Panel       │                │                │     Panel      │
│                │                │                │                │
│ - Add/Remove   │ - Tables List  │ - Query Input  │ - AI Results   │
│ - Select DS    │ - Columns      │ - Execute Btn  │ - Rewrite Tips │
│                │ - Data Types   │ - Copy to AI   │ - Index Tips   │
│                │                │ - Autocomplete │ - Explain Plan │
└────────────────┴────────────────┴────────────────┴────────────────┘
```

#### SQLEditorWithAutocomplete.tsx (Main SQL Editor)
Features:
- **SQL Input**: Multi-line textarea with syntax validation
- **Autocomplete**:
  - Tables (from schema)
  - Columns (from all tables)
  - SQL keywords (SELECT, FROM, WHERE, etc.)
  - Arrow keys navigation, Enter to insert
- **Validation**:
  - Unclosed quotes detection
  - Unknown table warnings
  - Visual error indicators
- **Execute Button**: Triggers all 4 analyses sequentially
  - Shows loading state: "⏳ AI Suggestions..." → "⏳ Rewrite Advice..." → etc.
- **Copy to AI Editor Button**: Copy query to AI Suggestions panel (optional feature)

**After Execute, displays 4 sections in order**:

1. **🤖 AI Suggestions** (first):
   - Only AI-related suggestions
   - Shows: type, summary, rationale
   - For rewrites: displays new_sql
   - For indexes: displays CREATE INDEX statement
   - Expected performance gains

2. **✏️ Rewrite Advice** (second):
   - Query optimization recommendations
   - Category, summary, sql_fix
   - Expected gains and risk levels

3. **📊 Index Advice** (third):
   - Index creation recommendations
   - Category, summary, sql_fix
   - Expected performance improvements

4. **📈 Explain Plan** (fourth):
   - Full query execution plan JSON
   - Formatted with syntax highlighting

#### API Client (api/client.ts)

**analyzeApi**:
- `getSchema(dsId)`: Fetch database schema
- `getTopQueries(dsId, limit)`: Get top queries
- `explain(dsId, sql, analyze)`: Get EXPLAIN plan
- `getLocks(dsId)`: Get database locks
- `getStats(dsId)`: Get database statistics
- `adviseIndex(dsId, sql)`: Get index recommendations
- `adviseRewrite(dsId, sql)`: Get rewrite recommendations
- `adviseAI(dsId, sql)`: Get AI suggestions (returns 3 items)
- `explainPlanAI(dsId, sql)`: Get AI explanation

**datasourcesApi**:
- `list()`: Get all connections
- `create(data)`: Add new connection

Base URL: `http://127.0.0.1:8000`

### Types (types/index.ts)

Key interfaces:
- `DataSource`: {id, engine, dsn}
- `TableSchema`: {column, type, nullable}
- `SchemaResponse`: {tables: Record<string, TableSchema[]>}
- `TopQuery`: {query, calls, mean_time_ms, rows, source}
- `Lock`: {locktype, mode, granted, pid, age}
- `Stats`: {total_db_size, active_backends}
- `ExplainPlan`: {plan: any[]}
- `Recommendation`: {category, summary, sql_fix?, risk?, expected_gain?}
- `AIAdviceResponse`: {suggestions: Array<{type, summary, rationale?, new_sql?, sql_fix?, expected_gain?, validated?, risk?}>}

## Database Setup

### Supported Database Connection Strings

**PostgreSQL**:
```
DSN: postgresql://user:password@localhost:5432/database
Example: postgresql://postgres:postgres@localhost:5432/UniversityDB
```

**MySQL/MariaDB**:
```
DSN: mysql://user:password@localhost:3306/database
Example: mysql://root:password@localhost:3306/mydb
```

**SQL Server**:
```
DSN: mssql://user:password@localhost:1433/database
Example: mssql://sa:Password123@localhost:1433/AdventureWorks
```

**Oracle Database**:
```
DSN: oracle://user:password@localhost:1521/service_name
Example: oracle://system:oracle@localhost:1521/ORCL
```

**MongoDB**:
```
DSN: mongodb://user:password@localhost:27017/database
Example: mongodb://admin:password@localhost:27017/mydb
```

**Redis**:
```
DSN: redis://localhost:6379/0
Example: redis://localhost:6379/0
```

**SQLite**:
```
DSN: sqlite:///path/to/database.db
Example: sqlite:///C:/data/myapp.db
```

**Cassandra**:
```
DSN: cassandra://localhost:9042/keyspace
Example: cassandra://localhost:9042/mykeyspace
```

### UniversityDB (PostgreSQL Sample Database)

**Connection**:
```
Host: localhost
Port: 5432
Database: UniversityDB
Username: postgres
Password: postgres
DSN: postgresql://postgres:postgres@localhost:5432/UniversityDB
```

**Tables** (with sample data):
- `departments` (10 rows): department_id, department_name, hod
- `students` (12,000 rows): student_id, first_name, last_name, dob, email, department_id, enrollment_year
- `professors` (500 rows): professor_id, name, department_id, email
- `courses` (150 rows): course_id, course_name, department_id, credits
- `enrollments` (15,000 rows): enrollment_id, student_id, course_id, semester, grade
- `fees` (12,000 rows): fee_id, student_id, amount, due_date, status
- `hostel` (20 rows): hostel_id, hostel_name, capacity, warden_name
- `hostelallocation` (10,000 rows): allocation_id, student_id, hostel_id, room_no, allocation_date
- `librarybooks` (5,000 rows): book_id, title, author, department_id, available_copies
- `bookloans` (14,000 rows): loan_id, student_id, book_id, loan_date, return_date

**Scripts**:
- `inspect_db.py`: Inspect table structures and row counts
- `populate_university_db.py`: Populate tables with sample data

## Commands

### Backend Setup & Run

```bash
# Install dependencies
cd C:\Users\chowh\OneDrive\Desktop\ai-db-advisor
pip install -r requirements.txt

# Run backend (from root)
python run.py

# Server runs on http://127.0.0.1:8000 with auto-reload
# API docs: http://127.0.0.1:8000/docs
# Health check: http://127.0.0.1:8000/healthz
```

### Frontend Setup & Run

```bash
# Install dependencies
cd C:\Users\chowh\OneDrive\Desktop\ai-db-advisor\tauri-app
npm install

# Run development server (Vite only, no Tauri)
npm run dev
# Opens on http://localhost:5173

# Run Tauri desktop app (requires Rust)
npm run tauri dev
# Opens desktop window

# Build for production
npm run tauri build
```

### Database Setup

```bash
# Inspect database tables
cd C:\Users\chowh\OneDrive\Desktop\ai-db-advisor\.venv\app
python inspect_db.py

# Populate with sample data (10,000-15,000 rows per table)
python populate_university_db.py
```

### LLM Setup

1. Install Ollama: https://ollama.ai
2. Pull model:
   ```bash
   ollama pull qwen2.5:7b-instruct
   ```
3. Verify running:
   ```bash
   curl http://127.0.0.1:11434/api/tags
   ```

## Key Dependencies

### Backend
- **FastAPI 0.115**: Modern async web framework
- **Database Drivers**:
  - **psycopg 3.2**: PostgreSQL adapter with dict_row support
  - **pymysql**: MySQL/MariaDB driver
  - **pyodbc**: SQL Server driver (requires ODBC Driver 17)
  - **cx_Oracle**: Oracle Database driver
  - **pymongo**: MongoDB driver
  - **redis**: Redis client (redis-py)
  - **sqlite3**: SQLite (Python stdlib)
  - **cassandra-driver**: Apache Cassandra driver
- **sqlglot 25.6**: SQL parsing for predicate analysis
- **httpx 0.27**: HTTP client for Ollama API
- **uvicorn**: ASGI server

### Frontend
- **React 18**: UI framework
- **TypeScript 5**: Type-safe JavaScript
- **Vite 6**: Fast build tool
- **@tauri-apps/api 2**: Tauri JavaScript bindings

## Database-Specific Requirements

### PostgreSQL Extensions
**Recommended**:
- `pg_stat_statements`: Query performance statistics
  - Used for top queries by execution time
  - Falls back to `pg_stat_activity` if unavailable

**Not Used** (Windows limitation):
- `hypopg`: Hypothetical index testing
  - Extension not available on Windows
  - Suggestions still generated, just not validated

### SQL Server Requirements
- **ODBC Driver 17 for SQL Server**: Required for pyodbc connections
- **Permissions**: Requires access to DMVs (dm_exec_query_stats, dm_tran_locks)

### Oracle Database Requirements
- **Oracle Instant Client**: Required for cx_Oracle
- **Permissions**: Requires access to V$ views (V$SQL, V$LOCK) and ALL_ views

### NoSQL Databases
- **MongoDB**: No special extensions required
- **Redis**: Slowlog should be enabled for query performance tracking
- **Cassandra**: No special requirements

## Development Workflow

### Adding New Features

1. **Backend**: Add endpoint to `routers/analyze.py`
2. **Backend**: Add business logic to `services/`
3. **Frontend**: Add API method to `api/client.ts`
4. **Frontend**: Add UI component to `components/`
5. **Frontend**: Add types to `types/index.ts`

### Debugging

**Backend Logs**:
```bash
# All API requests logged
# AI suggestions show:
#   - Input SQL
#   - Schema context
#   - LLM prompt
#   - Raw LLM response
#   - Parsed suggestions
#   - Validation results
```

**Frontend Logs**:
- Open DevTools in desktop app
- Check Network tab for API calls
- Check Console for errors

### Testing

```bash
# Backend tests (if available)
cd .venv/app
pytest

# Frontend
cd tauri-app
npm run test  # (if test scripts exist)
```

## Common Issues & Solutions

### Issue 1: AI Returns Only 1 Suggestion Instead of 3

**Cause**: LLM token limit too low, or JSON parsing fails

**Solution**:
- Increased `max_tokens` to 1500 (ai_client.py:13)
- Enabled Ollama JSON mode (ai_client.py:29)
- Improved JSON parsing with fallbacks (ai_client.py:44-79)
- Better system prompt with examples (ai_suggest.py:14-60)

### Issue 2: HypoPG Not Available

**Status**: Expected on Windows

**Impact**: Index suggestions not validated

**Workaround**: Suggestions still generated with SQL fixes, just marked as unvalidated

### Issue 3: Connection Refused to Backend

**Check**:
1. Backend running: `python run.py`
2. Listening on 127.0.0.1:8000
3. No firewall blocking
4. CORS enabled for localhost:5173

### Issue 4: Ollama Not Responding

**Check**:
1. Ollama running: `ollama list`
2. Model pulled: `ollama pull qwen2.5:7b-instruct`
3. Endpoint: http://127.0.0.1:11434
4. Test: `curl http://127.0.0.1:11434/api/tags`

## Project Structure Summary

```
ai-db-advisor/
├── .venv/app/              # FastAPI Backend
│   ├── routers/            # API endpoints
│   ├── services/           # Business logic
│   ├── utils/              # Helpers
│   ├── tests/              # Tests
│   ├── config.py           # Configuration
│   ├── deps.py             # Dependencies
│   ├── schemas.py          # Pydantic models
│   └── main.py             # FastAPI app
│
├── tauri-app/              # Tauri Desktop App (ACTIVE)
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── api/            # API client
│   │   ├── types/          # TypeScript types
│   │   ├── App.tsx         # Root component
│   │   └── main.tsx        # Entry point
│   ├── src-tauri/          # Tauri Rust backend
│   ├── package.json
│   └── vite.config.ts
│
├── electron-app/           # NOT USED
├── requirements.txt        # Python dependencies
├── run.py                  # Backend entry point
└── CLAUDE.md              # This file
```

## Best Practices

1. **Always restart backend after code changes** (unless using auto-reload)
2. **Check logs** for AI suggestions to debug unexpected responses
3. **Use TypeScript strictly** - no `any` types in frontend
4. **Validate inputs** on both frontend and backend
5. **Handle errors gracefully** - show user-friendly messages
6. **Keep schema context small** - 3 tables max for AI prompts
7. **Use batch API calls** when possible (frontend optimization)
8. **Log extensively** for debugging AI interactions

## Completed Features

- ✅ Multi-database support (8 database types)
- ✅ PostgreSQL, MySQL, SQL Server, Oracle, MongoDB, Redis, SQLite, Cassandra
- ✅ AI-powered optimization for all database types
- ✅ Database and table-level optimization endpoints
- ✅ Index validation to prevent duplicate suggestions
- ✅ Delete datasource functionality
- ✅ Dynamic DSN placeholders in UI
- ✅ **postgres-mcp integration** via MCP bridge server
- ✅ Real-time database queries through AI chat with MCP
- ✅ MCP approval workflow with safety validation
- ✅ Unified AI + MCP suggestions in chat interface

## Future Enhancements

- Add query execution history
- Add query performance benchmarking
- Export suggestions as migration scripts
- Add user authentication
- Support multiple LLM providers (OpenAI, Anthropic)
- Implement HypoPG for Linux/macOS builds
- Add automated testing suite for all database types
- Create installers for Windows/Mac/Linux
- Add database migration suggestions
- Support for additional databases (Elasticsearch, Neo4j, etc.)
