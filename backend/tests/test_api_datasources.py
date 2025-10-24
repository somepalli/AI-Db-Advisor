# tests/test_api_datasources.py
"""
API tests for datasource management endpoints
"""
import pytest
from fastapi import status


class TestDataSourcesAPI:
    """Test suite for /datasources endpoints"""

    def test_healthcheck(self, client):
        """Test healthcheck endpoint"""
        response = client.get("/healthz")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"ok": True}

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ok"] is True
        assert data["service"] == "ai-db-advisor"
        assert data["ui"] == "/ui"

    def test_list_datasources_empty(self, client):
        """Test listing datasources when none are registered"""
        response = client.get("/datasources")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 0

    def test_register_datasource_success(self, client, sample_datasource):
        """Test registering a new datasource"""
        response = client.post("/datasources", json=sample_datasource)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["ok"] is True
        assert data["id"] == sample_datasource["id"]

    def test_register_datasource_missing_fields(self, client):
        """Test registering datasource with missing required fields"""
        incomplete_ds = {"id": "test"}
        response = client.post("/datasources", json=incomplete_ds)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_datasource_duplicate_id(self, client, sample_datasource):
        """Test registering datasource with duplicate ID"""
        # Register first time
        client.post("/datasources", json=sample_datasource)

        # Try to register again with same ID
        response = client.post("/datasources", json=sample_datasource)
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_list_datasources_after_registration(self, client, sample_datasource):
        """Test listing datasources after registering one"""
        # Register a datasource
        client.post("/datasources", json=sample_datasource)

        # List datasources
        response = client.get("/datasources")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == sample_datasource["id"]
        assert data["items"][0]["engine"] == sample_datasource["engine"]
        assert data["items"][0]["dsn"] == sample_datasource["dsn"]

    def test_register_multiple_datasources(self, client):
        """Test registering multiple datasources"""
        datasources = [
            {"id": "pg-dev", "engine": "postgres", "dsn": "postgresql://localhost/dev"},
            {"id": "pg-prod", "engine": "postgres", "dsn": "postgresql://localhost/prod"},
            {"id": "pg-test", "engine": "postgres", "dsn": "postgresql://localhost/test"},
        ]

        for ds in datasources:
            response = client.post("/datasources", json=ds)
            assert response.status_code == status.HTTP_201_CREATED

        # Verify all are listed
        response = client.get("/datasources")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 3

    def test_register_datasource_with_different_engines(self, client):
        """Test registering datasources with different engine names"""
        engines = ["postgres", "postgresql", "pg"]

        for idx, engine in enumerate(engines):
            ds = {
                "id": f"test-{engine}-{idx}",
                "engine": engine,
                "dsn": f"postgresql://localhost/test{idx}"
            }
            response = client.post("/datasources", json=ds)
            assert response.status_code == status.HTTP_201_CREATED