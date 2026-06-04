# tests/test_services_history.py
"""
Tests for history/audit logging services
"""
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from backend.services.history import (
    record_analyze,
    record_apply,
    get_recent_analyses,
    get_recent_applications,
    get_suggestion_history,
    _get_query_fingerprint,
    AUDIT_LOG_FILE
)


class TestHistoryServices:
    """Test suite for audit logging services"""

    @pytest.fixture
    def temp_log_file(self):
        """Create a temporary log file for testing"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    @pytest.fixture(autouse=True)
    def mock_audit_log_file(self, temp_log_file, monkeypatch):
        """Mock the AUDIT_LOG_FILE constant to use temp file"""
        import backend.services.history as history_module
        monkeypatch.setattr(history_module, 'AUDIT_LOG_FILE', temp_log_file)
        return temp_log_file

    def test_get_query_fingerprint_identical_queries(self):
        """Test that identical queries produce the same fingerprint"""
        sql1 = "SELECT * FROM users WHERE email = 'test@example.com'"
        sql2 = "SELECT * FROM users WHERE email = 'test@example.com'"

        fp1 = _get_query_fingerprint(sql1)
        fp2 = _get_query_fingerprint(sql2)

        assert fp1 == fp2
        assert len(fp1) == 16  # Hash is truncated to 16 chars

    def test_get_query_fingerprint_whitespace_normalization(self):
        """Test that whitespace differences are normalized"""
        sql1 = "SELECT * FROM users WHERE email = 'test@example.com'"
        sql2 = "SELECT   *   FROM   users   WHERE   email = 'test@example.com'"
        sql3 = """
        SELECT *
        FROM users
        WHERE email = 'test@example.com'
        """

        fp1 = _get_query_fingerprint(sql1)
        fp2 = _get_query_fingerprint(sql2)
        fp3 = _get_query_fingerprint(sql3)

        assert fp1 == fp2 == fp3

    def test_get_query_fingerprint_case_normalization(self):
        """Test that case differences are normalized"""
        sql1 = "SELECT * FROM users WHERE email = 'test@example.com'"
        sql2 = "select * from users where email = 'test@example.com'"

        fp1 = _get_query_fingerprint(sql1)
        fp2 = _get_query_fingerprint(sql2)

        assert fp1 == fp2

    def test_get_query_fingerprint_different_queries(self):
        """Test that different queries produce different fingerprints"""
        sql1 = "SELECT * FROM users WHERE email = 'test@example.com'"
        sql2 = "SELECT * FROM orders WHERE status = 'pending'"

        fp1 = _get_query_fingerprint(sql1)
        fp2 = _get_query_fingerprint(sql2)

        assert fp1 != fp2

    def test_record_analyze_success(self, temp_log_file):
        """Test recording an analyze event"""
        suggestions = [
            {
                "id": "idx_001",
                "category": "index",
                "validated": True
            },
            {
                "id": "rewrite_001",
                "category": "rewrite",
                "validated": False
            }
        ]
        notes = ["Validated 1/2 suggestions"]

        record_analyze(
            ds_id="test-pg",
            sql="SELECT * FROM users WHERE email = 'test@example.com'",
            suggestions=suggestions,
            include_ai=True,
            duration_ms=150.5,
            notes=notes
        )

        # Read the log file
        with open(temp_log_file, 'r') as f:
            line = f.readline()
            record = json.loads(line)

        assert record["event"] == "analyze"
        assert record["ds_id"] == "test-pg"
        assert record["suggestion_count"] == 2
        assert record["validated_count"] == 1
        assert record["include_ai"] is True
        assert record["duration_ms"] == 150.5
        assert "index" in record["categories"]
        assert "rewrite" in record["categories"]
        assert "query_fingerprint" in record
        assert record["notes"] == notes

    def test_record_analyze_multiple_events(self, temp_log_file):
        """Test recording multiple analyze events"""
        for i in range(3):
            record_analyze(
                ds_id=f"test-pg-{i}",
                sql=f"SELECT * FROM table{i}",
                suggestions=[{"id": f"idx_{i}", "category": "index", "validated": False}],
                include_ai=False,
                duration_ms=100.0 + i,
                notes=[]
            )

        # Read all lines
        with open(temp_log_file, 'r') as f:
            lines = f.readlines()

        assert len(lines) == 3
        for i, line in enumerate(lines):
            record = json.loads(line)
            assert record["ds_id"] == f"test-pg-{i}"
            assert record["duration_ms"] == 100.0 + i

    def test_record_apply_success(self, temp_log_file):
        """Test recording an apply event"""
        results = [
            {"id": "idx_001", "status": "success"},
            {"id": "idx_002", "status": "error"},
            {"id": "idx_003", "status": "skipped"}
        ]
        notes = ["Applied 1/3 suggestions successfully"]

        record_apply(
            ds_id="test-pg",
            suggestion_ids=["idx_001", "idx_002", "idx_003"],
            results=results,
            dry_run=True,
            duration_ms=250.0,
            notes=notes
        )

        # Read the log file
        with open(temp_log_file, 'r') as f:
            line = f.readline()
            record = json.loads(line)

        assert record["event"] == "apply"
        assert record["ds_id"] == "test-pg"
        assert record["suggestion_ids"] == ["idx_001", "idx_002", "idx_003"]
        assert record["dry_run"] is True
        assert record["total_count"] == 3
        assert record["success_count"] == 1
        assert record["error_count"] == 1
        assert record["skipped_count"] == 1
        assert record["duration_ms"] == 250.0
        assert record["notes"] == notes
        assert record["results"] == results

    def test_record_apply_all_success(self, temp_log_file):
        """Test recording apply event with all successes"""
        results = [
            {"id": "idx_001", "status": "success"},
            {"id": "idx_002", "status": "success"}
        ]

        record_apply(
            ds_id="test-pg",
            suggestion_ids=["idx_001", "idx_002"],
            results=results,
            dry_run=False,
            duration_ms=300.0,
            notes=[]
        )

        with open(temp_log_file, 'r') as f:
            record = json.loads(f.readline())

        assert record["success_count"] == 2
        assert record["error_count"] == 0
        assert record["skipped_count"] == 0
        assert record["dry_run"] is False

    def test_get_recent_analyses_empty_log(self, temp_log_file):
        """Test getting recent analyses from empty log"""
        analyses = get_recent_analyses()
        assert analyses == []

    def test_get_recent_analyses_with_data(self, temp_log_file):
        """Test getting recent analyses"""
        # Record some events
        for i in range(5):
            record_analyze(
                ds_id="test-pg",
                sql=f"SELECT * FROM table{i}",
                suggestions=[],
                include_ai=True,
                duration_ms=100.0,
                notes=[]
            )

        analyses = get_recent_analyses()
        assert len(analyses) == 5
        assert all(a["event"] == "analyze" for a in analyses)

    def test_get_recent_analyses_with_limit(self, temp_log_file):
        """Test getting recent analyses with limit"""
        # Record 10 events
        for i in range(10):
            record_analyze(
                ds_id="test-pg",
                sql=f"SELECT * FROM table{i}",
                suggestions=[],
                include_ai=True,
                duration_ms=100.0,
                notes=[]
            )

        analyses = get_recent_analyses(limit=5)
        assert len(analyses) == 5

    def test_get_recent_analyses_filtered_by_ds_id(self, temp_log_file):
        """Test getting recent analyses filtered by data source"""
        # Record events for different data sources
        for i in range(3):
            record_analyze(ds_id="test-pg-1", sql="SELECT 1", suggestions=[], include_ai=True, duration_ms=100.0, notes=[])
            record_analyze(ds_id="test-pg-2", sql="SELECT 2", suggestions=[], include_ai=True, duration_ms=100.0, notes=[])

        analyses = get_recent_analyses(ds_id="test-pg-1")
        assert len(analyses) == 3
        assert all(a["ds_id"] == "test-pg-1" for a in analyses)

    def test_get_recent_analyses_most_recent_first(self, temp_log_file):
        """Test that recent analyses are returned in reverse chronological order"""
        for i in range(5):
            record_analyze(
                ds_id="test-pg",
                sql=f"SELECT {i}",
                suggestions=[{"id": f"sug_{i}"}],
                include_ai=True,
                duration_ms=100.0 + i,
                notes=[]
            )

        analyses = get_recent_analyses(limit=5)
        # Most recent should be first (highest duration)
        assert analyses[0]["duration_ms"] == 104.0
        assert analyses[-1]["duration_ms"] == 100.0

    def test_get_recent_applications_empty_log(self, temp_log_file):
        """Test getting recent applications from empty log"""
        applications = get_recent_applications()
        assert applications == []

    def test_get_recent_applications_with_data(self, temp_log_file):
        """Test getting recent applications"""
        for i in range(3):
            record_apply(
                ds_id="test-pg",
                suggestion_ids=[f"idx_{i}"],
                results=[{"id": f"idx_{i}", "status": "success"}],
                dry_run=True,
                duration_ms=200.0,
                notes=[]
            )

        applications = get_recent_applications()
        assert len(applications) == 3
        assert all(a["event"] == "apply" for a in applications)

    def test_get_recent_applications_filtered_by_ds_id(self, temp_log_file):
        """Test getting recent applications filtered by data source"""
        record_apply(ds_id="test-pg-1", suggestion_ids=["idx_1"], results=[], dry_run=True, duration_ms=100.0, notes=[])
        record_apply(ds_id="test-pg-2", suggestion_ids=["idx_2"], results=[], dry_run=True, duration_ms=100.0, notes=[])
        record_apply(ds_id="test-pg-1", suggestion_ids=["idx_3"], results=[], dry_run=True, duration_ms=100.0, notes=[])

        applications = get_recent_applications(ds_id="test-pg-1")
        assert len(applications) == 2
        assert all(a["ds_id"] == "test-pg-1" for a in applications)

    def test_get_recent_applications_with_limit(self, temp_log_file):
        """Test getting recent applications with limit"""
        for i in range(10):
            record_apply(
                ds_id="test-pg",
                suggestion_ids=[f"idx_{i}"],
                results=[],
                dry_run=False,
                duration_ms=100.0,
                notes=[]
            )

        applications = get_recent_applications(limit=5)
        assert len(applications) == 5

    def test_get_suggestion_history_empty(self, temp_log_file):
        """Test getting suggestion history when suggestion hasn't been used"""
        history = get_suggestion_history("nonexistent_id")
        assert history == []

    def test_get_suggestion_history_with_data(self, temp_log_file):
        """Test getting suggestion history"""
        suggestion_id = "idx_users_email_001"

        # Record analyze event
        record_analyze(
            ds_id="test-pg",
            sql="SELECT * FROM users",
            suggestions=[{"id": suggestion_id, "category": "index"}],
            include_ai=True,
            duration_ms=100.0,
            notes=[]
        )

        # Record apply event
        record_apply(
            ds_id="test-pg",
            suggestion_ids=[suggestion_id],
            results=[{"id": suggestion_id, "status": "success"}],
            dry_run=False,
            duration_ms=200.0,
            notes=[]
        )

        history = get_suggestion_history(suggestion_id)
        assert len(history) == 2
        assert history[0]["event"] == "analyze"
        assert history[1]["event"] == "apply"

    def test_get_suggestion_history_multiple_occurrences(self, temp_log_file):
        """Test getting suggestion history when suggestion appears multiple times"""
        suggestion_id = "idx_common"

        # Same suggestion analyzed multiple times
        for i in range(3):
            record_analyze(
                ds_id=f"test-pg-{i}",
                sql="SELECT * FROM users",
                suggestions=[{"id": suggestion_id, "category": "index"}],
                include_ai=True,
                duration_ms=100.0,
                notes=[]
            )

        history = get_suggestion_history(suggestion_id)
        assert len(history) == 3

    def test_record_analyze_handles_errors_gracefully(self, temp_log_file, monkeypatch):
        """Test that record_analyze handles write errors gracefully"""
        # Make the log file read-only to cause write error
        temp_log_file.chmod(0o444)

        # Should not raise exception
        try:
            record_analyze(
                ds_id="test-pg",
                sql="SELECT 1",
                suggestions=[],
                include_ai=True,
                duration_ms=100.0,
                notes=[]
            )
        finally:
            # Restore permissions for cleanup
            temp_log_file.chmod(0o644)

    def test_record_apply_handles_errors_gracefully(self, temp_log_file, monkeypatch):
        """Test that record_apply handles write errors gracefully"""
        temp_log_file.chmod(0o444)

        try:
            record_apply(
                ds_id="test-pg",
                suggestion_ids=["idx_001"],
                results=[],
                dry_run=True,
                duration_ms=100.0,
                notes=[]
            )
        finally:
            temp_log_file.chmod(0o644)

    def test_mixed_analyze_and_apply_events(self, temp_log_file):
        """Test that different event types can coexist and be filtered correctly"""
        # Record mixed events
        record_analyze(ds_id="test-pg", sql="SELECT 1", suggestions=[{"id": "sug_1"}], include_ai=True, duration_ms=100.0, notes=[])
        record_apply(ds_id="test-pg", suggestion_ids=["sug_1"], results=[], dry_run=True, duration_ms=200.0, notes=[])
        record_analyze(ds_id="test-pg", sql="SELECT 2", suggestions=[{"id": "sug_2"}], include_ai=True, duration_ms=150.0, notes=[])

        analyses = get_recent_analyses()
        applications = get_recent_applications()

        assert len(analyses) == 2
        assert len(applications) == 1
        assert all(a["event"] == "analyze" for a in analyses)
        assert all(a["event"] == "apply" for a in applications)

    def test_jsonl_format_integrity(self, temp_log_file):
        """Test that each line in the log file is valid JSON"""
        # Record multiple events
        for i in range(5):
            record_analyze(
                ds_id="test-pg",
                sql=f"SELECT {i}",
                suggestions=[],
                include_ai=True,
                duration_ms=100.0,
                notes=[]
            )

        # Read and validate each line
        with open(temp_log_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line.strip())
                    assert isinstance(record, dict)
                except json.JSONDecodeError:
                    pytest.fail(f"Line {line_num} is not valid JSON: {line}")
