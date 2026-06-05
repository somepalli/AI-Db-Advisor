"""
Direct integration with Postgres MCP Pro (crystaldba/postgres-mcp).

Thin compatibility wrapper around ``PostgresMcpExecutor`` (the single in-process
entry point for Postgres MCP Pro). Kept so the existing AI-chat MCP suggestion merge
keeps working; new code should use ``PostgresMcpExecutor`` directly.

These suggestions run unrestricted (``trust="local"``) — they surface in the UI as
recommendations, not as data fed to a hosted model.
"""
import logging
from typing import Dict, Any, List, Optional

from .postgres_mcp_executor import PostgresMcpExecutor

logger = logging.getLogger(__name__)


async def get_optimization_suggestions(
    dsn: str,
    query: Optional[str] = None,
    max_suggestions: int = 5,
) -> List[Dict[str, Any]]:
    """Return optimization suggestions (health + top queries + index advice) via Postgres MCP Pro."""
    suggestions: List[Dict[str, Any]] = []
    executor = PostgresMcpExecutor(dsn, trust="local")
    try:
        try:
            health = await executor.health(health_type="all")
            if health:
                suggestions.append({
                    "type": "health_issue", "category": "database_health",
                    "description": "Database health analysis", "sql": "",
                    "rationale": str(health)[:2000], "risk_level": "low",
                    "is_mcp": True, "mcp_tool": "analyze_db_health",
                })
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")

        try:
            top = await executor.top_queries(limit=5)
            if top:
                lines = "\n".join(
                    f"- {str(q.get('query',''))[:100]} (calls: {q.get('calls',0)})" for q in top[:3]
                )
                suggestions.append({
                    "type": "slow_query", "category": "performance",
                    "description": f"Found {len(top)} slow queries",
                    "sql": f"-- Top slow queries:\n{lines}",
                    "rationale": "High execution time / call count — candidates for optimization",
                    "risk_level": "low", "is_mcp": True, "mcp_tool": "get_top_queries",
                })
        except Exception as e:
            logger.warning(f"Top queries analysis failed: {e}")

        try:
            advice = await executor.index_advice()
            if advice:
                suggestions.append({
                    "type": "index", "category": "index_recommendation",
                    "description": "Index tuning recommendations",
                    "sql": "", "rationale": str(advice)[:2000],
                    "expected_gain": "Potential query speedup",
                    "risk_level": "low", "is_mcp": True, "mcp_tool": "analyze_workload_indexes",
                })
        except Exception as e:
            logger.warning(f"Index analysis failed: {e}")

    except ImportError as e:
        logger.error(f"postgres-mcp not installed: {e}")
    except Exception as e:
        logger.error(f"Optimization analysis failed: {e}", exc_info=True)
    finally:
        await executor.aclose()

    return suggestions[:max_suggestions]


async def explain_query_with_indexes(
    dsn: str,
    query: str,
    hypothetical_indexes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Get an EXPLAIN plan for a query via Postgres MCP Pro (no execution)."""
    executor = PostgresMcpExecutor(dsn, trust="local")
    try:
        plan = await executor.explain(query)
        return {"plan": plan, "success": True}
    except Exception as e:
        logger.error(f"EXPLAIN query failed: {e}")
        return {"plan": {}, "success": False, "error": str(e)}
    finally:
        await executor.aclose()
