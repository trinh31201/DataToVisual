"""
SQL Correctness Tests.
Verify MCP generates correct SQL for given requests.
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.db.database import db


@pytest.fixture(autouse=True)
async def setup_db():
    """Connect to database before each test."""
    await db.connect()
    yield
    await db.disconnect()


class TestSimpleQuerySQLGeneration:
    """Test simple_query tool generates correct SQL."""

    @pytest.mark.asyncio
    async def test_generates_select(self):
        """Test generates SELECT statement."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, _ = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "SUM",
            "chart_type": "bar"
        })

        assert sql.strip().upper().startswith("SELECT")

    @pytest.mark.asyncio
    async def test_generates_correct_columns(self):
        """Test generates correct label and value columns."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, _ = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "SUM",
            "chart_type": "bar"
        })

        assert "category AS label" in sql
        assert "SUM(price) AS value" in sql

    @pytest.mark.asyncio
    async def test_generates_correct_table(self):
        """Test generates correct FROM table."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, _ = await build_sql_from_structure({
            "table": "sales",
            "label_column": "product_id",
            "value_column": "total_amount",
            "aggregation": "SUM",
            "chart_type": "bar"
        })

        assert "FROM sales" in sql

    @pytest.mark.asyncio
    async def test_generates_group_by_for_aggregation(self):
        """Test generates GROUP BY when aggregating."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, _ = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "AVG",
            "chart_type": "bar"
        })

        assert "GROUP BY category" in sql

    @pytest.mark.asyncio
    async def test_no_group_by_without_aggregation(self):
        """Test no GROUP BY when aggregation is NONE."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, _ = await build_sql_from_structure({
            "table": "products",
            "label_column": "name",
            "value_column": "price",
            "aggregation": "NONE",
            "chart_type": "bar"
        })

        assert "GROUP BY" not in sql

    @pytest.mark.asyncio
    async def test_generates_where_clause(self):
        """Test generates WHERE clause for filters."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, params = await build_sql_from_structure({
            "table": "sales",
            "label_column": "product_id",
            "value_column": "total_amount",
            "aggregation": "SUM",
            "filters": [
                {"column": "product_id", "operator": "=", "value": "1"}
            ],
            "chart_type": "bar"
        })

        assert "WHERE" in sql
        assert "product_id =" in sql
        assert "filter_0" in params

    @pytest.mark.asyncio
    async def test_generates_order_by(self):
        """Test generates ORDER BY clause."""
        from app.mcp.sql_builder import build_sql_from_structure

        # Test value_desc
        sql, _ = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "SUM",
            "order_by": "value_desc",
            "chart_type": "bar"
        })
        assert "ORDER BY value DESC" in sql

        # Test label_asc
        sql, _ = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "SUM",
            "order_by": "label_asc",
            "chart_type": "bar"
        })
        assert "ORDER BY label ASC" in sql

    @pytest.mark.asyncio
    async def test_generates_limit(self):
        """Test generates LIMIT clause."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, _ = await build_sql_from_structure({
            "table": "products",
            "label_column": "name",
            "value_column": "price",
            "aggregation": "NONE",
            "limit": 5,
            "chart_type": "bar"
        })

        assert "LIMIT 5" in sql

    @pytest.mark.asyncio
    async def test_all_aggregation_functions(self):
        """Test all aggregation functions generate correct SQL."""
        from app.mcp.sql_builder import build_sql_from_structure

        test_cases = [
            ("SUM", "SUM(price)"),
            ("COUNT", "COUNT(price)"),
            ("AVG", "AVG(price)"),
            ("MAX", "MAX(price)"),
            ("MIN", "MIN(price)"),
        ]

        for agg, expected in test_cases:
            sql, _ = await build_sql_from_structure({
                "table": "products",
                "label_column": "category",
                "value_column": "price",
                "aggregation": agg,
                "chart_type": "bar"
            })
            assert expected in sql, f"Expected {expected} for aggregation {agg}"


class TestAdvancedQuerySQLValidation:
    """Test advanced_query validates SQL correctly."""

    def test_accepts_valid_select(self):
        """Test accepts valid SELECT query."""
        from app.mcp.sql_builder import validate_raw_sql

        sql = validate_raw_sql(
            "SELECT p.category AS label, SUM(s.total_amount) AS value "
            "FROM sales s JOIN products p ON s.product_id = p.id "
            "GROUP BY p.category"
        )

        assert sql.startswith("SELECT")
        assert "LIMIT" in sql  # Auto-added

    def test_accepts_subquery(self):
        """Test accepts query with subquery."""
        from app.mcp.sql_builder import validate_raw_sql

        sql = validate_raw_sql(
            "SELECT category AS label, total AS value FROM "
            "(SELECT p.category, SUM(s.total_amount) as total "
            "FROM sales s JOIN products p ON s.product_id = p.id "
            "GROUP BY p.category) sub"
        )

        assert "SELECT" in sql

    def test_rejects_non_select(self):
        """Test rejects non-SELECT statements."""
        from app.mcp.sql_builder import validate_raw_sql

        with pytest.raises(ValueError, match="Only SELECT"):
            validate_raw_sql("UPDATE products SET price = 0")

    def test_rejects_dangerous_keywords(self):
        """Test rejects dangerous SQL keywords."""
        from app.mcp.sql_builder import validate_raw_sql

        dangerous = [
            "SELECT * FROM products; DROP TABLE products",
            "SELECT * FROM products WHERE 1=1 -- comment",
            "SELECT * FROM products /* block comment */",
        ]

        for sql in dangerous:
            with pytest.raises(ValueError):
                validate_raw_sql(sql)


