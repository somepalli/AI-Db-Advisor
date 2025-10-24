# Postgres-MCP Integration Guide

This guide explains how to integrate postgres-mcp with AI DB Advisor for enhanced PostgreSQL database insights and AI-powered query assistance.

## Overview

**postgres-mcp** is a Model Context Protocol (MCP) server that provides direct database access tools to AI assistants. When integrated with AI DB Advisor, it enables:

- **Real-time database queries** via AI chat
- **Schema exploration** through natural language
- **Table structure analysis** with AI assistance
- **Performance insights** directly from the database
- **Safe, read-only queries** executed through MCP

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│          AI DB Advisor Frontend (Tauri/React)           │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP
                      ▼
┌─────────────────────────────────────────────────────────┐
│         FastAPI Backend (port 8000)                      │
│  ┌────────────────────────────────────────────────┐    │
│  │  AI Chat Router (/ai-chat/chat)                │    │
│  │  - Generates SQL from natural language         │    │
│  │  - Fetches MCP suggestions                     │    │
│  │  - Merges AI + MCP recommendations             │    │
│  └────────────────┬───────────────────────────────┘    │
└───────────────────┼───────────────────────────────────┘
                    │ HTTP
                    ▼
┌─────────────────────────────────────────────────────────┐
│         MCP Bridge Server (port 3000)                    │
│  - Wraps postgres-mcp (stdio) as HTTP endpoints         │
│  - Provides: /tools (list), /tools/call (execute)       │
│  - JSON-RPC 2.0 protocol adapter                        │
└────────────────────┬────────────────────────────────────┘
                     │ stdio (JSON-RPC)
                     ▼
┌─────────────────────────────────────────────────────────┐
│         postgres-mcp (MCP Server)                        │
│  - Executes SQL queries (read-only)                     │
│  - Lists tables and describes schema                    │
│  - Provides query insights                              │
└────────────────────┬────────────────────────────────────┘
                     │ PostgreSQL protocol
                     ▼
┌─────────────────────────────────────────────────────────┐
│            PostgreSQL Database                           │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Node.js & npm/npx** (for running postgres-mcp)
   ```bash
   node --version  # Should be v18 or higher
   npx --version
   ```

2. **Python 3.10+** with FastAPI
   ```bash
   python --version
   pip install -r requirements.txt
   ```

3. **PostgreSQL database** accessible from your machine
   - Can be local or remote
   - Need connection string (DSN)

4. **Ollama with LLM model** (for AI chat)
   ```bash
   ollama pull qwen2.5:7b-instruct
   ```

## Installation & Setup

### Step 1: Configure PostgreSQL Connection

Edit `.env` file in the project root and set your PostgreSQL DSN:

```env
# Postgres MCP Configuration
POSTGRES_DSN=postgresql://user:password@host:port/database

# Example for UniversityDB
POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/UniversityDB
```

**Connection String Format:**
```
postgresql://[user]:[password]@[host]:[port]/[database]
```

### Step 2: Enable MCP Integration

Ensure MCP is enabled in `.env`:

```env
# MCP Configuration
MCP_ENABLED=true
MCP_ENDPOINT=http://localhost:3000
MCP_MAX_SUGGESTIONS=5
```

### Step 3: Start Services

**Option A: Start both services with one command (Windows)**
```bash
start_with_mcp.bat
```

This will open two windows:
1. MCP Bridge Server (port 3000)
2. AI DB Advisor API (port 8000)

**Option B: Start services manually**

Terminal 1 - MCP Bridge:
```bash
# Windows
start_mcp_bridge.bat

# Or directly with Python
python mcp_bridge_server.py
```

Terminal 2 - Main API:
```bash
python run.py
```

### Step 4: Verify Integration

**Check MCP Bridge Health:**
```bash
curl http://localhost:3000/health
```

Expected response:
```json
{
  "status": "healthy",
  "mcp_enabled": true,
  "postgres_dsn_configured": true
}
```

**List Available MCP Tools:**
```bash
curl http://localhost:3000/tools
```

Expected response:
```json
{
  "tools": [
    {
      "name": "query",
      "description": "Execute a read-only SQL query",
      "inputSchema": { ... }
    },
    {
      "name": "list_tables",
      "description": "List all tables in the database",
      "inputSchema": { ... }
    },
    {
      "name": "describe_table",
      "description": "Get detailed schema for a table",
      "inputSchema": { ... }
    }
  ]
}
```

**Test AI Chat with MCP:**
```bash
curl -X POST http://localhost:8000/ai-chat/chat \
  -H "Content-Type: application/json" \
  -d '{
    "ds_id": "postgres-db",
    "message": "Show me all tables in the database",
    "save_to_history": false
  }'
```

