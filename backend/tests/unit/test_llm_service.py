import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_service import LLMService
from app.exceptions import AppException
from app.errors import ErrorType


class TestLLMService:
    """Tests for LLM service with function calling."""

    def test_no_api_key(self):
        """Test that service raises exception when no API key is configured."""
        with patch("app.services.llm_service.Config") as mock_config:
            mock_config.GEMINI_API_KEY = None
            service = LLMService()

            with pytest.raises(AppException) as exc_info:
                service.get_function_call("Show me sales")

            assert exc_info.value.error_type == ErrorType.NOT_CONFIGURED
            assert "not configured" in exc_info.value.message

    def test_get_function_call_success(self):
        """Test successful function call extraction."""
        # Mock a function call response
        mock_fc = MagicMock()
        mock_fc.name = "query_sales"
        mock_fc.args = {"group_by": "category", "chart_type": "bar"}

        mock_part = MagicMock()
        mock_part.function_call = mock_fc

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()
            result = service.get_function_call("Show sales by category")

            assert result["name"] == "query_sales"
            assert result["args"]["group_by"] == "category"
            assert result["args"]["chart_type"] == "bar"

    def test_no_function_call_in_response(self):
        """Test handling when LLM returns text instead of function call."""
        mock_part = MagicMock()
        mock_part.function_call = None
        del mock_part.function_call  # Simulate no function_call attribute

        mock_content = MagicMock()
        mock_content.parts = [mock_part]

        mock_candidate = MagicMock()
        mock_candidate.content = mock_content

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()

            with pytest.raises(AppException) as exc_info:
                service.get_function_call("What's the weather?")

            assert exc_info.value.error_type == ErrorType.INVALID_RESPONSE

    def test_no_candidates(self):
        """Test handling when LLM returns no candidates."""
        mock_response = MagicMock()
        mock_response.candidates = []

        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()

            with pytest.raises(AppException) as exc_info:
                service.get_function_call("Show data")

            assert exc_info.value.error_type == ErrorType.INVALID_RESPONSE

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

            with pytest.raises(AppException) as exc_info:
                service.get_function_call("Show data")

            assert exc_info.value.error_type == ErrorType.API_ERROR
            assert "API Error" in exc_info.value.message

    def test_rate_limit_exception(self):
        """Test handling of rate limit errors."""
        with patch("app.services.llm_service.Config") as mock_config, \
             patch("app.services.llm_service.genai") as mock_genai:
            mock_config.GEMINI_API_KEY = "test-key"
            mock_config.GEMINI_MODEL = "gemini-2.5-flash"

            mock_model = MagicMock()
            mock_model.generate_content.side_effect = Exception("429 quota exceeded")
            mock_genai.GenerativeModel.return_value = mock_model

            service = LLMService()

            with pytest.raises(AppException) as exc_info:
                service.get_function_call("Show data")

            assert exc_info.value.error_type == ErrorType.RATE_LIMIT
