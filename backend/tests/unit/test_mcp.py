import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.exceptions import AppException
from app.errors import ErrorType


class TestMCPServer:
    """Tests for Generic MCP server tools."""

    def test_tools_defined(self):
        """Test that MCP tools are properly defined."""
        from app.mcp.server import TOOLS

        assert len(TOOLS) == 3

        tool_names = [t.name for t in TOOLS]
        assert "query" in tool_names
        assert "list_tables" in tool_names
        assert "describe_table" in tool_names

        # Check query tool has required properties
        query_tool = next(t for t in TOOLS if t.name == "query")
        assert "sql" in query_tool.inputSchema["properties"]
        assert "chart_type" in query_tool.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test list_tools returns all tools."""
        from app.mcp.server import list_tools

        tools = await list_tools()
        assert len(tools) == 3

    @pytest.mark.asyncio
    async def test_execute_query(self):
        """Test execute_query runs SQL."""
        from app.mcp.server import execute_query

        mock_db = MagicMock()
        mock_db.execute_query = AsyncMock(return_value=[
            {"label": "Electronics", "value": 50000}
        ])

        result = await execute_query(
            mock_db,
            sql="SELECT category AS label, SUM(total_amount) AS value FROM sales GROUP BY category",
            chart_type="bar"
        )

        assert result["chart_type"] == "bar"
        assert "rows" in result
        mock_db.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_select_only(self):
        """Test execute_query only allows SELECT."""
        from app.mcp.server import execute_query

        mock_db = MagicMock()

        with pytest.raises(ValueError) as exc_info:
            await execute_query(
                mock_db,
                sql="DELETE FROM sales",
                chart_type="bar"
            )

        assert "Only SELECT" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_query_blocks_dangerous(self):
        """Test execute_query blocks dangerous keywords."""
        from app.mcp.server import execute_query

        mock_db = MagicMock()

        with pytest.raises(ValueError) as exc_info:
            await execute_query(
                mock_db,
                sql="SELECT * FROM sales; DROP TABLE sales;",
                chart_type="bar"
            )

        assert "DROP" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_tables(self):
        """Test list_tables returns table names."""
        from app.mcp.server import list_tables_impl

        mock_db = MagicMock()
        mock_db.execute_query = AsyncMock(return_value=[
            {"table_name": "products"},
            {"table_name": "sales"}
        ])

        result = await list_tables_impl(mock_db)

        assert "tables" in result
        assert "products" in result["tables"]
        assert "sales" in result["tables"]

    @pytest.mark.asyncio
    async def test_describe_table(self):
        """Test describe_table returns columns."""
        from app.mcp.server import describe_table_impl

        mock_db = MagicMock()
        mock_db.execute_query = AsyncMock(return_value=[
            {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
            {"column_name": "name", "data_type": "varchar", "is_nullable": "NO"}
        ])

        result = await describe_table_impl(mock_db, table_name="products")

        assert result["table"] == "products"
        assert len(result["columns"]) == 2


class TestMCPClient:
    """Tests for MCP client."""

    def test_no_api_key_raises_exception(self):
        """Test that client raises exception when Gemini key not configured."""
        with patch("app.mcp.clients.gemini.Config") as mock_config:
            mock_config.GEMINI_API_KEY = ""
            mock_config.MCP_SERVER_URL = "http://localhost:3001/sse"

            from app.mcp.clients.gemini import GeminiMCPClient

            with pytest.raises(AppException) as exc_info:
                GeminiMCPClient()

            assert exc_info.value.error_type == ErrorType.NOT_CONFIGURED
