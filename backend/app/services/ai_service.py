"""
AI Service - works with any AI provider using MCP tool format.
Supports: Claude, Gemini, OpenAI
"""
import json
from app.config import Config
from app.errors import ErrorType
from app.exceptions import AppException
from app.mcp.server import TOOLS


class AIService:
    """AI-agnostic service using MCP tool definitions."""

    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize the AI client based on provider."""
        if self.provider == "claude":
            if not Config.ANTHROPIC_API_KEY:
                return
            from anthropic import Anthropic
            self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)

        elif self.provider == "openai":
            if not Config.OPENAI_API_KEY:
                return
            from openai import OpenAI
            self.client = OpenAI(api_key=Config.OPENAI_API_KEY)

        elif self.provider == "gemini":
            if not Config.GEMINI_API_KEY:
                return
            import google.generativeai as genai
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.client = genai.GenerativeModel(Config.GEMINI_MODEL)

    def _get_prompt(self, question: str) -> str:
        """Generate the prompt for the AI."""
        return f"""You are a data analyst. Based on the user's question,
call the appropriate function to query the database.

Available data:
- Sales data (can group by category, year, month, product)
- Product data (can get all, by category, or top selling)

User question: {question}

Call the appropriate function with the right parameters."""

    def get_function_call(self, question: str) -> dict:
        """Get function call from any AI provider.

        Returns:
            dict with 'name' and 'args' keys

        Raises:
            AppException: On any error
        """
        if not self.client:
            raise AppException(
                ErrorType.NOT_CONFIGURED,
                f"{self.provider.upper()} API key not configured"
            )

        prompt = self._get_prompt(question)

        try:
            if self.provider == "claude":
                return self._call_claude(prompt)
            elif self.provider == "openai":
                return self._call_openai(prompt)
            elif self.provider == "gemini":
                return self._call_gemini(prompt)
        except AppException:
            raise
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                raise AppException(ErrorType.RATE_LIMIT, "Rate limit exceeded")
            raise AppException(ErrorType.API_ERROR, error_str)

    def _call_claude(self, prompt: str) -> dict:
        """Call Claude with MCP tools."""
        # Convert to Claude format
        claude_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"]
            }
            for t in TOOLS
        ]

        response = self.client.messages.create(
            model=Config.CLAUDE_MODEL,
            max_tokens=1024,
            tools=claude_tools,
            messages=[{"role": "user", "content": prompt}]
        )

        for block in response.content:
            if block.type == "tool_use":
                return {"name": block.name, "args": block.input}

        raise AppException(
            ErrorType.INVALID_RESPONSE,
            "Claude did not return a function call. Try rephrasing your question."
        )

    def _call_openai(self, prompt: str) -> dict:
        """Call OpenAI with MCP tools."""
        # Convert to OpenAI format
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"]
                }
            }
            for t in TOOLS
        ]

        response = self.client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            tools=openai_tools
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            return {
                "name": tool_call.function.name,
                "args": json.loads(tool_call.function.arguments)
            }

        raise AppException(
            ErrorType.INVALID_RESPONSE,
            "OpenAI did not return a function call. Try rephrasing your question."
        )

    def _call_gemini(self, prompt: str) -> dict:
        """Call Gemini with MCP tools."""
        import google.generativeai as genai

        # Convert MCP tools to Gemini format
        gemini_tools = []
        for t in TOOLS:
            properties = {}
            for prop_name, prop_def in t["input_schema"]["properties"].items():
                prop_schema = {"type": genai.protos.Type.STRING}

                if prop_def.get("type") == "integer":
                    prop_schema = {"type": genai.protos.Type.INTEGER}
                elif prop_def.get("type") == "array":
                    prop_schema = {
                        "type": genai.protos.Type.ARRAY,
                        "items": genai.protos.Schema(type=genai.protos.Type.INTEGER)
                    }

                if "enum" in prop_def:
                    prop_schema["enum"] = prop_def["enum"]
                if "description" in prop_def:
                    prop_schema["description"] = prop_def["description"]

                properties[prop_name] = genai.protos.Schema(**prop_schema)

            func_decl = genai.protos.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties=properties,
                    required=t["input_schema"].get("required", [])
                )
            )
            gemini_tools.append(func_decl)

        # Create model with tools
        model = genai.GenerativeModel(
            Config.GEMINI_MODEL,
            tools=[genai.protos.Tool(function_declarations=gemini_tools)]
        )

        response = model.generate_content(prompt)

        if not response.candidates:
            raise AppException(ErrorType.INVALID_RESPONSE, "No response from Gemini")

        candidate = response.candidates[0]
        if hasattr(candidate, 'content') and candidate.content.parts:
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    return {"name": fc.name, "args": dict(fc.args)}

        raise AppException(
            ErrorType.INVALID_RESPONSE,
            "Gemini did not return a function call. Try rephrasing your question."
        )


ai_service = AIService()
