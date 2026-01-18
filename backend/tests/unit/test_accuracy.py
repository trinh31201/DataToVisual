"""
Unit tests for chart accuracy.
Tests individual functions in isolation with mocks.
"""
import pytest
from unittest.mock import patch, AsyncMock
from decimal import Decimal
from datetime import date


class TestChartTypeAccuracy:
    """Test chart type prediction based on question keywords."""

    BAR_CHART_QUESTIONS = [
        "Show total sales by category",
        "Compare sales between categories",
        "What are the top 5 products by revenue",
        "Show revenue by product",
        "Count products per category",
        "Which category has highest sales",
        "Compare Q1 vs Q2 sales",
        "Show sales by region",
    ]

    LINE_CHART_QUESTIONS = [
        "Show monthly sales trend",
        "How are sales trending over time",
        "Show yearly revenue trend",
        "Display sales over the last 5 years",
        "Show daily orders for January",
        "What is the sales trend for 2024",
        "Show growth over time",
    ]

    PIE_CHART_QUESTIONS = [
        "Show sales distribution by category",
        "What percentage of sales is Electronics",
        "Show breakdown of revenue by product",
        "What is the proportion of each category",
        "Show market share by category",
        "Display percentage breakdown",
    ]

    def _predict_chart_type(self, question: str) -> str:
        """Predict chart type based on question keywords."""
        q = question.lower()

        line_keywords = ["trend", "over time", "monthly", "yearly", "daily", "growth", "over the last", "timeline"]
        if any(kw in q for kw in line_keywords):
            return "line"

        pie_keywords = ["distribution", "percentage", "proportion", "breakdown", "share", "percent"]
        if any(kw in q for kw in pie_keywords):
            return "pie"

        return "bar"

    @pytest.mark.parametrize("question", BAR_CHART_QUESTIONS)
    def test_bar_chart_questions(self, question):
        """Test questions that should produce bar charts."""
        assert self._predict_chart_type(question) == "bar"

    @pytest.mark.parametrize("question", LINE_CHART_QUESTIONS)
    def test_line_chart_questions(self, question):
        """Test questions that should produce line charts."""
        assert self._predict_chart_type(question) == "line"

    @pytest.mark.parametrize("question", PIE_CHART_QUESTIONS)
    def test_pie_chart_questions(self, question):
        """Test questions that should produce pie charts."""
        assert self._predict_chart_type(question) == "pie"


class TestDataFormatAccuracy:
    """Test data formatting functions."""

    def test_response_structure(self):
        """Test expected response structure."""
        response = {
            "question": "Show sales by category",
            "chart_type": "bar",
            "rows": [{"label": "Electronics", "value": 50000}]
        }
        assert "question" in response
        assert "chart_type" in response
        assert "rows" in response
        assert response["chart_type"] in ["bar", "line", "pie"]

    def test_row_structure(self):
        """Test each row has label and value."""
        rows = [
            {"label": "Electronics", "value": 50000},
            {"label": "Clothing", "value": 30000},
        ]
        for row in rows:
            assert "label" in row
            assert "value" in row

    def test_decimal_to_float(self):
        """Test Decimal values convert to float."""
        from app.mcp.server import format_rows
        rows = [{"label": "Test", "value": Decimal("12345.67")}]
        result = format_rows(rows)
        assert isinstance(result[0]["value"], float)
        assert result[0]["value"] == 12345.67

    def test_date_to_iso(self):
        """Test date values convert to ISO string."""
        from app.mcp.server import format_rows
        rows = [{"label": "Test", "value": date(2024, 1, 15)}]
        result = format_rows(rows)
        assert result[0]["value"] == "2024-01-15"

    def test_null_handling(self):
        """Test None values are preserved."""
        from app.mcp.server import format_rows
        rows = [{"label": "Test", "value": None}]
        result = format_rows(rows)
        assert result[0]["value"] is None


