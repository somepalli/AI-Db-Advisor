# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI DB Advisor is a FastAPI-based multi-database performance advisor that provides both rule-based and AI-powered query optimization recommendations for 8 major database types. It uses local LLMs via Ollama for AI suggestions and supports both SQL and NoSQL databases.

**Supported Databases (8 types):**
- **SQL Databases**: PostgreSQL, MySQL/MariaDB, SQL Server, Oracle, SQLite
- **NoSQL Databases**: MongoDB (document), Redis (key-value), Cassandra (wide-column)

## Architecture

### Core Components

- **Agent Layer** (`services/`): Database-specific agents implementing the `BaseAgent` interface

  **SQL Database Agents**:
  - `PostgresAgent` (postgres_agent.py): PostgreSQL via psycopg 3.2, pg_stat_statements, pg_catalog
  - `MySQLAgent` (mysql_agent.py): MySQL/MariaDB via pymysql, INFORMATION_SCHEMA, performance_schema
  - `SQLServerAgent` (sqlserver_agent.py): SQL Server via pyodbc, sys tables, SHOWPLAN_XML
  - `OracleAgent` (oracle_agent.py): Oracle via cx_Oracle, ALL_TAB_COLUMNS, V$SQL, EXPLAIN PLAN
  - `SQLiteAgent` (sqlite_agent.py): SQLite via sqlite3 (stdlib), PRAGMA commands, EXPLAIN QUERY PLAN

  **NoSQL Database Agents**:
  - `MongoDBAgent` (mongodb_agent.py): MongoDB via pymongo, collections, explain(), index_information()
  - `RedisAgent` (redis_agent.py): Redis via redis-py, key patterns, SLOWLOG
  - `CassandraAgent` (cassandra_agent.py): Cassandra via cassandra-driver, system_schema, query tracing

  - `registry.py`: Factory pattern mapping 19 engine aliases to 8 agent classes

- **Advisor System** (`services/advisor.py`):
  - `index_advice_pg()`: Rule-based index recommendations using predicate analysis with duplicate prevention
  - `rewrite_advice()`: Heuristic query rewrite suggestions (SELECT *, OFFSET/LIMIT patterns)
  - Index validation via `index_exists()` to prevent duplicate suggestions

- **AI Integration** (`services/`):
  - `ai_client.py`: LLMClient wraps Ollama API for chat completions with JSON mode
  - `ai_suggest.py`: Combines schema context + EXPLAIN plans with LLM to generate validated optimization suggestions
  - `super_agent.py`: Orchestrates AI suggestions with deduplication and validation

- **SQL Analysis** (`utils/`):
  - `sql_parse.py`: Uses sqlglot to extract predicates, columns, and query structure
  - `plan_diff.py`: Compares EXPLAIN plan costs/rows before/after optimizations

- **API Routers** (`routers/`):
  - `datasources.py`: Register/list/delete database connections, list supported engines
  - `analyze.py`: Query analysis endpoints (schema, top queries, EXPLAIN, locks, stats, AI advice)
  - `suggestions.py`: Apply optimization suggestions directly to database
  - Optimization endpoints: `/optimize/database`, `/optimize/table/{table}`, `/optimize/apply`

### Data Flow

1. User registers a data source via POST /datasources with DSN and engine type
2. Datasources stored in-memory in `settings.DATASOURCES` (config.py)
3. `resolve_agent()` (deps.py) fetches config and instantiates appropriate agent via registry
4. Analysis endpoints use agent methods to query database and run advisors
5. AI advisor calls LLM with schema sample + EXPLAIN excerpt, generates suggestions
6. Index validation prevents duplicate suggestions via `index_exists()` check

### Configuration

- **Environment Variables** (config.py):
  - `LLM_PROVIDER`: Default "ollama"
  - `LLM_MODEL`: Default "qwen2.5:7b-instruct"
  - `LLM_ENDPOINT`: Default "http://127.0.0.1:11434"
  - `ENV`: "dev" or "prod"

## API Endpoints

### Datasource Management
- `GET /datasources`: List all registered data sources
- `POST /datasources`: Register new database connection (any supported engine)
- `DELETE /datasources/{ds_id}`: Delete a data source
- `GET /datasources/engines`: List all supported database engines (19 aliases, 8 types)

