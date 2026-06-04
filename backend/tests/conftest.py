# tests/conftest.py
"""
Pytest configuration and shared fixtures for all tests
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.main import app
from backend.config import settings


@pytest.fixture(scope="function")
def client():
    """FastAPI test client"""
    # Clear any existing datasources before each test
    settings.DATASOURCES.clear()
    return TestClient(app)


@pytest.fixture
def mock_postgres_agent():
    """Mock PostgresAgent for testing without real database"""
    agent = MagicMock()
    agent.__class__.__name__ = "PostgresAgent"

    # Mock schema
    agent.get_schema.return_value = {
        "tables": {
            "public.users": [
                {"column": "id", "type": "integer", "nullable": "NO"},
                {"column": "name", "type": "varchar", "nullable": "YES"},
                {"column": "email", "type": "varchar", "nullable": "NO"},
                {"column": "created_at", "type": "timestamp", "nullable": "YES"},
            ],
            "public.orders": [
                {"column": "id", "type": "integer", "nullable": "NO"},
                {"column": "user_id", "type": "integer", "nullable": "NO"},
                {"column": "amount", "type": "numeric", "nullable": "NO"},
                {"column": "status", "type": "varchar", "nullable": "YES"},
            ],
        }
    }

    # Mock top queries
    agent.get_top_queries.return_value = [
        {
            "query": "SELECT * FROM users WHERE id = $1",
            "calls": 1000,
            "mean_time_ms": 2.5,
            "rows": 1,
            "source": "pg_stat_statements"
        },
        {
            "query": "SELECT COUNT(*) FROM orders",
            "calls": 500,
            "mean_time_ms": 15.3,
            "rows": 1,
            "source": "pg_stat_statements"
        },
    ]

    # Mock explain
    agent.explain.return_value = {
        "plan": [
            {
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Relation Name": "users",
                    "Total Cost": 100.0,
                    "Plan Rows": 1000,
                }
            }
        ]
    }

    # Mock locks
    agent.locks.return_value = [
        {
            "locktype": "relation",
            "mode": "AccessShareLock",
            "granted": True,
            "pid": 12345,
            "age": "00:00:05"
        }
    ]

    # Mock stats
    agent.stats.return_value = {
        "total_db_size": 1073741824,  # 1GB
        "active_backends": 5
    }

    # Mock hypothetical index
    agent.hypothetical_index.return_value = {
        "hypo_stmt": "CREATE INDEX ON users (email)",
        "hypopg_available": True
    }

    # Mock plan with hypo
    agent.plan_with_hypo.return_value = {
        "plan": [
            {
                "Plan": {
                    "Node Type": "Index Scan",
                    "Relation Name": "users",
                    "Total Cost": 50.0,
                    "Plan Rows": 1000,
                }
            }
        ],
        "validated": True
    }

    return agent


@pytest.fixture
def sample_datasource():
    """Sample datasource configuration"""
    return {
        "id": "test-pg",
        "engine": "postgres",
        "dsn": "postgresql://user:pass@localhost:5432/testdb"
    }


@pytest.fixture
def sample_sql():
    """Sample SQL queries for testing"""
    return {
        "simple": "SELECT * FROM users WHERE email = 'test@example.com'",
        "complex": """
            SELECT u.name, COUNT(o.id) as order_count
            FROM users u
            LEFT JOIN orders o ON u.id = o.user_id
            WHERE u.created_at > '2024-01-01'
            GROUP BY u.name
            ORDER BY order_count DESC
            LIMIT 10
        """,
        "with_offset": "SELECT * FROM users ORDER BY id OFFSET 1000 LIMIT 10",
        "select_star": "SELECT * FROM users",
    }


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for AI testing"""
    client = MagicMock()
    client.chat.return_value = '{"suggestions": [{"type": "index", "summary": "Add index on email column", "index": {"table": "users", "columns": ["email"]}, "risk": "low", "rationale": "Frequently used in WHERE clauses"}]}'
    return client