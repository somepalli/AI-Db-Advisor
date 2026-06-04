"""
Direct Integration with postgres-mcp (crystaldba)

This module provides direct access to postgres-mcp optimization tools
without needing to run it as a separate stdio MCP server.

It wraps the key optimization functions for use in AI Chat.
"""
import logging
from typing import Dict, Any, List, Optional
import asyncio

logger = logging.getLogger(__name__)


async def get_optimization_suggestions(
    dsn: str,
    query: Optional[str] = None,
    max_suggestions: int = 5
) -> List[Dict[str, Any]]:
    """
    Get optimization suggestions using postgres-mcp tools.

    Args:
        dsn: PostgreSQL connection string
        query: Optional SQL query to optimize
        max_suggestions: Maximum number of suggestions to return

    Returns:
        List of optimization suggestions with type, description, SQL, etc.
    """
    suggestions = []

    try:
        # Import postgres-mcp modules
        from postgres_mcp.sql import DbConnPool
        from postgres_mcp.database_health import DatabaseHealthTool
        from postgres_mcp.top_queries import TopQueriesCalc
        from postgres_mcp.index.dta_calc import DatabaseTuningAdvisor

        logger.info(f"Getting optimization suggestions for DSN: {dsn[:30]}...")

        # Create connection pool
        pool = DbConnPool(dsn, max_conn=5)
        await pool.ensure_created()

        # 1. Check database health
        try:
            health_tool = DatabaseHealthTool(pool)
            health_results = await health_tool.analyze_database_health()

            # Convert health issues to suggestions
            if isinstance(health_results, dict):
                for category, data in health_results.items():
                    if isinstance(data, dict) and data.get("status") != "healthy":
                        suggestions.append({
                            "type": "health_issue",
                            "category": "database_health",
                            "description": f"{category}: {data.get('message', 'Issue detected')}",
                            "sql": data.get("fix_sql", ""),
                            "rationale": f"Database health check identified issues in {category}",
                            "risk_level": "medium" if data.get("status") == "warning" else "high",
                            "is_mcp": True,
                            "mcp_tool": "analyze_db_health"
                        })

            logger.info(f"Database health check completed: {len(suggestions)} issues found")
        except Exception as health_error:
            logger.warning(f"Database health check failed: {health_error}")

        # 2. Get top slow queries
        try:
            top_queries_calc = TopQueriesCalc(pool)
            top_queries = await top_queries_calc.get_top_queries_from_stat(limit=5)

            if top_queries and len(top_queries) > 0:
                # Add suggestion to analyze slow queries
                slow_query_list = "\n".join([
                    f"- {q.get('query', '')[:100]}... (calls: {q.get('calls', 0)}, avg time: {q.get('mean_exec_time', 0):.2f}ms)"
                    for q in top_queries[:3]
                ])

                suggestions.append({
                    "type": "slow_query",
                    "category": "performance",
                    "description": f"Found {len(top_queries)} slow queries that need optimization",
                    "sql": f"-- Top slow queries:\n{slow_query_list}",
                    "rationale": "These queries have high execution time or call count and would benefit from optimization",
                    "risk_level": "low",
                    "is_mcp": True,
                    "mcp_tool": "get_top_queries",
                    "queries": top_queries
                })

            logger.info(f"Top queries analysis completed: {len(top_queries)} slow queries found")
        except Exception as top_queries_error:
            logger.warning(f"Top queries analysis failed: {top_queries_error}")

        # 3. Analyze workload for index recommendations
        if query or (top_queries and len(top_queries) > 0):
            try:
                # Use top queries if no specific query provided
                queries_to_analyze = [query] if query else [q.get("query", "") for q in top_queries[:5]]

                # Initialize Database Tuning Advisor
                dta = DatabaseTuningAdvisor(pool)

                # Analyze and recommend indexes
                index_recommendations = await dta.analyze_workload_indexes(
                    queries=queries_to_analyze,
                    max_indexes=min(max_suggestions, 5)
                )

                if index_recommendations:
                    for idx, recommendation in enumerate(index_recommendations[:max_suggestions]):
                        suggestions.append({
                            "type": "index",
                            "category": "index_recommendation",
                            "description": f"Create index: {recommendation.get('index_name', f'recommended_idx_{idx}')}",
                            "sql": recommendation.get("create_sql", ""),
                            "rationale": recommendation.get("rationale", "This index will improve query performance"),
                            "expected_gain": recommendation.get("expected_improvement", "Significant performance improvement"),
                            "risk_level": "low",
                            "is_mcp": True,
                            "mcp_tool": "analyze_workload_indexes",
                            "tables_affected": recommendation.get("tables", []),
                            "columns": recommendation.get("columns", [])
                        })

                logger.info(f"Index analysis completed: {len(index_recommendations)} recommendations generated")
            except Exception as index_error:
                logger.warning(f"Index analysis failed: {index_error}")

        # Close pool
        await pool.close()

        logger.info(f"Total optimization suggestions generated: {len(suggestions)}")

    except ImportError as import_error:
        logger.error(f"postgres-mcp not installed: {import_error}")
        # Return a helpful message
        suggestions.append({
            "type": "error",
            "category": "setup",
            "description": "postgres-mcp not installed",
            "sql": "-- pip install postgres-mcp",
            "rationale": "Install postgres-mcp to get advanced optimization suggestions",
            "risk_level": "info",
            "is_mcp": False
        })

    except Exception as e:
        logger.error(f"Optimization analysis failed: {e}", exc_info=True)
        suggestions.append({
            "type": "error",
            "category": "analysis_error",
            "description": f"Optimization analysis failed: {str(e)}",
            "sql": "",
            "rationale": "Unable to complete optimization analysis",
            "risk_level": "info",
            "is_mcp": False
        })

    return suggestions[:max_suggestions]


async def explain_query_with_indexes(
    dsn: str,
    query: str,
    hypothetical_indexes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Get EXPLAIN plan for a query, optionally with hypothetical indexes.

    Args:
        dsn: PostgreSQL connection string
        query: SQL query to explain
        hypothetical_indexes: List of CREATE INDEX statements to test

    Returns:
        Explain plan with cost estimates
    """
    try:
        from postgres_mcp.sql import DbConnPool
        from postgres_mcp.explain import ExplainPlanTool

        pool = DbConnPool(dsn, max_conn=2)
        await pool.ensure_created()

        explain_tool = ExplainPlanTool(pool)
        plan = await explain_tool.explain_query(
            sql=query,
            analyze=False,  # Don't execute, just plan
            buffers=True
        )

        await pool.close()

        return {
            "plan": plan,
            "success": True
        }

    except Exception as e:
        logger.error(f"EXPLAIN query failed: {e}")
        return {
            "plan": {},
            "success": False,
            "error": str(e)
        }
