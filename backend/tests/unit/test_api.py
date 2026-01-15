import pytest
from unittest.mock import patch, AsyncMock
from app.exceptions import AppException
from app.errors import ErrorType


class TestQueryEndpoint:
    """Tests for /api/v1/query endpoint - raw SQL approach."""

    @pytest.mark.asyncio
    async def test_query_success(self, client):
        """Test successful query with mocked LLM."""
        mock_result = {"sql": "SELECT category AS label, COUNT(*) AS value FROM products GROUP BY category", "chart_type": "bar"}
        mock_rows = [{"label": "Electronics", "value": 50000}, {"label": "Clothing", "value": 30000}]

        with patch("app.routers.query.llm_service") as mock_llm:
            with patch("app.routers.query.db") as mock_db:
                mock_llm.generate_sql = lambda q: mock_result
                mock_db.execute_query = AsyncMock(return_value=mock_rows)

                response = await client.post(
                    "/api/v1/query",
                    json={"question": "Show sales by category"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["question"] == "Show sales by category"
                assert data["chart_type"] == "bar"
                assert data["rows"] == mock_rows

    @pytest.mark.asyncio
    async def test_query_llm_failure(self, client):
        """Test query when LLM fails returns 400."""
        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql = lambda q: (_ for _ in ()).throw(
                AppException(ErrorType.INVALID_RESPONSE, "Invalid response")
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
            mock_llm.generate_sql = lambda q: (_ for _ in ()).throw(
                AppException(ErrorType.RATE_LIMIT, "Rate limit exceeded")
            )

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show me sales"}
            )

            assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_query_not_configured(self, client):
        """Test query when AI not configured returns 503."""
        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql = lambda q: (_ for _ in ()).throw(
                AppException(ErrorType.NOT_CONFIGURED, "API key not configured")
            )

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show me sales"}
            )

            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_query_empty_result(self, client):
        """Test query with empty result."""
        mock_result = {"sql": "SELECT * FROM sales WHERE 1=0", "chart_type": "bar"}

        with patch("app.routers.query.llm_service") as mock_llm:
            with patch("app.routers.query.db") as mock_db:
                mock_llm.generate_sql = lambda q: mock_result
                mock_db.execute_query = AsyncMock(return_value=[])

                response = await client.post(
                    "/api/v1/query",
                    json={"question": "Show sales for 2030"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["rows"] == []

    @pytest.mark.asyncio
    async def test_query_missing_question(self, client):
        """Test query with missing question field."""
        response = await client.post("/api/v1/query", json={})
        assert response.status_code == 422
