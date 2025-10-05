# tests/test_services_guardrails.py
"""
Tests for guardrails services (SQL safety checks)
"""
import pytest
from app.services.guardrails import (
    check_sql_safety,
    check_risk_level,
    validate_suggestion_for_apply,
    sanitize_sql
)


class TestGuardrailsServices:
    """Test suite for guardrails/safety checks"""

    def test_check_sql_safety_drop_table(self):
        """Test that DROP TABLE is blocked"""
        safe, reason = check_sql_safety("DROP TABLE users;", "index")
        assert safe is False
        assert "DROP TABLE" in reason

    def test_check_sql_safety_drop_database(self):
        """Test that DROP DATABASE is blocked"""
        safe, reason = check_sql_safety("DROP DATABASE production;", "config")
        assert safe is False
        assert "DROP DATABASE" in reason

    def test_check_sql_safety_truncate(self):
        """Test that TRUNCATE is blocked"""
        safe, reason = check_sql_safety("TRUNCATE TABLE users;", "cleanup")
        assert safe is False
        assert "TRUNCATE" in reason

    def test_check_sql_safety_delete_without_where(self):
        """Test that DELETE without WHERE is blocked"""
        safe, reason = check_sql_safety("DELETE FROM users;", "cleanup")
        assert safe is False
        assert "DELETE without WHERE" in reason

    def test_check_sql_safety_delete_with_where(self):
        """Test that DELETE with WHERE is allowed"""
        safe, reason = check_sql_safety("DELETE FROM users WHERE id = 123;", "cleanup")
        assert safe is True
        assert reason == ""

    def test_check_sql_safety_update_without_where(self):
        """Test that UPDATE without WHERE is blocked"""
        safe, reason = check_sql_safety("UPDATE users SET active = false;", "config")
        assert safe is False
        assert "UPDATE without WHERE" in reason

    def test_check_sql_safety_update_with_where(self):
        """Test that UPDATE with WHERE is allowed"""
        safe, reason = check_sql_safety("UPDATE users SET active = false WHERE id = 123;", "config")
        assert safe is True

    def test_check_sql_safety_create_index(self):
        """Test that CREATE INDEX is allowed"""
        safe, reason = check_sql_safety("CREATE INDEX idx_users_email ON users(email);", "index")
        assert safe is True
        assert reason == ""

    def test_check_sql_safety_create_unique_index(self):
        """Test that CREATE UNIQUE INDEX is allowed"""
        safe, reason = check_sql_safety("CREATE UNIQUE INDEX idx_email ON users(email);", "index")
        assert safe is True

    def test_check_sql_safety_select_query(self):
        """Test that SELECT queries are allowed"""
        safe, reason = check_sql_safety("SELECT * FROM users WHERE email = 'test@example.com';", "rewrite")
        assert safe is True

    def test_check_sql_safety_set_command(self):
        """Test that SET commands are allowed for config category"""
        safe, reason = check_sql_safety("SET work_mem = '256MB';", "config")
        assert safe is True

    def test_check_sql_safety_alter_table(self):
        """Test that ALTER TABLE is blocked for non-partition category"""
        safe, reason = check_sql_safety("ALTER TABLE users ADD COLUMN new_col VARCHAR(255);", "index")
        assert safe is False
        assert "ALTER TABLE" in reason

    def test_check_sql_safety_alter_table_partition(self):
        """Test that ALTER TABLE is allowed for partition category"""
        safe, reason = check_sql_safety("ALTER TABLE orders ATTACH PARTITION orders_2024;", "partition")
        assert safe is True

    def test_check_sql_safety_case_insensitive(self):
        """Test that safety checks are case-insensitive"""
        safe1, _ = check_sql_safety("drop table users;", "index")
        safe2, _ = check_sql_safety("DROP TABLE users;", "index")
        safe3, _ = check_sql_safety("DrOp TaBlE users;", "index")

        assert safe1 is False
        assert safe2 is False
        assert safe3 is False

    def test_check_risk_level_validated_index(self):
        """Test risk level for validated index"""
        risk = check_risk_level(
            "CREATE INDEX idx ON users(email);",
            "index",
            validated=True
        )
        assert risk == "low"

    def test_check_risk_level_unvalidated_index(self):
        """Test risk level for unvalidated index"""
        risk = check_risk_level(
            "CREATE INDEX idx ON users(email);",
            "index",
            validated=False
        )
        assert risk == "medium"

    def test_check_risk_level_drop_index(self):
        """Test risk level for DROP INDEX"""
        risk = check_risk_level(
            "DROP INDEX idx_users_email;",
            "index",
            validated=False
        )
        assert risk == "high"

    def test_check_risk_level_rewrite(self):
        """Test risk level for query rewrite"""
        risk = check_risk_level(
            "SELECT id, name FROM users WHERE active = true;",
            "rewrite",
            validated=True
        )
        assert risk == "low"

    def test_check_risk_level_config_change(self):
        """Test risk level for config changes"""
        risk = check_risk_level(
            "SET work_mem = '256MB';",
            "config",
            validated=False
        )
        assert risk == "medium"

    def test_check_risk_level_alter_table(self):
        """Test risk level for ALTER TABLE"""
        risk = check_risk_level(
            "ALTER TABLE users ADD COLUMN new_col VARCHAR(255);",
            "partition",
            validated=False
        )
        assert risk == "high"

    def test_check_risk_level_delete_with_where(self):
        """Test risk level for DELETE with WHERE"""
        risk = check_risk_level(
            "DELETE FROM users WHERE id = 123;",
            "cleanup",
            validated=False
        )
        assert risk == "medium"

    def test_check_risk_level_update_with_where(self):
        """Test risk level for UPDATE with WHERE"""
        risk = check_risk_level(
            "UPDATE users SET active = false WHERE id = 123;",
            "config",
            validated=False
        )
        assert risk == "medium"

    def test_validate_suggestion_for_apply_safe_index_dry_run(self):
        """Test validation for safe index in dry-run mode"""
        can_apply, reason = validate_suggestion_for_apply(
            "idx_001",
            "CREATE INDEX idx_users_email ON users(email);",
            "index",
            "low",
            dry_run=True
        )
        assert can_apply is True
        assert reason == ""

    def test_validate_suggestion_for_apply_safe_index_real(self):
        """Test validation for safe validated index in real mode"""
        can_apply, reason = validate_suggestion_for_apply(
            "idx_001",
            "CREATE INDEX idx_users_email ON users(email);",
            "index",
            "low",
            dry_run=False
        )
        assert can_apply is True

    def test_validate_suggestion_for_apply_medium_risk_no_dry_run(self):
        """Test validation blocks medium-risk operations without dry-run"""
        can_apply, reason = validate_suggestion_for_apply(
            "idx_002",
            "CREATE INDEX idx_users_name ON users(name);",
            "index",
            "medium",
            dry_run=False
        )
        assert can_apply is False
        assert "dry-run" in reason.lower()

    def test_validate_suggestion_for_apply_high_risk_blocked(self):
        """Test validation blocks high-risk operations"""
        can_apply, reason = validate_suggestion_for_apply(
            "drop_001",
            "DROP INDEX idx_users_old;",
            "index",
            "high",
            dry_run=False
        )
        assert can_apply is False
        assert "high-risk" in reason.lower()

    def test_validate_suggestion_for_apply_high_risk_dry_run_allowed(self):
        """Test validation allows high-risk operations in dry-run mode"""
        can_apply, reason = validate_suggestion_for_apply(
            "drop_001",
            "DROP INDEX idx_users_old;",
            "index",
            "high",
            dry_run=True
        )
        assert can_apply is True

    def test_validate_suggestion_for_apply_unsafe_sql(self):
        """Test validation blocks unsafe SQL patterns"""
        can_apply, reason = validate_suggestion_for_apply(
            "unsafe_001",
            "DROP TABLE users;",
            "cleanup",
            "low",
            dry_run=True
        )
        assert can_apply is False
        assert "DROP TABLE" in reason

    def test_validate_suggestion_for_apply_delete_without_where(self):
        """Test validation blocks DELETE without WHERE"""
        can_apply, reason = validate_suggestion_for_apply(
            "delete_001",
            "DELETE FROM old_logs;",
            "cleanup",
            "low",
            dry_run=False
        )
        assert can_apply is False
        assert "DELETE without WHERE" in reason

    def test_validate_suggestion_for_apply_empty_sql(self):
        """Test validation handles empty SQL"""
        can_apply, reason = validate_suggestion_for_apply(
            "empty_001",
            "",
            "note",
            "low",
            dry_run=False
        )
        assert can_apply is False
        assert "empty" in reason.lower() or "no sql" in reason.lower()

    def test_validate_suggestion_for_apply_none_sql(self):
        """Test validation handles None SQL"""
        can_apply, reason = validate_suggestion_for_apply(
            "none_001",
            None,
            "note",
            "low",
            dry_run=False
        )
        assert can_apply is False

    def test_sanitize_sql_basic(self):
        """Test basic SQL sanitization"""
        sanitized = sanitize_sql("SELECT * FROM users;")
        assert sanitized == "SELECT * FROM users;"

    def test_sanitize_sql_removes_comments(self):
        """Test that SQL sanitization removes comments"""
        sql = """
        -- This is a comment
        SELECT * FROM users; -- Inline comment
        """
        sanitized = sanitize_sql(sql)
        assert "--" not in sanitized
        assert "SELECT * FROM users;" in sanitized

    def test_sanitize_sql_removes_multiline_comments(self):
        """Test that SQL sanitization removes multiline comments"""
        sql = """
        /* This is a
           multiline comment */
        SELECT * FROM users;
        """
        sanitized = sanitize_sql(sql)
        assert "/*" not in sanitized
        assert "*/" not in sanitized
        assert "SELECT * FROM users;" in sanitized

    def test_sanitize_sql_trims_whitespace(self):
        """Test that SQL sanitization trims excess whitespace"""
        sql = "  SELECT   *   FROM   users  ;  "
        sanitized = sanitize_sql(sql)
        assert sanitized.strip() == sanitized
        assert "  " not in sanitized or sanitized.count("  ") < sql.count("  ")

    def test_sanitize_sql_handles_semicolons(self):
        """Test that SQL sanitization handles multiple semicolons"""
        sql = "SELECT * FROM users;;;"
        sanitized = sanitize_sql(sql)
        # Should normalize to single semicolon or remove trailing ones
        assert sanitized.count(";;;") == 0

    def test_check_risk_level_concurrent_index(self):
        """Test risk level for CONCURRENTLY index creation"""
        risk = check_risk_level(
            "CREATE INDEX CONCURRENTLY idx_users_email ON users(email);",
            "index",
            validated=False
        )
        # CONCURRENTLY is safer (non-blocking) so might be lower risk
        assert risk in ["low", "medium"]

    def test_validate_suggestion_for_apply_rewrite_always_safe(self):
        """Test that SELECT rewrites are always considered safe"""
        can_apply, reason = validate_suggestion_for_apply(
            "rewrite_001",
            "SELECT id, name FROM users WHERE active = true;",
            "rewrite",
            "low",
            dry_run=False
        )
        assert can_apply is True

    def test_validate_suggestion_for_apply_config_medium_risk(self):
        """Test that config changes require validation"""
        can_apply, reason = validate_suggestion_for_apply(
            "config_001",
            "SET work_mem = '1GB';",
            "config",
            "medium",
            dry_run=False
        )
        # Medium risk config should require dry-run first
        assert can_apply is False

    def test_validate_suggestion_for_apply_partition_operations(self):
        """Test validation for partition operations"""
        can_apply, reason = validate_suggestion_for_apply(
            "part_001",
            "ALTER TABLE orders ATTACH PARTITION orders_2024_q1;",
            "partition",
            "medium",
            dry_run=True
        )
        assert can_apply is True

    def test_check_sql_safety_multiple_statements(self):
        """Test safety check for multiple statements"""
        sql = "CREATE INDEX idx1 ON users(email); CREATE INDEX idx2 ON users(name);"
        safe, reason = check_sql_safety(sql, "index")
        # Should handle multiple statements
        assert safe is True or "multiple statements" in reason.lower()

    def test_check_risk_level_note_category(self):
        """Test risk level for note category"""
        risk = check_risk_level(
            "This is just a performance note",
            "note",
            validated=False
        )
        assert risk == "low"  # Notes should always be low risk

    def test_validate_suggestion_for_apply_validated_reduces_risk(self):
        """Test that validated suggestions get lower risk assessment"""
        # Same SQL, different validation status
        unvalidated_can_apply, _ = validate_suggestion_for_apply(
            "idx_001",
            "CREATE INDEX idx_users_email ON users(email);",
            "index",
            "medium",
            dry_run=False
        )

        validated_can_apply, _ = validate_suggestion_for_apply(
            "idx_002",
            "CREATE INDEX idx_users_email ON users(email);",
            "index",
            "low",  # Validated suggestions marked as low risk
            dry_run=False
        )

        assert validated_can_apply is True
        assert unvalidated_can_apply is False
