"""
Generic MCP Server with HTTP/SSE transport.
Can be used externally by any MCP client (Claude Desktop, Cursor, etc.)
"""
import json
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, Prompt, PromptMessage, PromptArgument, Resource, GetPromptResult
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("datatovisual")

# SSE transport for HTTP
sse = SseServerTransport("/messages/")


# Resources - data AI can read
RESOURCES = [
    Resource(
        uri="schema://database",
        name="Database Schema",
        description="Database schema from database (always up-to-date)",
        mimeType="text/plain"
    )
]


# Prompts for AI
PROMPTS = [
    Prompt(
        name="data_analyst",
        description="Prompt for analyzing data and writing SQL queries",
        arguments=[
            PromptArgument(
                name="schema",
                description="Database schema information",
                required=True
            ),
            PromptArgument(
                name="question",
                description="User's question about the data",
                required=True
            )
        ]
    )
]


# Single tool for data visualization
TOOLS = [
    Tool(
        name="query",
        description="Execute a SQL query and return data for chart visualization.",
        inputSchema={
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SELECT query with 'label' and 'value' aliases for chart data"
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "pie"],
                    "description": "Chart type: bar (comparisons), line (trends), pie (proportions)"
                }
            },
            "required": ["sql", "chart_type"]
        }
    )
]


@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return RESOURCES


@server.read_resource()
async def read_resource(uri) -> str:
    """Read a resource by URI."""
    uri_str = str(uri)  # Convert AnyUrl to string
    logger.info(f"Reading resource: {uri_str}")
    if uri_str == "schema://database":
        from app.db.database import db

        if not db.pool:
            await db.connect()

        # Get list of tables
        tables_sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """
        tables = await db.execute_query(tables_sql)

        # Build schema string
        schema_parts = ["DATABASE SCHEMA:", ""]

        for table_row in tables:
            table_name = table_row["table_name"]

            # Get columns for this table
            columns_sql = f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position
            """
            columns = await db.execute_query(columns_sql)

            schema_parts.append(f"Table: {table_name}")
            for col in columns:
                nullable = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
                schema_parts.append(f"  - {col['column_name']}: {col['data_type']} ({nullable})")
            schema_parts.append("")

        return "\n".join(schema_parts)

    raise ValueError(f"Unknown resource: {uri_str}")


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List available prompts."""
    return PROMPTS


@server.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    """Get a prompt by name with arguments filled in."""
    if name == "data_analyst":
        schema = arguments.get("schema", "") if arguments else ""
        question = arguments.get("question", "") if arguments else ""

        content = f"""You are a data analyst. Convert the user's question into a SQL query for visualization.

{schema}

RULES:
- Use the query tool to execute SQL and return chart data
- Always use column aliases 'label' and 'value' in your SELECT
  Example: SELECT category AS label, SUM(amount) AS value FROM sales GROUP BY category
- Choose chart_type: "bar" (comparisons), "line" (trends), "pie" (proportions)
- Reject questions unrelated to data analysis

User question: {question}"""

        return GetPromptResult(
            messages=[PromptMessage(role="user", content=TextContent(type="text", text=content))]
        )

    raise ValueError(f"Unknown prompt: {name}")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """AI calls this to discover available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute the query tool."""
    from app.db.database import db

    if not db.pool:
        await db.connect()

    try:
        if name != "query":
            raise ValueError(f"Unknown tool: {name}")

        sql = arguments.get("sql", "")
        chart_type = arguments.get("chart_type", "bar")

        # Validate SQL
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "EXEC"]
        for keyword in dangerous:
            if keyword in sql_upper:
                raise ValueError(f"Dangerous keyword '{keyword}' not allowed")

        # Execute query
        rows = await db.execute_query(sql)

        result = {"chart_type": chart_type, "rows": rows}
        return [TextContent(type="text", text=json.dumps(result))]

    except Exception as e:
        logger.error(f"Tool error: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


# HTTP endpoints for SSE transport
async def handle_sse(request):
    """Handle SSE connection from MCP client."""
    logger.info("New SSE connection")
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options()
        )


async def handle_messages(request):
    """Handle POST messages from MCP client."""
    await sse.handle_post_message(request.scope, request.receive, request._send)


async def health(request):
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "server": "datatovisual-mcp"})


# Starlette app for HTTP server
app = Starlette(
    debug=True,
    routes=[
        Route("/health", health),
        Route("/sse", handle_sse),
        Route("/messages/", handle_messages, methods=["POST"]),
    ]
)


# For running with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