### Query Analysis
- `GET /analyze/{ds_id}/schema`: Get database schema (all DB types)
- `GET /analyze/{ds_id}/top`: Get top queries by execution time (DB-specific)
- `POST /analyze/{ds_id}/explain`: Get EXPLAIN plan (DB-specific format)
- `GET /analyze/{ds_id}/locks`: Get current database locks (DB-specific)
- `GET /analyze/{ds_id}/stats`: Get database statistics (DB-specific)
- `POST /analyze/{ds_id}/advise/index`: Get index recommendations (SQL databases)
- `POST /analyze/{ds_id}/advise/rewrite`: Get query rewrite suggestions (SQL databases)
- `POST /analyze/{ds_id}/advise/ai`: Get AI-powered suggestions (all DB types, 3 suggestions)
- `POST /analyze/{ds_id}/explain/ai`: Get AI explanation of EXPLAIN plan (all DB types)

### Optimization
- `POST /analyze/{ds_id}/optimize/database`: Get database-level AI optimizations
- `POST /analyze/{ds_id}/optimize/table/{table_name}`: Get table-level AI optimizations
- `POST /analyze/{ds_id}/optimize/apply`: Apply selected optimization SQL statements

## Database Connection Strings

**PostgreSQL**:
```
postgresql://user:password@host:5432/database
```

**MySQL/MariaDB**:
```
mysql://user:password@host:3306/database
```

**SQL Server**:
```
mssql://user:password@host:1433/database
```

**Oracle Database**:
```
oracle://user:password@host:1521/service_name
```

**MongoDB**:
```
mongodb://user:password@host:27017/database
```

**Redis**:
```
redis://host:6379/0
```

**SQLite**:
```
sqlite:///path/to/database.db
```

**Cassandra**:
```
cassandra://host:9042/keyspace
```

## Commands

