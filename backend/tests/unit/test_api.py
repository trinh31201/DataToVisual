import pytest
from unittest.mock import patch, AsyncMock


class TestHealthEndpoint:
    """Tests for /api/v1/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestQueryEndpoint:
    """Tests for /api/v1/query endpoint."""

    @pytest.mark.asyncio
    async def test_query_success(self, client, mock_llm_response):
        """Test successful query with mocked LLM and DB."""
        mock_db_result = [
            {"category": "Electronics", "total": 50000},
            {"category": "Clothing", "total": 30000},
        ]

        with patch("app.routers.query.llm_service") as mock_llm, \
             patch("app.routers.query.db") as mock_db:
            mock_llm.generate_sql.return_value = mock_llm_response
            mock_db.execute_query = AsyncMock(return_value=mock_db_result)

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show sales by category"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["question"] == "Show sales by category"
            assert data["chart_type"] == "bar"
            assert data["data"]["labels"] == ["Electronics", "Clothing"]

    @pytest.mark.asyncio
    async def test_query_llm_failure(self, client):
        """Test query when LLM fails."""
        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql.return_value = {
                "success": False,
                "error": "API rate limit exceeded"
            }

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show me sales"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "API rate limit exceeded" in data["error"]

    @pytest.mark.asyncio
    async def test_query_db_error(self, client, mock_llm_response):
        """Test query when database fails."""
        with patch("app.routers.query.llm_service") as mock_llm, \
             patch("app.routers.query.db") as mock_db:
            mock_llm.generate_sql.return_value = mock_llm_response
            mock_db.execute_query = AsyncMock(
                side_effect=Exception("Database connection failed")
            )

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show sales"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "Database connection failed" in data["error"]

    @pytest.mark.asyncio
    async def test_query_empty_result(self, client, mock_llm_response):
        """Test query with empty database result."""
        with patch("app.routers.query.llm_service") as mock_llm, \
             patch("app.routers.query.db") as mock_db:
            mock_llm.generate_sql.return_value = mock_llm_response
            mock_db.execute_query = AsyncMock(return_value=[])

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show sales for 2030"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["labels"] == []
            assert data["data"]["datasets"] == []

    @pytest.mark.asyncio
    async def test_query_missing_question(self, client):
        """Test query with missing question field."""
        response = await client.post("/api/v1/query", json={})
        assert response.status_code == 422  # Validation error
