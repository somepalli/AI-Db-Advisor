"""
MCP Orchestrator - Coordinates MCP tool invocations with safety controls

Orchestrates the complete flow:
1. MCP tool invocation (suggestion-only)
2. Safety validation
3. User approval workflow
4. Controlled execution
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from .mcp_client import MCPClient, MCPToolMode, MCPToolCategory, get_mcp_client
from .safety_validator import SafetyValidator, RiskLevel
from .approval_workflow import ApprovalWorkflow, get_workflow
from ..deps import resolve_agent

logger = logging.getLogger(__name__)


class MCPOrchestrator:
    """
    Orchestrates MCP tool invocations with comprehensive safety controls.

    Workflow:
    1. Request suggestions from MCP tools
    2. Validate each suggestion for safety
    3. Submit validated suggestions for user approval
    4. Execute only user-approved suggestions
    """

    def __init__(self, ds_id: str):
        """
        Initialize MCP orchestrator for a datasource.

        Args:
            ds_id: Datasource identifier
        """
        self.ds_id = ds_id
        self.mcp_client = get_mcp_client()
        self.validator = SafetyValidator(ds_id)
        self.workflow = get_workflow(ds_id)

        if not self.mcp_client:
            logger.warning("MCP client not initialized - MCP features disabled")

        logger.info(f"MCP Orchestrator initialized for: {ds_id}")

    async def request_database_suggestions(
        self,
        query: Optional[str] = None,
        schema_context: Optional[Dict[str, Any]] = None,
        optimization_type: str = "general",
        max_suggestions: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Request suggestions from MCP tools for database optimization.

        SAFETY: This method ONLY generates suggestions.
        No execution happens without user approval.

        Args:
            query: SQL query to optimize (optional)
            schema_context: Database schema information
            optimization_type: Type of optimization requested
            max_suggestions: Maximum number of suggestions to request

        Returns:
            List of validated suggestions ready for user approval:
            [
                {
                    "id": "suggestion-uuid",
                    "approval_id": "approval-uuid",
                    "mcp_tool": "tool_name",
                    "sql": "SUGGESTED SQL",
                    "description": "What this does",
                    "rationale": "Why this is recommended",
                    "risk_level": "low|medium|high|critical",
                    "warnings": ["warning1", "warning2"],
                    "requires_backup": bool,
                    "requires_confirmation": bool,
                    "status": "pending_approval"
                },
                ...
            ]
        """
        if not self.mcp_client:
            logger.warning("MCP client not available")
            return []

        logger.info(
            f"Requesting MCP suggestions for {self.ds_id}: "
            f"type={optimization_type}, max={max_suggestions}"
        )

        # Build context for MCP tools
        context = await self._build_mcp_context(
            query=query,
            schema_context=schema_context,
            optimization_type=optimization_type
        )

        validated_suggestions = []

        try:
            # Discover available database tools
            tools = await self.mcp_client.discover_tools(
                category=MCPToolCategory.DATABASE_OPTIMIZATION
            )

            logger.info(f"Found {len(tools)} MCP database tools")

            # Request suggestions from each relevant tool
            for tool in tools[:max_suggestions]:
                try:
                    # Generate suggestion (SUGGESTION_ONLY mode)
                    suggestion = await self.mcp_client.generate_suggestion(
                        tool_name=tool["name"],
                        context=context,
                        mode=MCPToolMode.SUGGESTION_ONLY
                    )

                    # Validate suggestion for safety
                    validation_result = await self._validate_and_prepare(suggestion)

                    if validation_result["is_valid"]:
                        # Submit for user approval
                        approval_id = self.workflow.submit_for_approval(
                            validation_result["suggestion"]
                        )

                        # Add approval ID to suggestion
                        validated_suggestion = validation_result["suggestion"]
                        validated_suggestion["approval_id"] = approval_id
                        validated_suggestion["status"] = "pending_approval"

                        validated_suggestions.append(validated_suggestion)

                        logger.info(
                            f"Suggestion added: {suggestion['id']} "
                            f"(risk={validation_result['risk_level']}, "
                            f"approval={approval_id})"
                        )

                except Exception as tool_error:
                    logger.error(f"MCP tool {tool['name']} failed: {tool_error}")
                    continue

        except Exception as e:
            logger.error(f"MCP suggestion request failed: {e}")
            raise

        logger.info(
            f"Generated {len(validated_suggestions)} validated MCP suggestions"
        )

        return validated_suggestions

    async def _build_mcp_context(
        self,
        query: Optional[str] = None,
        schema_context: Optional[Dict[str, Any]] = None,
        optimization_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for MCP tool invocation.

        Args:
            query: SQL query
            schema_context: Database schema
            optimization_type: Optimization type

        Returns:
            Context dictionary for MCP
        """
        context = {
            "datasource_id": self.ds_id,
            "optimization_type": optimization_type,
            "timestamp": datetime.utcnow().isoformat(),
            "query": query if query else ""  # Always include query field (empty string if none)
        }

        # Add schema if provided
        if schema_context:
            context["schema"] = schema_context
        else:
            # Fetch schema from database
            try:
                agent = resolve_agent(self.ds_id)
                schema = agent.get_schema()
                context["schema"] = schema
            except Exception as e:
                logger.warning(f"Could not fetch schema: {e}")

        # Add database type
        try:
            agent = resolve_agent(self.ds_id)
            context["database_type"] = agent.get_db_type()
        except Exception:
            context["database_type"] = "unknown"

        return context

    async def _validate_and_prepare(
        self,
        suggestion: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate MCP suggestion and prepare for user approval.

        Args:
            suggestion: MCP-generated suggestion

        Returns:
            Validation result with enhanced suggestion
        """
        # Get database agent for impact estimation
        try:
            agent = resolve_agent(self.ds_id)
        except Exception:
            agent = None

        # Validate suggestion
        validation_result = await self.validator.validate_suggestion(
            suggestion,
            agent=agent
        )

        logger.info(
            f"Validation result for {suggestion['id']}: "
            f"valid={validation_result['is_valid']}, "
            f"safe={validation_result['is_safe']}, "
            f"risk={validation_result['risk_level']}"
        )

        return validation_result

    async def execute_approved_suggestion(
        self,
        approval_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute an APPROVED MCP suggestion.

        CRITICAL SAFETY:
        This method ONLY executes suggestions that have been:
        1. Validated for safety
        2. Approved by a user
        3. Confirmed for execution

        Args:
            approval_id: Approval identifier
            user_id: User requesting execution

        Returns:
            Execution result

        Raises:
            ValueError: If suggestion is not approved
            Exception: If execution fails
        """
        logger.info(f"Execution request: approval={approval_id}, user={user_id}")

        # Get approval record
        approval_record = self.workflow.get_approval_by_id(approval_id)

        if not approval_record:
            raise ValueError(f"Approval ID not found: {approval_id}")

        # Verify approval status
        if approval_record["status"] != "approved":
            raise ValueError(
                f"Cannot execute: suggestion not approved "
                f"(status={approval_record['status']})"
            )

        # Get suggestion
        suggestion = approval_record["suggestion"]

        # Mark as executing
        self.workflow.mark_executing(approval_id)

        try:
            # Execute via database agent
            agent = resolve_agent(self.ds_id)
            sql = suggestion["sql"]

            logger.info(f"Executing approved SQL: {sql[:100]}...")

            # Execute SQL
            # Note: Actual execution would use agent's execute method
            # For safety, we're showing the structure here
            execution_result = await self._execute_sql_safely(agent, sql)

            # Mark as executed
            self.workflow.mark_executed(
                approval_id,
                execution_result=execution_result,
                rollback_available=False  # Would check if transaction-based
            )

            logger.info(f"Execution successful: {approval_id}")

            return {
                "success": True,
                "approval_id": approval_id,
                "suggestion_id": suggestion["id"],
                "result": execution_result,
                "executed_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            # Mark as failed
            self.workflow.mark_failed(approval_id, error=str(e))

            logger.error(f"Execution failed: {approval_id} - {e}")

            raise

    async def _execute_sql_safely(
        self,
        agent: Any,
        sql: str
    ) -> Dict[str, Any]:
        """
        Execute SQL with safety measures.

        Args:
            agent: Database agent
            sql: SQL statement

        Returns:
            Execution result
        """
        # This would be implemented with actual database execution
        # For now, return placeholder
        return {
            "sql": sql,
            "rows_affected": 0,
            "execution_time_ms": 0,
            "note": "Execution placeholder - implement with actual agent"
        }

    def get_pending_suggestions(self) -> List[Dict[str, Any]]:
        """
        Get all suggestions pending user approval.

        Returns:
            List of pending suggestions
        """
        return self.workflow.get_pending_approvals()

    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get execution history for audit.

        Args:
            limit: Maximum number of records

        Returns:
            List of execution records
        """
        return self.workflow.get_execution_history(limit=limit)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get MCP orchestrator statistics.

        Returns:
            Statistics dictionary
        """
        workflow_stats = self.workflow.get_statistics()

        return {
            "datasource_id": self.ds_id,
            "mcp_enabled": self.mcp_client is not None,
            **workflow_stats
        }
