import json
import google.generativeai as genai
from app.config import Config
from app.db.database import SCHEMA_DESCRIPTION
from app.errors import ErrorType


class LLMService:
    def __init__(self):
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(Config.GEMINI_MODEL)
        else:
            self.model = None

    def generate_sql(self, question: str) -> dict:
        if not self.model:
            return {
                "success": False,
                "error": "Gemini API key not configured",
                "error_type": ErrorType.NOT_CONFIGURED
            }

        prompt = f"""You are a SQL expert. Given a natural language question, generate a PostgreSQL query.

{SCHEMA_DESCRIPTION}

RULES:
1. Only generate SELECT queries (no INSERT, UPDATE, DELETE, DROP)
2. Use proper PostgreSQL syntax
3. Return results that can be visualized in a chart
4. Choose appropriate chart type based on the question:
   - Time trends/changes over time → "line"
   - Comparisons between categories → "bar"
   - Proportions/percentages → "pie"
5. Order results logically (by date for trends, by value for rankings)

Respond ONLY with valid JSON in this exact format:
{{"sql": "SELECT ...", "chart_type": "line|bar|pie"}}

Question: {question}

JSON Response:"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            # Clean up response if wrapped in markdown
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            result = json.loads(text)

            if "sql" not in result or "chart_type" not in result:
                return {
                    "success": False,
                    "error": "Invalid LLM response format",
                    "error_type": ErrorType.INVALID_RESPONSE
                }

            # Basic SQL safety check
            sql_upper = result["sql"].upper()
            if any(keyword in sql_upper for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER"]):
                return {
                    "success": False,
                    "error": "Only SELECT queries allowed",
                    "error_type": ErrorType.DANGEROUS_SQL
                }

            return {
                "success": True,
                "sql": result["sql"],
                "chart_type": result["chart_type"]
            }

        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Failed to parse LLM response",
                "error_type": ErrorType.INVALID_RESPONSE
            }
        except Exception as e:
            error_str = str(e)
            # Detect rate limit errors
            if "429" in error_str or "quota" in error_str.lower():
                return {
                    "success": False,
                    "error": "Rate limit exceeded",
                    "error_type": ErrorType.RATE_LIMIT
                }
            return {
                "success": False,
                "error": error_str,
                "error_type": ErrorType.API_ERROR
            }


llm_service = LLMService()
