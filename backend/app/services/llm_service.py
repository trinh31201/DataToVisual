import google.generativeai as genai
from app.config import Config
from app.errors import ErrorType
from app.exceptions import AppException
from app.tools.database_tools import TOOL_DEFINITIONS


class LLMService:
    def __init__(self):
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                Config.GEMINI_MODEL,
                tools=[TOOL_DEFINITIONS]  # Register tools with Gemini
            )
        else:
            self.model = None

    def get_function_call(self, question: str) -> dict:
        """Get function call from Gemini (structured, not raw SQL).

        Returns:
            dict with 'name' and 'args' keys

        Raises:
            AppException: On any error
        """
        if not self.model:
            raise AppException(ErrorType.NOT_CONFIGURED, "Gemini API key not configured")

        prompt = f"""You are a data analyst. Based on the user's question,
call the appropriate function to query the database.

Available data:
- Sales data (can group by category, year, month, product)
- Product data (can get all, by category, or top selling)

User question: {question}

Call the appropriate function with the right parameters."""

        try:
            response = self.model.generate_content(prompt)

            # Check if Gemini returned a function call
            if not response.candidates:
                raise AppException(ErrorType.INVALID_RESPONSE, "No response from LLM")

            candidate = response.candidates[0]

            # Check for function call in the response
            if hasattr(candidate, 'content') and candidate.content.parts:
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        return {
                            "name": fc.name,
                            "args": dict(fc.args)
                        }

            # No function call found - Gemini returned text instead
            raise AppException(
                ErrorType.INVALID_RESPONSE,
                "LLM did not return a function call. Try rephrasing your question."
            )

        except AppException:
            raise
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                raise AppException(ErrorType.RATE_LIMIT, "Rate limit exceeded")
            raise AppException(ErrorType.API_ERROR, error_str)


llm_service = LLMService()
