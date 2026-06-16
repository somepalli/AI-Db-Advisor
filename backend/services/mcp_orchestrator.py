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
from . import approval_store
from . import destructive_alerts
from . import apply as apply_service
from .agent_guardrails import evaluate as guardrail_evaluate, GuardrailDecision
from ..schemas import Suggestion
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

                    # Guardrail WALL: destructive/unknown statements are dropped
                    # before they can ever be queued for approval.
                    sql = (validation_result["suggestion"].get("sql") or "")
                    wall = guardrail_evaluate(sql, agentic=True)
                    if wall.decision is GuardrailDecision.DENY:
                        logger.warning(
                            f"Guardrail wall DENY — dropping MCP suggestion {suggestion.get('id')}: "
                            f"{wall.matched_rule or wall.risk_class.value}"
                        )
                        if wall.alert:
                            destructive_alerts.raise_destructive_blocked(
                                self.ds_id, sql,
                                matched_rule=wall.matched_rule,
                                risk_class=wall.risk_class.value,
                                reason=wall.reason,
                                source="mcp_orchestrator",
                            )
                        continue

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
        sug = self._suggestion_from_mcp(suggestion)

        # Mark as executing
        self.workflow.mark_executing(approval_id)

        try:
            agent = resolve_agent(self.ds_id)
            db_type = self._db_type(agent)

            logger.info(f"Executing approved SQL via apply.py (agentic): {sug.sql_fix[:100]}...")

            # Phase 1: DRY-RUN (BEGIN…ROLLBACK) through the guardrail-walled apply path.
            dry = self._run_apply(agent, sug, dry_run=True, db_type=db_type)
            if dry.status != "success":
                self.workflow.mark_failed(approval_id, error=f"Dry-run failed: {dry.message}")
                raise ValueError(f"Dry-run validation failed, real execution blocked: {dry.message}")

            # Phase 2: REAL execution — only because the dry-run passed.
            real = self._run_apply(agent, sug, dry_run=False, db_type=db_type)
            if real.status != "success":
                self.workflow.mark_failed(approval_id, error=real.message)
                raise ValueError(f"Execution failed: {real.message}")

            execution_result = {
                "sql": sug.sql_fix,
                "status": real.status,
                "message": real.message,
                "dry_run_validated": True,
            }
            self.workflow.mark_executed(
                approval_id,
                execution_result=execution_result,
                rollback_available=bool(real.rollback_sql),
                rollback_sql=real.rollback_sql,
            )

            logger.info(f"Execution successful: {approval_id}")

            return {
                "success": True,
                "approval_id": approval_id,
                "suggestion_id": suggestion.get("id", approval_id),
                "result": execution_result,
                "executed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            # Ensure the record is marked failed (idempotent if already failed above).
            try:
                rec = self.workflow.get_approval_by_id(approval_id)
                if rec and rec["status"] == "executing":
                    self.workflow.mark_failed(approval_id, error=str(e))
            except Exception:
                pass
            logger.error(f"Execution failed: {approval_id} - {e}")
            raise

    def _suggestion_from_mcp(self, mcp: Dict[str, Any]) -> Suggestion:
        """
        Convert a stored MCP suggestion dict into a Suggestion for apply.py.

        risk is set to "low" deliberately: the agent_guardrails WALL plus the
        explicit two-phase (dry-run then real) execution are the real safety
        gate here, so the legacy validator's "dry-run first" requirement (which
        would otherwise block the real commit for medium/high risk) is already
        satisfied by construction.
        """
        sql = (mcp.get("sql") or "")
        valid = {"index", "rewrite", "config", "partition", "cleanup", "note"}
        category = mcp.get("category")
        if category not in valid:
            up = sql.strip().upper()
            category = "index" if up.startswith(("CREATE INDEX", "CREATE UNIQUE INDEX")) else "config"
        return Suggestion(
            id=mcp.get("id") or mcp.get("approval_id") or "mcp-suggestion",
            level="table",
            category=category,
            title=mcp.get("description") or "MCP suggestion",
            summary=mcp.get("rationale") or mcp.get("description") or "",
            sql_fix=sql,
            validated=True,
            confidence="validated",
            risk="low",
            related_objects=mcp.get("tables_affected") or [],
            metadata={},
        )

    def _db_type(self, agent: Any) -> str:
        db_type = ""
        if hasattr(agent, "get_db_type"):
            try:
                db_type = (agent.get_db_type() or "").lower()
            except Exception:
                db_type = ""
        if not db_type:
            db_type = agent.__class__.__name__.replace("Agent", "").lower()
        return db_type or "unknown"

    def _run_apply(self, agent: Any, sug: Suggestion, *, dry_run: bool, db_type: str):
        """Open a connection the way the agent expects and run the walled apply."""
        if agent.__class__.__name__ == "PostgresAgent":
            with agent._conn() as conn:
                results = apply_service.apply_suggestions(
                    conn, [sug], dry_run, db_type, is_agentic=True, ds_id=self.ds_id
                )
        else:
            conn = agent._conn()
            try:
                results = apply_service.apply_suggestions(
                    conn, [sug], dry_run, db_type, is_agentic=True, ds_id=self.ds_id
                )
            finally:
                conn.close()
        return results[0]

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
