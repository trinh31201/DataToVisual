import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_service import LLMService


class TestLLMService:
    """Tests for LLM service."""

    def test_no_api_key(self):
        """Test that service returns error when no API key is configured."""
        with patch("app.services.llm_service.Config") as mock_config:
            mock_config.GEMINI_API_KEY = None
            service = LLMService()
            result = service.generate_sql("Show me sales")
            assert result["success"] is False
            assert "not configured" in result["error"]

    def test_generate_sql_success(self):
        """Test successful SQL generation."""
        mock_response = MagicMock()
        mock_response.text = '{"sql": "SELECT * FROM products", "chart_type": "bar"}'

        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()
            result = service.generate_sql("List all products")

            assert result["success"] is True
            assert result["sql"] == "SELECT * FROM products"
            assert result["chart_type"] == "bar"

    def test_generate_sql_with_markdown_wrapper(self):
        """Test that markdown code blocks are properly stripped."""
        mock_response = MagicMock()
        mock_response.text = '```json\n{"sql": "SELECT * FROM sales", "chart_type": "line"}\n```'

        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()
            result = service.generate_sql("Show sales trend")

            assert result["success"] is True
            assert result["sql"] == "SELECT * FROM sales"

    def test_rejects_insert_query(self):
        """Test that INSERT queries are rejected."""
        mock_response = MagicMock()
        mock_response.text = '{"sql": "INSERT INTO products VALUES (1, \'test\')", "chart_type": "bar"}'

        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()
            result = service.generate_sql("Add a product")

            assert result["success"] is False
            assert "SELECT" in result["error"]

    def test_rejects_delete_query(self):
        """Test that DELETE queries are rejected."""
        mock_response = MagicMock()
        mock_response.text = '{"sql": "DELETE FROM products WHERE id = 1", "chart_type": "bar"}'

        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()
            result = service.generate_sql("Remove product")

            assert result["success"] is False
            assert "SELECT" in result["error"]

    def test_rejects_drop_query(self):
        """Test that DROP queries are rejected."""
        mock_response = MagicMock()
        mock_response.text = '{"sql": "DROP TABLE products", "chart_type": "bar"}'

        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()
            result = service.generate_sql("Drop products table")

            assert result["success"] is False
            assert "SELECT" in result["error"]

    def test_invalid_json_response(self):
        """Test handling of invalid JSON from LLM."""
        mock_response = MagicMock()
        mock_response.text = "This is not valid JSON"

        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()
            result = service.generate_sql("Show data")

            assert result["success"] is False
            assert "parse" in result["error"].lower()

    def test_missing_sql_field(self):
        """Test handling of response missing sql field."""
        mock_response = MagicMock()
        mock_response.text = '{"chart_type": "bar"}'

        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()
            result = service.generate_sql("Show data")

            assert result["success"] is False
            assert "Invalid" in result["error"]

    def test_api_exception(self):
        """Test handling of API exceptions."""
        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.side_effect = Exception("API Error")
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()
            result = service.generate_sql("Show data")

            assert result["success"] is False
            assert "API Error" in result["error"]