### Run the application
```bash
# From repository root
python run.py
# Server runs on http://127.0.0.1:8000 with auto-reload
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### API Documentation
- Swagger UI: http://127.0.0.1:8000/docs
- Healthcheck: http://127.0.0.1:8000/healthz

## Key Dependencies

### Database Drivers
- **psycopg 3.2**: PostgreSQL adapter with dict_row support
- **pymysql**: MySQL/MariaDB driver
- **pyodbc**: SQL Server driver (requires ODBC Driver 17)
- **cx_Oracle**: Oracle Database driver (requires Oracle Instant Client)
- **pymongo**: MongoDB driver
- **redis**: Redis client (redis-py)
- **sqlite3**: SQLite (Python stdlib)
- **cassandra-driver**: Apache Cassandra driver

### Core Libraries
- **FastAPI 0.115**: Modern async web framework
- **sqlglot 25.6**: SQL parsing for predicate mining
- **httpx 0.27**: HTTP client for Ollama API calls
- **uvicorn**: ASGI server

## Database-Specific Requirements

### PostgreSQL
- **Recommended Extension**: `pg_stat_statements` for query performance statistics
- Falls back to `pg_stat_activity` if unavailable
- **Note**: `hypopg` not used on Windows (index suggestions still generated but not validated)

### SQL Server
- **Required**: ODBC Driver 17 for SQL Server
- **Permissions**: Access to DMVs (dm_exec_query_stats, dm_tran_locks)

### Oracle Database
- **Required**: Oracle Instant Client for cx_Oracle
- **Permissions**: Access to V$ views (V$SQL, V$LOCK) and ALL_ views

### NoSQL Databases
- **MongoDB**: No special requirements
- **Redis**: Slowlog should be enabled for query performance tracking
- **Cassandra**: No special requirements

## BaseAgent Interface

All database agents must implement these methods:

```python
class BaseAgent:
    def get_db_type(self) -> str:
        """Return database type identifier"""

    def _conn(self):
        """Create and return database connection"""

    def get_schema(self) -> Dict[str, Any]:
        """Get database schema (tables/collections and columns/fields)"""

    def get_top_queries(self, limit: int = 20, window_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get top queries by execution time"""

    def explain(self, sql: str, analyze: bool = False) -> Dict[str, Any]:
        """Get query execution plan"""

    def locks(self) -> List[Dict[str, Any]]:
        """Get current database locks"""

    def stats(self) -> Dict[str, Any]:
        """Get database statistics (size, connections)"""

    def get_existing_indexes(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get existing indexes"""

    def index_exists(self, table_name: str, columns: List[str]) -> bool:
        """Check if index already exists (prevents duplicates)"""

    def get_optimization_context(self) -> Dict[str, Any]:
        """Get database-specific optimization context for AI"""
```

## Index Validation System

To prevent duplicate index suggestions, the system implements 3-layer filtering:

1. **Advisor Layer** (`advisor.py`): Checks `agent.index_exists()` before creating suggestion
2. **AI Suggestion Filter**: Validates AI-generated index suggestions against existing indexes
3. **Deduplication Safety Net** (`super_agent.py`): Final check before returning suggestions

Each layer queries database system catalogs:
- PostgreSQL: `pg_class`, `pg_index`, `pg_attribute`
- MySQL: `INFORMATION_SCHEMA.STATISTICS`
- SQL Server: `sys.indexes`, `sys.index_columns`
- Oracle: `ALL_INDEXES`, `ALL_IND_COLUMNS`
- MongoDB: `index_information()`
- Cassandra: `system_schema.indexes`

Prefix matching: Index on (a,b,c) covers queries on (a,b)

## Adding New Database Engines

1. Create a new agent class inheriting from `BaseAgent` (e.g., `Neo4jAgent`)
2. Implement all required methods listed in BaseAgent interface
3. Add database driver to requirements.txt
4. Register in `registry.py:SUPPORTED_ENGINES` with engine name mappings
5. Update `datasources.py:/engines` endpoint with grouped database type
6. Add DSN format documentation
7. Test all endpoints with new database type

## AI Suggestion Flow

```
User SQL → Schema Sample (3 tables, 6 columns each)
    ↓
EXPLAIN Plan → Extract key metrics (Node Type, Cost, Rows, Filters)
    ↓
LLM Prompt → System prompt with DB type context
    ↓
Ollama API → JSON mode enabled, max_tokens=1500
    ↓
Parse JSON → Fallbacks: direct parse → markdown extraction → regex
    ↓
Validate → Check existing indexes, generate SQL fixes
    ↓
Return 3 suggestions → type: "index"|"rewrite"|"note"
```

## Optimization Endpoints

### Database-Level Optimization
`POST /analyze/{ds_id}/optimize/database`
- AI generates 2-3 database-level suggestions
- Examples: connection pooling, query cache, buffer pool size
- Returns suggestions with unique IDs and executable SQL

### Table-Level Optimization
`POST /analyze/{ds_id}/optimize/table/{table_name}`
- AI generates 2-4 CREATE INDEX statements for table
- Filters out indexes that already exist
- Returns suggestions with unique IDs and executable SQL

### Apply Optimizations
`POST /analyze/{ds_id}/optimize/apply`
- Request body: `{sql_statements: string[]}`
- Executes SQL statements in transaction
- Returns results with success/error status per statement

## Best Practices

1. **Always check `index_exists()`** before suggesting indexes
2. **Use database-specific system catalogs** for metadata queries
3. **Handle missing features gracefully** (e.g., Redis has no indexes, SQLite has no query stats)
4. **Normalize column names** (lowercase, strip) for comparison
5. **Log extensively** for debugging AI interactions
6. **Return unified format** across all database types
7. **Close connections properly** in finally blocks
8. **Use connection context managers** when available

## Testing

### Manual Testing Checklist per Database
- [ ] Register datasource with valid DSN
- [ ] Get schema (verify tables/collections returned)
- [ ] Get top queries (or empty list if not supported)
- [ ] Execute EXPLAIN plan
- [ ] Get locks (or empty list if not supported)
- [ ] Get statistics
- [ ] Get AI suggestions (verify 3 suggestions returned)
- [ ] Verify index validation prevents duplicates
- [ ] Test database/table optimization endpoints
- [ ] Test apply endpoint with valid SQL

### Error Handling
- Invalid DSN → Connection error with user-friendly message
- Missing driver → ImportError with installation instructions
- Permission denied → Log warning, return empty list
- Unsupported feature → Return empty list or default values

## Completed Features

- ✅ Multi-database support (8 database types, 19 engine aliases)
- ✅ AI-powered optimization for all database types
- ✅ Index validation to prevent duplicate suggestions (3-layer filtering)
- ✅ Database and table-level optimization endpoints
- ✅ Delete datasource functionality
- ✅ Batch apply optimizations endpoint
- ✅ Unified schema/stats/locks format across databases

## Future Enhancements

- Add automated testing suite for all database types
- Implement HypoPG support for Linux/macOS PostgreSQL
- Add query execution history
- Support additional databases (Elasticsearch, Neo4j, etc.)
- Add database migration suggestions
- Export optimization suggestions as SQL migration files
