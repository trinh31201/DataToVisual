"""Base MCP Client with validation and retry logic."""
import json
import logging
from abc import ABC, abstractmethod

from mcp import ClientSession
from mcp.client.sse import sse_client

from app.errors import ErrorType
from app.exceptions import AppException
from app.config import Config

logger = logging.getLogger(__name__)


class BaseMCPClient(ABC):
    """Base MCP client using SSE transport with validation and retry."""

    def __init__(self, server_url: str = None):
        self.server_url = server_url or Config.MCP_SERVER_URL

    def _validate_ai_response(self, function_call: dict, tools: list) -> None:
        """
        Validate AI response has correct structure and valid values.

        Args:
            function_call: AI response with tool name and args
            tools: Available tools from MCP server (dynamic)
        """
        # Check required fields
        if not isinstance(function_call, dict):
            raise AppException(
                ErrorType.INVALID_RESPONSE,
                f"AI response must be dict, got {type(function_call).__name__}"
            )

        if "name" not in function_call:
            raise AppException(
                ErrorType.INVALID_RESPONSE,
                "AI response missing 'name' field"
            )

        if "args" not in function_call:
            raise AppException(
                ErrorType.INVALID_RESPONSE,
                "AI response missing 'args' field"
            )

        # Get valid tool names dynamically from MCP server
        valid_tool_names = {t.name for t in tools}
        tool_name = function_call["name"]

        if tool_name not in valid_tool_names:
            raise AppException(
                ErrorType.INVALID_RESPONSE,
                f"Invalid tool '{tool_name}'. Valid: {valid_tool_names}"
            )

        # Validate args is dict
        if not isinstance(function_call["args"], dict):
            raise AppException(
                ErrorType.INVALID_RESPONSE,
                f"Tool args must be dict, got {type(function_call['args']).__name__}"
            )

        # Get required fields from tool schema dynamically
        tool = next(t for t in tools if t.name == tool_name)
        required_fields = tool.inputSchema.get("required", [])
        args = function_call["args"]

        missing = [f for f in required_fields if f not in args]
        if missing:
            raise AppException(
                ErrorType.INVALID_RESPONSE,
                f"{tool_name} missing required fields: {missing}"
            )

        # Validate enum values from schema
        properties = tool.inputSchema.get("properties", {})
        for field, value in args.items():
            if field in properties:
                enum_values = properties[field].get("enum")
                if enum_values and value not in enum_values:
                    raise AppException(
                        ErrorType.INVALID_RESPONSE,
                        f"Invalid {field}='{value}'. Valid: {enum_values}"
                    )

        logger.info(f"AI response validated: tool={tool_name}")

    async def query(self, question: str) -> dict:
        """
        MCP flow over HTTP/SSE with validation and retry:
        1. Connect to MCP server via SSE
        2. Get tools, schema, prompt
        3. AI decides which tool to use
        4. Validate AI response
        5. Execute tool (retry with advanced_query if simple_query fails)
        """
        async with sse_client(f"{self.server_url}/sse") as (read, write):
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

                # AI decides which tool to use
                try:
                    function_call = await self._call_ai(prompt, tools)
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "quota" in error_str.lower():
                        raise AppException(ErrorType.RATE_LIMIT, "Rate limit exceeded")
                    raise AppException(ErrorType.API_ERROR, error_str)

                # Validate AI response
                self._validate_ai_response(function_call, tools)

                logger.info(f"AI chose: {function_call}")

                # Execute tool with retry logic
                result = await self._execute_with_retry(
                    session, function_call, tools, question
                )

                return result

    async def _execute_with_retry(
        self,
        session: ClientSession,
        function_call: dict,
        tools: list,
        question: str
    ) -> dict:
        """
        Execute tool with retry logic.
        If simple_query fails, retry with advanced_query.
        """
        tool_name = function_call["name"]
        args = function_call["args"]

        try:
            result = await session.call_tool(tool_name, args)
            data = json.loads(result.content[0].text)

            if "error" in data:
                raise AppException(ErrorType.INTERNAL_ERROR, data["error"])

            return data

        except AppException as e:
            # If simple_query failed, try advanced_query as fallback
            if tool_name == "simple_query":
                logger.warning(f"simple_query failed: {e.message}. Trying advanced_query...")

                # Check if advanced_query is available
                advanced_tool = next((t for t in tools if t.name == "advanced_query"), None)
                if not advanced_tool:
                    raise  # No fallback available

                # Ask AI to generate SQL directly
                fallback_prompt = (
                    f"The structured query failed. Generate a raw SQL query instead.\n"
                    f"Question: {question}\n"
                    f"Return a SELECT query with 'label' and 'value' columns."
                )

                try:
                    fallback_call = await self._call_ai(fallback_prompt, [advanced_tool])
                    self._validate_ai_response(fallback_call, [advanced_tool])

                    result = await session.call_tool(
                        fallback_call["name"],
                        fallback_call["args"]
                    )
                    data = json.loads(result.content[0].text)

                    if "error" in data:
                        raise AppException(ErrorType.INTERNAL_ERROR, data["error"])

                    logger.info("Fallback to advanced_query succeeded")
                    return data

                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {fallback_error}")
                    raise e  # Raise original error

            raise

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