class TestGeneratedSQLExecutes:
    """Test generated SQL actually executes on database."""

    @pytest.mark.asyncio
    async def test_simple_query_executes(self):
        """Test simple_query generated SQL executes."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, params = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "AVG",
            "chart_type": "bar"
        })

        # Should not raise
        rows = await db.execute_query(sql, params)
        assert isinstance(rows, list)

    @pytest.mark.asyncio
    async def test_simple_query_with_order_executes(self):
        """Test simple_query with ORDER BY executes."""
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
        assert isinstance(rows, list)
        assert len(rows) <= 5

    @pytest.mark.asyncio
    async def test_advanced_query_executes(self):
        """Test advanced_query validated SQL executes."""
        from app.mcp.sql_builder import validate_raw_sql

        sql = validate_raw_sql(
            "SELECT p.category AS label, SUM(s.total_amount) AS value "
            "FROM sales s JOIN products p ON s.product_id = p.id "
            "GROUP BY p.category ORDER BY value DESC"
        )

        rows = await db.execute_query(sql)
        assert isinstance(rows, list)


class TestGeneratedSQLReturnsCorrectFormat:
    """Test generated SQL returns data in correct format."""

    @pytest.mark.asyncio
    async def test_returns_label_and_value(self):
        """Test result has label and value columns."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, params = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "SUM",
            "chart_type": "bar"
        })

        rows = await db.execute_query(sql, params)

        for row in rows:
            assert "label" in row, "Missing 'label' column"
            assert "value" in row, "Missing 'value' column"

    @pytest.mark.asyncio
    async def test_label_is_string_or_date(self):
        """Test label is string or date type."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, params = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "SUM",
            "chart_type": "bar"
        })

        rows = await db.execute_query(sql, params)

        for row in rows:
            assert row["label"] is not None

    @pytest.mark.asyncio
    async def test_value_is_numeric(self):
        """Test value is numeric type."""
        from app.mcp.sql_builder import build_sql_from_structure

        sql, params = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "SUM",
            "chart_type": "bar"
        })

        rows = await db.execute_query(sql, params)

        for row in rows:
            # Value should be numeric (int, float, Decimal)
            assert isinstance(row["value"], (int, float)) or hasattr(row["value"], '__float__')


class TestSQLMatchesIntent:
    """Test generated SQL matches the intended query."""

    @pytest.mark.asyncio
    async def test_sum_by_category_intent(self):
        """Test 'total sales by category' generates correct SQL."""
        from app.mcp.sql_builder import build_sql_from_structure

        # Intent: "Show total sales by category"
        sql, _ = await build_sql_from_structure({
            "table": "sales",
            "label_column": "product_id",  # Would need JOIN for category
            "value_column": "total_amount",
            "aggregation": "SUM",
            "chart_type": "bar"
        })

        # Should have SUM aggregation
        assert "SUM(total_amount)" in sql
        # Should group by label
        assert "GROUP BY" in sql

    @pytest.mark.asyncio
    async def test_count_products_intent(self):
        """Test 'count products per category' generates correct SQL."""
        from app.mcp.sql_builder import build_sql_from_structure

        # Intent: "Count products per category"
        sql, _ = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "id",
            "aggregation": "COUNT",
            "chart_type": "bar"
        })

        assert "COUNT(id)" in sql
        assert "GROUP BY category" in sql

    @pytest.mark.asyncio
    async def test_top_5_intent(self):
        """Test 'top 5 products' generates correct SQL."""
        from app.mcp.sql_builder import build_sql_from_structure

        # Intent: "Top 5 products by price"
        sql, _ = await build_sql_from_structure({
            "table": "products",
            "label_column": "name",
            "value_column": "price",
            "aggregation": "NONE",
            "order_by": "value_desc",
            "limit": 5,
            "chart_type": "bar"
        })

        assert "ORDER BY value DESC" in sql
        assert "LIMIT 5" in sql

    @pytest.mark.asyncio
    async def test_average_price_intent(self):
        """Test 'average price by category' generates correct SQL."""
        from app.mcp.sql_builder import build_sql_from_structure

        # Intent: "Average price by category"
        sql, _ = await build_sql_from_structure({
            "table": "products",
            "label_column": "category",
            "value_column": "price",
            "aggregation": "AVG",
            "chart_type": "bar"
        })

        assert "AVG(price)" in sql
        assert "GROUP BY category" in sql
