import pytest
from unittest.mock import patch, AsyncMock
from app.exceptions import AppException
from app.errors import ErrorType


class TestQueryEndpoint:
    """Tests for /api/v1/query endpoint with function calling."""

    @pytest.mark.asyncio
    async def test_query_success(self, client):
        """Test successful query with mocked LLM and tool execution."""
        mock_function_call = {
            "name": "query_sales",
            "args": {"group_by": "category", "chart_type": "bar"}
        }
        mock_tool_result = {
            "chart_type": "bar",
            "rows": [
                {"label": "Electronics", "value": 50000},
                {"label": "Clothing", "value": 30000},
            ]
        }

        with patch("app.routers.query.llm_service") as mock_llm, \
             patch("app.routers.query.execute_tool", new_callable=AsyncMock) as mock_tool:
            mock_llm.get_function_call.return_value = mock_function_call
            mock_tool.return_value = mock_tool_result

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show sales by category"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["question"] == "Show sales by category"
            assert data["chart_type"] == "bar"
            assert data["rows"] == mock_tool_result["rows"]
            mock_tool.assert_called_once_with("query_sales", {"group_by": "category", "chart_type": "bar"})

    @pytest.mark.asyncio
    async def test_query_llm_failure(self, client):
        """Test query when LLM fails returns 400."""
        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.get_function_call.side_effect = AppException(
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
            mock_llm.get_function_call.side_effect = AppException(
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
            mock_llm.get_function_call.side_effect = AppException(
                ErrorType.NOT_CONFIGURED, "Gemini API key not configured"
            )

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show me sales"}
            )

            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_query_tool_error(self, client):
        """Test query when tool execution fails returns 500."""
        mock_function_call = {
            "name": "query_sales",
            "args": {"group_by": "category", "chart_type": "bar"}
        }

        with patch("app.routers.query.llm_service") as mock_llm, \
             patch("app.routers.query.execute_tool", new_callable=AsyncMock) as mock_tool:
            mock_llm.get_function_call.return_value = mock_function_call
            mock_tool.side_effect = Exception("Database connection failed")

            response = await client.post(
                "/api/v1/query",
                json={"question": "Show sales"}
            )

            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_query_empty_result(self, client):
        """Test query with empty tool result."""
        mock_function_call = {
            "name": "query_sales",
            "args": {"group_by": "year", "years": [2030], "chart_type": "bar"}
        }
        mock_tool_result = {
            "chart_type": "bar",
            "rows": []
        }

        with patch("app.routers.query.llm_service") as mock_llm, \
             patch("app.routers.query.execute_tool", new_callable=AsyncMock) as mock_tool:
            mock_llm.get_function_call.return_value = mock_function_call
            mock_tool.return_value = mock_tool_result

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
        mock_function_call = {
            "name": "query_products",
            "args": {"select": "top_selling", "limit": 5, "chart_type": "bar"}
        }
        mock_tool_result = {
            "chart_type": "bar",
            "rows": [
                {"label": "Product A", "value": 10000},
                {"label": "Product B", "value": 8000},
            ]
        }

        with patch("app.routers.query.llm_service") as mock_llm, \
             patch("app.routers.query.execute_tool", new_callable=AsyncMock) as mock_tool:
            mock_llm.get_function_call.return_value = mock_function_call
            mock_tool.return_value = mock_tool_result

            response = await client.post(
                "/api/v1/query",
                json={"question": "What are top 5 selling products?"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["chart_type"] == "bar"
            assert len(data["rows"]) == 2
