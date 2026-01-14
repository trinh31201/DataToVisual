import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import db


@pytest.fixture(autouse=True)
async def setup_db():
    """Connect to database before each test, disconnect after."""
    await db.connect()
    yield
    await db.disconnect()


class TestAPIIntegration:
    """Integration tests for API with real database using function calling."""

    @pytest.mark.asyncio
    async def test_query_with_real_db(self):
        """Test query endpoint with real database, mocked LLM function call."""
        mock_function_call = {
            "name": "query_products",
            "args": {"select": "by_category", "chart_type": "bar"}
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.get_function_call.return_value = mock_function_call

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/query",
                    json={"question": "Show products by category"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["chart_type"] == "bar"
                assert len(data["rows"]) > 0
                assert "label" in data["rows"][0]
                assert "value" in data["rows"][0]

    @pytest.mark.asyncio
    async def test_query_sales_trend(self):
        """Test querying sales trend with real database."""
        mock_function_call = {
            "name": "query_sales",
            "args": {"group_by": "year", "chart_type": "line", "order": "ASC"}
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.get_function_call.return_value = mock_function_call

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/query",
                    json={"question": "Show sales trend over years"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["chart_type"] == "line"
                # Should have 5 years of data
                assert len(data["rows"]) == 5
                assert "label" in data["rows"][0]
                assert "value" in data["rows"][0]

    @pytest.mark.asyncio
    async def test_query_top_products(self):
        """Test querying top products with real database."""
        mock_function_call = {
            "name": "query_products",
            "args": {"select": "top_selling", "limit": 5, "chart_type": "bar"}
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.get_function_call.return_value = mock_function_call

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/query",
                    json={"question": "What are the top 5 products?"}
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data["rows"]) == 5

    @pytest.mark.asyncio
    async def test_query_unknown_tool(self):
        """Test that unknown tool returns 500 error."""
        mock_function_call = {
            "name": "unknown_tool",
            "args": {}
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.get_function_call.return_value = mock_function_call

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/query",
                    json={"question": "Show nonexistent data"}
                )

                assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_response_format(self):
        """Test that response has correct format with label and value."""
        mock_function_call = {
            "name": "query_sales",
            "args": {"group_by": "category", "chart_type": "pie"}
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.get_function_call.return_value = mock_function_call

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/query",
                    json={"question": "Show sales distribution by category"}
                )

                data = response.json()

                # Verify raw data format
                assert "rows" in data
                assert isinstance(data["rows"], list)

                # Each row should have label and value
                for row in data["rows"]:
                    assert isinstance(row, dict)
                    assert "label" in row
                    assert "value" in row

    @pytest.mark.asyncio
    async def test_query_sales_by_year_filter(self):
        """Test querying sales filtered by specific years."""
        mock_function_call = {
            "name": "query_sales",
            "args": {
                "group_by": "year",
                "years": [2022, 2026],
                "chart_type": "bar"
            }
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.get_function_call.return_value = mock_function_call

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/query",
                    json={"question": "Compare sales in 2022 vs 2026"}
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data["rows"]) == 2
