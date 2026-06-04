# tests/test_e2e_workflows.py
"""
End-to-end workflow tests simulating real user scenarios
"""
import pytest
from fastapi import status
from unittest.mock import patch


class TestEndToEndWorkflows:
    """Test complete user workflows from start to finish"""

    @patch('backend.deps.get_agent_for')
    def test_complete_workflow_new_user(self, mock_get_agent, client, sample_datasource, mock_postgres_agent, sample_sql):
        """
        Test complete workflow for a new user:
        1. Check health
        2. Register datasource
        3. View schema
        4. Get top queries
        5. Explain a query
        6. Get recommendations
        """
        mock_get_agent.return_value = mock_postgres_agent

        # Step 1: Health check
        response = client.get("/healthz")
        assert response.status_code == status.HTTP_200_OK

        # Step 2: List datasources (should be empty)
        response = client.get("/datasources")
        assert len(response.json()["items"]) == 0

        # Step 3: Register a datasource
        response = client.post("/datasources", json=sample_datasource)
        assert response.status_code == status.HTTP_201_CREATED
        ds_id = response.json()["id"]

        # Step 4: Verify datasource is listed
        response = client.get("/datasources")
        assert len(response.json()["items"]) == 1

        # Step 5: Get database schema
        response = client.get(f"/analyze/{ds_id}/schema")
        assert response.status_code == status.HTTP_200_OK
        schema = response.json()
        assert "tables" in schema

        # Step 6: Get database stats
        response = client.get(f"/analyze/{ds_id}/stats")
        assert response.status_code == status.HTTP_200_OK
        stats = response.json()
        assert "total_db_size" in stats

        # Step 7: Get top queries
        response = client.get(f"/analyze/{ds_id}/top")
        assert response.status_code == status.HTTP_200_OK
        top_queries = response.json()
        assert len(top_queries) > 0

        # Step 8: Explain a query
        payload = {"sql": sample_sql["simple"], "analyze": False}
        response = client.post(f"/analyze/{ds_id}/explain", json=payload)
        assert response.status_code == status.HTTP_200_OK
        plan = response.json()
        assert "plan" in plan

        # Step 9: Get index recommendations
        response = client.post(f"/analyze/{ds_id}/advise/index", json=payload)
        assert response.status_code == status.HTTP_200_OK

        # Step 10: Get rewrite recommendations
        payload = {"sql": sample_sql["select_star"], "analyze": False}
        response = client.post(f"/analyze/{ds_id}/advise/rewrite", json=payload)
        assert response.status_code == status.HTTP_200_OK
        recommendations = response.json()
        assert len(recommendations) > 0

    @patch('backend.deps.get_agent_for')
    def test_ui_workflow_dashboard_to_recommendations(self, mock_get_agent, client, sample_datasource, mock_postgres_agent, sample_sql):
        """
        Test UI workflow:
        1. Visit home page
        2. Navigate to datasources page
        3. Register datasource
        4. Navigate to analyze page
        5. View dashboard
        6. Explain query
        7. Get recommendations
        """
        mock_get_agent.return_value = mock_postgres_agent

        # Step 1: Visit home page
        response = client.get("/ui/pages/home")
        assert response.status_code == status.HTTP_200_OK

        # Step 2: Visit datasources page
        response = client.get("/ui/pages/datasources")
        assert response.status_code == status.HTTP_200_OK

        # Step 3: Register datasource (via API)
        client.post("/datasources", json=sample_datasource)
        ds_id = sample_datasource["id"]

        # Step 4: Visit analyze page
        response = client.get("/ui/pages/analyze")
        assert response.status_code == status.HTTP_200_OK

        # Step 5: Select datasource
        response = client.get(f"/ui/pages/analyze?ds_id={ds_id}")
        assert response.status_code == status.HTTP_200_OK

        # Step 6: View dashboard
        response = client.get(f"/ui/pages/ds/{ds_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert ds_id in str(data)

        # Step 7: Explain query page
        response = client.get(f"/ui/pages/explain?ds_id={ds_id}&sql={sample_sql['simple']}")
        assert response.status_code == status.HTTP_200_OK

        # Step 8: Get recommendations
        response = client.get(f"/ui/pages/advise?ds_id={ds_id}&sql={sample_sql['select_star']}&ai=0")
        assert response.status_code == status.HTTP_200_OK

    @patch('backend.deps.get_agent_for')
    @patch('backend.services.ai_client.LLMClient')
    def test_workflow_with_ai_recommendations(self, mock_llm_class, mock_get_agent, client, sample_datasource, mock_postgres_agent, sample_sql, mock_llm_client):
        """
        Test workflow with AI-powered recommendations:
        1. Register datasource
        2. Get AI recommendations
        3. Get AI EXPLAIN interpretation
        """
        mock_get_agent.return_value = mock_postgres_agent
        mock_llm_class.return_value = mock_llm_client

        # Register datasource
        client.post("/datasources", json=sample_datasource)
        ds_id = sample_datasource["id"]

        # Get AI recommendations
        payload = {"sql": sample_sql["simple"], "analyze": False}
        response = client.post(f"/analyze/{ds_id}/advise/ai", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "suggestions" in data

        # Get AI EXPLAIN interpretation
        response = client.post(f"/analyze/{ds_id}/explain/ai", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "explanation" in data

    @patch('backend.deps.get_agent_for')
    def test_workflow_multiple_datasources(self, mock_get_agent, client, mock_postgres_agent):
        """
        Test workflow with multiple datasources:
        1. Register multiple datasources
        2. Switch between them
        3. Query each one
        """
        mock_get_agent.return_value = mock_postgres_agent

        datasources = [
            {"id": "pg-dev", "engine": "postgres", "dsn": "postgresql://localhost/dev"},
            {"id": "pg-staging", "engine": "postgres", "dsn": "postgresql://localhost/staging"},
            {"id": "pg-prod", "engine": "postgres", "dsn": "postgresql://localhost/prod"},
        ]

        # Register all datasources
        for ds in datasources:
            response = client.post("/datasources", json=ds)
            assert response.status_code == status.HTTP_201_CREATED

        # Query each datasource
        for ds in datasources:
            # Get schema
            response = client.get(f"/analyze/{ds['id']}/schema")
            assert response.status_code == status.HTTP_200_OK

            # Get stats
            response = client.get(f"/analyze/{ds['id']}/stats")
            assert response.status_code == status.HTTP_200_OK

            # View in UI
            response = client.get(f"/ui/pages/ds/{ds['id']}")
            assert response.status_code == status.HTTP_200_OK

    @patch('backend.deps.get_agent_for')
    def test_workflow_query_optimization_cycle(self, mock_get_agent, client, sample_datasource, mock_postgres_agent, sample_sql):
        """
        Test query optimization workflow:
        1. Start with poorly performing query
        2. Get EXPLAIN plan
        3. Get recommendations
        4. Test hypothetical index
        5. View improved plan
        """
        mock_get_agent.return_value = mock_postgres_agent

        # Setup
        client.post("/datasources", json=sample_datasource)
        ds_id = sample_datasource["id"]

        # Step 1: EXPLAIN original query
        payload = {"sql": sample_sql["simple"], "analyze": False}
        response = client.post(f"/analyze/{ds_id}/explain", json=payload)
        assert response.status_code == status.HTTP_200_OK
        original_plan = response.json()["plan"]

        # Step 2: Get index recommendations
        response = client.post(f"/analyze/{ds_id}/advise/index", json=payload)
        assert response.status_code == status.HTTP_200_OK

        # Step 3: Create hypothetical index
        hypo_payload = {
            "table": "users",
            "columns": ["email"],
            "method": "btree"
        }
        response = client.post(f"/analyze/{ds_id}/hypo-index", json=hypo_payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["hypopg_available"] is True

        # Step 4: View improved stats
        response = client.get(f"/analyze/{ds_id}/stats")
        assert response.status_code == status.HTTP_200_OK

    def test_workflow_error_handling(self, client):
        """
        Test error handling workflow:
        1. Try to query non-existent datasource
        2. Try to register duplicate datasource
        3. Try invalid SQL
        """
        # Try to query non-existent datasource
        response = client.get("/analyze/non-existent/schema")
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Register a datasource
        ds = {"id": "test", "engine": "postgres", "dsn": "postgresql://localhost/test"}
        client.post("/datasources", json=ds)

        # Try to register duplicate
        response = client.post("/datasources", json=ds)
        assert response.status_code == status.HTTP_409_CONFLICT

        # Try incomplete datasource registration
        incomplete = {"id": "incomplete"}
        response = client.post("/datasources", json=incomplete)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch('backend.deps.get_agent_for')
    def test_workflow_performance_monitoring(self, mock_get_agent, client, sample_datasource, mock_postgres_agent):
        """
        Test performance monitoring workflow:
        1. Register datasource
        2. Check database stats
        3. View top queries
        4. Check locks
        5. Monitor via dashboard
        """
        mock_get_agent.return_value = mock_postgres_agent

        # Setup
        client.post("/datasources", json=sample_datasource)
        ds_id = sample_datasource["id"]

        # Get stats
        response = client.get(f"/analyze/{ds_id}/stats")
        assert response.status_code == status.HTTP_200_OK
        stats = response.json()
        assert "total_db_size" in stats
        assert "active_backends" in stats

        # Get top queries
        response = client.get(f"/analyze/{ds_id}/top?limit=10")
        assert response.status_code == status.HTTP_200_OK
        queries = response.json()
        assert isinstance(queries, list)

        # Check locks
        response = client.get(f"/analyze/{ds_id}/locks")
        assert response.status_code == status.HTTP_200_OK
        locks = response.json()
        assert isinstance(locks, list)

        # View dashboard
        response = client.get(f"/ui/pages/ds/{ds_id}")
        assert response.status_code == status.HTTP_200_OK
        dashboard = response.json()
        dashboard_str = str(dashboard)
        assert "Database Size" in dashboard_str or "Active" in dashboard_str