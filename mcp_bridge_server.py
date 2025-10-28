"""
MCP Bridge Server - HTTP wrapper for MCP servers (stdio to HTTP)

This bridge server wraps MCP servers that communicate via stdio (Toolbox in --stdio mode)
and exposes them as HTTP endpoints for easy consumption by the AI DB Advisor.

Environment variables:
    TOOLBOX_MODE=docker|binary (default: docker)
    TOOLBOX_TOOLS_FILE=path/to/tools.yaml
    TOOLBOX_IMAGE=us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:VERSION
    TOOLBOX_CLICKHOUSE_* overrides for Toolbox source credentials
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from local env files
logger_init = logging.getLogger(__name__)

base_env_path = Path(__file__).parent / ".env"
if base_env_path.exists():
    load_dotenv(dotenv_path=base_env_path)
    logger_init.info(f"Loaded environment from {base_env_path}")

clickhouse_env_path = Path(__file__).parent / ".env.clickhouse"
if clickhouse_env_path.exists():
    load_dotenv(dotenv_path=clickhouse_env_path, override=False)
    logger_init.info(f"Loaded ClickHouse environment from {clickhouse_env_path}")

toolbox_env_path = Path(__file__).parent / ".env.toolbox"
if toolbox_env_path.exists():
    load_dotenv(dotenv_path=toolbox_env_path, override=False)
    logger_init.info(f"Loaded Toolbox environment from {toolbox_env_path}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ToolCallRequest(BaseModel):
    """Request to call an MCP tool"""
    name: str
    arguments: Dict[str, Any] = {}


class ToolCallResponse(BaseModel):
    """Response from MCP tool call"""
    result: Dict[str, Any]
    error: Optional[str] = None


class MCPProcess:
    """Manages an MCP server process via stdio"""

    def __init__(self, command: List[str], env: Optional[Dict[str, str]] = None):
        """
        Initialize MCP process.

        Args:
            command: Command to start MCP server (e.g., ["npx", "-y", "@modelcontextprotocol/server-postgres"])
            env: Environment variables for the process
        """
        self.command = command
        self.env = {**os.environ, **(env or {})}
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0

    async def start(self):
        """Start the MCP server process"""
        try:
            logger.info(f"Starting MCP process: {' '.join(self.command)}")

            # On Windows, we need to use shell=True or specify the full path to npx.cmd
            # Using shell=True is simpler and works across platforms
            import platform
            if platform.system() == "Windows":
                # Windows: use shell to find npx in PATH
                command_str = " ".join(self.command)
                self.process = await asyncio.create_subprocess_shell(
                    command_str,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=self.env
                )
            else:
                # Unix-like: use exec directly
                self.process = await asyncio.create_subprocess_exec(
                    *self.command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=self.env
                )

            logger.info(f"MCP process started with PID: {self.process.pid}")

            # Initialize the MCP session
            await self._send_initialize()

        except Exception as e:
            logger.error(f"Failed to start MCP process: {e}")
            raise

    async def _send_initialize(self):
        """Send initialize request to MCP server"""
        init_request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "ai-db-advisor",
                    "version": "1.0.0"
                }
            }
        }

        response = await self._send_request(init_request)
        logger.info(f"MCP initialized: {response}")

        # Send initialized notification
        initialized_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        await self._write_message(initialized_notif)

    def _next_id(self) -> int:
        """Get next request ID"""
        self.request_id += 1
        return self.request_id

    async def _write_message(self, message: Dict[str, Any]):
        """Write JSON-RPC message to MCP server"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP process not started")

        message_bytes = (json.dumps(message) + "\n").encode("utf-8")
        self.process.stdin.write(message_bytes)
        await self.process.stdin.drain()
        logger.debug(f"Sent to MCP: {message}")

    async def _read_message(self) -> Dict[str, Any]:
        """Read JSON-RPC message from MCP server"""
        if not self.process or not self.process.stdout:
            raise RuntimeError("MCP process not started")

        line = await self.process.stdout.readline()
        if not line:
            raise RuntimeError("MCP process closed stdout")

        message = json.loads(line.decode("utf-8"))
        logger.debug(f"Received from MCP: {message}")
        return message

    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request and wait for response"""
        await self._write_message(request)

        # Read response (skip notifications)
        while True:
            response = await self._read_message()

            # Check if it's a notification (no id field)
            if "id" not in response:
                logger.debug(f"Received notification: {response.get('method')}")
                continue

            # Check if it matches our request
            if response.get("id") == request.get("id"):
                if "error" in response:
                    raise Exception(f"MCP error: {response['error']}")
                return response.get("result", {})

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP server"""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list"
        }

        result = await self._send_request(request)
        return result.get("tools", [])

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool.

        Args:
            tool_name: Name of the tool (e.g., "query", "list_tables")
            arguments: Tool arguments

        Returns:
            Tool result
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        result = await self._send_request(request)
        return result

    async def stop(self):
        """Stop the MCP server process"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            logger.info("MCP process stopped")


# Global MCP process instance
mcp_process: Optional[MCPProcess] = None
ACTIVE_TOOLS_FILE: Optional[str] = None
ACTIVE_TOOLBOX_MODE: Optional[str] = None


def build_toolbox_command() -> Tuple[List[str], Dict[str, str]]:
    """
    Build the command used to launch the Toolbox MCP server.

    Returns:
        Tuple of (command list, environment overrides)
    """
    global ACTIVE_TOOLS_FILE, ACTIVE_TOOLBOX_MODE

    tools_file_env = os.getenv("TOOLBOX_TOOLS_FILE")
    if tools_file_env:
        tools_path = Path(tools_file_env)
        if not tools_path.is_absolute():
            tools_path = (Path(__file__).parent / tools_path).resolve()
    else:
        tools_path = (Path(__file__).parent / "toolbox" / "tools.yaml").resolve()

    if not tools_path.exists():
        raise FileNotFoundError(f"Toolbox configuration not found at {tools_path}")

    ACTIVE_TOOLS_FILE = str(tools_path)
    toolbox_mode = os.getenv("TOOLBOX_MODE", "docker").lower()
    ACTIVE_TOOLBOX_MODE = toolbox_mode

    toolbox_image = os.getenv(
        "TOOLBOX_IMAGE",
        os.getenv("TOOLBOX_DOCKER_IMAGE", "us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:0.11.0"),
    )
    container_tools_path = os.getenv("TOOLBOX_CONTAINER_TOOLS_PATH", "/app/tools.yaml")

    clickhouse_host = os.getenv("TOOLBOX_CLICKHOUSE_HOST", os.getenv("CLICKHOUSE_HOST", "host.docker.internal"))
    clickhouse_port = os.getenv("TOOLBOX_CLICKHOUSE_PORT", os.getenv("CLICKHOUSE_PORT", "8123"))
    clickhouse_protocol = os.getenv("TOOLBOX_CLICKHOUSE_PROTOCOL", os.getenv("CLICKHOUSE_PROTOCOL", "http"))
    clickhouse_db = os.getenv("TOOLBOX_CLICKHOUSE_DATABASE", os.getenv("CLICKHOUSE_DATABASE", "ai_db_advisor"))
    clickhouse_user = os.getenv("TOOLBOX_CLICKHOUSE_USER", "toolbox_reader")
    clickhouse_password = os.getenv("TOOLBOX_CLICKHOUSE_PASSWORD", "ToolboxReader#2025")
    toolbox_api_key = os.getenv("TOOLBOX_API_KEY", "toolbox-local-key")

    toolbox_env = {
        "CLICKHOUSE_HOST": clickhouse_host,
        "CLICKHOUSE_PORT": str(clickhouse_port),
        "CLICKHOUSE_PROTOCOL": clickhouse_protocol,
        "CLICKHOUSE_DATABASE": clickhouse_db,
        "CLICKHOUSE_USER": clickhouse_user,
        "CLICKHOUSE_PASSWORD": clickhouse_password,
        "TOOLBOX_API_KEY": toolbox_api_key,
    }

    if toolbox_mode == "binary":
        toolbox_binary = os.getenv("TOOLBOX_BINARY") or shutil.which("toolbox")
        if not toolbox_binary:
            raise RuntimeError(
                "Toolbox binary not found. Set TOOLBOX_BINARY or install the toolbox CLI to use binary mode."
            )

        command = [
            toolbox_binary,
            "--stdio",
            f"--tools-file={ACTIVE_TOOLS_FILE}",
            "--log-level=INFO",
            "--disable-reload",
        ]
        env_overrides = toolbox_env
    else:
        command: List[str] = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--add-host=host.docker.internal:host-gateway",
            "-v",
            f"{ACTIVE_TOOLS_FILE}:{container_tools_path}:ro",
        ]

        custom_network = os.getenv("TOOLBOX_DOCKER_NETWORK")
        if custom_network:
            command.extend(["--network", custom_network])

        additional_args = os.getenv("TOOLBOX_DOCKER_ARGS")
        if additional_args:
            command.extend(additional_args.split())

        for key, value in toolbox_env.items():
            command.extend(["-e", f"{key}={value}"])

        command.append(toolbox_image)
        command.extend(
            [
                "--stdio",
                f"--tools-file={container_tools_path}",
                "--log-level=INFO",
                "--disable-reload",
            ]
        )
        env_overrides = {}

    return command, env_overrides


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for FastAPI"""
    global mcp_process

    # Startup: start Toolbox MCP process
    try:
        command, env_overrides = build_toolbox_command()
        logger.info("Launching Toolbox MCP server with command: %s", " ".join(command))
        mcp_process = MCPProcess(command=command, env=env_overrides)
        await mcp_process.start()
        logger.info("Toolbox MCP bridge server started successfully")
    except Exception as e:
        logger.error(f"Failed to start Toolbox MCP process: {e}")
        mcp_process = None

    yield

    # Shutdown: Stop MCP process
    if mcp_process:
        await mcp_process.stop()


