# tests/test_api_suggestions.py
"""
API tests for suggestions workflow endpoints
"""
import pytest
from fastapi import status
from unittest.mock import patch, MagicMock
from app.schemas import Suggestion, ApplyResult


class TestSuggestionsAPI:
    """Test suite for /suggestions endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self, client, sample_datasource, mock_postgres_agent):
        """Setup: Register a datasource before each test"""
        client.post("/datasources", json=sample_datasource)
        self.ds_id = sample_datasource["id"]
        self.mock_agent = mock_postgres_agent

    @patch('app.deps.get_agent_for')
    @patch('app.routers.suggestions.analyze_query_suggestions')
    def test_analyze_suggestions_success(self, mock_analyze, mock_get_agent, client, sample_sql):
        """Test successful suggestion analysis"""
        mock_get_agent.return_value = self.mock_agent

        # Mock suggestions response
        mock_suggestions = [
            Suggestion(
                id="idx_users_email_001",
                level="table",
                category="index",
                title="Create index on users(email)",
                summary="Add index to optimize email lookups",
                sql_fix="CREATE INDEX idx_users_email ON users(email);",
                validated=True,
                confidence="validated",
                risk="low",
                estimated_gain="Cost reduction: 75%",
                related_objects=["users"],
                metadata={"source": "index_advisor"}
            ),
            Suggestion(
                id="rewrite_select_star_001",
                level="query",
                category="rewrite",
                title="Avoid SELECT * - Specify columns explicitly",
                summary="SELECT * retrieves unnecessary columns",
                sql_fix="SELECT id, name, email FROM users WHERE email = 'test@example.com'",
                validated=False,
                confidence="rule-based",
                risk="low",
                estimated_gain=None,
                related_objects=["users"],
                metadata={"source": "rewrite_advisor"}
            )
        ]
        mock_notes = ["Validated 1/2 suggestions", "Limited to top 12 suggestions"]
        mock_analyze.return_value = (mock_suggestions, mock_notes)

        payload = {
            "ds_id": self.ds_id,
            "sql": sample_sql["simple"],
            "include_ai": True,
            "top_k": 12
        }
        response = client.post("/suggestions/analyze", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "suggestions" in data
        assert "notes" in data
        assert len(data["suggestions"]) == 2
        assert data["suggestions"][0]["id"] == "idx_users_email_001"
        assert data["suggestions"][0]["validated"] is True
        assert data["suggestions"][1]["category"] == "rewrite"
        assert len(data["notes"]) == 2

    @patch('app.deps.get_agent_for')
    @patch('app.routers.suggestions.analyze_query_suggestions')
    def test_analyze_suggestions_without_ai(self, mock_analyze, mock_get_agent, client, sample_sql):
        """Test suggestion analysis without AI suggestions"""
        mock_get_agent.return_value = self.mock_agent

        mock_suggestions = [
            Suggestion(
                id="idx_001",
                level="table",
                category="index",
                title="Create index",
                summary="Index suggestion",
                sql_fix="CREATE INDEX idx ON table(col);",
                validated=False,
                confidence="rule-based",
                risk="medium",
                related_objects=["table"],
                metadata={"source": "index_advisor"}
            )
        ]
        mock_notes = ["AI suggestions disabled"]
        mock_analyze.return_value = (mock_suggestions, mock_notes)

        payload = {
            "ds_id": self.ds_id,
            "sql": sample_sql["simple"],
            "include_ai": False,
            "top_k": 10
        }
        response = client.post("/suggestions/analyze", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["suggestions"]) == 1
        assert "AI suggestions disabled" in data["notes"]

    @patch('app.deps.get_agent_for')
    def test_analyze_suggestions_non_postgres(self, mock_get_agent, client, sample_sql):
        """Test that analyze rejects non-PostgreSQL agents"""
        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "MySQLAgent"
        mock_get_agent.return_value = mock_agent

        payload = {
            "ds_id": self.ds_id,
            "sql": sample_sql["simple"],
            "include_ai": True,
            "top_k": 12
        }
        response = client.post("/suggestions/analyze", json=payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "PostgreSQL" in response.json()["detail"]

    @patch('app.deps.get_agent_for')
    @patch('app.routers.suggestions.analyze_query_suggestions')
    def test_analyze_suggestions_with_errors(self, mock_analyze, mock_get_agent, client, sample_sql):
        """Test suggestion analysis with partial errors"""
        mock_get_agent.return_value = self.mock_agent

        mock_suggestions = []
        mock_notes = [
            "Index advisor error: Table not found",
            "Rewrite advisor error: Invalid SQL syntax",
            "AI advisor error: LLM timeout"
        ]
        mock_analyze.return_value = (mock_suggestions, mock_notes)

        payload = {
            "ds_id": self.ds_id,
            "sql": sample_sql["simple"],
            "include_ai": True,
            "top_k": 12
        }
        response = client.post("/suggestions/analyze", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["suggestions"]) == 0
        assert len(data["notes"]) == 3

    @patch('app.deps.get_agent_for')
    def test_analyze_suggestions_datasource_not_found(self, mock_get_agent, client, sample_sql):
        """Test analyze with non-existent datasource"""
        from fastapi import HTTPException
        mock_get_agent.side_effect = HTTPException(404, "Data source not found")

        payload = {
            "ds_id": "non-existent",
            "sql": sample_sql["simple"],
            "include_ai": True,
            "top_k": 12
        }
        response = client.post("/suggestions/analyze", json=payload)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('app.deps.get_agent_for')
    def test_apply_suggestions_not_implemented(self, mock_get_agent, client):
        """Test that /apply endpoint returns not-implemented message"""
        mock_get_agent.return_value = self.mock_agent

        payload = {
            "ds_id": self.ds_id,
            "suggestion_ids": ["idx_001", "rewrite_002"],
            "dry_run": True
        }
        response = client.post("/suggestions/apply", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert all(r["status"] == "skipped" for r in data["results"])
        assert "not yet implemented" in data["results"][0]["message"]

    @patch('app.deps.get_agent_for')
    @patch('app.routers.suggestions.apply_suggestions')
    def test_apply_direct_dry_run_success(self, mock_apply, mock_get_agent, client):
        """Test direct application in dry-run mode"""
        mock_get_agent.return_value = self.mock_agent

        # Mock apply results
        mock_results = [
            ApplyResult(
                id="idx_001",
                status="success",
                message="Dry-run validated successfully (changes rolled back)",
                rollback_sql="DROP INDEX IF EXISTS idx_users_email;"
            )
        ]
        mock_apply.return_value = mock_results

        suggestions = [
            {
                "id": "idx_001",
                "level": "table",
                "category": "index",
                "title": "Create index",
                "summary": "Index suggestion",
                "sql_fix": "CREATE INDEX idx_users_email ON users(email);",
                "validated": True,
                "confidence": "validated",
                "risk": "low",
                "related_objects": ["users"],
                "metadata": {}
            }
        ]

        params = {
            "ds_id": self.ds_id,
            "suggestions": suggestions,
            "dry_run": True
        }
        response = client.post("/suggestions/apply_direct", json=params)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "success"
        assert data["results"][0]["rollback_sql"] is not None
        assert "Dry-run validated" in data["results"][0]["message"]

    @patch('app.deps.get_agent_for')
    @patch('app.routers.suggestions.apply_suggestions')
    def test_apply_direct_real_execution(self, mock_apply, mock_get_agent, client):
        """Test direct application with real execution (dry_run=False)"""
        mock_get_agent.return_value = self.mock_agent

        mock_results = [
            ApplyResult(
                id="idx_001",
                status="success",
                message="Applied successfully",
                rollback_sql="DROP INDEX IF EXISTS idx_users_email;"
            )
        ]
        mock_apply.return_value = mock_results

        suggestions = [
            {
                "id": "idx_001",
                "level": "table",
                "category": "index",
                "title": "Create index",
                "summary": "Index suggestion",
                "sql_fix": "CREATE INDEX idx_users_email ON users(email);",
                "validated": True,
                "confidence": "validated",
                "risk": "low",
                "related_objects": ["users"],
                "metadata": {}
            }
        ]

        params = {
            "ds_id": self.ds_id,
            "suggestions": suggestions,
            "dry_run": False
        }
        response = client.post("/suggestions/apply_direct", json=params)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["results"][0]["status"] == "success"
        assert "Applied successfully" in data["results"][0]["message"]
        assert "1/1 suggestions successfully" in " ".join(data["notes"])

    @patch('app.deps.get_agent_for')
    @patch('app.routers.suggestions.apply_suggestions')
    def test_apply_direct_with_errors(self, mock_apply, mock_get_agent, client):
        """Test direct application with some failures"""
        mock_get_agent.return_value = self.mock_agent

        mock_results = [
            ApplyResult(
                id="idx_001",
                status="success",
                message="Applied successfully",
                rollback_sql="DROP INDEX IF EXISTS idx_users_email;"
            ),
            ApplyResult(
                id="idx_002",
                status="error",
                message="Execution failed: relation does not exist",
                rollback_sql=None
            ),
            ApplyResult(
                id="rewrite_001",
                status="skipped",
                message="Blocked: High-risk operation requires dry-run first",
                rollback_sql=None
            )
        ]
        mock_apply.return_value = mock_results

        suggestions = [
            {
                "id": "idx_001",
                "level": "table",
                "category": "index",
                "title": "Create index 1",
                "summary": "Index suggestion 1",
                "sql_fix": "CREATE INDEX idx_users_email ON users(email);",
                "validated": True,
                "confidence": "validated",
                "risk": "low",
                "related_objects": ["users"],
                "metadata": {}
            },
            {
                "id": "idx_002",
                "level": "table",
                "category": "index",
                "title": "Create index 2",
                "summary": "Index suggestion 2",
                "sql_fix": "CREATE INDEX idx_orders_status ON orders(status);",
                "validated": False,
                "confidence": "rule-based",
                "risk": "medium",
                "related_objects": ["orders"],
                "metadata": {}
            },
            {
                "id": "rewrite_001",
                "level": "query",
                "category": "rewrite",
                "title": "Query rewrite",
                "summary": "Rewrite suggestion",
                "sql_fix": "SELECT id FROM users;",
                "validated": False,
                "confidence": "rule-based",
                "risk": "high",
                "related_objects": ["users"],
                "metadata": {}
            }
        ]

        params = {
            "ds_id": self.ds_id,
            "suggestions": suggestions,
            "dry_run": False
        }
        response = client.post("/suggestions/apply_direct", json=params)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 3

        # Check outcomes
        success_count = sum(1 for r in data["results"] if r["status"] == "success")
        error_count = sum(1 for r in data["results"] if r["status"] == "error")
        skipped_count = sum(1 for r in data["results"] if r["status"] == "skipped")

        assert success_count == 1
        assert error_count == 1
        assert skipped_count == 1
        assert "1 suggestions failed" in " ".join(data["notes"])
        assert "1 suggestions skipped" in " ".join(data["notes"])

    @patch('app.deps.get_agent_for')
    def test_apply_direct_non_postgres(self, mock_get_agent, client):
        """Test that apply_direct rejects non-PostgreSQL agents"""
        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "MySQLAgent"
        mock_get_agent.return_value = mock_agent

        suggestions = [
            {
                "id": "idx_001",
                "level": "table",
                "category": "index",
                "title": "Create index",
                "summary": "Index suggestion",
                "sql_fix": "CREATE INDEX idx ON users(email);",
                "validated": False,
                "confidence": "rule-based",
                "risk": "low",
                "related_objects": ["users"],
                "metadata": {}
            }
        ]

        params = {
            "ds_id": self.ds_id,
            "suggestions": suggestions,
            "dry_run": True
        }
        response = client.post("/suggestions/apply_direct", json=params)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "PostgreSQL" in response.json()["detail"]

    @patch('app.deps.get_agent_for')
    @patch('app.routers.suggestions.apply_suggestions')
    def test_apply_direct_batch_application(self, mock_apply, mock_get_agent, client):
        """Test applying multiple suggestions in batch"""
        mock_get_agent.return_value = self.mock_agent

        mock_results = [
            ApplyResult(id=f"idx_{i:03d}", status="success", message="Applied successfully", rollback_sql=f"DROP INDEX IF EXISTS idx_{i};")
            for i in range(5)
        ]
        mock_apply.return_value = mock_results

        suggestions = [
            {
                "id": f"idx_{i:03d}",
                "level": "table",
                "category": "index",
                "title": f"Create index {i}",
                "summary": f"Index suggestion {i}",
                "sql_fix": f"CREATE INDEX idx_{i} ON table_{i}(col);",
                "validated": True,
                "confidence": "validated",
                "risk": "low",
                "related_objects": [f"table_{i}"],
                "metadata": {}
            }
            for i in range(5)
        ]

        params = {
            "ds_id": self.ds_id,
            "suggestions": suggestions,
            "dry_run": False
        }
        response = client.post("/suggestions/apply_direct", json=params)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 5
        assert all(r["status"] == "success" for r in data["results"])
        assert "Applied 5/5 suggestions successfully" in " ".join(data["notes"])

    @patch('app.deps.get_agent_for')
    def test_apply_direct_invalid_suggestion_schema(self, mock_get_agent, client):
        """Test apply_direct with invalid suggestion schema"""
        mock_get_agent.return_value = self.mock_agent

        # Missing required fields
        suggestions = [
            {
                "id": "idx_001",
                "level": "table",
                # Missing category
                "title": "Create index",
                "summary": "Index suggestion",
            }
        ]

        params = {
            "ds_id": self.ds_id,
            "suggestions": suggestions,
            "dry_run": True
        }
        response = client.post("/suggestions/apply_direct", json=params)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
