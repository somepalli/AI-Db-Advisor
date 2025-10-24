# Complete MCP Setup Guide

## What We've Built

I've created a **complete MCP integration** for your AI DB Advisor:

```
┌──────────────────────┐
│ AI DB Advisor        │  ← Your FastAPI app (port 8000)
│ (FastAPI)            │
└──────────┬───────────┘
           │ HTTP
           ▼
┌──────────────────────┐
│ MCP HTTP Bridge      │  ← NEW! Translates HTTP ↔ MCP (port 3000)
│ (mcp_http_bridge.py) │
└──────────┬───────────┘
           │ stdio
           ▼
┌──────────────────────┐
│ PostgreSQL MCP       │  ← Official Anthropic MCP server
│ Server (npx)         │
└──────────┬───────────┘
           │ SQL
           ▼
┌──────────────────────┐
│ PostgreSQL Database  │  ← Your UniversityDB
└──────────────────────┘
```

## Files Created

1. **`mcp_http_bridge.py`** - HTTP bridge to MCP servers
2. **`.env`** - Updated configuration
3. **Updated `services/mcp_client.py`** - Works with local bridge
4. **This guide** - Setup instructions

## Setup Steps

### Step 1: Start the MCP HTTP Bridge

Open a **new terminal** and run:

```bash
cd C:\Users\chowh\Desktop\ai-db-advisor
python mcp_http_bridge.py
```

This will:
- Start the HTTP bridge on `http://localhost:3000`
- Automatically start the PostgreSQL MCP server
- Connect to your `UniversityDB` database

**Expected output:**
```
================================================================================
MCP HTTP BRIDGE
================================================================================

This bridges HTTP requests to MCP stdio protocol

Endpoints:
  - GET  /health          - Health check
  - GET  /tools           - List available MCP tools
  - POST /tools/call      - Call an MCP tool
  - POST /query/optimize  - Optimize SQL query

Starting server on http://localhost:3000
================================================================================

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:services.mcp_client:Starting MCP server: npx -y @modelcontextprotocol/server-postgres postgresql://...
INFO:services.mcp_client:MCP server started
INFO:     Application startup complete.
```

### Step 2: Test the MCP Bridge

In **another terminal**, test the bridge:

```bash
# Test health
curl http://localhost:3000/health

# List available tools
curl http://localhost:3000/tools
```

**Expected response:**
```json
{
  "tools": [
    {
      "name": "query",
      "description": "Execute SQL queries on the database",
      "inputSchema": {...}
    },
    {
      "name": "describe_table",
      "description": "Get table schema information",
      "inputSchema": {...}
    }
  ]
}
```

### Step 3: Start Your FastAPI App

In **another terminal**, start your main app:

```bash
cd C:\Users\chowh\Desktop\ai-db-advisor
python run.py
```

Your app will now connect to the MCP bridge!

### Step 4: Test the Full Integration

Test the MCP integration through your app:

```bash
# Test MCP health through your app
curl http://localhost:8000/mcp/health

# Request MCP suggestions
curl -X POST http://localhost:8000/mcp/postgres-db/request-suggestions \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT * FROM students WHERE enrollment_year = 2020",
    "optimization_type": "performance",
    "max_suggestions": 3
  }'
```

## Configuration

Your `.env` file is already configured:

```env
MCP_ENABLED=true
MCP_API_KEY=  # Not needed for local bridge
MCP_ENDPOINT=http://localhost:3000
MCP_TIMEOUT=30
MCP_MAX_SUGGESTIONS=5
```

## Using MCP in Your App

### From AI Chat Endpoint

```bash
curl -X POST http://localhost:8000/ai-chat/chat \
  -H "Content-Type: application/json" \
  -d '{
    "ds_id": "postgres-db",
    "message": "Optimize my slow query",
    "current_sql": "SELECT * FROM students WHERE enrollment_year = 2020"
  }'
```

The AI chat will automatically:
1. Generate AI suggestions (Ollama)
2. Fetch MCP suggestions (real MCP server)
3. Combine both in the response

### From MCP Endpoints

```bash
# List pending approvals
curl http://localhost:8000/mcp/postgres-db/pending

# Approve a suggestion
curl -X POST http://localhost:8000/mcp/postgres-db/approve/{approval_id} \
  -H "Content-Type: application/json" \
  -d '{"notes": "Looks good!"}'

# Execute approved suggestion
curl -X POST http://localhost:8000/mcp/postgres-db/execute/{approval_id}
```

## Available MCP Tools

The PostgreSQL MCP server provides these tools:

1. **`query`** - Execute SQL queries
   ```json
   {
     "name": "query",
     "arguments": {
       "sql": "SELECT * FROM students LIMIT 5"
     }
   }
   ```

2. **`describe_table`** - Get table schema
   ```json
   {
     "name": "describe_table",
     "arguments": {
       "table_name": "students"
     }
   }
   ```

3. **`list_tables`** - List all tables
   ```json
   {
     "name": "list_tables",
     "arguments": {}
   }
   ```

## Customizing the Bridge

Edit `mcp_http_bridge.py` to:

### Change Database Connection

```python
# Line 75 - Update the connection string
mcp_command = [
    "npx", "-y",
    "@modelcontextprotocol/server-postgres",
    "postgresql://your_user:your_password@localhost:5432/your_database"
]
```

### Add More MCP Servers

You can run multiple MCP servers:

```python
# For MySQL
mcp_command = [
    "npx", "-y",
    "@modelcontextprotocol/server-mysql",
    "mysql://root:password@localhost:3306/mydb"
]

# For SQLite
mcp_command = [
    "npx", "-y",
    "@modelcontextprotocol/server-sqlite",
    "path/to/database.db"
]
```

## Troubleshooting

### Bridge won't start

**Error:** `npx: command not found`
- **Solution:** Install Node.js from https://nodejs.org/

**Error:** `Connection refused to PostgreSQL`
- **Solution:** Check PostgreSQL is running:
  ```bash
  # Windows
  sc query postgresql-x64-16

  # Start if not running
  net start postgresql-x64-16
  ```

### MCP tools not showing

**Check MCP bridge logs:**
```bash
# Should see:
INFO:services.mcp_client:MCP server started
INFO:services.mcp_client:Discovered 3 MCP tools
```

**Test MCP server directly:**
```bash
npx -y @modelcontextprotocol/server-postgres postgresql://postgres:postgres@localhost:5432/UniversityDB
```

### App can't connect to MCP bridge

**Error:** `Connection refused to localhost:3000`
- **Solution:** Make sure mcp_http_bridge.py is running

**Check MCP_ENDPOINT:**
```bash
# In .env file
MCP_ENDPOINT=http://localhost:3000
```

## Production Deployment

For production:

1. **Run as systemd service (Linux)** or **Windows Service**
2. **Add authentication** to the bridge
3. **Use reverse proxy** (nginx) for SSL
4. **Monitor with logging** (add more detailed logs)
5. **Add rate limiting** to prevent abuse

## Next Steps

Now that MCP is set up:

✅ **Real MCP suggestions** from PostgreSQL MCP server
✅ **HTTP bridge** translates between your app and MCP
✅ **Safety workflow** with approval/rejection
✅ **Combined AI + MCP** suggestions

You can:
- Add more MCP servers for other databases
- Create custom MCP tools for specific optimizations
- Integrate with other MCP servers (GitHub, Slack, etc.)

---

**Need help?** Check:
- MCP Documentation: https://modelcontextprotocol.io/
- PostgreSQL MCP Server: https://github.com/modelcontextprotocol/servers
- Your logs in both terminals

