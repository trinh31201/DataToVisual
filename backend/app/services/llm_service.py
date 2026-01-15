"""
Simple LLM service - returns raw SQL query.
No MCP, no function calling. Just prompt → SQL.
"""
import json
import logging
import google.generativeai as genai

from app.config import Config
from app.db.database import SCHEMA_DESCRIPTION
from app.errors import ErrorType
from app.exceptions import AppException

logger = logging.getLogger(__name__)


class LLMService:
    """Simple LLM service that returns raw SQL."""

    def __init__(self):
        if not Config.GEMINI_API_KEY:
            raise AppException(ErrorType.NOT_CONFIGURED, "GEMINI_API_KEY not configured")
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(Config.GEMINI_MODEL)

    def generate_sql(self, question: str) -> dict:
        """
        Send question to LLM, get raw SQL back.

        Returns:
            {"sql": "SELECT ...", "chart_type": "bar"}
        """
        prompt = f"""You are a SQL expert. Generate a SQL query for the user's question.

{SCHEMA_DESCRIPTION}

Rules:
1. Return ONLY valid JSON with "sql" and "chart_type" fields
2. Use "bar" for comparisons, "line" for trends over time, "pie" for distributions
3. Always return columns named "label" and "value" for charting
4. Use standard SQL syntax

User question: {question}

Return JSON:
{{"sql": "SELECT ... AS label, ... AS value FROM ...", "chart_type": "bar|line|pie"}}"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            # Clean markdown code blocks if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            result = json.loads(text)

            if "sql" not in result or "chart_type" not in result:
                raise AppException(ErrorType.INVALID_RESPONSE, "Missing sql or chart_type")

            logger.info(f"Generated SQL: {result['sql']}")
            return result

        except json.JSONDecodeError as e:
            raise AppException(ErrorType.INVALID_RESPONSE, f"Invalid JSON: {e}")
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                raise AppException(ErrorType.RATE_LIMIT, "Rate limit exceeded")
            raise AppException(ErrorType.API_ERROR, error_str)


# Singleton
llm_service = LLMService()
