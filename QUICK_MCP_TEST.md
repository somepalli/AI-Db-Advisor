# Quick MCP Test Guide

## ✅ Status: MCP is NOW RUNNING!

Both services are active:
- **MCP Bridge**: `http://localhost:3000` ✅
- **Main App**: `http://localhost:8000` ✅
- **MCP Integration**: ENABLED ✅

## Quick Test Commands

### 1. Check MCP Status
```bash
curl http://localhost:8000/mcp/health
```

**Expected output:**
```json
{
  "mcp_enabled": true,
  "status": "healthy",
  "credentials_valid": true
}
```

### 2. Register a Datasource
```bash
curl -X POST http://localhost:8000/datasources \
  -H "Content-Type: application/json" \
  -d "{\"id\":\"postgres-mcp-test\",\"engine\":\"postgres\",\"dsn\":\"postgresql://postgres:postgres@localhost:5432/UniversityDB\"}"
```

### 3. Request MCP Suggestions (Direct)
```bash
curl -X POST "http://localhost:8000/mcp/postgres-mcp-test/request-suggestions" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"SELECT * FROM students WHERE enrollment_year = 2020\",\"optimization_type\":\"performance\",\"max_suggestions\":3}"
```

###  4. Test via AI Chat (with MCP)
```bash
curl -X POST "http://localhost:8000/ai-chat/chat" \
  -H "Content-Type: application/json" \
  -d "{\"ds_id\":\"postgres-mcp-test\",\"message\":\"Optimize my query\",\"current_sql\":\"SELECT * FROM students WHERE enrollment_year = 2020 ORDER BY student_id\",\"save_to_history\":false}"
```

This will return BOTH:
- **AI Suggestions** (from Ollama)
- **MCP Suggestions** (from real MCP server) ✨

### 5. Check MCP Tools
```bash
curl http://localhost:3000/tools
```

### 6. Call MCP Tool Directly
```bash
curl -X POST "http://localhost:3000/tools/call" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"query\",\"arguments\":{\"sql\":\"SELECT COUNT(*) FROM students\"}}"
```

## What's Working Now?

✅ **Real MCP Integration** - Not demo mode!
✅ **PostgreSQL MCP Server** - Via npx @modelcontextprotocol/server-postgres
✅ **HTTP Bridge** - Translates HTTP ↔ MCP stdio protocol
✅ **MCP Orchestrator** - Manages suggestions with approval workflow
✅ **AI Chat Integration** - Combines Ollama + MCP suggestions
✅ **Safety Workflow** - All MCP suggestions require approval before execution

## Architecture

```
Your Request
    ↓
AI Chat Endpoint (port 8000)
    ├→ Ollama AI (generates AI suggestions)
    └→ MCP Client
        ↓ HTTP
    MCP Bridge (port 3000)
        ↓ stdio
    PostgreSQL MCP Server (npx)
        ↓ SQL
    UniversityDB Database
```

## Next Steps

1. **Test the endpoints** above to see MCP in action
2. **Approve MCP suggestions** via `/mcp/{ds_id}/approve/{approval_id}`
3. **Execute approved suggestions** via `/mcp/{ds_id}/execute/{approval_id}`
4. **View execution history** via `/mcp/{ds_id}/history`

## Key Files

- **MCP Bridge**: `mcp_http_bridge.py` (running on port 3000)
- **MCP Client**: `.venv/app/services/mcp_client.py`
- **MCP Orchestrator**: `.venv/app/services/mcp_orchestrator.py`
- **AI Chat Integration**: `.venv/app/routers/ai_chat.py` (line 517-557)
- **Configuration**: `.env` (MCP_ENABLED=true, MCP_ENDPOINT=http://localhost:3000)

## Logs

Watch real-time MCP activity in the terminal where you started `mcp_http_bridge.py`!

---

**Congratulations!** 🎉 You now have **real MCP** running with your AI DB Advisor!
