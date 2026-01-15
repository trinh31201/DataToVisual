"""
MCP Client - connects to MCP server via HTTP/SSE.
Generic approach where AI writes raw SQL.
Schema is discovered dynamically from MCP server.
"""
import json
import logging

from mcp import ClientSession
from mcp.client.sse import sse_client

from app.config import Config
from app.errors import ErrorType
from app.exceptions import AppException

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP client - connects to MCP server via HTTP."""

    def __init__(self):
        self.provider = Config.AI_PROVIDER
        self.ai_client = None
        self.mcp_server_url = Config.MCP_SERVER_URL
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

    async def query(self, question: str) -> dict:
        """
        Generic MCP flow via HTTP:
        1. Connect to MCP server via SSE
        2. Get tools from server
        3. Read schema from resource (schema://database)
        4. Get prompt from server (data_analyst)
        5. AI writes SQL
        6. Execute via query tool
        7. Return result
        """
        if not self.ai_client:
            raise AppException(
                ErrorType.NOT_CONFIGURED,
                f"{self.provider.upper()} API key not configured"
            )

        # Connect to MCP server via HTTP/SSE
        async with sse_client(self.mcp_server_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_response = await session.list_tools()
                tools = tools_response.tools

                logger.info(f"Discovered {len(tools)} tools from MCP server")

                # Step 1: Discover schema dynamically
                schema = await self._discover_schema(session)
                logger.info(f"Discovered schema: {len(schema)} tables")

                # Step 2: Get function call from AI (AI writes SQL)
                try:
                    function_call = await self._get_function_call(question, tools, schema, session)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "quota" in error_str.lower():
                        raise AppException(ErrorType.RATE_LIMIT, "Rate limit exceeded")
                    raise AppException(ErrorType.API_ERROR, error_str)

                logger.info(f"AI returned: {function_call}")

                # Step 3: Execute tool via MCP server
                result = await session.call_tool(
                    function_call["name"],
                    function_call["args"]
                )

                data = json.loads(result.content[0].text)

                if "error" in data:
                    raise AppException(ErrorType.INTERNAL_ERROR, data["error"])

                return data

    async def _discover_schema(self, session: ClientSession) -> str:
        """Read database schema from MCP resource."""
        # Read schema from database (always up-to-date)
        schema_result = await session.read_resource("schema://database")
        return schema_result.contents[0].text

    async def _get_function_call(
        self, question: str, tools: list, schema: str, session: ClientSession
    ) -> dict:
        """Get function call from AI - AI writes SQL."""
        # Get prompt from MCP server
        prompt_result = await session.get_prompt(
            "data_analyst",
            {"schema": schema, "question": question}
        )
        prompt = prompt_result.messages[0].content.text

        logger.info("Using prompt from MCP server")

        if self.provider == "claude":
            return await self._call_claude(prompt, tools)
        elif self.provider == "openai":
            return await self._call_openai(prompt, tools)
        elif self.provider == "gemini":
            return await self._call_gemini(prompt, tools)

    async def _call_claude(self, prompt: str, tools: list) -> dict:
        """Call Claude with tools from MCP server."""
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
