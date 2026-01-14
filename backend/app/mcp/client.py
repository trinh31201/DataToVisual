"""
MCP Client - connects to MCP server and AI providers.
Tools are discovered automatically from MCP server.
"""
import json
import logging
import sys
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import Config
from app.errors import ErrorType
from app.exceptions import AppException

logger = logging.getLogger(__name__)


class MCPClient:
    """Full MCP client - discovers tools from MCP server."""

    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self.ai_client = None
        self._init_ai_client()

    def _init_ai_client(self):
        """Initialize the AI client based on provider."""
        if self.provider == "claude":
            if not Config.ANTHROPIC_API_KEY:
                return
            from anthropic import Anthropic
            self.ai_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)

        elif self.provider == "openai":
            if not Config.OPENAI_API_KEY:
                return
            from openai import OpenAI
            self.ai_client = OpenAI(api_key=Config.OPENAI_API_KEY)

        elif self.provider == "gemini":
            if not Config.GEMINI_API_KEY:
                return
            import google.generativeai as genai
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.ai_client = genai

    def _get_mcp_server_params(self) -> StdioServerParameters:
        """Get parameters to start MCP server subprocess."""
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.server"],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            env={
                **os.environ,
                "DATABASE_URL": Config.DATABASE_URL
            }
        )

    async def query(self, question: str) -> dict:
        """
        Full MCP flow:
        1. Connect to MCP server
        2. Get tools via list_tools() (auto-discovery!)
        3. Send to AI with tools
        4. Execute tool via call_tool()
        5. Return result
        """
        if not self.ai_client:
            raise AppException(
                ErrorType.NOT_CONFIGURED,
                f"{self.provider.upper()} API key not configured"
            )

        server_params = self._get_mcp_server_params()

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize connection
                await session.initialize()

                # 1. Get tools from MCP server (auto-discovery!)
                tools_response = await session.list_tools()
                tools = tools_response.tools

                logger.info(f"Discovered {len(tools)} tools from MCP server")

                # 2. Get function call from AI
                try:
                    function_call = await self._get_function_call(question, tools)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "quota" in error_str.lower():
                        raise AppException(ErrorType.RATE_LIMIT, "Rate limit exceeded")
                    raise AppException(ErrorType.API_ERROR, error_str)

                logger.info(f"AI returned function call: {function_call}")

                # 3. Execute tool via MCP server
                result = await session.call_tool(
                    function_call["name"],
                    function_call["args"]
                )

                # Parse result
                data = json.loads(result.content[0].text)

                if "error" in data:
                    raise AppException(ErrorType.INTERNAL_ERROR, data["error"])

                return data

    async def _get_function_call(self, question: str, tools: list) -> dict:
        """Get function call from AI provider with MCP tools."""
        prompt = f"""You are a data analyst. Based on the user's question,
call the appropriate function to query the database.

Available data:
- Sales data (can group by category, year, month, product)
- Product data (can get all, by category, or top selling)

User question: {question}

Call the appropriate function with the right parameters."""

        if self.provider == "claude":
            return await self._call_claude(prompt, tools)
        elif self.provider == "openai":
            return await self._call_openai(prompt, tools)
        elif self.provider == "gemini":
            return await self._call_gemini(prompt, tools)

    async def _call_claude(self, prompt: str, tools: list) -> dict:
        """Call Claude with tools from MCP server."""
        # Convert MCP tools to Claude format
        claude_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema
            }
            for t in tools
        ]

        response = self.ai_client.messages.create(
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
            "Claude did not return a function call."
        )

    async def _call_openai(self, prompt: str, tools: list) -> dict:
        """Call OpenAI with tools from MCP server."""
        # Convert MCP tools to OpenAI format
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.inputSchema
                }
            }
            for t in tools
        ]

        response = self.ai_client.chat.completions.create(
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
            "OpenAI did not return a function call."
        )

    async def _call_gemini(self, prompt: str, tools: list) -> dict:
        """Call Gemini with tools from MCP server."""
        genai = self.ai_client

        # Convert MCP tools to Gemini format
        gemini_tools = []
        for t in tools:
            properties = {}
            for prop_name, prop_def in t.inputSchema["properties"].items():
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
            "Gemini did not return a function call."
        )


# Singleton instance
mcp_client = MCPClient()
