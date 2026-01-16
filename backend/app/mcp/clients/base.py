"""Base MCP Client - shared logic for all AI providers."""
import json
import logging
import sys
from abc import ABC, abstractmethod

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from app.errors import ErrorType
from app.exceptions import AppException

logger = logging.getLogger(__name__)


class BaseMCPClient(ABC):
    """Base MCP client with shared logic."""

    def __init__(self):
        import os
        # stdio transport - spawn MCP server as subprocess
        # Pass current environment so subprocess can access DATABASE_URL etc.
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.server_stdio"],
            env=dict(os.environ)  # Inherit all environment variables
        )

    async def query(self, question: str) -> dict:
        """
        MCP flow (same for all AI providers):
        1. Connect to MCP server (via stdio subprocess)
        2. Get tools
        3. Get schema
        4. Get prompt
        5. Call AI (different per provider)
        6. Execute tool
        7. Return result
        """
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Get tools from MCP server
                tools_response = await session.list_tools()
                tools = tools_response.tools
                logger.info(f"Discovered {len(tools)} tools")

                # Get schema from MCP resource
                schema_result = await session.read_resource("schema://database")
                schema = schema_result.contents[0].text

                # Get prompt from MCP server
                prompt_result = await session.get_prompt(
                    "data_analyst",
                    {"schema": schema, "question": question}
                )
                prompt = prompt_result.messages[0].content.text

                # Call AI (different per provider)
                try:
                    function_call = await self._call_ai(prompt, tools)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "quota" in error_str.lower():
                        raise AppException(ErrorType.RATE_LIMIT, "Rate limit exceeded")
                    raise AppException(ErrorType.API_ERROR, error_str)

                logger.info(f"AI returned: {function_call}")

                # Execute tool via MCP server
                result = await session.call_tool(
                    function_call["name"],
                    function_call["args"]
                )

                data = json.loads(result.content[0].text)

                if "error" in data:
                    raise AppException(ErrorType.INTERNAL_ERROR, data["error"])

                return data

    @abstractmethod
    async def _call_ai(self, prompt: str, tools: list) -> dict:
        """
        Call AI to get function call. Override this per provider.

        Args:
            prompt: The prompt with schema and question
            tools: List of MCP tools

        Returns:
            dict with "name" and "args"
        """
        pass
