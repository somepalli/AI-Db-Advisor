# tests/test_api_analyze.py
"""
API tests for analyze endpoints
"""
import pytest
from fastapi import status
from unittest.mock import patch, MagicMock


class TestAnalyzeAPI:
    """Test suite for /analyze endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self, client, sample_datasource, mock_postgres_agent):
        """Setup: Register a datasource before each test"""
        client.post("/datasources", json=sample_datasource)
        self.ds_id = sample_datasource["id"]
        self.mock_agent = mock_postgres_agent

    def test_get_schema_not_found(self, client):
        """Test getting schema for non-existent datasource"""
        response = client.get("/analyze/non-existent/schema")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('backend.deps.get_agent_for')
    def test_get_schema_success(self, mock_get_agent, client):
        """Test getting database schema"""
        mock_get_agent.return_value = self.mock_agent

        response = client.get(f"/analyze/{self.ds_id}/schema")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tables" in data
        assert "public.users" in data["tables"]
        assert "public.orders" in data["tables"]

    @patch('backend.deps.get_agent_for')
    def test_get_top_queries_default_limit(self, mock_get_agent, client):
        """Test getting top queries with default limit"""
        mock_get_agent.return_value = self.mock_agent

        response = client.get(f"/analyze/{self.ds_id}/top")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["query"] == "SELECT * FROM users WHERE id = $1"
        assert data[0]["calls"] == 1000

    @patch('backend.deps.get_agent_for')
    def test_get_top_queries_custom_limit(self, mock_get_agent, client):
        """Test getting top queries with custom limit"""
        mock_get_agent.return_value = self.mock_agent

        response = client.get(f"/analyze/{self.ds_id}/top?limit=5")
        assert response.status_code == status.HTTP_200_OK
        self.mock_agent.get_top_queries.assert_called_with(limit=5)

    @patch('backend.deps.get_agent_for')
    def test_get_top_queries_limit_validation(self, mock_get_agent, client):
        """Test top queries limit validation (must be 1-100)"""
        mock_get_agent.return_value = self.mock_agent

        # Test too low
        response = client.get(f"/analyze/{self.ds_id}/top?limit=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test too high
        response = client.get(f"/analyze/{self.ds_id}/top?limit=101")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch('backend.deps.get_agent_for')
    def test_explain_query(self, mock_get_agent, client, sample_sql):
        """Test EXPLAIN query endpoint"""
        mock_get_agent.return_value = self.mock_agent

        payload = {"sql": sample_sql["simple"], "analyze": False}
        response = client.post(f"/analyze/{self.ds_id}/explain", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "plan" in data
        assert data["plan"][0]["Plan"]["Node Type"] == "Seq Scan"

    @patch('backend.deps.get_agent_for')
    def test_explain_query_with_analyze(self, mock_get_agent, client, sample_sql):
        """Test EXPLAIN ANALYZE query endpoint"""
        mock_get_agent.return_value = self.mock_agent

        payload = {"sql": sample_sql["simple"], "analyze": True}
        response = client.post(f"/analyze/{self.ds_id}/explain", json=payload)
        assert response.status_code == status.HTTP_200_OK
        self.mock_agent.explain.assert_called_with(sample_sql["simple"], analyze=True)

    @patch('backend.deps.get_agent_for')
    def test_get_locks(self, mock_get_agent, client):
        """Test getting database locks"""
        mock_get_agent.return_value = self.mock_agent

        response = client.get(f"/analyze/{self.ds_id}/locks")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["locktype"] == "relation"

    @patch('backend.deps.get_agent_for')
    def test_get_stats(self, mock_get_agent, client):
        """Test getting database statistics"""
        mock_get_agent.return_value = self.mock_agent

        response = client.get(f"/analyze/{self.ds_id}/stats")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_db_size" in data
        assert "active_backends" in data
        assert data["total_db_size"] == 1073741824
        assert data["active_backends"] == 5

    @patch('backend.deps.get_agent_for')
    def test_advise_index(self, mock_get_agent, client, sample_sql):
        """Test index advisor endpoint"""
        mock_get_agent.return_value = self.mock_agent

        payload = {"sql": sample_sql["simple"], "analyze": False}
        response = client.post(f"/analyze/{self.ds_id}/advise/index", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @patch('backend.deps.get_agent_for')
    def test_advise_rewrite(self, mock_get_agent, client, sample_sql):
        """Test query rewrite advisor endpoint"""
        mock_get_agent.return_value = self.mock_agent

        # Test with SELECT *
        payload = {"sql": sample_sql["select_star"], "analyze": False}
        response = client.post(f"/analyze/{self.ds_id}/advise/rewrite", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert any("SELECT *" in r["summary"] for r in data)

    @patch('backend.deps.get_agent_for')
    def test_advise_rewrite_offset_pagination(self, mock_get_agent, client, sample_sql):
        """Test rewrite advisor detects OFFSET pagination issues"""
        mock_get_agent.return_value = self.mock_agent

        payload = {"sql": sample_sql["with_offset"], "analyze": False}
        response = client.post(f"/analyze/{self.ds_id}/advise/rewrite", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) > 0
        assert any("pagination" in r["summary"].lower() for r in data)

    @patch('backend.deps.get_agent_for')
    def test_hypothetical_index(self, mock_get_agent, client):
        """Test hypothetical index endpoint"""
        mock_get_agent.return_value = self.mock_agent

        payload = {
            "table": "users",
            "columns": ["email"],
            "include": ["name"],
            "method": "btree"
        }
        response = client.post(f"/analyze/{self.ds_id}/hypo-index", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "hypo_stmt" in data
        assert data["hypopg_available"] is True

    @patch('backend.deps.get_agent_for')
    @patch('backend.services.ai_client.LLMClient')
    def test_advise_ai_success(self, mock_llm_class, mock_get_agent, client, sample_sql, mock_llm_client):
        """Test AI advisor endpoint with successful LLM response"""
        mock_get_agent.return_value = self.mock_agent
        mock_llm_class.return_value = mock_llm_client

        payload = {"sql": sample_sql["simple"], "analyze": False}
        response = client.post(f"/analyze/{self.ds_id}/advise/ai", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "suggestions" in data

    @patch('backend.deps.get_agent_for')
    @patch('backend.services.ai_client.LLMClient')
    def test_explain_plan_ai(self, mock_llm_class, mock_get_agent, client, sample_sql):
        """Test AI-powered EXPLAIN plan explanation"""
        mock_get_agent.return_value = self.mock_agent
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "This plan performs a sequential scan on the users table."
        mock_llm_class.return_value = mock_llm

        payload = {"sql": sample_sql["simple"], "analyze": False}
        response = client.post(f"/analyze/{self.ds_id}/explain/ai", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "explanation" in data
        assert "sequential scan" in data["explanation"].lower()

    @patch('backend.deps.get_agent_for')
    def test_advise_index_non_postgres(self, mock_get_agent, client, sample_sql):
        """Test index advisor rejects non-PostgreSQL agents"""
        # Create a mock agent with different class name
        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "MySQLAgent"
        mock_get_agent.return_value = mock_agent

        payload = {"sql": sample_sql["simple"], "analyze": False}
        response = client.post(f"/analyze/{self.ds_id}/advise/index", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Postgres only" in response.json()["detail"]