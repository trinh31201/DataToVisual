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
    """Integration tests for API with real database."""

    @pytest.mark.asyncio
    async def test_query_with_real_db(self):
        """Test query endpoint with real database, mocked LLM."""
        mock_result = {
            "sql": "SELECT category AS label, COUNT(*) AS value FROM products GROUP BY category",
            "chart_type": "bar"
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql = lambda q: mock_result

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
        """Test querying sales trend with mocked LLM."""
        mock_result = {
            "sql": """
                SELECT EXTRACT(YEAR FROM sale_date) AS label, SUM(total_amount) AS value
                FROM sales GROUP BY EXTRACT(YEAR FROM sale_date) ORDER BY label
            """,
            "chart_type": "line"
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql = lambda q: mock_result

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
                assert "label" in data["rows"][0]
                assert "value" in data["rows"][0]

    @pytest.mark.asyncio
    async def test_query_error(self):
        """Test that error from LLM returns proper status code."""
        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql = lambda q: (_ for _ in ()).throw(
                AppException(ErrorType.INTERNAL_ERROR, "Database error")
            )

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/query",
                    json={"question": "Show nonexistent data"}
                )

                assert response.status_code == 500