## Using postgres-mcp in AI Chat

Once integrated, the AI chat will automatically use postgres-mcp for PostgreSQL queries:

### Example 1: Schema Exploration
```
User: What tables are in my database?

AI: [Uses postgres-mcp list_tables tool]
The database contains the following tables:
- students (12,000 rows)
- courses (150 rows)
- enrollments (15,000 rows)
- professors (500 rows)
...
```

### Example 2: Natural Language Query
```
User: Show me students enrolled in 2020

AI: [Uses postgres-mcp query tool]
Here's the SQL query and results:

SELECT * FROM students WHERE enrollment_year = 2020 LIMIT 10;

Found 2,500 students enrolled in 2020.

Suggestions:
1. [MCP] Add index on enrollment_year for faster queries
2. [AI] Consider adding WHERE conditions to limit results
```

### Example 3: Table Structure Analysis
```
User: What's the structure of the enrollments table?

AI: [Uses postgres-mcp describe_table tool]
The enrollments table has the following columns:
- enrollment_id (INTEGER, PRIMARY KEY)
- student_id (INTEGER, FOREIGN KEY → students)
- course_id (INTEGER, FOREIGN KEY → courses)
- semester (VARCHAR)
- grade (VARCHAR)
...
```

## MCP Tools Available

### 1. `query` - Execute SQL (read-only)
**Purpose:** Execute SELECT queries on the database

**Example:**
```json
POST /tools/call
{
  "name": "query",
  "arguments": {
    "sql": "SELECT * FROM students LIMIT 10"
  }
}
```

**Safety:** Only SELECT queries are allowed. DDL/DML statements are blocked.

### 2. `list_tables` - List All Tables
**Purpose:** Get a list of all tables in the database

**Example:**
```json
POST /tools/call
{
  "name": "list_tables",
  "arguments": {}
}
```

### 3. `describe_table` - Get Table Schema
**Purpose:** Get detailed column information for a specific table

**Example:**
```json
POST /tools/call
{
  "name": "describe_table",
  "arguments": {
    "table_name": "students"
  }
}
```

### 4. `append_insights` - Query Performance Insights
**Purpose:** Get AI-generated performance insights for a query

**Example:**
```json
POST /tools/call
{
  "name": "append_insights",
  "arguments": {
    "query": "SELECT * FROM students WHERE enrollment_year = 2020",
    "insights_type": "performance"
  }
}
```

## How AI Chat Uses MCP

When you send a message to `/ai-chat/chat`, here's what happens:

1. **User Message Processing**
   - AI analyzes your natural language request
   - Generates appropriate SQL query
   - Identifies relevant database objects

2. **MCP Tool Selection**
   - If query needs execution → use `query` tool
   - If schema info needed → use `list_tables` or `describe_table`
   - If performance insights needed → use `append_insights`

3. **MCP Suggestion Generation**
   - MCP bridge calls postgres-mcp via JSON-RPC
   - postgres-mcp executes tool and returns results
   - Results are formatted as "MCP suggestions"

4. **Response Merging**
   - AI-generated suggestions (from Ollama)
   - MCP-generated suggestions (from postgres-mcp)
   - Combined into single response with `is_mcp: true` flag

5. **Display to User**
   - SQL query shown
   - Results displayed
   - Suggestions listed (both AI and MCP)
   - Performance recommendations

## Configuration Reference

### Environment Variables

```env
# Enable MCP
MCP_ENABLED=true                          # Enable/disable MCP integration
MCP_ENDPOINT=http://localhost:3000       # MCP bridge server URL
MCP_TIMEOUT=30                            # Request timeout (seconds)
MCP_MAX_SUGGESTIONS=5                     # Max suggestions per request

# Postgres-MCP
POSTGRES_DSN=postgresql://...             # PostgreSQL connection string
MCP_BRIDGE_PORT=3000                      # Bridge server port

# Safety (DO NOT CHANGE)
MCP_AUTO_EXECUTE=false                    # Never auto-execute
MCP_REQUIRE_APPROVAL=true                 # Always require approval
```

### Security Notes

1. **Read-Only Access:** postgres-mcp only executes SELECT queries by default
2. **No Auto-Execution:** All suggestions require user approval before execution
3. **Connection Security:** Use SSL connection strings in production
4. **Credential Protection:** Never commit `.env` files with real credentials

## Troubleshooting

### Issue: "MCP process not available"

**Cause:** MCP bridge server not running or POSTGRES_DSN not set

