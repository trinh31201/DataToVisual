"""
Integration tests for chart accuracy.
Tests with real database connections and full API flow.
"""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import db


@pytest.fixture(autouse=True)
async def setup_db():
    """Connect to database before each test, disconnect after."""
    await db.connect()
    yield
    await db.disconnect()


class TestDatabaseAccuracy:
    """Test data accuracy against real database."""

    @pytest.mark.asyncio
    async def test_schema_introspection(self):
        """Test schema introspection returns real tables."""
        from app.mcp.sql_builder import get_valid_tables

        tables = await get_valid_tables()

        assert "products" in tables
        assert "sales" in tables
        assert "features" in tables

    @pytest.mark.asyncio
    async def test_column_introspection(self):
        """Test column introspection returns real columns."""
        from app.mcp.sql_builder import get_valid_columns

        # Products table
        product_cols = await get_valid_columns("products")
        assert "id" in product_cols
        assert "name" in product_cols
        assert "category" in product_cols
        assert "price" in product_cols

        # Sales table
        sales_cols = await get_valid_columns("sales")
        assert "id" in sales_cols
        assert "product_id" in sales_cols
        assert "total_amount" in sales_cols
        assert "sale_date" in sales_cols

    @pytest.mark.asyncio
    async def test_direct_sql_execution(self):
        """Test direct SQL execution returns data."""
        sql = "SELECT category, COUNT(*) as count FROM products GROUP BY category"
        rows = await db.execute_query(sql)

        assert len(rows) > 0
        for row in rows:
            assert "category" in row
            assert "count" in row

    @pytest.mark.asyncio
    async def test_sales_data_exists(self):
        """Test sales data exists in database."""
        sql = "SELECT COUNT(*) as count FROM sales"
        rows = await db.execute_query(sql)

        assert rows[0]["count"] > 0

    @pytest.mark.asyncio
    async def test_products_have_categories(self):
        """Test products have expected categories."""
        sql = "SELECT DISTINCT category FROM products"
        rows = await db.execute_query(sql)

        categories = [row["category"] for row in rows]
        assert len(categories) >= 1  # At least one category exists


class TestSQLBuilderWithRealDB:
    """Test SQL builder with real database schema."""

    @pytest.mark.asyncio
    async def test_build_products_query(self):
        """Test building query for products table."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, params = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "AVG",
            "chart_type": "bar"
        })

        # Execute the generated SQL
        rows = await db.execute_query(sql, params)

        assert len(rows) > 0
        for row in rows:
            assert "label" in row
            assert "value" in row
            assert isinstance(row["value"], (int, float))

    @pytest.mark.asyncio
    async def test_build_sales_query(self):
        """Test building query for sales table."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, params = await build_sql_from_structure({
            "table": "sales",
            "label_column": "product_id",
            "value_column": "total_amount",
            "aggregation": "SUM",
            "chart_type": "bar"
        })

        rows = await db.execute_query(sql, params)

        assert len(rows) > 0
        for row in rows:
            assert "label" in row
            assert "value" in row

    @pytest.mark.asyncio
    async def test_build_query_with_limit(self):
        """Test LIMIT is respected."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, params = await build_sql_from_structure({
            "table": "products",
            "label_column": "name",
            "value_column": "price",
            "aggregation": "NONE",
            "limit": 3,
            "chart_type": "bar"
        })

        rows = await db.execute_query(sql, params)

        assert len(rows) <= 3

    @pytest.mark.asyncio
    async def test_build_query_with_order(self):
        """Test ORDER BY is applied."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, params = await build_sql_from_structure({
            "table": "products",
            "label_column": "name",
            "value_column": "price",
            "aggregation": "NONE",
            "order_by": "value_desc",
            "limit": 5,
            "chart_type": "bar"
        })

        rows = await db.execute_query(sql, params)

        # Check descending order
        if len(rows) > 1:
            for i in range(len(rows) - 1):
                assert rows[i]["value"] >= rows[i + 1]["value"]


