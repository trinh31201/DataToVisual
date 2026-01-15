import pytest
from unittest.mock import patch, MagicMock
from app.exceptions import AppException
from app.errors import ErrorType


class TestLLMService:
    """Tests for LLM service - raw SQL generation."""

    def test_no_api_key(self):
        """Test that service raises exception when API key not configured."""
        with patch("app.services.llm_service.Config") as mock_config:
            mock_config.GEMINI_API_KEY = ""

            with pytest.raises(AppException) as exc_info:
                from app.services.llm_service import LLMService
                LLMService()

            assert exc_info.value.error_type == ErrorType.NOT_CONFIGURED

    def test_generate_sql_success(self):
        """Test successful SQL generation."""
        with patch("app.services.llm_service.Config") as mock_config:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.0-flash"

            with patch("app.services.llm_service.genai") as mock_genai:
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.text = '{"sql": "SELECT * FROM products", "chart_type": "bar"}'
                mock_model.generate_content.return_value = mock_response
                mock_genai.GenerativeModel.return_value = mock_model

                from app.services.llm_service import LLMService
                service = LLMService()
                result = service.generate_sql("Show all products")

                assert result["sql"] == "SELECT * FROM products"
                assert result["chart_type"] == "bar"

    def test_generate_sql_with_markdown(self):
        """Test SQL generation when response has markdown code blocks."""
        with patch("app.services.llm_service.Config") as mock_config:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.0-flash"

            with patch("app.services.llm_service.genai") as mock_genai:
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.text = '```json\n{"sql": "SELECT * FROM products", "chart_type": "bar"}\n```'
                mock_model.generate_content.return_value = mock_response
                mock_genai.GenerativeModel.return_value = mock_model

                from app.services.llm_service import LLMService
                service = LLMService()
                result = service.generate_sql("Show all products")

                assert result["sql"] == "SELECT * FROM products"
                assert result["chart_type"] == "bar"

    def test_generate_sql_invalid_json(self):
        """Test SQL generation with invalid JSON response."""
        with patch("app.services.llm_service.Config") as mock_config:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.0-flash"

            with patch("app.services.llm_service.genai") as mock_genai:
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.text = "not valid json"
                mock_model.generate_content.return_value = mock_response
                mock_genai.GenerativeModel.return_value = mock_model

                from app.services.llm_service import LLMService
                service = LLMService()

                with pytest.raises(AppException) as exc_info:
                    service.generate_sql("Show all products")

                assert exc_info.value.error_type == ErrorType.INVALID_RESPONSE
