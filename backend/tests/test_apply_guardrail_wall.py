# tests/test_apply_guardrail_wall.py
"""
Stage 1 tests: enforce the guardrail wall inside apply.py's execution path.

Core invariant (PostgreSQL): a destructive statement
(DROP / TRUNCATE / DELETE / unqualified-UPDATE / DROP COLUMN / CASCADE) must
NEVER reach cursor.execute from any apply path — it is rejected at the wall
before any dry-run or real execution, with alert=True.
"""
import pytest
from unittest.mock import MagicMock

from backend.services.apply import _apply_single_suggestion, apply_suggestions
from backend.schemas import Suggestion


def make_conn():
    """Mock connection whose cursor records every execute() call."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def executed_statements(cursor):
    return [c.args[0] for c in cursor.execute.call_args_list if c.args]


def sug(sql, *, category="cleanup", risk="low", sid="s1"):
    return Suggestion(
        id=sid, level="table", category=category,
        title="t", summary="s", sql_fix=sql,
        validated=True, confidence="validated", risk=risk,
        related_objects=["students"], metadata={},
    )


DESTRUCTIVE = [
    "DROP TABLE students;",
    "TRUNCATE enrollments;",
    "DELETE FROM students;",                  # unqualified
    "DELETE FROM students WHERE id = 1;",     # qualified — still walled off
    "UPDATE students SET gpa = 0;",           # unqualified UPDATE
    "ALTER TABLE students DROP COLUMN gpa;",
    "DROP TABLE students CASCADE;",
    "DROP TABLE students; -- cleanup",        # comment-smuggled
]


class TestWallBlocksDestructive:
    @pytest.mark.parametrize("sql", DESTRUCTIVE)
    @pytest.mark.parametrize("dry_run", [True, False])
    @pytest.mark.parametrize("is_agentic", [True, False])
    def test_destructive_never_executes(self, sql, dry_run, is_agentic):
        conn, cursor = make_conn()
        result = _apply_single_suggestion(
            conn, sug(sql), dry_run=dry_run, db_type="postgres",
            is_agentic=is_agentic,
        )
        assert result.status == "error"
        assert result.alert is True
        assert "guardrail wall" in result.message.lower()
        # The destructive statement must never have hit the cursor.
        stmts = executed_statements(cursor)
        assert sql not in stmts
        # In fact the cursor is never even opened for a walled statement.
        conn.cursor.assert_not_called()

    def test_qualified_delete_blocked_proves_new_wall(self):
        # A qualified DELETE in a non-"rewrite" category passes the LEGACY
        # check but is stopped by the new wall — proving the wall is active.
        from backend.services.guardrails import check_sql_safety
        legacy_safe, _ = check_sql_safety("DELETE FROM students WHERE id = 1;", "cleanup")
        assert legacy_safe is True  # legacy would have allowed it
        conn, cursor = make_conn()
        result = _apply_single_suggestion(
            conn, sug("DELETE FROM students WHERE id = 1;"),
            dry_run=True, db_type="postgres",
        )
        assert result.status == "error"
        assert result.alert is True
        conn.cursor.assert_not_called()


class TestWallAllowsSafe:
    def test_concurrent_index_dry_run_executes(self):
        conn, cursor = make_conn()
        sql = "CREATE INDEX CONCURRENTLY idx_email ON students(email);"
        result = _apply_single_suggestion(
            conn, sug(sql, category="index"), dry_run=True, db_type="postgres",
        )
        assert result.status == "success"
        assert sql in executed_statements(cursor)

    def test_note_without_sql_is_skipped_not_walled(self):
        conn, cursor = make_conn()
        s = Suggestion(
            id="n1", level="db", category="note", title="t", summary="s",
            sql_fix=None, validated=False, confidence="ai-heuristic",
            risk="low", related_objects=[], metadata={},
        )
        result = _apply_single_suggestion(conn, s, dry_run=True, db_type="postgres")
        assert result.status == "skipped"
        assert result.alert is False


class TestElevatedPath:
    GRANT = "GRANT SELECT ON students TO analyst;"  # unclassified -> REQUIRE_ELEVATED (non-agentic)

    def test_elevated_refused_without_confirmation(self):
        conn, cursor = make_conn()
        result = _apply_single_suggestion(
            conn, sug(self.GRANT), dry_run=True, db_type="postgres",
            is_agentic=False,
        )
        assert result.status == "error"
        assert "elevated review required" in result.message.lower()
        conn.cursor.assert_not_called()

    def test_elevated_denied_on_agentic_path(self):
        # On the agentic path, unknown statements are hard-denied, not elevated.
        conn, cursor = make_conn()
        result = _apply_single_suggestion(
            conn, sug(self.GRANT), dry_run=True, db_type="postgres",
            is_agentic=True,
        )
        assert result.status == "error"
        assert result.alert is True
        conn.cursor.assert_not_called()

    def test_elevated_proceeds_with_confirmation_and_object_name(self):
        conn, cursor = make_conn()
        result = _apply_single_suggestion(
            conn, sug(self.GRANT), dry_run=True, db_type="postgres",
            is_agentic=False,
            elevated_confirmation=True, elevated_object_name="students",
        )
        # Passes the wall and reaches execution (dry-run validated).
        assert result.status == "success"
        assert self.GRANT in executed_statements(cursor)


class TestBatchThreadsAgenticFlag:
    def test_batch_blocks_destructive(self):
        conn, _ = make_conn()
        results = apply_suggestions(
            conn,
            [sug("DROP TABLE students;", sid="a"), sug("ANALYZE students;", category="config", sid="b")],
            dry_run=True, db_type="postgres", is_agentic=True,
        )
        by_id = {r.id: r for r in results}
        assert by_id["a"].status == "error" and by_id["a"].alert is True
