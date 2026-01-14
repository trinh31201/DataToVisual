"""
Database tools for Gemini Function Calling.
LLM picks the tool, WE build the SQL.
"""
import google.generativeai as genai
from app.db.database import db


# Define tools using Gemini's format
query_sales_func = genai.protos.FunctionDeclaration(
    name="query_sales",
    description="Query sales data with aggregation. Use for questions about sales, revenue, trends.",
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "group_by": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                enum=["category", "year", "month", "product"],
                description="How to group the sales data"
            ),
            "aggregate": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                enum=["SUM", "COUNT", "AVG"],
                description="Aggregation function"
            ),
            "years": genai.protos.Schema(
                type=genai.protos.Type.ARRAY,
                items=genai.protos.Schema(type=genai.protos.Type.INTEGER),
                description="Filter by specific years"
            ),
            "limit": genai.protos.Schema(
                type=genai.protos.Type.INTEGER,
                description="Limit number of results"
            ),
            "order": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                enum=["ASC", "DESC"],
                description="Sort order"
            ),
            "chart_type": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                enum=["bar", "line", "pie"],
                description="Type of chart to display"
            )
        },
        required=["group_by", "chart_type"]
    )
)

query_products_func = genai.protos.FunctionDeclaration(
    name="query_products",
    description="Query product data. Use for questions about products, categories.",
    parameters=genai.protos.Schema(
        type=genai.protos.Type.OBJECT,
        properties={
            "select": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                enum=["all", "by_category", "top_selling"],
                description="What product data to get"
            ),
            "limit": genai.protos.Schema(
                type=genai.protos.Type.INTEGER,
                description="Limit number of results"
            ),
            "chart_type": genai.protos.Schema(
                type=genai.protos.Type.STRING,
                enum=["bar", "line", "pie"],
                description="Type of chart to display"
            )
        },
        required=["select", "chart_type"]
    )
)

# Create the tool
TOOL_DEFINITIONS = genai.protos.Tool(
    function_declarations=[query_sales_func, query_products_func]
)


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
    """Query sales - WE build the SQL (safe!)"""

    # Map group_by to SQL
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
    """Query products - WE build the SQL (safe!)"""

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
