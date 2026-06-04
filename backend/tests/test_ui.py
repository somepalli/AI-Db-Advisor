# tests/test_ui.py
"""
UI integration tests for FastUI pages
"""
import pytest
from fastapi import status
from unittest.mock import patch


class TestUIPages:
    """Test suite for UI page endpoints"""

    def test_ui_root_html_shell(self, client):
        """Test UI root returns HTML shell"""
        response = client.get("/ui/")
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]
        assert b"<!doctype html>" in response.content.lower()

    def test_ui_any_path_returns_html(self, client):
        """Test any /ui/* path returns HTML shell"""
        paths = ["/ui/home", "/ui/datasources", "/ui/analyze", "/ui/anything"]
        for path in paths:
            response = client.get(path)
            assert response.status_code == status.HTTP_200_OK
            assert "text/html" in response.headers["content-type"]

    def test_ui_pages_root_redirect(self, client):
        """Test /ui/pages redirects to home"""
        response = client.get("/ui/pages")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_ui_pages_home(self, client):
        """Test home page JSON endpoint"""
        response = client.get("/ui/pages/home")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check response structure
        assert isinstance(data, list)
        assert len(data) >= 2

        # First element should be PageTitle
        page_title = data[0]
        assert page_title["type"] == "PageTitle"
        assert page_title["text"] == "AI DB Advisor"

        # Second element should be Page
        page = data[1]
        assert page["type"] == "Page"
        assert "components" in page

        # Check for key components
        components = page["components"]
        headings = [c for c in components if c.get("type") == "Heading"]
        assert len(headings) > 0
        assert any("AI Database Performance Advisor" in h.get("text", "") for h in headings)

    def test_ui_pages_datasources_empty(self, client):
        """Test datasources page with no datasources"""
        response = client.get("/ui/pages/datasources")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) >= 2
        page_title = data[0]
        assert page_title["type"] == "PageTitle"
        assert "Data Source" in page_title["text"]

        page = data[1]
        assert page["type"] == "Page"

    def test_ui_pages_datasources_with_data(self, client, sample_datasource):
        """Test datasources page with registered datasource"""
        # Register a datasource
        client.post("/datasources", json=sample_datasource)

        # Check UI page
        response = client.get("/ui/pages/datasources")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify datasource appears in page
        page_json = str(data)
        assert sample_datasource["id"] in page_json

    def test_ui_pages_analyze_no_datasources(self, client):
        """Test analyze page with no datasources"""
        response = client.get("/ui/pages/analyze")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check for PageTitle and Page components
        page_titles = [d for d in data if d.get("type") == "PageTitle"]
        pages = [d for d in data if d.get("type") == "Page"]

        assert len(page_titles) > 0
        assert "Analyze" in page_titles[0]["text"]
        assert len(pages) > 0

        # Should show warning about no datasources
        page_str = str(data)
        assert "No Data Sources" in page_str or "no data source" in page_str.lower()

    def test_ui_pages_analyze_with_datasources(self, client, sample_datasource):
        """Test analyze page with datasources registered"""
        # Register a datasource
        client.post("/datasources", json=sample_datasource)

        response = client.get("/ui/pages/analyze")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check for PageTitle and Page
        assert len(data) >= 2
        page_title = data[0]
        assert page_title["type"] == "PageTitle"

        page = data[1]
        assert page["type"] == "Page"

        # Should show datasource selector
        page_str = str(data)
        assert "Select" in page_str or "Choose" in page_str

    def test_ui_pages_analyze_with_selected_ds(self, client, sample_datasource):
        """Test analyze page with selected datasource"""
        # Register a datasource
        client.post("/datasources", json=sample_datasource)

        response = client.get(f"/ui/pages/analyze?ds_id={sample_datasource['id']}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        page_str = str(data)
        assert sample_datasource["id"] in page_str
        assert "Dashboard" in page_str

    @patch('backend.deps.get_agent_for')
    def test_ui_pages_dashboard(self, mock_get_agent, client, sample_datasource, mock_postgres_agent):
        """Test dashboard page"""
        # Register datasource and mock agent
        client.post("/datasources", json=sample_datasource)
        mock_get_agent.return_value = mock_postgres_agent

        response = client.get(f"/ui/pages/ds/{sample_datasource['id']}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check for PageTitle with datasource id
        assert len(data) >= 2
        page_title = data[0]
        assert page_title["type"] == "PageTitle"
        assert sample_datasource["id"] in page_title["text"]

        # Check for Page component
        page = data[1]
        assert page["type"] == "Page"

        # Check for statistics
        page_str = str(data)
        assert "Database Size" in page_str or "Active" in page_str

    @patch('backend.deps.get_agent_for')
    def test_ui_pages_explain_form(self, mock_get_agent, client, sample_datasource, mock_postgres_agent):
        """Test explain query page renders form"""
        client.post("/datasources", json=sample_datasource)
        mock_get_agent.return_value = mock_postgres_agent

        response = client.get(f"/ui/pages/explain?ds_id={sample_datasource['id']}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        page_str = str(data)
        assert "EXPLAIN" in page_str
        assert "SQL" in page_str or "Query" in page_str

    @patch('backend.deps.get_agent_for')
    def test_ui_pages_explain_with_sql(self, mock_get_agent, client, sample_datasource, mock_postgres_agent, sample_sql):
        """Test explain query page with SQL query"""
        client.post("/datasources", json=sample_datasource)
        mock_get_agent.return_value = mock_postgres_agent

        sql = sample_sql["simple"]
        response = client.get(f"/ui/pages/explain?ds_id={sample_datasource['id']}&sql={sql}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        page_str = str(data)
        # Should show plan results
        assert "Cost" in page_str or "Plan" in page_str
        assert "Seq Scan" in page_str

    @patch('backend.deps.get_agent_for')
    def test_ui_pages_advise_rule_based(self, mock_get_agent, client, sample_datasource, mock_postgres_agent, sample_sql):
        """Test advisor page with rule-based recommendations"""
        client.post("/datasources", json=sample_datasource)
        mock_get_agent.return_value = mock_postgres_agent

        sql = sample_sql["select_star"]
        response = client.get(f"/ui/pages/advise?ds_id={sample_datasource['id']}&sql={sql}&ai=0")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        page = data[0]
        assert page["type"] == "Page"

        page_str = str(data)
        # Should show recommendations section
        assert "Rule-Based" in page_str or "Recommendation" in page_str

    @patch('backend.deps.get_agent_for')
    @patch('backend.services.ai_client.LLMClient')
    def test_ui_pages_advise_ai_mode(self, mock_llm_class, mock_get_agent, client, sample_datasource, mock_postgres_agent, sample_sql, mock_llm_client):
        """Test advisor page with AI mode enabled"""
        client.post("/datasources", json=sample_datasource)
        mock_get_agent.return_value = mock_postgres_agent
        mock_llm_class.return_value = mock_llm_client

        sql = sample_sql["simple"]
        response = client.get(f"/ui/pages/advise?ds_id={sample_datasource['id']}&sql={sql}&ai=1")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        page_str = str(data)
        # Should show AI recommendations section
        assert "AI" in page_str

    def test_ui_pages_invalid_datasource(self, client):
        """Test UI pages with invalid datasource ID"""
        response = client.get("/ui/pages/ds/non-existent")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('backend.deps.get_agent_for')
    def test_ui_navigation_buttons(self, mock_get_agent, client, sample_datasource, mock_postgres_agent):
        """Test navigation buttons are present in UI pages"""
        client.post("/datasources", json=sample_datasource)
        mock_get_agent.return_value = mock_postgres_agent

        pages = [
            f"/ui/pages/ds/{sample_datasource['id']}",
            f"/ui/pages/explain?ds_id={sample_datasource['id']}",
            f"/ui/pages/advise?ds_id={sample_datasource['id']}&sql=SELECT 1&ai=0",
        ]

        for page_url in pages:
            response = client.get(page_url)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            page_str = str(data)

            # Check for navigation elements
            assert "Back" in page_str or "Home" in page_str