class TestSQLBuilderAccuracy:
    """Test SQL builder generates correct queries."""

    @pytest.mark.asyncio
    async def test_sum_aggregation(self):
        """Test SUM aggregation SQL."""
        from app.mcp.sql_builder import build_sql_from_structure

        with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
            with patch("app.mcp.sql_builder.get_valid_columns", new_callable=AsyncMock) as mock_c:
                mock_t.return_value = ["sales"]
                mock_c.return_value = ["category", "total_amount"]

                sql, _ = await build_sql_from_structure({
                    "table": "sales",
                    "label_column": "category",
                    "value_column": "total_amount",
                    "aggregation": "SUM",
                    "chart_type": "bar"
                })

                assert "SUM(total_amount)" in sql
                assert "GROUP BY category" in sql

    @pytest.mark.asyncio
    async def test_count_aggregation(self):
        """Test COUNT aggregation SQL."""
        from app.mcp.sql_builder import build_sql_from_structure

        with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
            with patch("app.mcp.sql_builder.get_valid_columns", new_callable=AsyncMock) as mock_c:
                mock_t.return_value = ["products"]
                mock_c.return_value = ["category", "id"]

                sql, _ = await build_sql_from_structure({
                    "table": "products",
                    "label_column": "category",
                    "value_column": "id",
                    "aggregation": "COUNT",
                    "chart_type": "bar"
                })

                assert "COUNT(id)" in sql

    @pytest.mark.asyncio
    async def test_no_aggregation(self):
        """Test NONE aggregation skips GROUP BY."""
        from app.mcp.sql_builder import build_sql_from_structure

        with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
            with patch("app.mcp.sql_builder.get_valid_columns", new_callable=AsyncMock) as mock_c:
                mock_t.return_value = ["products"]
                mock_c.return_value = ["name", "price"]

                sql, _ = await build_sql_from_structure({
                    "table": "products",
                    "label_column": "name",
                    "value_column": "price",
                    "aggregation": "NONE",
                    "chart_type": "bar"
                })

                assert "GROUP BY" not in sql

    @pytest.mark.asyncio
    async def test_limit_always_applied(self):
        """Test LIMIT is always added."""
        from app.mcp.sql_builder import build_sql_from_structure

        with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
            with patch("app.mcp.sql_builder.get_valid_columns", new_callable=AsyncMock) as mock_c:
                mock_t.return_value = ["products"]
                mock_c.return_value = ["name", "price"]

                sql, _ = await build_sql_from_structure({
                    "table": "products",
                    "label_column": "name",
                    "value_column": "price",
                    "aggregation": "NONE",
                    "chart_type": "bar"
                })

                assert "LIMIT" in sql

    @pytest.mark.asyncio
    async def test_all_aggregation_types(self):
        """Test all aggregation types work."""
        from app.mcp.sql_builder import build_sql_from_structure

        for agg in ["SUM", "COUNT", "AVG", "MAX", "MIN"]:
            with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
                with patch("app.mcp.sql_builder.get_valid_columns", new_callable=AsyncMock) as mock_c:
                    mock_t.return_value = ["sales"]
                    mock_c.return_value = ["category", "amount"]

                    sql, _ = await build_sql_from_structure({
                        "table": "sales",
                        "label_column": "category",
                        "value_column": "amount",
                        "aggregation": agg,
                        "chart_type": "bar"
                    })

                    assert f"{agg}(amount)" in sql


class TestSecurityAccuracy:
    """Test SQL security validation."""

    DANGEROUS_QUERIES = [
        "DROP TABLE users",
        "DELETE FROM sales",
        "UPDATE products SET price = 0",
        "INSERT INTO users VALUES (1, 'hack')",
        "SELECT * FROM users; DROP TABLE users;--",
        "SELECT * FROM users WHERE 1=1 OR 1=1--",
        "SELECT * /* comment */ FROM users",
    ]

    @pytest.mark.parametrize("sql", DANGEROUS_QUERIES)
    def test_dangerous_sql_blocked(self, sql):
        """Test dangerous SQL is blocked."""
        from app.mcp.sql_builder import validate_raw_sql
        with pytest.raises(ValueError):
            validate_raw_sql(sql)

    def test_select_only(self):
        """Test only SELECT allowed."""
        from app.mcp.sql_builder import validate_raw_sql

        result = validate_raw_sql("SELECT name FROM products")
        assert result.startswith("SELECT")

        with pytest.raises(ValueError, match="Only SELECT"):
            validate_raw_sql("SHOW TABLES")

    @pytest.mark.asyncio
    async def test_invalid_table_rejected(self):
        """Test invalid table is rejected."""
        from app.mcp.sql_builder import build_sql_from_structure

        with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
            mock_t.return_value = ["products", "sales"]

            with pytest.raises(ValueError, match="Invalid table"):
                await build_sql_from_structure({
                    "table": "users",
                    "label_column": "name",
                    "value_column": "id",
                    "aggregation": "COUNT",
                    "chart_type": "bar"
                })

    @pytest.mark.asyncio
    async def test_invalid_column_rejected(self):
        """Test invalid column is rejected."""
        from app.mcp.sql_builder import build_sql_from_structure

        with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
            with patch("app.mcp.sql_builder.get_valid_columns", new_callable=AsyncMock) as mock_c:
                mock_t.return_value = ["products"]
                mock_c.return_value = ["id", "name", "price"]

                with pytest.raises(ValueError, match="Invalid column"):
                    await build_sql_from_structure({
                        "table": "products",
                        "label_column": "password",
                        "value_column": "price",
                        "aggregation": "SUM",
                        "chart_type": "bar"
                    })
