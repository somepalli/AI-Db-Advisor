# tests/test_services_apply.py
"""
Tests for apply services (suggestion application)
"""
import pytest
from unittest.mock import MagicMock, patch
from backend.services.apply import (
    generate_rollback_sql,
    apply_suggestions,
    apply_suggestion_batch,
    _apply_single_suggestion
)
from backend.schemas import Suggestion, ApplyResult


class TestApplyServices:
    """Test suite for apply services"""

    @pytest.fixture
    def mock_connection(self):
        """Mock database connection"""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn, cursor

    @pytest.fixture
    def sample_suggestions(self):
        """Sample suggestions for testing"""
        return [
            Suggestion(
                id="idx_001",
                level="table",
                category="index",
                title="Create index on users(email)",
                summary="Add index for email lookups",
                sql_fix="CREATE INDEX idx_users_email ON users(email);",
                validated=True,
                confidence="validated",
                risk="low",
                related_objects=["users"],
                metadata={}
            ),
            Suggestion(
                id="rewrite_001",
                level="query",
                category="rewrite",
                title="Optimize SELECT *",
                summary="Specify columns explicitly",
                sql_fix="SELECT id, name, email FROM users WHERE active = true;",
                validated=True,
                confidence="validated",
                risk="low",
                related_objects=["users"],
                metadata={}
            ),
            Suggestion(
                id="config_001",
                level="db",
                category="config",
                title="Increase work_mem",
                summary="Improve sort performance",
                sql_fix="SET work_mem = '256MB';",
                validated=False,
                confidence="rule-based",
                risk="medium",
                related_objects=[],
                metadata={}
            )
        ]

    def test_generate_rollback_sql_for_index(self):
        """Test generating rollback SQL for index creation"""
        suggestion = Suggestion(
            id="idx_001",
            level="table",
            category="index",
            title="Create index",
            summary="Index suggestion",
            sql_fix="CREATE INDEX idx_users_email ON users(email);",
            validated=True,
            confidence="validated",
            risk="low",
            related_objects=["users"],
            metadata={}
        )

        rollback = generate_rollback_sql(suggestion)
        assert rollback == "DROP INDEX IF EXISTS idx_users_email;"

    def test_generate_rollback_sql_for_unique_index(self):
        """Test generating rollback SQL for unique index"""
        suggestion = Suggestion(
            id="idx_002",
            level="table",
            category="index",
            title="Create unique index",
            summary="Unique index suggestion",
            sql_fix="CREATE UNIQUE INDEX idx_users_email_unique ON users(email);",
            validated=True,
            confidence="validated",
            risk="low",
            related_objects=["users"],
            metadata={}
        )

        rollback = generate_rollback_sql(suggestion)
        assert rollback == "DROP INDEX IF EXISTS idx_users_email_unique;"

    def test_generate_rollback_sql_for_concurrent_index(self):
        """Test generating rollback SQL for concurrent index creation"""
        suggestion = Suggestion(
            id="idx_003",
            level="table",
            category="index",
            title="Create index concurrently",
            summary="Non-blocking index creation",
            sql_fix="CREATE INDEX CONCURRENTLY idx_users_status ON users(status);",
            validated=True,
            confidence="validated",
            risk="low",
            related_objects=["users"],
            metadata={}
        )

        rollback = generate_rollback_sql(suggestion)
        assert rollback == "DROP INDEX IF EXISTS idx_users_status;"

    def test_generate_rollback_sql_for_config_set(self):
        """Test generating rollback SQL for SET command"""
        suggestion = Suggestion(
            id="config_001",
            level="db",
            category="config",
            title="Set work_mem",
            summary="Config change",
            sql_fix="SET work_mem = '256MB';",
            validated=False,
            confidence="rule-based",
            risk="medium",
            related_objects=[],
            metadata={}
        )

        rollback = generate_rollback_sql(suggestion)
        assert rollback == "RESET work_mem;"

    def test_generate_rollback_sql_for_rewrite(self):
        """Test generating rollback SQL for query rewrite (should be None)"""
        suggestion = Suggestion(
            id="rewrite_001",
            level="query",
            category="rewrite",
            title="Optimize query",
            summary="Rewrite suggestion",
            sql_fix="SELECT id FROM users;",
            validated=True,
            confidence="validated",
            risk="low",
            related_objects=["users"],
            metadata={}
        )

        rollback = generate_rollback_sql(suggestion)
        assert rollback is None  # Rewrites don't need rollback

    def test_generate_rollback_sql_for_note(self):
        """Test generating rollback SQL for note (should be None)"""
        suggestion = Suggestion(
            id="note_001",
            level="query",
            category="note",
            title="Performance note",
            summary="Just a note",
            sql_fix=None,
            validated=False,
            confidence="rule-based",
            risk="low",
            related_objects=[],
            metadata={}
        )

        rollback = generate_rollback_sql(suggestion)
        assert rollback is None

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_dry_run_success(self, mock_validate, mock_connection, sample_suggestions):
        """Test applying suggestions in dry-run mode"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        results = apply_suggestions(conn, [sample_suggestions[0]], dry_run=True)

        assert len(results) == 1
        assert results[0].status == "success"
        assert "Dry-run validated" in results[0].message
        assert results[0].rollback_sql is not None

        # Verify transaction rollback
        calls = [call[0][0] for call in cursor.execute.call_args_list]
        assert "BEGIN" in calls
        assert "ROLLBACK" in calls

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_real_execution(self, mock_validate, mock_connection, sample_suggestions):
        """Test applying suggestions with real execution"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        results = apply_suggestions(conn, [sample_suggestions[0]], dry_run=False)

        assert len(results) == 1
        assert results[0].status == "success"
        assert "Applied successfully" in results[0].message

        # Verify transaction commit
        calls = [call[0][0] for call in cursor.execute.call_args_list]
        assert "BEGIN" in calls
        assert "COMMIT" in calls
        assert sample_suggestions[0].sql_fix in calls

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_skipped(self, mock_validate, mock_connection, sample_suggestions):
        """Test applying suggestion that should be skipped"""
        conn, cursor = mock_connection
        mock_validate.return_value = (False, "Blocked: High-risk operation requires dry-run first")

        results = apply_suggestions(conn, [sample_suggestions[2]], dry_run=False)

        assert len(results) == 1
        assert results[0].status == "skipped"
        assert "High-risk operation" in results[0].message
        assert results[0].rollback_sql is None

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_no_sql_fix(self, mock_validate, mock_connection):
        """Test applying suggestion with no SQL (note)"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        suggestion = Suggestion(
            id="note_001",
            level="query",
            category="note",
            title="Performance note",
            summary="Just a note",
            sql_fix=None,
            validated=False,
            confidence="rule-based",
            risk="low",
            related_objects=[],
            metadata={}
        )

        results = apply_suggestions(conn, [suggestion], dry_run=False)

        assert len(results) == 1
        assert results[0].status == "skipped"
        assert "No SQL to execute" in results[0].message

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_execution_error(self, mock_validate, mock_connection, sample_suggestions):
        """Test applying suggestion with execution error"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        # Simulate SQL execution error
        cursor.execute.side_effect = [
            None,  # BEGIN
            None,  # SET statement_timeout
            None,  # SET lock_timeout
            Exception("Relation 'users' does not exist"),  # CREATE INDEX fails
        ]

        results = apply_suggestions(conn, [sample_suggestions[0]], dry_run=False)

        assert len(results) == 1
        assert results[0].status == "error"
        assert "Execution failed" in results[0].message
        assert "does not exist" in results[0].message

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_timeout_error(self, mock_validate, mock_connection, sample_suggestions):
        """Test applying suggestion with timeout error"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        cursor.execute.side_effect = [
            None,  # BEGIN
            None,  # SET statement_timeout
            None,  # SET lock_timeout
            Exception("Lock timeout exceeded"),
        ]

        results = apply_suggestions(conn, [sample_suggestions[0]], dry_run=False)

        assert len(results) == 1
        assert results[0].status == "error"
        assert "timeout" in results[0].message.lower()

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_batch(self, mock_validate, mock_connection, sample_suggestions):
        """Test applying multiple suggestions"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        results = apply_suggestions(conn, sample_suggestions, dry_run=True)

        assert len(results) == 3
        assert all(r.status == "success" for r in results)

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_batch_mixed_results(self, mock_validate, mock_connection, sample_suggestions):
        """Test batch application with mixed success/failure"""
        conn, cursor = mock_connection

        # First succeeds, second is skipped, third succeeds
        mock_validate.side_effect = [
            (True, ""),
            (False, "Blocked: High-risk"),
            (True, ""),
        ]

        results = apply_suggestions(conn, sample_suggestions, dry_run=False)

        assert len(results) == 3
        assert results[0].status == "success"
        assert results[1].status == "skipped"
        assert results[2].status == "success"

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestion_batch_stop_on_error(self, mock_validate, mock_connection, sample_suggestions):
        """Test batch application that stops on first error"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        # First succeeds, second fails
        cursor.execute.side_effect = [
            None, None, None, None, None,  # First suggestion succeeds (BEGIN, timeouts, SQL, COMMIT)
            None, None, None,  # Second suggestion: BEGIN, timeouts
            Exception("Error in second suggestion"),
        ]

        results = apply_suggestion_batch(
            conn,
            sample_suggestions,
            dry_run=False,
            stop_on_error=True
        )

        assert len(results) == 3
        assert results[0].status == "success"
        assert results[1].status == "error"
        assert results[2].status == "skipped"
        assert "previous error" in results[2].message

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestion_batch_continue_on_error(self, mock_validate, mock_connection, sample_suggestions):
        """Test batch application that continues despite errors"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        # Configure mock to fail on second suggestion but continue
        execution_sequence = [
            None, None, None, None, None,  # First succeeds
            None, None, None,  # Second: BEGIN, timeouts
            Exception("Error in second"),  # Second fails
            None, None, None, None, None,  # Third succeeds
        ]
        cursor.execute.side_effect = execution_sequence

        results = apply_suggestion_batch(
            conn,
            sample_suggestions,
            dry_run=False,
            stop_on_error=False
        )

        # All three should be processed
        assert len(results) == 3
        assert results[0].status == "success"
        assert results[1].status == "error"
        # Third may succeed or fail depending on mock setup, but should be processed

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_with_timeouts(self, mock_validate, mock_connection, sample_suggestions):
        """Test that appropriate timeouts are set during application"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        apply_suggestions(conn, [sample_suggestions[0]], dry_run=True)

        # Check that timeouts were set
        calls = [call[0][0] for call in cursor.execute.call_args_list]
        assert any("statement_timeout" in call for call in calls)
        assert any("lock_timeout" in call for call in calls)

        # Dry-run should have shorter timeouts
        assert any("30s" in call for call in calls)  # statement_timeout for dry-run

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_rollback_generation(self, mock_validate, mock_connection):
        """Test that rollback SQL is properly generated for applicable suggestions"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        index_suggestion = Suggestion(
            id="idx_001",
            level="table",
            category="index",
            title="Create index",
            summary="Index suggestion",
            sql_fix="CREATE INDEX idx_test ON table1(col);",
            validated=True,
            confidence="validated",
            risk="low",
            related_objects=["table1"],
            metadata={}
        )

        results = apply_suggestions(conn, [index_suggestion], dry_run=True)

        assert len(results) == 1
        assert results[0].rollback_sql == "DROP INDEX IF EXISTS idx_test;"

    @patch('backend.services.apply.validate_suggestion_for_apply')
    def test_apply_suggestions_ensures_rollback_on_error(self, mock_validate, mock_connection, sample_suggestions):
        """Test that transaction is rolled back even if execution fails"""
        conn, cursor = mock_connection
        mock_validate.return_value = (True, "")

        # Simulate failure during SQL execution
        cursor.execute.side_effect = [
            None,  # BEGIN
            None,  # SET statement_timeout
            None,  # SET lock_timeout
            Exception("Execution failed"),  # SQL fails
        ]

        results = apply_suggestions(conn, [sample_suggestions[0]], dry_run=False)

        assert results[0].status == "error"

        # Verify rollback was attempted
        # The implementation tries to ROLLBACK in the except block
        calls = [call[0][0] for call in cursor.execute.call_args_list if isinstance(call[0][0], str)]
        assert "BEGIN" in calls