app = FastAPI(
    title="MCP Bridge Server",
    description="HTTP bridge for Model Context Protocol servers",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if mcp_process else "degraded",
        "mcp_enabled": mcp_process is not None,
        "toolbox_mode": ACTIVE_TOOLBOX_MODE,
        "tools_file": ACTIVE_TOOLS_FILE,
    }


@app.get("/tools")
async def list_tools():
    """
    List available MCP tools.

    Returns:
        List of tool definitions with names, descriptions, and input schemas
    """
    if not mcp_process:
        # Return empty list in demo mode
        return {
            "tools": [],
            "note": "Toolbox MCP process is not active. Check toolbox configuration and restart."
        }

    try:
        tools = await mcp_process.list_tools()
        return {"tools": tools}

    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """
    Call an MCP tool.

    Args:
        request: Tool call request with tool name and arguments

    Returns:
        Tool execution result

    Example:
        POST /tools/call
        {
            "name": "query",
            "arguments": {"sql": "SELECT * FROM users LIMIT 10"}
        }
    """
    if not mcp_process:
        raise HTTPException(
            status_code=503,
            detail="MCP process not available. Set POSTGRES_DSN environment variable."
        )

    try:
        logger.info(f"Calling MCP tool: {request.name} with args: {request.arguments}")
        result = await mcp_process.call_tool(request.name, request.arguments)

        return ToolCallResponse(result=result)

    except Exception as e:
        logger.error(f"Tool call failed: {e}")
        return ToolCallResponse(
            result={},
            error=str(e)
        )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "MCP Bridge Server",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "list_tools": "/tools",
            "call_tool": "/tools/call"
        },
        "mcp_enabled": mcp_process is not None
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("MCP_BRIDGE_PORT", "3000"))

    logger.info(f"Starting MCP Bridge Server on port {port}")
    logger.info("Toolbox MCP bridge expects toolbox/tools.yaml and ClickHouse credentials to be configured.")
    logger.info("Override defaults with TOOLBOX_* environment variables if needed.")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info"
    )
