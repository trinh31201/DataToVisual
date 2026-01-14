import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.exceptions import AppException
from app.errors import ErrorType


class TestMCPServer:
    """Tests for MCP server tools."""

    def test_tools_defined(self):
        """Test that MCP tools are properly defined."""
        from app.mcp.server import TOOLS

        assert len(TOOLS) == 2

        tool_names = [t.name for t in TOOLS]
        assert "query_sales" in tool_names
        assert "query_products" in tool_names

        # Check query_sales has required properties
        sales_tool = next(t for t in TOOLS if t.name == "query_sales")
        assert "group_by" in sales_tool.inputSchema["properties"]
        assert "chart_type" in sales_tool.inputSchema["properties"]

        # Check query_products has required properties
        products_tool = next(t for t in TOOLS if t.name == "query_products")
        assert "select" in products_tool.inputSchema["properties"]
        assert "chart_type" in products_tool.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test list_tools returns all tools."""
        from app.mcp.server import list_tools

        tools = await list_tools()
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_query_sales(self):
        """Test query_sales builds correct SQL."""
        from app.mcp.server import query_sales

        mock_db = MagicMock()
        mock_db.execute_query = AsyncMock(return_value=[
            {"label": "Electronics", "value": 50000}
        ])

        result = await query_sales(
            mock_db,
            group_by="category",
            chart_type="bar"
        )

        assert result["chart_type"] == "bar"
        assert "rows" in result
        mock_db.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_sales_with_years(self):
        """Test query_sales with year filter."""
        from app.mcp.server import query_sales

        mock_db = MagicMock()
        mock_db.execute_query = AsyncMock(return_value=[
            {"label": "2022", "value": 100000},
            {"label": "2023", "value": 120000}
        ])

        result = await query_sales(
            mock_db,
            group_by="year",
            chart_type="line",
            years=[2022, 2023]
        )

        assert result["chart_type"] == "line"
        # Verify years filter is in SQL
        call_args = mock_db.execute_query.call_args[0][0]
        assert "2022" in call_args
        assert "2023" in call_args

    @pytest.mark.asyncio
    async def test_query_products_all(self):
        """Test query_products with select=all."""
        from app.mcp.server import query_products

        mock_db = MagicMock()
        mock_db.execute_query = AsyncMock(return_value=[
            {"label": "Product A", "value": 100}
        ])

        result = await query_products(
            mock_db,
            select="all",
            chart_type="bar"
        )

        assert result["chart_type"] == "bar"
        assert "rows" in result

    @pytest.mark.asyncio
    async def test_query_products_top_selling(self):
        """Test query_products with select=top_selling."""
        from app.mcp.server import query_products

        mock_db = MagicMock()
        mock_db.execute_query = AsyncMock(return_value=[
            {"label": "Product A", "value": 10000},
            {"label": "Product B", "value": 8000}
        ])

        result = await query_products(
            mock_db,
            select="top_selling",
            chart_type="bar",
            limit=5
        )

        assert result["chart_type"] == "bar"
        # Verify LIMIT is in SQL
        call_args = mock_db.execute_query.call_args[0][0]
        assert "LIMIT 5" in call_args


class TestMCPClient:
    """Tests for MCP client."""

    def test_no_api_key_gemini(self):
        """Test that client has no AI client when Gemini key not configured."""
        with patch("app.mcp.client.Config") as mock_config:
            mock_config.AI_PROVIDER = "gemini"
            mock_config.GEMINI_API_KEY = ""
            mock_config.ANTHROPIC_API_KEY = ""
            mock_config.OPENAI_API_KEY = ""
            mock_config.DATABASE_URL = "postgresql://test"

            from app.mcp.client import MCPClient
            client = MCPClient()

            assert client.ai_client is None

    def test_no_api_key_claude(self):
        """Test that client has no AI client when Claude key not configured."""
        with patch("app.mcp.client.Config") as mock_config:
            mock_config.AI_PROVIDER = "claude"
            mock_config.GEMINI_API_KEY = ""
            mock_config.ANTHROPIC_API_KEY = ""
            mock_config.OPENAI_API_KEY = ""
            mock_config.DATABASE_URL = "postgresql://test"

            from app.mcp.client import MCPClient
            client = MCPClient()

            assert client.ai_client is None

    def test_no_api_key_openai(self):
        """Test that client has no AI client when OpenAI key not configured."""
        with patch("app.mcp.client.Config") as mock_config:
            mock_config.AI_PROVIDER = "openai"
            mock_config.GEMINI_API_KEY = ""
            mock_config.ANTHROPIC_API_KEY = ""
            mock_config.OPENAI_API_KEY = ""
            mock_config.DATABASE_URL = "postgresql://test"

            from app.mcp.client import MCPClient
            client = MCPClient()

            assert client.ai_client is None

    @pytest.mark.asyncio
    async def test_query_not_configured(self):
        """Test query raises exception when not configured."""
        with patch("app.mcp.client.Config") as mock_config:
            mock_config.AI_PROVIDER = "gemini"
            mock_config.GEMINI_API_KEY = ""
            mock_config.ANTHROPIC_API_KEY = ""
            mock_config.OPENAI_API_KEY = ""
            mock_config.DATABASE_URL = "postgresql://test"

            from app.mcp.client import MCPClient
            client = MCPClient()

            with pytest.raises(AppException) as exc_info:
                await client.query("Show me sales")

            assert exc_info.value.error_type == ErrorType.NOT_CONFIGURED
