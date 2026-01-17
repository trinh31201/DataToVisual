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
        schema = arguments.get("schema", "") if arguments else ""
        question = arguments.get("question", "") if arguments else ""

        content = f"""You are a data analyst. Convert the user's question into a database query for visualization.

{schema}

RULES:
- Use bar chart for comparisons
- Use line chart for trends over time
- Use pie chart for proportions
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


MAX_ROWS = 1000
QUERY_TIMEOUT = 30  # seconds

# Valid tables and columns (populated from schema)
VALID_TABLES = ["sales", "products", "features"]
VALID_COLUMNS = {
    "sales": ["id", "product_id", "quantity", "total_amount", "sale_date", "created_at"],
    "products": ["id", "name", "category", "price", "created_at"],
    "features": ["id", "product_id", "name", "description", "created_at"],
}


def build_sql_from_structure(args: dict) -> str:
    """Build SQL from structured arguments. Validates and returns safe SQL."""
    table = args["table"]
    label_col = args["label_column"]
    value_col = args["value_column"]
    agg = args.get("aggregation", "NONE")
    filters = args.get("filters", [])
    order_by = args.get("order_by")
    limit = args.get("limit", MAX_ROWS)

    # Validate table
    if table not in VALID_TABLES:
        raise ValueError(f"Invalid table '{table}'. Valid: {VALID_TABLES}")

    # Build SELECT clause
    if agg != "NONE":
        select = f"{label_col} AS label, {agg}({value_col}) AS value"
    else:
        select = f"{label_col} AS label, {value_col} AS value"

    sql = f"SELECT {select} FROM {table}"

    # Build WHERE clause
    if filters:
        conditions = []
        for f in filters:
            col = f["column"]
            op = f["operator"]
            val = f["value"]
            # Escape single quotes in value
            val_escaped = val.replace("'", "''")
            if op == "IN":
                conditions.append(f"{col} IN ({val_escaped})")
            else:
                conditions.append(f"{col} {op} '{val_escaped}'")
        sql += f" WHERE {' AND '.join(conditions)}"

    # Add GROUP BY if aggregating
    if agg != "NONE":
        sql += f" GROUP BY {label_col}"

    # Add ORDER BY
    if order_by:
        order_map = {
            "label_asc": "label ASC",
            "label_desc": "label DESC",
            "value_asc": "value ASC",
            "value_desc": "value DESC"
        }
        sql += f" ORDER BY {order_map.get(order_by, 'value DESC')}"

    # Add LIMIT
    sql += f" LIMIT {min(limit, MAX_ROWS)}"

    return sql


def validate_raw_sql(sql: str) -> str:
    """Validate raw SQL for advanced_query. Returns sanitized SQL or raises ValueError."""
    sql = sql.strip().rstrip(";")  # Remove trailing semicolon
    sql_upper = sql.upper()

    # Must be SELECT
    if not sql_upper.startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed")

    # Block dangerous keywords
    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "EXEC", "GRANT", "REVOKE"]
    for keyword in dangerous:
        if keyword in sql_upper:
            raise ValueError(f"Dangerous keyword '{keyword}' not allowed")

    # Block SQL injection patterns
    injection_patterns = [
        ";",           # Multiple statements (after stripping trailing)
        "--",          # SQL comments
        "/*",          # Block comments
        "INTO OUTFILE", # File writes
        "LOAD_FILE",   # File reads
    ]
    for pattern in injection_patterns:
        if pattern in sql_upper:
            raise ValueError(f"SQL pattern '{pattern}' not allowed")

    # Add row limit if not present
    if "LIMIT" not in sql_upper:
        sql = f"{sql} LIMIT {MAX_ROWS}"

    return sql


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
            sql = build_sql_from_structure(arguments)
            chart_type = arguments.get("chart_type", "bar")
            logger.info(f"simple_query built SQL: {sql}")

        elif name == "advanced_query":
            sql = validate_raw_sql(arguments.get("sql", ""))
            chart_type = arguments.get("chart_type", "bar")
            logger.info(f"advanced_query SQL: {sql}")

        else:
            raise ValueError(f"Unknown tool: {name}")

        # Execute query with timeout
        try:
            rows = await asyncio.wait_for(
                db.execute_query(sql),
                timeout=QUERY_TIMEOUT
            )
        except asyncio.TimeoutError:
            raise ValueError(f"Query timed out after {QUERY_TIMEOUT} seconds")

        result = {"chart_type": chart_type, "rows": rows}
        return [TextContent(type="text", text=json.dumps(result))]

    except Exception as e:
        logger.error(f"Tool error: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


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