class TestEndToEndAccuracy:
    """Test full API flow with real database."""

    @pytest.mark.asyncio
    async def test_api_returns_correct_structure(self):
        """Test API returns correct response structure."""
        mock_result = {
            "chart_type": "bar",
            "rows": [
                {"label": "Electronics", "value": 50000.0},
                {"label": "Clothing", "value": 30000.0},
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
                    json={"question": "Show sales by category"}
                )

                assert response.status_code == 200
                data = response.json()

                # Structure checks
                assert "question" in data
                assert "chart_type" in data
                assert "rows" in data
                assert data["chart_type"] in ["bar", "line", "pie"]

                # Row structure
                for row in data["rows"]:
                    assert "label" in row
                    assert "value" in row

    @pytest.mark.asyncio
    async def test_api_handles_empty_results(self):
        """Test API handles empty query results."""
        mock_result = {
            "chart_type": "bar",
            "rows": []
        }

        with patch("app.routers.query.mcp_client") as mock_mcp:
            mock_mcp.query = AsyncMock(return_value=mock_result)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/query",
                    json={"question": "Show sales for year 3000"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["rows"] == []

    @pytest.mark.asyncio
    async def test_api_handles_large_values(self):
        """Test API handles large numeric values."""
        mock_result = {
            "chart_type": "bar",
            "rows": [
                {"label": "Total", "value": 99999999999.99}
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
                    json={"question": "Show total revenue"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["rows"][0]["value"] > 99999999999


class TestDataIntegrity:
    """Test data integrity between components."""

    @pytest.mark.asyncio
    async def test_product_count_matches(self):
        """Test product count is consistent."""
        # Direct count
        direct = await db.execute_query("SELECT COUNT(*) as count FROM products")
        direct_count = direct[0]["count"]

        # Via SQL builder
        from app.mcp.sql_builder import build_sql_from_structure
        sql, params = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "id",
            "aggregation": "COUNT",
            "chart_type": "bar"
        })
        builder_rows = await db.execute_query(sql, params)
        builder_count = sum(row["value"] for row in builder_rows)

        assert direct_count == builder_count

    @pytest.mark.asyncio
    async def test_sales_total_matches(self):
        """Test sales total is consistent."""
        # Direct sum
        direct = await db.execute_query(
            "SELECT SUM(total_amount) as total FROM sales"
        )
        direct_total = float(direct[0]["total"])

        # Via SQL builder (sum by product_id, then sum again)
        from app.mcp.sql_builder import build_sql_from_structure
        sql, params = await build_sql_from_structure({
            "table": "sales",
            "label_column": "product_id",
            "value_column": "total_amount",
            "aggregation": "SUM",
            "chart_type": "bar"
        })
        builder_rows = await db.execute_query(sql, params)
        builder_total = sum(float(row["value"]) for row in builder_rows)

        # Allow small floating point difference
        assert abs(direct_total - builder_total) < 0.01

    @pytest.mark.asyncio
    async def test_category_names_preserved(self):
        """Test category names are not modified."""
        # Get actual categories from DB
        direct = await db.execute_query(
            "SELECT DISTINCT category FROM products ORDER BY category"
        )
        direct_categories = [row["category"] for row in direct]

        # Via SQL builder
        from app.mcp.sql_builder import build_sql_from_structure
        sql, params = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "id",
            "aggregation": "COUNT",
            "order_by": "label_asc",
            "chart_type": "bar"
        })
        builder_rows = await db.execute_query(sql, params)
        builder_categories = [row["label"] for row in builder_rows]

        assert direct_categories == builder_categories


class TestQueryTimeout:
    """Test query timeout handling."""

    @pytest.mark.asyncio
    async def test_simple_query_completes(self):
        """Test simple queries complete within timeout."""
        from app.mcp.sql_builder import build_sql_from_structure
        import asyncio

        sql, params = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "AVG",
            "chart_type": "bar"
        })

        # Should complete within 5 seconds
        try:
            rows = await asyncio.wait_for(
                db.execute_query(sql, params),
                timeout=5.0
            )
            assert len(rows) >= 0  # Query completed
        except asyncio.TimeoutError:
            pytest.fail("Query timed out unexpectedly")
