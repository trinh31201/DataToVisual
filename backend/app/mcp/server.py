"""
Full MCP Server - runs as separate process.
AI discovers tools automatically via list_tools().
"""
import asyncio
import json
import sys
import os

# Add parent directory to path for imports when running as subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Create MCP server
server = Server("datatovisual")


# Tool definitions
TOOLS = [
    Tool(
        name="query_sales",
        description="Query sales data with aggregation. Use for questions about sales, revenue, trends.",
        inputSchema={
            "type": "object",
            "properties": {
                "group_by": {
                    "type": "string",
                    "enum": ["category", "year", "month", "product"],
                    "description": "How to group the sales data"
                },
                "aggregate": {
                    "type": "string",
                    "enum": ["SUM", "COUNT", "AVG"],
                    "description": "Aggregation function"
                },
                "years": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Filter by specific years"
                },
                "limit": {
                    "type": "integer",
                    "description": "Limit number of results"
                },
                "order": {
                    "type": "string",
                    "enum": ["ASC", "DESC"],
                    "description": "Sort order"
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "pie"],
                    "description": "Type of chart to display"
                }
            },
            "required": ["group_by", "chart_type"]
        }
    ),
    Tool(
        name="query_products",
        description="Query product data. Use for questions about products, categories.",
        inputSchema={
            "type": "object",
            "properties": {
                "select": {
                    "type": "string",
                    "enum": ["all", "by_category", "top_selling"],
                    "description": "What product data to get"
                },
                "limit": {
                    "type": "integer",
                    "description": "Limit number of results"
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "pie"],
                    "description": "Type of chart to display"
                }
            },
            "required": ["select", "chart_type"]
        }
    )
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """AI calls this to discover available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """AI calls this to execute a tool."""
    from app.db.database import db

    # Connect to database if not connected
    if not db.pool:
        await db.connect()

    try:
        if name == "query_sales":
            result = await query_sales(db, **arguments)
        elif name == "query_products":
            result = await query_products(db, **arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def query_sales(
    db,
    group_by: str,
    chart_type: str,
    aggregate: str = "SUM",
    years: list[int] = None,
    limit: int = None,
    order: str = "DESC"
) -> dict:
    """Query sales - builds SQL safely from parameters."""
    group_map = {
        "category": "p.category",
        "year": "EXTRACT(YEAR FROM s.sale_date)",
        "month": "EXTRACT(MONTH FROM s.sale_date)",
        "product": "p.name"
    }
    group_col = group_map[group_by]

    sql = f"""
        SELECT {group_col} as label, {aggregate}(s.total_amount) as value
        FROM sales s
        JOIN products p ON s.product_id = p.id
    """

    if years:
        years_str = ", ".join(str(y) for y in years)
        sql += f" WHERE EXTRACT(YEAR FROM s.sale_date) IN ({years_str})"

    sql += f" GROUP BY {group_col}"
    sql += f" ORDER BY value {order}"

    if limit:
        sql += f" LIMIT {limit}"

    rows = await db.execute_query(sql)

    return {
        "chart_type": chart_type,
        "rows": rows
    }


async def query_products(
    db,
    select: str,
    chart_type: str,
    limit: int = None
) -> dict:
    """Query products - builds SQL safely from parameters."""
    if select == "all":
        sql = "SELECT name as label, price as value FROM products"
    elif select == "by_category":
        sql = "SELECT category as label, COUNT(*) as value FROM products GROUP BY category"
    elif select == "top_selling":
        sql = """
            SELECT p.name as label, SUM(s.total_amount) as value
            FROM products p
            JOIN sales s ON p.id = s.product_id
            GROUP BY p.name
            ORDER BY value DESC
        """

    if limit:
        sql += f" LIMIT {limit}"

    rows = await db.execute_query(sql)

    return {
        "chart_type": chart_type,
        "rows": rows
    }


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
