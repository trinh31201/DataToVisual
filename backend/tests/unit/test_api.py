import pytest
from unittest.mock import patch, AsyncMock
from app.exceptions import AppException
from app.errors import ErrorType


class TestQueryEndpoint:
    """Tests for /api/v1/query endpoint."""

    @pytest.mark.asyncio
    async def test_query_success(self, client):
        """Test successful query with mocked LLM and DB."""
        mock_llm_result = {
            "sql": "SELECT category, SUM(total) FROM sales GROUP BY category",
            "chart_type": "bar"
        }
        mock_db_result = [
            {"category": "Electronics", "total": 50000},
            {"category": "Clothing", "total": 30000},
        ]

        with patch("app.routers.query.llm_service") as mock_llm, \
             patch("app.routers.query.db") as mock_db:
            mock_llm.generate_sql.return_value = mock_llm_result
            mock_db.execute_query = AsyncMock(return_value=mock_db_result)

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show sales by category"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["question"] == "Show sales by category"
            assert data["chart_type"] == "bar"
            assert data["data"]["labels"] == ["Electronics", "Clothing"]

    @pytest.mark.asyncio
    async def test_query_llm_failure(self, client):
        """Test query when LLM fails returns 400."""
        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql.side_effect = AppException(
                ErrorType.INVALID_RESPONSE, "Invalid response"
            )

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show me sales"}
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_query_rate_limit(self, client):
        """Test query when rate limited returns 429."""
        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql.side_effect = AppException(
                ErrorType.RATE_LIMIT, "Rate limit exceeded"
            )

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show me sales"}
            )

            assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_query_not_configured(self, client):
        """Test query when LLM not configured returns 503."""
        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql.side_effect = AppException(
                ErrorType.NOT_CONFIGURED, "Gemini API key not configured"
            )

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show me sales"}
            )

            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_query_db_error(self, client):
        """Test query when database fails returns 500."""
        mock_llm_result = {
            "sql": "SELECT * FROM sales",
            "chart_type": "bar"
        }

        with patch("app.routers.query.llm_service") as mock_llm, \
             patch("app.routers.query.db") as mock_db:
            mock_llm.generate_sql.return_value = mock_llm_result
            mock_db.execute_query = AsyncMock(
                side_effect=Exception("Database connection failed")
            )

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show sales"}
            )

            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_query_empty_result(self, client):
        """Test query with empty database result."""
        mock_llm_result = {
            "sql": "SELECT * FROM sales WHERE year = 2030",
            "chart_type": "bar"
        }

        with patch("app.routers.query.llm_service") as mock_llm, \
             patch("app.routers.query.db") as mock_db:
            mock_llm.generate_sql.return_value = mock_llm_result
            mock_db.execute_query = AsyncMock(return_value=[])

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show sales for 2030"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["labels"] == []
            assert data["data"]["datasets"] == []

    @pytest.mark.asyncio
    async def test_query_missing_question(self, client):
        """Test query with missing question field."""
        response = await client.post("/api/v1/query", json={})
        assert response.status_code == 422  # Validation error
