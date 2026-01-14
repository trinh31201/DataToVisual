import pytest
from unittest.mock import patch, AsyncMock
from app.exceptions import AppException
from app.errors import ErrorType


class TestQueryEndpoint:
    """Tests for /api/v1/query endpoint with full MCP integration."""

    @pytest.mark.asyncio
    async def test_query_success(self, client):
        """Test successful query with mocked MCP client."""
        mock_result = {
            "chart_type": "bar",
            "rows": [
                {"label": "Electronics", "value": 50000},
                {"label": "Clothing", "value": 30000},
            ]
        }

        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(return_value=mock_result)

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show sales by category"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["question"] == "Show sales by category"
            assert data["chart_type"] == "bar"
            assert data["rows"] == mock_result["rows"]
            mock_mcp.query.assert_called_once_with("Show sales by category")

    @pytest.mark.asyncio
    async def test_query_llm_failure(self, client):
        """Test query when LLM fails returns 400."""
        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(side_effect=AppException(
                ErrorType.INVALID_RESPONSE, "Invalid response"
            ))

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show me sales"}
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_query_rate_limit(self, client):
        """Test query when rate limited returns 429."""
        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(side_effect=AppException(
                ErrorType.RATE_LIMIT, "Rate limit exceeded"
            ))

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show me sales"}
            )

            assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_query_not_configured(self, client):
        """Test query when AI not configured returns 503."""
        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(side_effect=AppException(
                ErrorType.NOT_CONFIGURED, "API key not configured"
            ))

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show me sales"}
            )

            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_query_internal_error(self, client):
        """Test query when internal error returns 500."""
        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(side_effect=AppException(
                ErrorType.INTERNAL_ERROR, "Database connection failed"
            ))

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show sales"}
            )

            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_query_empty_result(self, client):
        """Test query with empty result."""
        mock_result = {
            "chart_type": "bar",
            "rows": []
        }

        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(return_value=mock_result)

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
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_query_products(self, client):
        """Test query for products."""
        mock_result = {
            "chart_type": "bar",
            "rows": [
                {"label": "Product A", "value": 10000},
                {"label": "Product B", "value": 8000},
            ]
        }

        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(return_value=mock_result)

            response = await client.post(
                "/api/v1/query",
                json={"question": "What are top 5 selling products?"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["chart_type"] == "bar"
            assert len(data["rows"]) == 2
