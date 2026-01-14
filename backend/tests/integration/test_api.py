import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import db
from app.exceptions import AppException
from app.errors import ErrorType


@pytest.fixture(autouse=True)
async def setup_db():
    """Connect to database before each test, disconnect after."""
    await db.connect()
    yield
    await db.disconnect()


class TestAPIIntegration:
    """Integration tests for API with real database using MCP."""

    @pytest.mark.asyncio
    async def test_query_with_real_db(self):
        """Test query endpoint with real database, mocked MCP client."""
        mock_result = {
            "chart_type": "bar",
            "rows": [
                {"label": "Electronics", "value": 3},
                {"label": "Clothing", "value": 3},
                {"label": "Food", "value": 3},
                {"label": "Home", "value": 3}
            ]
        }

        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(return_value=mock_result)

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
        """Test querying sales trend with mocked MCP client."""
        mock_result = {
            "chart_type": "line",
            "rows": [
                {"label": 2022, "value": 100000},
                {"label": 2023, "value": 120000},
                {"label": 2024, "value": 140000},
                {"label": 2025, "value": 160000},
                {"label": 2026, "value": 180000}
            ]
        }

        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(return_value=mock_result)

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
                assert len(data["rows"]) == 5
                assert "label" in data["rows"][0]
                assert "value" in data["rows"][0]

    @pytest.mark.asyncio
    async def test_query_top_products(self):
        """Test querying top products with mocked MCP client."""
        mock_result = {
            "chart_type": "bar",
            "rows": [
                {"label": "Product A", "value": 50000},
                {"label": "Product B", "value": 40000},
                {"label": "Product C", "value": 30000},
                {"label": "Product D", "value": 20000},
                {"label": "Product E", "value": 10000}
            ]
        }

        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(return_value=mock_result)

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
    async def test_query_error(self):
        """Test that error from MCP client returns 500."""
        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(side_effect=AppException(
                ErrorType.INTERNAL_ERROR, "Database error"
            ))

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
        mock_result = {
            "chart_type": "pie",
            "rows": [
                {"label": "Electronics", "value": 50000},
                {"label": "Clothing", "value": 30000}
            ]
        }

        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(return_value=mock_result)

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
        mock_result = {
            "chart_type": "bar",
            "rows": [
                {"label": 2022, "value": 100000},
                {"label": 2026, "value": 180000}
            ]
        }

        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(return_value=mock_result)

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
