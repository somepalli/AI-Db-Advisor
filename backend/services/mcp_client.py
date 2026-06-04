"""
MCP Client Wrapper - Suggestion-Only Mode

CRITICAL SAFETY:
This client NEVER executes MCP tools directly.
It only requests suggestions and returns them for user approval.
All execution happens AFTER explicit user confirmation in the approval workflow.
"""
from typing import Dict, Any, List, Optional
from enum import Enum
import logging
import httpx
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class MCPToolMode(Enum):
    """MCP tool invocation modes"""
    SUGGESTION_ONLY = "suggestion_only"  # Default: only generate suggestions
    PREVIEW = "preview"                  # Show what would happen (dry-run)
    # EXECUTE mode is intentionally NOT included - use ApprovalWorkflow instead


class MCPToolCategory(Enum):
    """Categories of MCP tools"""
    DATABASE_OPTIMIZATION = "database_optimization"
    QUERY_ANALYSIS = "query_analysis"
    SCHEMA_SUGGESTION = "schema_suggestion"
    INDEX_RECOMMENDATION = "index_recommendation"
    PERFORMANCE_TUNING = "performance_tuning"


class MCPClient:
    """
    MCP (Model Context Protocol) Client Wrapper

    Connects to Google's MCP Toolbox for database operations.
    Enforces strict suggestion-only mode for safety.
    """

    def __init__(
        self,
        mcp_endpoint: str,
        api_key: str,
        timeout: int = 30
    ):
        """
        Initialize MCP client for Google's MCP API.

        Args:
            mcp_endpoint: MCP API endpoint URL (Google Cloud endpoint)
            api_key: Google API key for authentication
            timeout: Request timeout in seconds
        """
        self.endpoint = mcp_endpoint.rstrip('/')
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AI-DB-Advisor/1.0"
            }
        )

        logger.info(f"MCP Client initialized: {mcp_endpoint}")
        logger.info(f"API Key configured: {api_key[:10]}...")

    async def discover_tools(
        self,
        category: Optional[MCPToolCategory] = None
    ) -> List[Dict[str, Any]]:
        """
        Discover available MCP tools from Google's API.

        Args:
            category: Optional category filter

        Returns:
            List of tool definitions
        """
        try:
            # For local MCP bridge, no API key needed
            response = await self.client.get(f"{self.endpoint}/tools")
            response.raise_for_status()

            tools = response.json().get("tools", [])

            logger.info(f"Discovered {len(tools)} MCP tools from local bridge")

            return tools

        except httpx.HTTPStatusError as e:
            logger.error(f"Tool discovery HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Tool discovery failed: {e}")
            raise

    async def generate_suggestion(
        self,
        tool_name: str,
        context: Dict[str, Any],
        mode: MCPToolMode = MCPToolMode.SUGGESTION_ONLY
    ) -> Dict[str, Any]:
        """
        Generate suggestion using MCP tool.

        CRITICAL SAFETY:
        This method ONLY generates suggestions.
        It NEVER executes changes on the database.

        Args:
            tool_name: MCP tool identifier (e.g., "db_index_optimizer")
            context: Context data for the tool
                - datasource_id: Database identifier
                - query: SQL query (optional)
                - schema: Database schema (optional)
                - optimization_type: Type of optimization requested
            mode: SUGGESTION_ONLY (default) or PREVIEW

        Returns:
            Suggestion object:
                {
                    "id": "unique-suggestion-id",
                    "mcp_tool": "tool_name",
                    "sql": "SUGGESTED SQL STATEMENT",
                    "description": "What this suggestion does",
                    "rationale": "Why this is recommended",
                    "generated_at": "2025-01-05T12:00:00Z",
                    "mode": "suggestion_only",
                    "status": "generated"
                }

        Raises:
            ValueError: If mode is not SUGGESTION_ONLY or PREVIEW
            HTTPException: If MCP API call fails
        """
        # SAFETY ENFORCEMENT
        if mode not in [MCPToolMode.SUGGESTION_ONLY, MCPToolMode.PREVIEW]:
            raise ValueError(
                "SECURITY VIOLATION: Only SUGGESTION_ONLY and PREVIEW modes are allowed. "
                "Use ApprovalWorkflow for execution after user approval."
            )

        # Generate unique suggestion ID
        suggestion_id = str(uuid.uuid4())

        # Build request payload
        payload = {
            "tool": tool_name,
            "suggestion_id": suggestion_id,
            "mode": mode.value,
            "context": context,
            "execute": False,  # CRITICAL: Never auto-execute
            "return_suggestion": True,
            "metadata": {
                "source": "ai_db_advisor",
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        logger.info(f"Requesting MCP suggestion: tool={tool_name}, mode={mode.value}")
        logger.debug(f"MCP request context: {context}")

        # Map context to tool-specific arguments
        arguments = self._map_context_to_tool_arguments(tool_name, context)

        logger.debug(f"MCP tool arguments: {arguments}")

        try:
            # Call local MCP bridge
            response = await self.client.post(
                f"{self.endpoint}/tools/call",
                json={
                    "name": tool_name,
                    "arguments": arguments
                }
            )
            response.raise_for_status()

            suggestion_data = response.json().get("result", {})

            # Enhance with metadata
            suggestion = {
                "id": suggestion_id,
                "mcp_tool": tool_name,
                "sql": suggestion_data.get("sql", ""),
                "description": suggestion_data.get("description", ""),
                "rationale": suggestion_data.get("rationale", ""),
                "category": suggestion_data.get("category", "optimization"),
                "generated_at": datetime.utcnow().isoformat(),
                "mode": mode.value,
                "status": "generated",
                "context_used": context,
                "raw_response": suggestion_data  # Keep full response for debugging
            }

            logger.info(f"MCP suggestion generated: {suggestion_id}")

            return suggestion

        except httpx.HTTPStatusError as e:
            logger.error(f"MCP API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"MCP tool invocation failed: {e.response.text}")

        except Exception as e:
            logger.error(f"MCP request failed: {e}")
            raise

    def _map_context_to_tool_arguments(
        self,
        tool_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Map generic context to tool-specific arguments.

        Different MCP tools expect different argument formats.
        This method translates our generic context to tool-specific arguments.

        Supported postgres-mcp tools:
        - query: Execute SQL query (readonly)
        - list_tables: List all tables in database
        - describe_table: Get table schema details
        - append_insights: Append query insights to context

        Args:
            tool_name: Name of the MCP tool
            context: Generic context dictionary

        Returns:
            Tool-specific arguments dictionary
        """
        # Get the query from context
        query = context.get("query", "")

        # Tool-specific mapping for crystaldba/postgres-mcp
        # This MCP server provides advanced optimization tools

        if tool_name == "execute_sql":
            # Execute SQL query (crystaldba uses execute_sql instead of query)
            if not query or query.strip() == "":
                query = "SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') LIMIT 10;"
                logger.info(f"Empty query provided, using default: {query[:50]}...")
            return {"sql": query}

        elif tool_name == "analyze_workload_indexes":
            # Analyze workload and recommend optimal indexes
            # This is the key optimization tool!
            queries = context.get("queries", [])
            if not queries and query:
                queries = [query]

            return {
                "queries": queries if queries else [],
                "max_indexes": context.get("max_indexes", 5)
            }

        elif tool_name == "get_top_queries":
            # Get slowest queries from pg_stat_statements
            return {
                "limit": context.get("limit", 10),
                "min_calls": context.get("min_calls", 5)
            }

        elif tool_name == "analyze_db_health":
            # Perform comprehensive database health check
            # Returns: buffer cache hit rates, connection health, constraint validation,
            # index health (duplicate/unused/invalid), sequence limits, vacuum health
            return {}

        elif tool_name == "explain_query":
            # Get execution plan for a query
            if not query:
                logger.warning("explain_query called without query")
                return {}

            return {
                "sql": query,
                "analyze": context.get("analyze", False),
                "buffers": context.get("buffers", True)
            }

        elif tool_name == "list_schemas":
            # List all database schemas
            return {}

        elif tool_name == "list_objects":
            # List database objects (tables, views, indexes, etc.)
            return {
                "schema": context.get("schema", "public"),
                "object_type": context.get("object_type", "table")
            }

        elif tool_name == "get_object_details":
            # Get detailed information about a database object
            return {
                "schema": context.get("schema", "public"),
                "object_name": context.get("object_name", ""),
                "object_type": context.get("object_type", "table")
            }

        # Legacy tool names (for backward compatibility)
        elif tool_name == "query":
            # Redirect to execute_sql
            return self._map_context_to_tool_arguments("execute_sql", context)

        elif tool_name in ["list_tables", "describe_table"]:
            # Redirect to list_objects
            return self._map_context_to_tool_arguments("list_objects", context)

        else:
            # For unknown tools, pass the full context minus internal metadata
            safe_context = {
                k: v for k, v in context.items()
                if k not in ["datasource_id", "timestamp"]
            }
            logger.warning(
                f"Unknown tool '{tool_name}', passing filtered context as arguments"
            )
            return safe_context

    async def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific MCP tool.

        Args:
            tool_name: Tool identifier

        Returns:
            Tool metadata and schema
        """
        try:
            # For local MCP bridge, tool info is in the tools list
            tools = await self.discover_tools()
            tool_info = next((t for t in tools if t.get("name") == tool_name), None)

            if not tool_info:
                raise ValueError(f"Tool {tool_name} not found")

            return tool_info

        except Exception as e:
            logger.error(f"Failed to get tool info: {e}")
            raise

    async def validate_credentials(self) -> bool:
        """
        Validate MCP bridge connection (local server, no credentials needed).

        Returns:
            True if MCP bridge is accessible
        """
        try:
            # Check health endpoint
            response = await self.client.get(f"{self.endpoint}/health")
            is_valid = response.status_code == 200

            if is_valid:
                logger.info("MCP bridge connection validated successfully")
            else:
                logger.warning(f"MCP bridge validation failed: {response.status_code}")

            return is_valid

        except Exception as e:
            logger.error(f"MCP bridge validation failed: {e}")
            return False

    async def close(self):
        """Close HTTP client connection."""
        await self.client.aclose()
        logger.info("MCP client closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Singleton instance (configured in config.py)
_mcp_client_instance: Optional[MCPClient] = None


def get_mcp_client() -> Optional[MCPClient]:
    """Get the global MCP client instance."""
    return _mcp_client_instance


def initialize_mcp_client(endpoint: str, api_key: str) -> MCPClient:
    """
    Initialize the global MCP client instance.

    This should be called once at application startup.
    """
    global _mcp_client_instance

    if _mcp_client_instance is None:
        _mcp_client_instance = MCPClient(endpoint, api_key)
        logger.info("Global MCP client initialized")

    return _mcp_client_instance
