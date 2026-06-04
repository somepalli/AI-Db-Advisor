"""
Custom Prometheus Metrics for AI DB Advisor

This module defines custom metrics for tracking:
- Database query performance
- AI suggestion generation
- MCP operations
- Optimization improvements
"""
from prometheus_client import Counter, Histogram, Gauge, Summary
import time
from contextlib import contextmanager
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# Database Metrics
# =============================================================================

# Query execution time by database type
db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query execution time in seconds',
    ['db_type', 'operation'],  # Labels: postgres, mysql, etc. / select, insert, etc.
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)

# Active database connections
database_connections_active = Gauge(
    'database_connections_active',
    'Number of active database connections',
    ['datasource_id', 'db_type']
)

# Total queries executed
db_queries_total = Counter(
    'db_queries_total',
    'Total number of database queries executed',
    ['db_type', 'operation', 'status']  # status: success, error
)

# Database size (updated periodically)
database_size_bytes = Gauge(
    'database_size_bytes',
    'Database size in bytes',
    ['datasource_id', 'db_type']
)

# =============================================================================
# AI/LLM Metrics
# =============================================================================

# AI suggestion generation time
ai_suggestion_generation_duration = Histogram(
    'ai_suggestion_generation_seconds',
    'AI suggestion generation time in seconds',
    ['model', 'suggestion_type'],  # model: ollama, openai / type: index, rewrite, note
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
)

# Total AI suggestions generated
ai_suggestions_generated_total = Counter(
    'ai_suggestions_generated_total',
    'Total number of AI suggestions generated',
    ['suggestion_type', 'status']  # type: index, rewrite, note / status: success, error
)

# AI suggestion validation success rate
ai_suggestions_validated_total = Counter(
    'ai_suggestions_validated_total',
    'Total number of AI suggestions validated',
    ['suggestion_type', 'validation_result']  # result: valid, invalid
)

