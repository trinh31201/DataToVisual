"""Gemini MCP Client - AI decides which tool to use."""
import google.generativeai as genai

from app.config import Config
from app.errors import ErrorType
from app.exceptions import AppException
from app.mcp.clients.base import BaseMCPClient


class GeminiMCPClient(BaseMCPClient):
    """MCP client using Gemini for AI."""

    def __init__(self):
        super().__init__()
        if not Config.GEMINI_API_KEY:
            raise AppException(ErrorType.NOT_CONFIGURED, "GEMINI_API_KEY not configured")
        genai.configure(api_key=Config.GEMINI_API_KEY)

    async def _call_ai(self, prompt: str, tools: list) -> dict:
        """AI decides which tool to use based on prompt and available tools."""
        # Convert MCP tools to Gemini format
        gemini_tools = self._build_tools(tools)

        model = genai.GenerativeModel(
            Config.GEMINI_MODEL,
            tools=[genai.protos.Tool(function_declarations=gemini_tools)]
        )

        response = model.generate_content(prompt)

        if not response.candidates:
            raise AppException(ErrorType.INVALID_RESPONSE, "No response from Gemini")

        # Extract function call (AI's tool choice)
        candidate = response.candidates[0]
        if hasattr(candidate, 'content') and candidate.content.parts:
            text_response = None
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    return {"name": fc.name, "args": dict(fc.args)}
                if hasattr(part, 'text') and part.text:
                    text_response = part.text

            # AI responded with text instead of tool call (rejection)
            if text_response:
                raise AppException(ErrorType.INVALID_QUESTION, text_response)

        raise AppException(
            ErrorType.INVALID_RESPONSE,
            "Gemini did not return a function call."
        )

    def _build_tools(self, tools: list) -> list:
        """Convert MCP tools to Gemini format."""
        gemini_tools = []
        for t in tools:
            properties = {}
            for prop_name, prop_def in t.inputSchema.get("properties", {}).items():
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
                name=t.name,
                description=t.description,
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties=properties,
                    required=t.inputSchema.get("required", [])
                )
            )
            gemini_tools.append(func_decl)

        return gemini_tools
