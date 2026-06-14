# tests/test_agent_guardrails.py
"""
Stage 0 tests for the agentic guardrail wall (PostgreSQL-focused).

Covers the plan's required cases:
  - DROP / TRUNCATE / DELETE / unqualified-UPDATE / DROP COLUMN / CASCADE /
    FLUSHALL  -> DENY with alert=True
  - CREATE INDEX [CONCURRENTLY], ANALYZE, SET -> REQUIRE_APPROVAL
  - EXPLAIN-without-ANALYZE and pg_stat SELECTs -> ALLOW
  - comment-smuggled `DROP TABLE x; -- comment` -> DENY
  - unclassified `SELECT col FROM t` on the agentic path -> DENY

These guardrails are NOT yet wired into any execution path (Stage 0).
"""
import pytest

from backend.services.agent_guardrails import (
    evaluate,
    classify_statement,
    GuardrailDecision,
    RiskClass,
)
from backend.services.agent_tool_policy import (
    build_agent_toolset,
    screen_proposed_action,
)


# (sql, expected_decision, expected_alert) on the agentic path
DESTRUCTIVE_CASES = [
    ("DROP TABLE students;",                              GuardrailDecision.DENY, True),
    ("DROP DATABASE university;",                         GuardrailDecision.DENY, True),
    ("DROP SCHEMA public;",                               GuardrailDecision.DENY, True),
    ("DROP VIEW v_active_students;",                      GuardrailDecision.DENY, True),
    ("DROP MATERIALIZED VIEW mv_stats;",                  GuardrailDecision.DENY, True),
    ("TRUNCATE enrollments;",                             GuardrailDecision.DENY, True),
    ("DELETE FROM students;",                             GuardrailDecision.DENY, True),
    ("DELETE FROM students WHERE id = 1;",                GuardrailDecision.DENY, True),  # all DELETE walled off
    ("UPDATE students SET gpa = 0;",                      GuardrailDecision.DENY, True),  # unqualified UPDATE
    ("ALTER TABLE students DROP COLUMN gpa;",             GuardrailDecision.DENY, True),
    ("DROP TABLE students CASCADE;",                      GuardrailDecision.DENY, True),
    ("DROP TABLE students; -- cleanup",                   GuardrailDecision.DENY, True),  # comment-smuggled
    ("DROP TABLE students; /* drop it */",                GuardrailDecision.DENY, True),
    ("FLUSHALL",                                          GuardrailDecision.DENY, True),
    ("FLUSHDB",                                           GuardrailDecision.DENY, True),
    ("DROP KEYSPACE university;",                         GuardrailDecision.DENY, True),
]

APPROVAL_CASES = [
    "CREATE INDEX CONCURRENTLY idx_email ON students(email);",
    "CREATE INDEX idx_email ON students(email);",
    "CREATE UNIQUE INDEX idx_email ON students(email);",
    "ANALYZE students;",
    "SET work_mem = '256MB';",
    "VACUUM students;",
    "ALTER TABLE students ADD COLUMN gpa numeric;",
]

ALLOW_CASES = [
    "EXPLAIN SELECT * FROM students;",
    "SELECT * FROM pg_stat_user_indexes;",
    "SELECT relname FROM pg_class;",
    "SHOW work_mem;",
]


class TestAgenticWallDestructive:
    @pytest.mark.parametrize("sql,decision,alert", DESTRUCTIVE_CASES)
    def test_destructive_denied_with_alert(self, sql, decision, alert):
        r = evaluate(sql, agentic=True)
        assert r.decision is decision, f"{sql!r} -> {r.decision}"
        assert r.alert is alert, f"{sql!r} alert should be {alert}"
        assert r.risk_class is RiskClass.DESTRUCTIVE

    @pytest.mark.parametrize("sql,decision,alert", DESTRUCTIVE_CASES)
    def test_destructive_denied_on_human_path_too(self, sql, decision, alert):
        # The wall blocks destructive verbs even on the non-agentic path.
        r = evaluate(sql, agentic=False)
        assert r.decision is GuardrailDecision.DENY
        assert r.alert is True


class TestAgenticWallApproval:
    @pytest.mark.parametrize("sql", APPROVAL_CASES)
    def test_safe_and_impactful_require_approval(self, sql):
        r = evaluate(sql, agentic=True)
        assert r.decision is GuardrailDecision.REQUIRE_APPROVAL, f"{sql!r} -> {r.decision}"
        assert r.risk_class in {RiskClass.SAFE_WRITE, RiskClass.IMPACTFUL_WRITE}

    def test_concurrent_index_is_safe_write(self):
        r = evaluate("CREATE INDEX CONCURRENTLY idx ON students(email);", agentic=True)
        assert r.risk_class is RiskClass.SAFE_WRITE

    def test_plain_index_is_impactful_write(self):
        r = evaluate("CREATE INDEX idx ON students(email);", agentic=True)
        assert r.risk_class is RiskClass.IMPACTFUL_WRITE


class TestAgenticWallAllow:
    @pytest.mark.parametrize("sql", ALLOW_CASES)
    def test_metadata_reads_allowed(self, sql):
        r = evaluate(sql, agentic=True)
        assert r.decision is GuardrailDecision.ALLOW, f"{sql!r} -> {r.decision}"
        assert r.risk_class is RiskClass.METADATA_READ
        assert r.alert is False


class TestUnknownStatements:
    def test_unknown_select_denied_on_agentic_path(self):
        # A plain row-reading SELECT is NOT a recognized metadata read -> UNKNOWN -> DENY.
        r = evaluate("SELECT name, email FROM students;", agentic=True)
        assert r.decision is GuardrailDecision.DENY
        assert r.risk_class is RiskClass.UNKNOWN
        assert r.alert is True

    def test_unknown_requires_elevated_on_human_path(self):
        r = evaluate("SELECT name, email FROM students;", agentic=False)
        assert r.decision is GuardrailDecision.REQUIRE_ELEVATED
        assert r.require_typed_confirmation is True

    def test_classify_unknown(self):
        assert classify_statement("SELECT name FROM students;") is RiskClass.UNKNOWN


class TestAgentToolPolicy:
    def test_toolset_is_metadata_only(self):
        tools = build_agent_toolset()
        assert tools, "toolset must not be empty"
        assert not any(t.reads_row_data for t in tools), "no row-reading tools allowed"

    def test_no_arbitrary_sql_tool(self):
        names = {t.name for t in build_agent_toolset()}
        assert not (names & {"execute_sql", "run_query", "raw_sql"})

    def test_screen_allows_index(self):
        ok, _ = screen_proposed_action("CREATE INDEX CONCURRENTLY i ON t(a);")
        assert ok is True

    @pytest.mark.parametrize("sql", ["DROP TABLE t;", "DELETE FROM t;", "TRUNCATE t;"])
    def test_screen_blocks_destructive(self, sql):
        ok, _ = screen_proposed_action(sql)
        assert ok is False

    def test_screen_blocks_unknown_select(self):
        ok, _ = screen_proposed_action("SELECT name FROM students;")
        assert ok is False