# LLM API response time
llm_api_response_duration = Histogram(
    'llm_api_response_seconds',
    'LLM API response time in seconds',
    ['provider', 'model'],  # provider: ollama, openai
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

# =============================================================================
# MCP Metrics
# =============================================================================

# MCP operations counter
mcp_operation_total = Counter(
    'mcp_operation_total',
    'Total MCP operations performed',
    ['operation_type', 'status']  # type: suggest, approve, execute / status: success, error
)

# MCP suggestion generation time
mcp_suggestion_duration = Histogram(
    'mcp_suggestion_duration_seconds',
    'MCP suggestion generation time',
    ['mcp_tool'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)

# MCP suggestions approved
mcp_suggestions_approved_total = Counter(
    'mcp_suggestions_approved_total',
    'Total MCP suggestions approved by users',
    ['mcp_tool', 'risk_level']
)

# MCP suggestions executed
mcp_suggestions_executed_total = Counter(
    'mcp_suggestions_executed_total',
    'Total MCP suggestions executed',
    ['mcp_tool', 'execution_status']  # status: success, failed
)

# MCP suggestions rejected
mcp_suggestions_rejected_total = Counter(
    'mcp_suggestions_rejected_total',
    'Total MCP suggestions rejected by users',
    ['mcp_tool', 'risk_level']
)

# =============================================================================
# Optimization Metrics
# =============================================================================

# Optimization improvement percentage
optimization_improvement_percentage = Gauge(
    'optimization_improvement_percentage',
    'Average optimization improvement percentage',
    ['optimization_type']  # type: index, rewrite, config
)

# Index recommendations applied
index_recommendations_applied_total = Counter(
    'index_recommendations_applied_total',
    'Total index recommendations applied',
    ['db_type', 'status']  # status: success, failed
)

# Query rewrites applied
query_rewrites_applied_total = Counter(
    'query_rewrites_applied_total',
    'Total query rewrites applied',
    ['db_type', 'status']
)

# =============================================================================
# Metric Helper Functions
# =============================================================================

@contextmanager
def track_query_time(db_type: str, operation: str = "query"):
    """
    Context manager to track database query execution time.

    Usage:
        with track_query_time("postgres", "select"):
            # execute query
            pass
    """
    start_time = time.time()
    status = "success"

    try:
        yield
    except Exception as e:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        db_query_duration.labels(db_type=db_type, operation=operation).observe(duration)
        db_queries_total.labels(db_type=db_type, operation=operation, status=status).inc()


@contextmanager
def track_ai_suggestion_generation(model: str, suggestion_type: str):
    """
    Context manager to track AI suggestion generation time.

    Usage:
        with track_ai_suggestion_generation("ollama", "index"):
            # generate suggestion
            pass
    """
    start_time = time.time()
    status = "success"

    try:
        yield
    except Exception as e:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        ai_suggestion_generation_duration.labels(
            model=model,
            suggestion_type=suggestion_type
        ).observe(duration)
        ai_suggestions_generated_total.labels(
            suggestion_type=suggestion_type,
            status=status
        ).inc()


@contextmanager
def track_mcp_operation(operation_type: str, mcp_tool: Optional[str] = None):
    """
    Context manager to track MCP operations.

    Usage:
        with track_mcp_operation("suggest", "query_optimizer"):
            # perform MCP operation
            pass
    """
    start_time = time.time()
    status = "success"

    try:
        yield
    except Exception as e:
        status = "error"
        raise
    finally:
        duration = time.time() - start_time
        mcp_operation_total.labels(
            operation_type=operation_type,
            status=status
        ).inc()

        if mcp_tool and operation_type == "suggest":
            mcp_suggestion_duration.labels(mcp_tool=mcp_tool).observe(duration)


def record_mcp_approval(mcp_tool: str, risk_level: str):
    """Record MCP suggestion approval."""
    mcp_suggestions_approved_total.labels(
        mcp_tool=mcp_tool,
        risk_level=risk_level
    ).inc()


def record_mcp_rejection(mcp_tool: str, risk_level: str):
    """Record MCP suggestion rejection."""
    mcp_suggestions_rejected_total.labels(
        mcp_tool=mcp_tool,
        risk_level=risk_level
    ).inc()


def record_mcp_execution(mcp_tool: str, execution_status: str):
    """Record MCP suggestion execution."""
    mcp_suggestions_executed_total.labels(
        mcp_tool=mcp_tool,
        execution_status=execution_status
    ).inc()


def update_database_connections(datasource_id: str, db_type: str, count: int):
    """Update active database connections count."""
    database_connections_active.labels(
        datasource_id=datasource_id,
        db_type=db_type
    ).set(count)


def update_database_size(datasource_id: str, db_type: str, size_bytes: int):
    """Update database size in bytes."""
    database_size_bytes.labels(
        datasource_id=datasource_id,
        db_type=db_type
    ).set(size_bytes)


def record_optimization_improvement(optimization_type: str, improvement_pct: float):
    """Record optimization improvement percentage."""
    optimization_improvement_percentage.labels(
        optimization_type=optimization_type
    ).set(improvement_pct)


def record_index_recommendation(db_type: str, success: bool):
    """Record index recommendation application."""
    status = "success" if success else "failed"
    index_recommendations_applied_total.labels(
        db_type=db_type,
        status=status
    ).inc()


def record_query_rewrite(db_type: str, success: bool):
    """Record query rewrite application."""
    status = "success" if success else "failed"
    query_rewrites_applied_total.labels(
        db_type=db_type,
        status=status
    ).inc()


# =============================================================================
# Metrics Summary Functions
# =============================================================================

def get_metrics_summary() -> dict:
    """
    Get a summary of all metrics for debugging/monitoring.

    Returns:
        Dictionary with current metric values
    """
    return {
        "database": {
            "queries_total": "See Prometheus /metrics",
            "active_connections": "See Prometheus /metrics"
        },
        "ai": {
            "suggestions_generated": "See Prometheus /metrics",
            "generation_time_avg": "See Prometheus /metrics"
        },
        "mcp": {
            "operations_total": "See Prometheus /metrics",
            "approvals": "See Prometheus /metrics",
            "executions": "See Prometheus /metrics"
        }
    }


logger.info("Custom Prometheus metrics initialized")
