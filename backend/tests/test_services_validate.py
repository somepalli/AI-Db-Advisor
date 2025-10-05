# tests/test_services_validate.py
"""
Tests for validation services (transactional validation)
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.validate import (
    explain_cost,
    validate_index_in_tx,
    validate_rewrite,
    can_validate_suggestion
)


class TestValidationServices:
    """Test suite for validation services"""

    @pytest.fixture
    def mock_connection(self):
        """Mock database connection"""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn, cursor

    def test_explain_cost_success(self, mock_connection):
        """Test extracting cost from EXPLAIN plan"""
        conn, cursor = mock_connection

        # Mock EXPLAIN response
        explain_result = [
            {
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Relation Name": "users",
                    "Total Cost": 150.5,
                    "Plan Rows": 1000
                }
            }
        ]
        cursor.fetchone.return_value = (explain_result,)

        cost = explain_cost(conn, "SELECT * FROM users WHERE email = 'test@example.com'")

        assert cost == 150.5
        cursor.execute.assert_called_once()
        assert "EXPLAIN (FORMAT JSON)" in cursor.execute.call_args[0][0]

    def test_explain_cost_with_timeout(self, mock_connection):
        """Test EXPLAIN with statement timeout"""
        conn, cursor = mock_connection

        explain_result = [{"Plan": {"Total Cost": 100.0}}]
        cursor.fetchone.return_value = (explain_result,)

        cost = explain_cost(conn, "SELECT * FROM users")

        # Should set statement timeout
        calls = [call[0][0] for call in cursor.execute.call_args_list]
        assert any("statement_timeout" in call for call in calls)

    def test_explain_cost_error_handling(self, mock_connection):
        """Test EXPLAIN cost extraction handles errors"""
        conn, cursor = mock_connection

        # Simulate query error
        cursor.execute.side_effect = Exception("Query timeout")

        with pytest.raises(Exception) as exc_info:
            explain_cost(conn, "SELECT * FROM invalid_table")

        assert "Query timeout" in str(exc_info.value)

    def test_validate_index_in_tx_success(self, mock_connection):
        """Test successful index validation using transaction rollback"""
        conn, cursor = mock_connection

        # Mock EXPLAIN results: before and after index creation
        before_plan = [{"Plan": {"Total Cost": 1000.0, "Plan Rows": 5000}}]
        after_plan = [{"Plan": {"Total Cost": 250.0, "Plan Rows": 5000}}]

        cursor.fetchone.side_effect = [
            (before_plan,),  # First EXPLAIN (baseline)
            (after_plan,),   # Second EXPLAIN (with index)
        ]

        result = validate_index_in_tx(
            conn,
            "CREATE INDEX idx_users_email ON users(email);",
            "SELECT * FROM users WHERE email = 'test@example.com'",
            "users"
        )

        assert result["validated"] is True
        assert result["cost_before"] == 1000.0
        assert result["cost_after"] == 250.0
        assert result["cost_delta_pct"] == 75.0  # 75% improvement
        assert "users" in result["table"]

        # Verify transaction usage
        calls = [call[0][0] for call in cursor.execute.call_args_list]
        assert "BEGIN" in calls
        assert "ROLLBACK" in calls
        assert "CREATE INDEX idx_users_email ON users(email);" in calls

    def test_validate_index_in_tx_no_improvement(self, mock_connection):
        """Test index validation when index doesn't improve performance"""
        conn, cursor = mock_connection

        # Mock EXPLAIN results: no improvement
        before_plan = [{"Plan": {"Total Cost": 100.0, "Plan Rows": 100}}]
        after_plan = [{"Plan": {"Total Cost": 105.0, "Plan Rows": 100}}]  # Worse!

        cursor.fetchone.side_effect = [
            (before_plan,),
            (after_plan,),
        ]

        result = validate_index_in_tx(
            conn,
            "CREATE INDEX idx_users_name ON users(name);",
            "SELECT * FROM users WHERE email = 'test@example.com'",
            "users"
        )

        assert result["validated"] is False
        assert result["cost_delta_pct"] < 0  # Negative improvement
        assert "note" in result

    def test_validate_index_in_tx_rollback_on_error(self, mock_connection):
        """Test that transaction is rolled back on error"""
        conn, cursor = mock_connection

        # First EXPLAIN succeeds
        cursor.fetchone.side_effect = [
            ([{"Plan": {"Total Cost": 100.0}}],),
            Exception("Lock timeout"),  # CREATE INDEX fails
        ]

        # Should raise but attempt rollback
        cursor.execute.side_effect = [
            None,  # BEGIN
            None,  # statement_timeout
            None,  # lock_timeout
            None,  # First EXPLAIN
            Exception("Lock timeout"),  # CREATE INDEX fails
        ]

        with pytest.raises(Exception):
            validate_index_in_tx(
                conn,
                "CREATE INDEX idx ON users(email);",
                "SELECT * FROM users",
                "users"
            )

    def test_validate_index_in_tx_row_count_check(self, mock_connection):
        """Test validation skips tables with too many rows"""
        conn, cursor = mock_connection

        # Mock table with 2M rows (exceeds 1M limit)
        before_plan = [{"Plan": {"Total Cost": 1000.0, "Plan Rows": 2000000}}]
        cursor.fetchone.return_value = (before_plan,)

        result = validate_index_in_tx(
            conn,
            "CREATE INDEX idx ON large_table(col);",
            "SELECT * FROM large_table WHERE col = 123",
            "large_table"
        )

        assert result["validated"] is False
        assert "too many rows" in result.get("note", "").lower()

    def test_validate_rewrite_success(self, mock_connection):
        """Test successful query rewrite validation"""
        conn, cursor = mock_connection

        # Mock EXPLAIN results: rewrite improves performance
        original_plan = [{"Plan": {"Total Cost": 500.0, "Plan Rows": 1000}}]
        rewrite_plan = [{"Plan": {"Total Cost": 150.0, "Plan Rows": 1000}}]

        cursor.fetchone.side_effect = [
            (original_plan,),
            (rewrite_plan,),
        ]

        result = validate_rewrite(
            conn,
            "SELECT * FROM users WHERE id > 100",
            "SELECT id, name, email FROM users WHERE id > 100"
        )

        assert result["validated"] is True
        assert result["cost_before"] == 500.0
        assert result["cost_after"] == 150.0
        assert result["cost_delta_pct"] == 70.0  # 70% improvement

    def test_validate_rewrite_no_improvement(self, mock_connection):
        """Test rewrite validation when rewrite doesn't help"""
        conn, cursor = mock_connection

        # Mock EXPLAIN results: no meaningful improvement
        original_plan = [{"Plan": {"Total Cost": 100.0, "Plan Rows": 100}}]
        rewrite_plan = [{"Plan": {"Total Cost": 99.5, "Plan Rows": 100}}]

        cursor.fetchone.side_effect = [
            (original_plan,),
            (rewrite_plan,),
        ]

        result = validate_rewrite(
            conn,
            "SELECT * FROM users",
            "SELECT id, name FROM users"
        )

        assert result["validated"] is False
        assert result["cost_delta_pct"] < 5  # Less than 5% improvement threshold

    def test_validate_rewrite_syntax_error(self, mock_connection):
        """Test rewrite validation handles syntax errors"""
        conn, cursor = mock_connection

        # Original query succeeds, rewrite has syntax error
        cursor.fetchone.side_effect = [
            ([{"Plan": {"Total Cost": 100.0}}],),
        ]
        cursor.execute.side_effect = [
            None,  # Original EXPLAIN succeeds
            Exception("Syntax error near 'FRMO'"),  # Rewrite EXPLAIN fails
        ]

        with pytest.raises(Exception) as exc_info:
            validate_rewrite(
                conn,
                "SELECT * FROM users",
                "SELECT * FRMO users"  # Typo
            )

        assert "Syntax error" in str(exc_info.value)

    def test_validate_rewrite_equivalent_cost(self, mock_connection):
        """Test rewrite validation when costs are equivalent"""
        conn, cursor = mock_connection

        # Mock EXPLAIN results: identical costs
        same_plan = [{"Plan": {"Total Cost": 100.0, "Plan Rows": 100}}]

        cursor.fetchone.side_effect = [
            (same_plan,),
            (same_plan,),
        ]

        result = validate_rewrite(
            conn,
            "SELECT id FROM users WHERE active = true",
            "SELECT id FROM users WHERE active IS true"
        )

        assert result["validated"] is False
        assert result["cost_delta_pct"] == 0.0

    def test_can_validate_suggestion_index(self):
        """Test can_validate_suggestion for index suggestions"""
        assert can_validate_suggestion("index", "CREATE INDEX idx ON users(email);") is True
        assert can_validate_suggestion("index", None) is False
        assert can_validate_suggestion("index", "") is False

    def test_can_validate_suggestion_rewrite(self):
        """Test can_validate_suggestion for rewrite suggestions"""
        assert can_validate_suggestion("rewrite", "SELECT id FROM users;") is True
        assert can_validate_suggestion("rewrite", None) is False

    def test_can_validate_suggestion_config(self):
        """Test can_validate_suggestion for config suggestions"""
        # Config changes can't be validated via EXPLAIN
        assert can_validate_suggestion("config", "SET work_mem = '256MB';") is False

    def test_can_validate_suggestion_note(self):
        """Test can_validate_suggestion for note suggestions"""
        assert can_validate_suggestion("note", "This is just a note") is False
        assert can_validate_suggestion("note", None) is False

    def test_validate_index_concurrent_creation(self, mock_connection):
        """Test validation works with CONCURRENTLY option"""
        conn, cursor = mock_connection

        before_plan = [{"Plan": {"Total Cost": 1000.0, "Plan Rows": 1000}}]
        after_plan = [{"Plan": {"Total Cost": 200.0, "Plan Rows": 1000}}]

        cursor.fetchone.side_effect = [
            (before_plan,),
            (after_plan,),
        ]

        result = validate_index_in_tx(
            conn,
            "CREATE INDEX CONCURRENTLY idx_users_email ON users(email);",
            "SELECT * FROM users WHERE email = 'test@example.com'",
            "users"
        )

        assert result["validated"] is True
        assert result["cost_delta_pct"] == 80.0

    def test_validate_index_partial_index(self, mock_connection):
        """Test validation works with partial indexes"""
        conn, cursor = mock_connection

        before_plan = [{"Plan": {"Total Cost": 500.0, "Plan Rows": 100}}]
        after_plan = [{"Plan": {"Total Cost": 50.0, "Plan Rows": 100}}]

        cursor.fetchone.side_effect = [
            (before_plan,),
            (after_plan,),
        ]

        result = validate_index_in_tx(
            conn,
            "CREATE INDEX idx_active_users ON users(email) WHERE active = true;",
            "SELECT * FROM users WHERE email = 'test@example.com' AND active = true",
            "users"
        )

        assert result["validated"] is True
        assert result["cost_delta_pct"] == 90.0
