"""Base MCP Client - agentic multi-turn approach."""
import json
import logging
import sys
from abc import ABC, abstractmethod

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from app.errors import ErrorType
from app.exceptions import AppException

logger = logging.getLogger(__name__)

# Meta-tools for AI to interact with MCP server
META_TOOLS = [
    {
        "name": "mcp_list_resources",
        "description": "List all available data resources. Call this first to discover what data is available.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "mcp_read_resource",
        "description": "Read a resource by URI to get its content (e.g., database schema).",
        "parameters": {
            "type": "object",
            "properties": {
                "uri": {"type": "string", "description": "Resource URI (e.g., 'schema://database')"}
            },
            "required": ["uri"]
        }
    },
    {
        "name": "mcp_list_tools",
        "description": "List all available tools for data operations.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "mcp_call_tool",
        "description": "Execute a tool with given arguments. Use this to run queries or get table info.",
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": "Name of the tool to call"},
                "tool_args": {"type": "object", "description": "Arguments for the tool"}
            },
            "required": ["tool_name", "tool_args"]
        }
    }
]

SYSTEM_PROMPT = """You are a data analyst assistant. You have access to tools that let you explore and query a database.

WORKFLOW:
1. First, call mcp_list_resources to discover available resources
2. Call mcp_read_resource to read the database schema
3. Call mcp_list_tools to see what data tools are available
4. Use mcp_call_tool to execute the appropriate tool

RULES:
- Only answer questions about the data in the database
- Reject questions unrelated to data analysis
- For queries, use column aliases 'label' and 'value' for chart data
- Choose chart_type: "bar" (comparisons), "line" (trends), "pie" (proportions)

When you have the final result, respond with the data."""


class BaseMCPClient(ABC):
    """Base MCP client with agentic multi-turn approach."""

    MAX_TURNS = 10  # Prevent infinite loops

    def __init__(self):
        import os
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.server_stdio"],
            env=dict(os.environ)
        )

    async def query(self, question: str) -> dict:
        """
        Agentic MCP flow - AI controls everything:
        1. AI receives question + meta-tools
        2. AI decides what to explore (resources, tools)
        3. AI calls tools, gets results, thinks again
        4. Loop until AI has final answer
        """
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Start conversation with just the question
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ]

                # Multi-turn loop
                for turn in range(self.MAX_TURNS):
                    logger.info(f"Turn {turn + 1}")

                    try:
                        response = await self._call_ai_multi_turn(messages, META_TOOLS)
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "quota" in error_str.lower():
                            raise AppException(ErrorType.RATE_LIMIT, "Rate limit exceeded")
                        raise AppException(ErrorType.API_ERROR, error_str)

                    # Check if AI wants to call a tool
                    if response.get("tool_call"):
                        tool_call = response["tool_call"]
                        logger.info(f"AI calls: {tool_call['name']}")

                        # Execute meta-tool
                        result = await self._execute_meta_tool(
                            session, tool_call["name"], tool_call["args"]
                        )
                        result_str = json.dumps(result)
                        logger.info(f"Tool result: {result_str[:200]}..." if len(result_str) > 200 else f"Tool result: {result_str}")

                        # Add assistant's tool call and result to conversation
                        messages.append({
                            "role": "assistant",
                            "content": f"Called {tool_call['name']}"
                        })
                        messages.append({
                            "role": "user",
                            "content": f"Tool result:\n{json.dumps(result, indent=2)}"
                        })

                    # Check if AI returned final data
                    elif response.get("final_result"):
                        logger.info("AI returned final result")
                        return response["final_result"]

                    # AI responded with text (might be rejection or clarification)
                    elif response.get("text"):
                        text = response["text"]
                        logger.info(f"AI text response: {text}")
                        # Treat as rejection/error
                        raise AppException(ErrorType.INVALID_QUESTION, text)

                # Max turns reached
                raise AppException(
                    ErrorType.INTERNAL_ERROR,
                    "AI could not complete the task within turn limit"
                )

    async def _execute_meta_tool(self, session: ClientSession, name: str, args: dict) -> dict:
        """Execute a meta-tool that interacts with MCP server."""

        if name == "mcp_list_resources":
            resources = await session.list_resources()
            return {
                "resources": [
                    {"uri": str(r.uri), "name": r.name, "description": r.description}
                    for r in resources.resources
                ]
            }

        elif name == "mcp_read_resource":
            uri = args.get("uri", "")
            result = await session.read_resource(uri)
            return {"content": result.contents[0].text}

        elif name == "mcp_list_tools":
            tools = await session.list_tools()
            return {
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.inputSchema
                    }
                    for t in tools.tools
                ]
            }

        elif name == "mcp_call_tool":
            tool_name = args.get("tool_name", "")
            tool_args = args.get("tool_args", {})

            result = await session.call_tool(tool_name, tool_args)
            data = json.loads(result.content[0].text)

            if "error" in data:
                return {"error": data["error"]}

            return data

        else:
            return {"error": f"Unknown meta-tool: {name}"}

    @abstractmethod
    async def _call_ai_multi_turn(self, messages: list, tools: list) -> dict:
        """
        Call AI with conversation history and tools.

        Args:
            messages: Conversation history [{"role": "...", "content": "..."}]
            tools: List of available tools

        Returns:
            dict with one of:
            - {"tool_call": {"name": "...", "args": {...}}}
            - {"final_result": {...}}
            - {"text": "..."}
        """
        pass