**Solution:**
1. Check if MCP bridge is running: `curl http://localhost:3000/health`
2. Verify POSTGRES_DSN in `.env`
3. Restart MCP bridge: `python mcp_bridge_server.py`

### Issue: "Connection refused" to PostgreSQL

**Cause:** Database not accessible or incorrect DSN

**Solution:**
1. Test connection manually:
   ```bash
   psql "postgresql://user:password@host:port/database"
   ```
2. Check firewall/network settings
3. Verify credentials

### Issue: "No MCP suggestions returned"

**Cause:** MCP integration working but no relevant tools found

**Solution:**
1. Check MCP bridge logs for errors
2. Verify tools are listed: `curl http://localhost:3000/tools`
3. Ensure query/message is database-related

### Issue: "npx command not found"

**Cause:** Node.js not installed or not in PATH

**Solution:**
1. Install Node.js from https://nodejs.org (v18+)
2. Verify installation: `npx --version`
3. Restart terminal/command prompt

## Demo Mode

If POSTGRES_DSN is not configured, the system runs in **demo mode**:

- MCP bridge server starts but without postgres-mcp
- AI chat returns 3 demo MCP suggestions
- No actual database queries executed
- Useful for testing UI without database

To exit demo mode, set POSTGRES_DSN in `.env` and restart services.

## Advanced Configuration

### Using Different PostgreSQL Accounts

Create a read-only user for added security:

```sql
-- Create read-only user
CREATE USER mcp_readonly WITH PASSWORD 'secure_password';

-- Grant schema access
GRANT USAGE ON SCHEMA public TO mcp_readonly;

-- Grant SELECT on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;

-- Grant SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO mcp_readonly;
```

Then use this DSN:
```env
POSTGRES_DSN=postgresql://mcp_readonly:secure_password@localhost:5432/UniversityDB
```

### Custom MCP Bridge Port

Change the bridge server port:

```env
MCP_BRIDGE_PORT=4000
MCP_ENDPOINT=http://localhost:4000
```

### Multiple Database Support

Currently, the MCP bridge connects to one PostgreSQL database (POSTGRES_DSN). To support multiple databases:

1. Start multiple MCP bridge instances on different ports
2. Configure each with different POSTGRES_DSN
3. Update MCP_ENDPOINT per datasource in the application

(Future enhancement: dynamic MCP bridge instances per datasource)

## Performance Considerations

1. **Connection Pooling:** postgres-mcp maintains a single connection to PostgreSQL
2. **Query Timeout:** Set `MCP_TIMEOUT` appropriately (default: 30s)
3. **Result Limits:** Limit results with LIMIT clause for large tables
4. **Concurrent Requests:** MCP bridge handles multiple requests sequentially

## Integration with Existing Features

### AI Chat Enhancement
- AI chat automatically includes MCP suggestions
- MCP suggestions marked with `is_mcp: true`
- Both AI and MCP suggestions shown side-by-side

### Query Validation
- MCP can validate queries before execution
- Suggests corrections for syntax errors
- Checks for missing tables/columns

### Performance Analysis
- MCP provides real-time database insights
- Complements EXPLAIN plan analysis
- Suggests indexes based on actual data

## FAQ

**Q: Do I need to install postgres-mcp separately?**
A: No, the MCP bridge server uses `npx -y @modelcontextprotocol/server-postgres`, which auto-installs it.

**Q: Can I use postgres-mcp with other databases?**
A: postgres-mcp is PostgreSQL-specific. For other databases, use appropriate MCP servers or the built-in database agents.

**Q: Is MCP required for AI DB Advisor to work?**
A: No, MCP is optional. AI DB Advisor works fully without it, using Ollama LLM and rule-based advisors.

**Q: Can MCP execute INSERT/UPDATE/DELETE queries?**
A: By default, postgres-mcp only executes read-only (SELECT) queries. This is a safety feature.

**Q: How do I disable MCP temporarily?**
A: Set `MCP_ENABLED=false` in `.env` and restart the API server.

## Support & Resources

- **AI DB Advisor Docs:** See `CLAUDE.md` in project root
- **postgres-mcp:** https://github.com/modelcontextprotocol/servers/tree/main/src/postgres
- **MCP Protocol:** https://modelcontextprotocol.io
- **FastAPI Docs:** http://localhost:8000/docs (when running)

## Next Steps

1. ✅ Configure POSTGRES_DSN in `.env`
2. ✅ Start MCP bridge server
3. ✅ Start AI DB Advisor API
4. ✅ Test AI chat with database queries
5. 🚀 Explore MCP-powered suggestions
6. 🚀 Optimize your database with AI + MCP insights

Happy database optimization! 🎉
