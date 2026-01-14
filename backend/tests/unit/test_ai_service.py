import pytest
from unittest.mock import patch, MagicMock
from app.exceptions import AppException
from app.errors import ErrorType


class TestAIService:
    """Tests for AI service with MCP tools."""

    def test_no_api_key_gemini(self):
        """Test that service raises exception when no Gemini API key is configured."""
        with patch("app.services.ai_service.Config") as mock_config:
            mock_config.AI_PROVIDER = "gemini"
            mock_config.GEMINI_API_KEY = ""
            mock_config.ANTHROPIC_API_KEY = ""
            mock_config.OPENAI_API_KEY = ""

            # Import after patching
            from app.services.ai_service import AIService
            service = AIService()

            with pytest.raises(AppException) as exc_info:
                service.get_function_call("Show me sales")

            assert exc_info.value.error_type == ErrorType.NOT_CONFIGURED

    def test_no_api_key_claude(self):
        """Test that service raises exception when no Claude API key is configured."""
        with patch("app.services.ai_service.Config") as mock_config:
            mock_config.AI_PROVIDER = "claude"
            mock_config.GEMINI_API_KEY = ""
            mock_config.ANTHROPIC_API_KEY = ""
            mock_config.OPENAI_API_KEY = ""

            from app.services.ai_service import AIService
            service = AIService()

            with pytest.raises(AppException) as exc_info:
                service.get_function_call("Show me sales")

            assert exc_info.value.error_type == ErrorType.NOT_CONFIGURED

    def test_no_api_key_openai(self):
        """Test that service raises exception when no OpenAI API key is configured."""
        with patch("app.services.ai_service.Config") as mock_config:
            mock_config.AI_PROVIDER = "openai"
            mock_config.GEMINI_API_KEY = ""
            mock_config.ANTHROPIC_API_KEY = ""
            mock_config.OPENAI_API_KEY = ""

            from app.services.ai_service import AIService
            service = AIService()

            with pytest.raises(AppException) as exc_info:
                service.get_function_call("Show me sales")

            assert exc_info.value.error_type == ErrorType.NOT_CONFIGURED

    def test_tools_defined(self):
        """Test that MCP tools are properly defined."""
        from app.mcp.server import TOOLS

        assert len(TOOLS) == 2

        tool_names = [t["name"] for t in TOOLS]
        assert "query_sales" in tool_names
        assert "query_products" in tool_names

        # Check query_sales has required properties
        sales_tool = next(t for t in TOOLS if t["name"] == "query_sales")
        assert "group_by" in sales_tool["input_schema"]["properties"]
        assert "chart_type" in sales_tool["input_schema"]["properties"]

        # Check query_products has required properties
        products_tool = next(t for t in TOOLS if t["name"] == "query_products")
        assert "select" in products_tool["input_schema"]["properties"]
        assert "chart_type" in products_tool["input_schema"]["properties"]

    def test_execute_tool_query_sales(self):
        """Test execute_tool routes to query_sales correctly."""
        from app.mcp.server import execute_tool
        import asyncio

        with patch("app.mcp.server.db") as mock_db:
            mock_db.execute_query = MagicMock(return_value=[
                {"label": "Electronics", "value": 50000}
            ])
            # Make it work with async
            async def mock_execute(sql):
                return [{"label": "Electronics", "value": 50000}]
            mock_db.execute_query = mock_execute

            result = asyncio.get_event_loop().run_until_complete(
                execute_tool("query_sales", {
                    "group_by": "category",
                    "chart_type": "bar"
                })
            )

            assert result["chart_type"] == "bar"
            assert "rows" in result

    def test_execute_tool_query_products(self):
        """Test execute_tool routes to query_products correctly."""
        from app.mcp.server import execute_tool
        import asyncio

        with patch("app.mcp.server.db") as mock_db:
            async def mock_execute(sql):
                return [{"label": "Product A", "value": 100}]
            mock_db.execute_query = mock_execute

            result = asyncio.get_event_loop().run_until_complete(
                execute_tool("query_products", {
                    "select": "all",
                    "chart_type": "bar"
                })
            )

            assert result["chart_type"] == "bar"
            assert "rows" in result

    def test_execute_tool_unknown(self):
        """Test execute_tool raises error for unknown tool."""
        from app.mcp.server import execute_tool
        import asyncio

        with pytest.raises(ValueError) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                execute_tool("unknown_tool", {})
            )

        assert "Unknown tool" in str(exc_info.value)
