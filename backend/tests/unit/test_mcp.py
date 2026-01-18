import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.exceptions import AppException
from app.errors import ErrorType


class TestMCPServerTools:
    """Tests for MCP server tool definitions."""

    def test_tools_count(self):
        """Test that MCP has 2 tools defined."""
        from app.mcp.server import TOOLS
        assert len(TOOLS) == 2

    def test_tool_names(self):
        """Test tool names are correct."""
        from app.mcp.server import TOOLS
        tool_names = [t.name for t in TOOLS]
        assert "simple_query" in tool_names
        assert "advanced_query" in tool_names

    def test_simple_query_schema(self):
        """Test simple_query has required properties."""
        from app.mcp.server import TOOLS
        tool = next(t for t in TOOLS if t.name == "simple_query")
        props = tool.inputSchema["properties"]

        assert "table" in props
        assert "label_column" in props
        assert "value_column" in props
        assert "aggregation" in props
        assert "chart_type" in props

    def test_advanced_query_schema(self):
        """Test advanced_query has required properties."""
        from app.mcp.server import TOOLS
        tool = next(t for t in TOOLS if t.name == "advanced_query")
        props = tool.inputSchema["properties"]

        assert "sql" in props
        assert "chart_type" in props


class TestMCPServerHandlers:
    """Tests for MCP server handlers."""

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test list_tools returns all tools."""
        from app.mcp.server import list_tools
        tools = await list_tools()
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_list_resources(self):
        """Test list_resources returns schema resource."""
        from app.mcp.server import list_resources
        resources = await list_resources()
        assert len(resources) == 1
        assert "schema://database" in str(resources[0].uri)

    @pytest.mark.asyncio
    async def test_list_prompts(self):
        """Test list_prompts returns data_analyst."""
        from app.mcp.server import list_prompts
        prompts = await list_prompts()
        assert len(prompts) == 1
        assert prompts[0].name == "data_analyst"


class TestMCPServerHelpers:
    """Tests for MCP server helper functions."""

    def test_format_rows_decimal(self):
        """Test format_rows converts Decimal to float."""
        from app.mcp.server import format_rows
        from decimal import Decimal

        rows = [{"label": "Test", "value": Decimal("100.50")}]
        result = format_rows(rows)
        assert result[0]["value"] == 100.50
        assert isinstance(result[0]["value"], float)

    def test_format_rows_date(self):
        """Test format_rows converts date to ISO string."""
        from app.mcp.server import format_rows
        from datetime import date

        rows = [{"label": "Test", "value": date(2024, 1, 15)}]
        result = format_rows(rows)
        assert result[0]["value"] == "2024-01-15"

    def test_format_rows_datetime(self):
        """Test format_rows converts datetime to ISO string."""
        from app.mcp.server import format_rows
        from datetime import datetime

        rows = [{"label": "Test", "value": datetime(2024, 1, 15, 10, 30)}]
        result = format_rows(rows)
        assert result[0]["value"] == "2024-01-15T10:30:00"

    def test_get_sql_hints_postgresql(self):
        """Test SQL hints for PostgreSQL."""
        from app.mcp.server import get_sql_hints
        hints = get_sql_hints("postgresql")
        assert "EXTRACT" in hints

    def test_get_sql_hints_sqlite(self):
        """Test SQL hints for SQLite."""
        from app.mcp.server import get_sql_hints
        hints = get_sql_hints("sqlite")
        assert "strftime" in hints

    def test_get_sql_hints_unknown(self):
        """Test SQL hints for unknown DB returns empty."""
        from app.mcp.server import get_sql_hints
        hints = get_sql_hints("unknown")
        assert hints == ""


class TestSQLValidation:
    """Tests for SQL validation in sql_builder."""

    def test_valid_select(self):
        """Test valid SELECT query passes."""
        from app.mcp.sql_builder import validate_raw_sql
        sql = validate_raw_sql("SELECT name, price FROM products")
        assert sql.startswith("SELECT")

    def test_auto_adds_limit(self):
        """Test LIMIT 1000 is auto-added."""
        from app.mcp.sql_builder import validate_raw_sql
        sql = validate_raw_sql("SELECT name FROM products")
        assert "LIMIT 1000" in sql

    def test_preserves_existing_limit(self):
        """Test existing LIMIT is preserved."""
        from app.mcp.sql_builder import validate_raw_sql
        sql = validate_raw_sql("SELECT name FROM products LIMIT 10")
        assert "LIMIT 10" in sql
        assert sql.count("LIMIT") == 1

    def test_blocks_drop(self):
        """Test DROP is blocked (fails SELECT check first)."""
        from app.mcp.sql_builder import validate_raw_sql
        with pytest.raises(ValueError, match="Only SELECT"):
            validate_raw_sql("DROP TABLE products")

    def test_blocks_delete(self):
        """Test DELETE is blocked (fails SELECT check first)."""
        from app.mcp.sql_builder import validate_raw_sql
        with pytest.raises(ValueError, match="Only SELECT"):
            validate_raw_sql("DELETE FROM products")

    def test_blocks_update(self):
        """Test UPDATE is blocked (fails SELECT check first)."""
        from app.mcp.sql_builder import validate_raw_sql
        with pytest.raises(ValueError, match="Only SELECT"):
            validate_raw_sql("UPDATE products SET price = 0")

    def test_blocks_insert(self):
        """Test INSERT is blocked (fails SELECT check first)."""
        from app.mcp.sql_builder import validate_raw_sql
        with pytest.raises(ValueError, match="Only SELECT"):
            validate_raw_sql("INSERT INTO products VALUES (1)")

    def test_blocks_drop_in_select(self):
        """Test DROP keyword inside SELECT is blocked."""
        from app.mcp.sql_builder import validate_raw_sql
        with pytest.raises(ValueError, match="Dangerous keyword"):
            validate_raw_sql("SELECT * FROM users WHERE 1=1 DROP TABLE users")

    def test_blocks_semicolon(self):
        """Test semicolon injection is blocked."""
        from app.mcp.sql_builder import validate_raw_sql
        with pytest.raises(ValueError, match="Dangerous keyword|SQL pattern"):
            validate_raw_sql("SELECT * FROM users; DROP TABLE users")

    def test_blocks_comment(self):
        """Test comment injection is blocked."""
        from app.mcp.sql_builder import validate_raw_sql
        with pytest.raises(ValueError, match="SQL pattern"):
            validate_raw_sql("SELECT * FROM users -- hack")

    def test_blocks_block_comment(self):
        """Test block comment is blocked."""
        from app.mcp.sql_builder import validate_raw_sql
        with pytest.raises(ValueError, match="SQL pattern"):
            validate_raw_sql("SELECT * /* hack */ FROM users")

    def test_requires_select(self):
        """Test non-SELECT is rejected."""
        from app.mcp.sql_builder import validate_raw_sql
        with pytest.raises(ValueError, match="Only SELECT"):
            validate_raw_sql("SHOW TABLES")


class TestSQLBuilder:
    """Tests for SQL builder functions."""

    @pytest.mark.asyncio
    async def test_build_basic_query(self):
        """Test building basic aggregation query."""
        from app.mcp.sql_builder import build_sql_from_structure

        with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
            with patch("app.mcp.sql_builder.get_valid_columns", new_callable=AsyncMock) as mock_c:
                mock_t.return_value = ["products"]
                mock_c.return_value = ["id", "name", "category", "price"]

                sql, params = await build_sql_from_structure({
                    "table": "products",
                    "label_column": "category",
                    "value_column": "price",
                    "aggregation": "SUM",
                    "chart_type": "bar"
                })

                assert "SELECT" in sql
                assert "category AS label" in sql
                assert "SUM(price) AS value" in sql
                assert "GROUP BY category" in sql

    @pytest.mark.asyncio
    async def test_build_query_no_aggregation(self):
        """Test building query without aggregation."""
        from app.mcp.sql_builder import build_sql_from_structure

        with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
            with patch("app.mcp.sql_builder.get_valid_columns", new_callable=AsyncMock) as mock_c:
                mock_t.return_value = ["products"]
                mock_c.return_value = ["name", "price"]

                sql, params = await build_sql_from_structure({
                    "table": "products",
                    "label_column": "name",
                    "value_column": "price",
                    "aggregation": "NONE",
                    "chart_type": "bar"
                })

                assert "GROUP BY" not in sql

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
                        "label_column": "invalid_col",
                        "value_column": "price",
                        "aggregation": "SUM",
                        "chart_type": "bar"
                    })

    @pytest.mark.asyncio
    async def test_build_query_with_filter(self):
        """Test building query with WHERE filter."""
        from app.mcp.sql_builder import build_sql_from_structure

        with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
            with patch("app.mcp.sql_builder.get_valid_columns", new_callable=AsyncMock) as mock_c:
                mock_t.return_value = ["sales"]
                mock_c.return_value = ["id", "product_id", "total_amount", "sale_date"]

                sql, params = await build_sql_from_structure({
                    "table": "sales",
                    "label_column": "product_id",
                    "value_column": "total_amount",
                    "aggregation": "SUM",
                    "filters": [{"column": "sale_date", "operator": ">=", "value": "2024-01-01"}],
                    "chart_type": "bar"
                })

                assert "WHERE" in sql
                assert "filter_0" in params

    @pytest.mark.asyncio
    async def test_build_query_with_order(self):
        """Test building query with ORDER BY."""
        from app.mcp.sql_builder import build_sql_from_structure

        with patch("app.mcp.sql_builder.get_valid_tables", new_callable=AsyncMock) as mock_t:
            with patch("app.mcp.sql_builder.get_valid_columns", new_callable=AsyncMock) as mock_c:
                mock_t.return_value = ["products"]
                mock_c.return_value = ["name", "price"]

                sql, params = await build_sql_from_structure({
                    "table": "products",
                    "label_column": "name",
                    "value_column": "price",
                    "aggregation": "NONE",
                    "order_by": "value_desc",
                    "chart_type": "bar"
                })

                assert "ORDER BY value DESC" in sql


class TestMCPClient:
    """Tests for MCP client."""

    def test_no_api_key_raises_exception(self):
        """Test missing API key raises NOT_CONFIGURED."""
        with patch("app.mcp.clients.gemini.Config") as mock_config:
            mock_config.GEMINI_API_KEY = ""
            mock_config.MCP_SERVER_URL = "http://localhost:3001/sse"

            with pytest.raises(AppException) as exc_info:
                from app.mcp.clients.gemini import GeminiMCPClient
                GeminiMCPClient()

            assert exc_info.value.error_type == ErrorType.NOT_CONFIGURED
