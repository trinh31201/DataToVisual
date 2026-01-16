"""Base MCP Client."""
import json
import logging
from abc import ABC, abstractmethod

from mcp import ClientSession
from mcp.client.sse import sse_client

from app.errors import ErrorType
from app.exceptions import AppException

logger = logging.getLogger(__name__)


class BaseMCPClient(ABC):
    """Base MCP client using SSE transport."""

    def __init__(self, server_url: str = "http://localhost:3001"):
        self.server_url = server_url

    async def query(self, question: str) -> dict:
        """
        MCP flow over HTTP/SSE:
        1. Client connects to MCP server via SSE
        2. Client gets tools, schema, prompt
        3. AI decides which tool to use
        4. Client executes tool
        """
        async with sse_client(f"{self.server_url}/sse") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Client gets tools from MCP server
                tools_response = await session.list_tools()
                tools = tools_response.tools
                logger.info(f"Discovered {len(tools)} tools")

                # Client gets schema from MCP resource
                schema_result = await session.read_resource("schema://database")
                schema = schema_result.contents[0].text

                # Client gets prompt from MCP server
                prompt_result = await session.get_prompt(
                    "data_analyst",
                    {"schema": schema, "question": question}
                )
                prompt = prompt_result.messages[0].content.text

                # AI decides which tool to use
                try:
                    function_call = await self._call_ai(prompt, tools)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "quota" in error_str.lower():
                        raise AppException(ErrorType.RATE_LIMIT, "Rate limit exceeded")
                    raise AppException(ErrorType.API_ERROR, error_str)

                logger.info(f"AI chose: {function_call}")

                # Client executes tool via MCP server
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
        AI decides which tool to use.

        Args:
            prompt: The prompt with schema and question
            tools: List of MCP tools

        Returns:
            dict with "name" and "args" for the chosen tool
        """
        pass
