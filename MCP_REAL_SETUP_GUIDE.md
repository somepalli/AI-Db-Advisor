# Setting Up Real MCP (Model Context Protocol) for Database Optimization

## What is MCP?

**Model Context Protocol (MCP)** is an **open-source standard by Anthropic** (not Google!) that enables AI assistants to connect with external tools and data sources.

- **Not a Google service** - it's from Anthropic (makers of Claude)
- **Open source** - you can run your own MCP servers
- **Protocol, not API** - requires setting up an MCP server

## Architecture Overview

```
┌─────────────────────┐
│  AI DB Advisor      │ ← Your FastAPI app (MCP Client)
│  (MCP Client)       │
└──────────┬──────────┘
           │ MCP Protocol (HTTP/SSE)
           ▼
┌─────────────────────┐
│  MCP Server         │ ← Needs to be set up
│  (Database Tools)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Your Databases     │
│  (PostgreSQL, etc)  │
└─────────────────────┘
```

## Option 1: Use Existing MCP Database Servers (Recommended)

Several open-source MCP servers already exist for databases:

### A. PostgreSQL MCP Server

**GitHub:** https://github.com/modelcontextprotocol/servers/tree/main/src/postgres

```bash
# Install using npx (Node.js required)
npx -y @modelcontextprotocol/server-postgres postgresql://user:password@localhost/dbname
```

### B. Multi-Database MCP Server

**GitHub:** https://github.com/executeautomation/mcp-database-server

Supports: SQLite, SQL Server, PostgreSQL

```bash
# Install
git clone https://github.com/executeautomation/mcp-database-server
cd mcp-database-server
npm install

# Run
npm start
```

### C. Microsoft SQL Server MCP Server

**GitHub:** https://github.com/dperussina/mssql-mcp-server

```bash
npm install -g mssql-mcp-server
mssql-mcp-server --connection "Server=localhost;Database=mydb;User Id=sa;Password=pass"
```

## Option 2: Google's MCP Toolbox for Databases (NEW!)

Google recently released an **MCP Toolbox for Databases**:

**Documentation:** https://googleapis.github.io/genai-toolbox/getting-started/introduction/

This is likely what you're looking for! It's an open-source MCP server that provides:
- Connection pooling
- Authentication
- Query optimization tools
- Support for multiple databases

### Installation:

```bash
# Install the toolbox
pip install google-genai-toolbox

# Run the MCP server
genai-toolbox serve --database-url postgresql://user:password@localhost/dbname
```

**This runs a local MCP server** that your app can connect to!

## Option 3: Build Your Own MCP Server (Custom)

If you want full control, you can build a custom MCP server:

**Python SDK:** https://github.com/modelcontextprotocol/python-sdk

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

app = Server("database-optimizer")

@app.list_tools()
async def list_tools():
    return [
        {
            "name": "optimize_query",
            "description": "Optimize a SQL query",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        }
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "optimize_query":
        # Your optimization logic here
        return {"optimized": "SELECT ...", "explanation": "..."}

# Run server
async def main():
    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())
```

## Recommended Setup for Your Project

Based on your requirements, here's what I recommend:

### Step 1: Install Google's MCP Toolbox (BEST OPTION)

```bash
# Install
pip install google-genai-toolbox

# This will give you a local MCP server with database tools
```

### Step 2: Configure the MCP Server

Create `mcp_server_config.json`:

```json
{
  "databases": {
    "postgres": {
      "type": "postgresql",
      "connection": "postgresql://postgres:postgres@localhost:5432/UniversityDB"
    },
    "mysql": {
      "type": "mysql",
      "connection": "mysql://root:password@localhost:3306/mydb"
    }
  },
  "tools": [
    "query_optimizer",
    "index_analyzer",
    "explain_plan"
  ],
  "port": 3000
}
```

### Step 3: Start the MCP Server

```bash
# Start the server
genai-toolbox serve --config mcp_server_config.json

# Server will run on http://localhost:3000
```

### Step 4: Update Your App Configuration

Update `.env`:

```env
# MCP Configuration
MCP_ENABLED=true
MCP_ENDPOINT=http://localhost:3000
MCP_API_KEY=  # Leave empty for local server
MCP_TIMEOUT=30
```

### Step 5: I'll Update the Code

I'll modify the MCP client to work with the local MCP server instead of expecting a Google API.

## Quick Start (Right Now)

Let me check if you have Node.js installed and set up a simple MCP server:

```bash
# Check Node.js
node --version

# If installed, we can use the official PostgreSQL MCP server
npx -y @modelcontextprotocol/server-postgres postgresql://postgres:postgres@localhost:5432/UniversityDB
```

---

## Which Option Do You Want?

**Option A (Recommended):** Use Google's MCP Toolbox
- ✅ Production-ready
- ✅ Multiple database support
- ✅ Built-in optimization tools
- ⚠️ Requires Python package installation

**Option B:** Use Official PostgreSQL MCP Server
- ✅ Simple setup
- ✅ Official Anthropic implementation
- ⚠️ PostgreSQL only
- ⚠️ Requires Node.js

**Option C:** Build Custom MCP Server
- ✅ Full control
- ✅ Custom tools
- ⚠️ More development work

Let me know which option you prefer, and I'll help you set it up!

