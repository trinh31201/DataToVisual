"""Gemini MCP Client - agentic multi-turn approach."""
import json
import google.generativeai as genai

from app.config import Config
from app.errors import ErrorType
from app.exceptions import AppException
from app.mcp.clients.base import BaseMCPClient


class GeminiMCPClient(BaseMCPClient):
    """MCP client using Gemini for AI with multi-turn support."""

    def __init__(self):
        super().__init__()
        if not Config.GEMINI_API_KEY:
            raise AppException(ErrorType.NOT_CONFIGURED, "GEMINI_API_KEY not configured")
        genai.configure(api_key=Config.GEMINI_API_KEY)

    async def _call_ai_multi_turn(self, messages: list, tools: list) -> dict:
        """
        Call Gemini with conversation history and tools.

        Returns:
            - {"tool_call": {"name": "...", "args": {...}}} if AI wants to call a tool
            - {"final_result": {...}} if AI returns data result
            - {"text": "..."} if AI responds with text
        """
        # Convert meta-tools to Gemini format
        gemini_tools = self._build_meta_tools(tools)

        model = genai.GenerativeModel(
            Config.GEMINI_MODEL,
            tools=[genai.protos.Tool(function_declarations=gemini_tools)],
            system_instruction=messages[0]["content"] if messages[0]["role"] == "system" else None
        )

        # Convert messages to Gemini format
        gemini_messages = self._convert_messages(messages)

        # Start chat and send messages
        chat = model.start_chat(history=gemini_messages[:-1] if len(gemini_messages) > 1 else [])
        response = chat.send_message(gemini_messages[-1]["parts"] if gemini_messages else "")

        if not response.candidates:
            raise AppException(ErrorType.INVALID_RESPONSE, "No response from Gemini")

        candidate = response.candidates[0]

        if hasattr(candidate, 'content') and candidate.content.parts:
            for part in candidate.content.parts:
                # Check for function call
                if hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    return {
                        "tool_call": {
                            "name": fc.name,
                            "args": dict(fc.args)
                        }
                    }

                # Check for text response
                if hasattr(part, 'text') and part.text:
                    text = part.text.strip()

                    # Strip markdown code blocks if present
                    json_text = text
                    if text.startswith("```"):
                        lines = text.split("\n")
                        # Remove first line (```json) and last line (```)
                        json_lines = [l for l in lines[1:] if not l.startswith("```")]
                        json_text = "\n".join(json_lines).strip()

                    # Try to parse as JSON (final result)
                    try:
                        data = json.loads(json_text)
                        # Check if it looks like a data result
                        if isinstance(data, dict) and any(
                            k in data for k in ["chart_type", "rows", "tables", "columns", "table"]
                        ):
                            return {"final_result": data}
                    except json.JSONDecodeError:
                        pass

                    # Return as text response
                    return {"text": text}

        raise AppException(
            ErrorType.INVALID_RESPONSE,
            "Gemini returned empty response"
        )

    def _convert_messages(self, messages: list) -> list:
        """Convert messages to Gemini chat format."""
        gemini_messages = []

        for msg in messages:
            if msg["role"] == "system":
                continue  # System prompt is handled separately

            role = "user" if msg["role"] == "user" else "model"
            gemini_messages.append({
                "role": role,
                "parts": [msg["content"]]
            })

        return gemini_messages

    def _build_meta_tools(self, tools: list) -> list:
        """Convert meta-tools (dict format) to Gemini format."""
        gemini_tools = []

        for t in tools:
            properties = {}
            params = t.get("parameters", {})

            for prop_name, prop_def in params.get("properties", {}).items():
                prop_schema = {"type": genai.protos.Type.STRING}

                if prop_def.get("type") == "integer":
                    prop_schema = {"type": genai.protos.Type.INTEGER}
                elif prop_def.get("type") == "object":
                    prop_schema = {"type": genai.protos.Type.OBJECT}
                elif prop_def.get("type") == "array":
                    prop_schema = {
                        "type": genai.protos.Type.ARRAY,
                        "items": genai.protos.Schema(type=genai.protos.Type.STRING)
                    }

                if "description" in prop_def:
                    prop_schema["description"] = prop_def["description"]

                properties[prop_name] = genai.protos.Schema(**prop_schema)

            func_decl = genai.protos.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties=properties,
                    required=params.get("required", [])
                )
            )
            gemini_tools.append(func_decl)

        return gemini_tools
