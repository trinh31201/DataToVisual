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
    """Integration tests for API with real database."""

    @pytest.mark.asyncio
    async def test_query_with_real_db(self):
        """Test query endpoint with real database, mocked LLM."""
        mock_llm_result = {
            "sql": "SELECT category, COUNT(*) as count FROM products GROUP BY category",
            "chart_type": "bar"
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql.return_value = mock_llm_result

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
                assert len(data["data"]["labels"]) > 0

    @pytest.mark.asyncio
    async def test_query_sales_trend(self):
        """Test querying sales trend with real database."""
        mock_llm_result = {
            "sql": """
                SELECT EXTRACT(YEAR FROM sale_date) as year, SUM(total_amount) as total
                FROM sales
                GROUP BY year
                ORDER BY year
            """,
            "chart_type": "line"
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql.return_value = mock_llm_result

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
                assert len(data["data"]["labels"]) == 5
                # Should have dataset with totals
                assert len(data["data"]["datasets"]) == 1

    @pytest.mark.asyncio
    async def test_query_top_products(self):
        """Test querying top products with real database."""
        mock_llm_result = {
            "sql": """
                SELECT p.name, SUM(s.total_amount) as total
                FROM sales s
                JOIN products p ON s.product_id = p.id
                GROUP BY p.name
                ORDER BY total DESC
                LIMIT 5
            """,
            "chart_type": "bar"
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql.return_value = mock_llm_result

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
                assert len(data["data"]["labels"]) == 5

    @pytest.mark.asyncio
    async def test_query_invalid_sql(self):
        """Test that invalid SQL returns 500 error."""
        mock_llm_result = {
            "sql": "SELECT * FROM nonexistent_table",
            "chart_type": "bar"
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql.return_value = mock_llm_result

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
    async def test_chart_data_format(self):
        """Test that chart data is properly formatted for Chart.js."""
        mock_llm_result = {
            "sql": """
                SELECT p.category, SUM(s.total_amount) as total_sales
                FROM sales s
                JOIN products p ON s.product_id = p.id
                GROUP BY p.category
            """,
            "chart_type": "pie"
        }

        with patch("app.routers.query.llm_service") as mock_llm:
            mock_llm.generate_sql.return_value = mock_llm_result

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/query",
                    json={"question": "Show sales distribution by category"}
                )

                data = response.json()

                # Verify Chart.js format
                chart_data = data["data"]
                assert "labels" in chart_data
                assert "datasets" in chart_data
                assert isinstance(chart_data["labels"], list)
                assert isinstance(chart_data["datasets"], list)

                # Each dataset should have label and data
                for dataset in chart_data["datasets"]:
                    assert "label" in dataset
                    assert "data" in dataset
                    assert isinstance(dataset["data"], list)
