"""
MCP HTTP Bridge - Converts HTTP requests to MCP stdio protocol

This bridges the gap between your HTTP-based FastAPI app and MCP servers
that use stdio (standard input/output) communication.
"""
import asyncio
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import subprocess
import sys
from contextlib import asynccontextmanager
from prometheus_client import Counter, Histogram, Gauge, REGISTRY, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
mcp_requests_total = Counter(
    'mcp_requests_total',
    'Total number of MCP requests',
    ['method', 'status']
)
mcp_request_duration = Histogram(
    'mcp_request_duration_seconds',
    'MCP request duration in seconds',
    ['method']
)
mcp_tools_discovered = Gauge(
    'mcp_tools_discovered',
    'Number of MCP tools discovered'
)
mcp_server_status = Gauge(
    'mcp_server_status',
    'MCP server status (1=running, 0=stopped)'
)


class MCPRequest(BaseModel):
    """Request to MCP server"""
    method: str  # "tools/list", "tools/call"
    params: Dict[str, Any] = {}


class MCPResponse(BaseModel):
    """Response from MCP server"""
    result: Any
    error: Optional[str] = None


class MCPBridge:
    """Bridge between HTTP and MCP stdio protocol"""

    def __init__(self, mcp_command: List[str]):
        """
        Initialize MCP bridge

        Args:
            mcp_command: Command to start MCP server
                Example: ["npx", "-y", "@modelcontextprotocol/server-postgres", "postgresql://..."]
        """
        self.mcp_command = mcp_command
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0

    async def start(self):
        """Start MCP server subprocess"""
        logger.info(f"Starting MCP server: {' '.join(self.mcp_command)}")

        self.process = subprocess.Popen(
            self.mcp_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        logger.info("MCP server started")

    async def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send JSON-RPC request to MCP server

        Args:
            method: MCP method (e.g., "tools/list", "tools/call")
            params: Method parameters

        Returns:
            Response from MCP server
        """
        if not self.process:
            raise RuntimeError("MCP server not started")

        self.request_id += 1

        # Build JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        logger.info(f"Sending to MCP: {json.dumps(request)}")

        # Send to MCP server
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

        # Read response
        response_line = self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("MCP server closed connection")

        logger.info(f"Received from MCP: {response_line.strip()}")

        response = json.loads(response_line)

        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")

        return response.get("result", {})

    async def stop(self):
        """Stop MCP server"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            logger.info("MCP server stopped")


# Global bridge instance
bridge: Optional[MCPBridge] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown"""
    global bridge

    # Startup
    logger.info("Starting MCP HTTP Bridge...")

    # Configuration - update with your database connection
    import shutil
    npx_path = shutil.which("npx") or "C:\\Program Files\\nodejs\\npx.cmd"

    mcp_command = [
        npx_path, "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://postgres:postgres@localhost:5432/UniversityDB"
    ]

    bridge = MCPBridge(mcp_command)
    await bridge.start()

    # Update metrics
    mcp_server_status.set(1)

    logger.info("MCP HTTP Bridge started")

    yield

    # Shutdown
    if bridge:
        await bridge.stop()
        mcp_server_status.set(0)
        logger.info("MCP HTTP Bridge stopped")


app = FastAPI(title="MCP HTTP Bridge", lifespan=lifespan)

# Initialize Prometheus instrumentation
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=False,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics"],
)
instrumentator.instrument(app)


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Expose Prometheus metrics"""
    return generate_latest(REGISTRY)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mcp_running": bridge is not None and bridge.process is not None
    }


@app.get("/tools")
async def list_tools():
    """List available MCP tools"""
    import time
    start_time = time.time()

    try:
        result = await bridge.send_request("tools/list")
        tools = result.get("tools", [])

        # Update metrics
        mcp_tools_discovered.set(len(tools))
        mcp_requests_total.labels(method="tools/list", status="success").inc()
        mcp_request_duration.labels(method="tools/list").observe(time.time() - start_time)

        return {"tools": tools}
    except Exception as e:
        mcp_requests_total.labels(method="tools/list", status="error").inc()
        mcp_request_duration.labels(method="tools/list").observe(time.time() - start_time)
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(500, f"Failed to list tools: {str(e)}")


@app.post("/tools/call")
async def call_tool(request: Dict[str, Any]):
    """
    Call an MCP tool

    Body:
    {
        "name": "tool_name",
        "arguments": {...}
    }
    """
    import time
    start_time = time.time()

    try:
        tool_name = request.get("name")
        arguments = request.get("arguments", {})

        result = await bridge.send_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments
            }
        )

        # Update metrics
        mcp_requests_total.labels(method="tools/call", status="success").inc()
        mcp_request_duration.labels(method="tools/call").observe(time.time() - start_time)

        return {"result": result}

    except Exception as e:
        mcp_requests_total.labels(method="tools/call", status="error").inc()
        mcp_request_duration.labels(method="tools/call").observe(time.time() - start_time)
        logger.error(f"Failed to call tool: {e}")
        raise HTTPException(500, f"Failed to call tool: {str(e)}")


@app.post("/query/optimize")
async def optimize_query(body: Dict[str, Any]):
    """
    Optimize SQL query using MCP tools

    Body:
    {
        "query": "SELECT * FROM students WHERE ...",
        "database": "UniversityDB"
    }
    """
    import time
    start_time = time.time()

    try:
        query = body.get("query")
        database = body.get("database", "default")

        # Call MCP tool to analyze query
        result = await bridge.send_request(
            "tools/call",
            {
                "name": "query",
                "arguments": {
                    "sql": query
                }
            }
        )

        # Update metrics
        mcp_requests_total.labels(method="query/optimize", status="success").inc()
        mcp_request_duration.labels(method="query/optimize").observe(time.time() - start_time)

        return {
            "original_query": query,
            "analysis": result,
            "suggestions": [
                {
                    "type": "mcp_suggestion",
                    "summary": "MCP-powered query analysis",
                    "details": result
                }
            ]
        }

    except Exception as e:
        mcp_requests_total.labels(method="query/optimize", status="error").inc()
        mcp_request_duration.labels(method="query/optimize").observe(time.time() - start_time)
        logger.error(f"Failed to optimize query: {e}")
        raise HTTPException(500, f"Failed to optimize query: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*80)
    print("MCP HTTP BRIDGE")
    print("="*80)
    print("\nThis bridges HTTP requests to MCP stdio protocol")
    print("\nEndpoints:")
    print("  - GET  /health          - Health check")
    print("  - GET  /tools           - List available MCP tools")
    print("  - POST /tools/call      - Call an MCP tool")
    print("  - POST /query/optimize  - Optimize SQL query")
    print("\nStarting server on http://localhost:3000")
    print("="*80 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=3000)
