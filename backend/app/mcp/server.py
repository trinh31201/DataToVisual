"""
Generic MCP Server with HTTP/SSE transport.
Can be used externally by any MCP client (Claude Desktop, Cursor, etc.)
"""
import json
import sys
import os
import logging
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, Prompt, PromptMessage, PromptArgument, Resource, GetPromptResult
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

from .sql_builder import (
    build_sql_from_structure,
    validate_raw_sql,
    get_valid_tables,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("datatovisual")

# SSE transport for HTTP
sse = SseServerTransport("/messages/")

# Query timeout
QUERY_TIMEOUT = 30  # seconds


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


# Two tools: simple (structured) and advanced (raw SQL)
TOOLS = [
    Tool(
        name="simple_query",
        description="Simple query for single-table aggregations. Use this for most queries.",
        inputSchema={
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table to query (e.g., 'sales', 'products')"
                },
                "label_column": {
                    "type": "string",
                    "description": "Column for chart labels/X-axis (e.g., 'category', 'sale_date')"
                },
                "value_column": {
                    "type": "string",
                    "description": "Column for chart values/Y-axis (e.g., 'total_amount', 'quantity')"
                },
                "aggregation": {
                    "type": "string",
                    "enum": ["SUM", "COUNT", "AVG", "MAX", "MIN", "NONE"],
                    "description": "Aggregation function. Use NONE for non-aggregated data."
                },
                "filters": {
                    "type": "array",
                    "description": "Optional WHERE conditions",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {"type": "string"},
                            "operator": {"type": "string", "enum": ["=", ">", "<", ">=", "<=", "LIKE", "IN"]},
                            "value": {"type": "string"}
                        },
                        "required": ["column", "operator", "value"]
                    }
                },
                "order_by": {
                    "type": "string",
                    "enum": ["label_asc", "label_desc", "value_asc", "value_desc"],
                    "description": "Sort order"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return"
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "pie"],
                    "description": "Chart type: bar (comparisons), line (trends), pie (proportions)"
                }
            },
            "required": ["table", "label_column", "value_column", "aggregation", "chart_type"]
        }
    ),
    Tool(
        name="advanced_query",
        description="Advanced query for JOINs, subqueries, or complex logic. Only use when simple_query cannot handle the request.",
        inputSchema={
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SELECT query with 'label' and 'value' aliases. Can include JOINs and subqueries."
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


# Database-specific SQL hints
SQL_HINTS = {
    "postgresql": """PostgreSQL syntax:
  - EXTRACT(YEAR FROM date_col) for year
  - EXTRACT(MONTH FROM date_col) for month
  - TO_CHAR(date_col, 'YYYY-MM') for formatting
  - Do NOT use strftime()""",
    "mysql": """MySQL syntax:
  - YEAR(date_col) for year
  - MONTH(date_col) for month
  - DATE_FORMAT(date_col, '%Y-%m') for formatting
  - Do NOT use strftime()""",
    "sqlite": """SQLite syntax:
  - strftime('%Y', date_col) for year
  - strftime('%m', date_col) for month
  - strftime('%Y-%m', date_col) for formatting""",
}


def get_sql_hints(db_type: str) -> str:
    """Get SQL hints for the database type."""
    return SQL_HINTS.get(db_type, "")


def format_rows(rows: list) -> list:
    """Convert Python objects to JSON-serializable types."""
    formatted = []
    for row in rows:
        formatted_row = {}
        for key, value in row.items():
            if isinstance(value, (date, datetime)):
                formatted_row[key] = value.isoformat()
            elif isinstance(value, Decimal):
                formatted_row[key] = float(value)
            else:
                formatted_row[key] = value
        formatted.append(formatted_row)
    return formatted


@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return RESOURCES


@server.read_resource()
async def read_resource(uri) -> str:
    """Read a resource by URI."""
    from sqlalchemy import inspect

    uri_str = str(uri)  # Convert AnyUrl to string
    logger.info(f"Reading resource: {uri_str}")
    if uri_str == "schema://database":
        from app.db.database import db

        if not db.engine:
            await db.connect()

        # Use SQLAlchemy Inspector - works for all databases
        async with db.engine.connect() as conn:
            def get_schema(sync_conn):
                inspector = inspect(sync_conn)
                schema_parts = ["DATABASE SCHEMA:", ""]

                for table_name in inspector.get_table_names():
                    schema_parts.append(f"Table: {table_name}")
                    for col in inspector.get_columns(table_name):
                        nullable = "NULL" if col["nullable"] else "NOT NULL"
                        col_type = str(col["type"])
                        schema_parts.append(f"  - {col['name']}: {col_type} ({nullable})")
                    schema_parts.append("")

                return "\n".join(schema_parts)

            return await conn.run_sync(get_schema)

    raise ValueError(f"Unknown resource: {uri_str}")


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List available prompts."""
    return PROMPTS


@server.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    """Get a prompt by name with arguments filled in."""
    if name == "data_analyst":
        from app.db.database import db

        schema = arguments.get("schema", "") if arguments else ""
        question = arguments.get("question", "") if arguments else ""
        sql_hints = get_sql_hints(db.db_type)

        content = f"""You are a data analyst. Convert the user's question into a database query for visualization.

{schema}

RULES:
- Use bar chart for comparisons
- Use line chart for trends over time
- Use pie chart for proportions
- Reject questions unrelated to data analysis
- {sql_hints}

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
    """Execute query tools."""
    import asyncio
    from app.db.database import db

    if not db.engine:
        await db.connect()

    try:
        # Build SQL based on tool type
        if name == "simple_query":
            sql, params = await build_sql_from_structure(arguments)
            chart_type = arguments.get("chart_type", "bar")
            logger.info(f"simple_query SQL: {sql}, params: {params}")

        elif name == "advanced_query":
            sql = validate_raw_sql(arguments.get("sql", ""))
            params = None  # advanced_query doesn't use params (raw SQL from AI)
            chart_type = arguments.get("chart_type", "bar")
            logger.info(f"advanced_query SQL: {sql}")

        else:
            raise ValueError(f"Unknown tool: {name}")

        # Execute query with timeout
        try:
            rows = await asyncio.wait_for(
                db.execute_query(sql, params),
                timeout=QUERY_TIMEOUT
            )
        except asyncio.TimeoutError:
            raise ValueError(f"Query timed out after {QUERY_TIMEOUT} seconds")

        result = {"chart_type": chart_type, "rows": format_rows(rows)}
        return [TextContent(type="text", text=json.dumps(result))]

    except Exception as e:
        logger.error(f"Tool error: {e}")
        # Include valid tables in error to help AI self-correct
        try:
            valid_tables = await get_valid_tables()
            error_msg = f"{str(e)}. Valid tables: {valid_tables}"
        except Exception:
            error_msg = str(e)
        return [TextContent(type="text", text=json.dumps({"error": error_msg}))]


# Health check endpoint
async def health(request):
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "server": "datatovisual-mcp"})


# ASGI app that handles MCP SSE transport
async def handle_mcp(scope, receive, send):
    """Route MCP SSE and message requests."""
    path = scope.get("path", "")

    if path == "/sse" or path == "/sse/":
        logger.info("New SSE connection")
        async with sse.connect_sse(scope, receive, send) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options()
            )
    elif "/messages" in path:
        await sse.handle_post_message(scope, receive, send)
    else:
        # 404 for unknown paths
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [[b"content-type", b"text/plain"]],
        })
        await send({
            "type": "http.response.body",
            "body": b"Not Found",
        })


# Starlette app for HTTP server
app = Starlette(
    debug=True,
    routes=[
        Route("/health", health),
        Mount("/", app=handle_mcp),
    ]
)


# For running with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
