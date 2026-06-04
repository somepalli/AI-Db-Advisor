# tests/test_utils.py
"""
Unit tests for utility functions
"""
import pytest
from backend.utils.sql_parse import mine_predicates, project_columns
from backend.utils.plan_diff import summarize_diff


class TestSQLParser:
    """Test SQL parsing utilities"""

    def test_mine_predicates_simple_where(self):
        """Test predicate mining from simple WHERE clause"""
        sql = "SELECT * FROM users WHERE email = 'test@example.com'"
        predicates = mine_predicates(sql)
        assert len(predicates) > 0
        assert any(p["column"] == "email" for p in predicates)

    def test_mine_predicates_multiple_conditions(self):
        """Test predicate mining with multiple conditions"""
        sql = "SELECT * FROM users WHERE age > 18 AND status = 'active'"
        predicates = mine_predicates(sql)
        assert len(predicates) >= 2

    def test_mine_predicates_with_order_by(self):
        """Test predicate mining with ORDER BY"""
        sql = "SELECT * FROM users ORDER BY created_at DESC"
        predicates = mine_predicates(sql)
        assert any(p["ctx"] == "order_by" for p in predicates)

    def test_mine_predicates_with_group_by(self):
        """Test predicate mining with GROUP BY"""
        sql = "SELECT name, COUNT(*) FROM users GROUP BY name"
        predicates = mine_predicates(sql)
        assert any(p["ctx"] == "group_by" for p in predicates)

    def test_mine_predicates_invalid_sql(self):
        """Test predicate mining with invalid SQL"""
        sql = "INVALID SQL QUERY"
        predicates = mine_predicates(sql)
        assert predicates == []

    def test_project_columns_simple(self):
        """Test column projection from simple SELECT"""
        sql = "SELECT id, name, email FROM users"
        columns = project_columns(sql)
        assert "id" in columns
        assert "name" in columns
        assert "email" in columns

    def test_project_columns_select_star(self):
        """Test column projection with SELECT *"""
        sql = "SELECT * FROM users"
        columns = project_columns(sql)
        # SELECT * doesn't parse to specific columns
        assert isinstance(columns, list)

    def test_project_columns_invalid_sql(self):
        """Test column projection with invalid SQL"""
        sql = "NOT A VALID QUERY"
        columns = project_columns(sql)
        assert columns == []


class TestPlanDiff:
    """Test query plan comparison utilities"""

    def test_summarize_diff_cost_reduction(self):
        """Test plan diff when cost is reduced"""
        before = [{"Plan": {"Total Cost": 100.0, "Plan Rows": 1000}}]
        after = [{"Plan": {"Total Cost": 50.0, "Plan Rows": 1000}}]

        diff = summarize_diff(before, after)
        assert diff["before_cost"] == 100.0
        assert diff["after_cost"] == 50.0
        assert diff["cost_down"] is True
        assert diff["cost_delta_pct"] == 50.0

    def test_summarize_diff_rows_reduction(self):
        """Test plan diff when rows are reduced"""
        before = [{"Plan": {"Total Cost": 100.0, "Plan Rows": 1000}}]
        after = [{"Plan": {"Total Cost": 100.0, "Plan Rows": 500}}]

        diff = summarize_diff(before, after)
        assert diff["before_rows"] == 1000
        assert diff["after_rows"] == 500
        assert diff["rows_down"] is True
        assert diff["rows_delta_pct"] == 50.0

    def test_summarize_diff_cost_increase(self):
        """Test plan diff when cost increases"""
        before = [{"Plan": {"Total Cost": 50.0, "Plan Rows": 1000}}]
        after = [{"Plan": {"Total Cost": 100.0, "Plan Rows": 1000}}]

        diff = summarize_diff(before, after)
        assert diff["cost_down"] is False
        assert diff["cost_delta_pct"] == -100.0

    def test_summarize_diff_invalid_plans(self):
        """Test plan diff with invalid plan data"""
        before = []
        after = []

        diff = summarize_diff(before, after)
        assert diff == {}

    def test_summarize_diff_no_change(self):
        """Test plan diff when nothing changes"""
        before = [{"Plan": {"Total Cost": 100.0, "Plan Rows": 1000}}]
        after = [{"Plan": {"Total Cost": 100.0, "Plan Rows": 1000}}]

        diff = summarize_diff(before, after)
        assert diff["cost_delta_pct"] == 0.0
        assert diff["rows_delta_pct"] == 0.0


class TestConfigValidation:
    """Test configuration validation"""

    def test_settings_default_values(self):
        """Test default configuration values"""
        from backend.config import settings

        assert settings.LLM_PROVIDER == "ollama"
        assert settings.LLM_ENDPOINT == "http://127.0.0.1:11434"
        assert isinstance(settings.DATASOURCES, dict)

    def test_settings_env_variable(self):
        """Test settings can be configured via environment"""
        from backend.config import settings

        # ENV defaults to 'dev'
        assert settings.ENV in ["dev", "prod"]