"""
MCP Server - exposes database tools to ANY AI provider.
Write once, works with Claude, Gemini, GPT, etc.
"""
from app.db.database import db


# Tool definitions in MCP format (AI-agnostic)
TOOLS = [
    {
        "name": "query_sales",
        "description": "Query sales data with aggregation. Use for questions about sales, revenue, trends.",
        "input_schema": {
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
    },
    {
        "name": "query_products",
        "description": "Query product data. Use for questions about products, categories.",
        "input_schema": {
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
    }
]


async def execute_tool(name: str, args: dict) -> dict:
    """Execute a tool and return results."""
    if name == "query_sales":
        return await query_sales(**args)
    elif name == "query_products":
        return await query_products(**args)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def query_sales(
    group_by: str,
    chart_type: str,
    aggregate: str = "SUM",
    years: list[int] = None,
    limit: int = None,
    order: str = "DESC"
) -> dict:
    """Query sales - builds SQL safely from parameters."""

    # Map group_by to SQL column
    group_map = {
        "category": "p.category",
        "year": "EXTRACT(YEAR FROM s.sale_date)",
        "month": "EXTRACT(MONTH FROM s.sale_date)",
        "product": "p.name"
    }
    group_col = group_map[group_by]

    # Build SQL safely
    sql = f"""
        SELECT {group_col} as label, {aggregate}(s.total_amount) as value
        FROM sales s
        JOIN products p ON s.product_id = p.id
    """

    # Add year filter if specified
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
