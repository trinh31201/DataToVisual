"""
SQL building and validation logic for MCP server.
"""
import logging

logger = logging.getLogger(__name__)

# Query limits
MAX_ROWS = 1000

# Schema cache for dynamic validation
_schema_cache: dict | None = None


async def get_schema_cache() -> dict:
    """Get database schema (tables and columns) dynamically."""
    global _schema_cache
    if _schema_cache:
        return _schema_cache

    from sqlalchemy import inspect
    from app.db.database import db

    if not db.engine:
        await db.connect()

    async with db.engine.connect() as conn:
        def _get_schema(sync_conn):
            inspector = inspect(sync_conn)
            schema = {}
            for table_name in inspector.get_table_names():
                schema[table_name] = [col["name"] for col in inspector.get_columns(table_name)]
            return schema

        _schema_cache = await conn.run_sync(_get_schema)
        return _schema_cache


async def get_valid_tables() -> list[str]:
    """Get valid table names from database."""
    schema = await get_schema_cache()
    return list(schema.keys())


async def get_valid_columns(table: str) -> list[str]:
    """Get valid column names for a table."""
    schema = await get_schema_cache()
    return schema.get(table, [])


async def build_sql_from_structure(args: dict) -> tuple[str, dict]:
    """Build SQL from structured arguments with parameterized queries.

    Returns:
        tuple: (sql_template, params_dict)
    """
    table = args["table"]
    label_col = args["label_column"]
    value_col = args["value_column"]
    agg = args.get("aggregation", "NONE")
    filters = args.get("filters", [])
    order_by = args.get("order_by")
    limit = args.get("limit", MAX_ROWS)

    # Validate table dynamically
    valid_tables = await get_valid_tables()
    if table not in valid_tables:
        raise ValueError(f"Invalid table '{table}'. Valid: {valid_tables}")

    # Validate columns dynamically
    valid_columns = await get_valid_columns(table)
    if label_col not in valid_columns:
        raise ValueError(f"Invalid column '{label_col}'. Valid: {valid_columns}")
    if value_col not in valid_columns:
        raise ValueError(f"Invalid column '{value_col}'. Valid: {valid_columns}")

    # Build SELECT clause
    if agg != "NONE":
        select = f"{label_col} AS label, {agg}({value_col}) AS value"
    else:
        select = f"{label_col} AS label, {value_col} AS value"

    sql = f"SELECT {select} FROM {table}"
    params = {}

    # Build WHERE clause with parameterized values
    if filters:
        conditions = []
        for i, f in enumerate(filters):
            col = f["column"]
            op = f["operator"]
            val = f["value"]

            # Validate filter column
            if col not in valid_columns:
                raise ValueError(f"Invalid filter column '{col}'. Valid: {valid_columns}")

            # Use parameterized placeholder
            param_name = f"filter_{i}"

            if op == "IN":
                # IN clause needs special handling
                conditions.append(f"{col} IN (:{param_name})")
                params[param_name] = val
            else:
                conditions.append(f"{col} {op} :{param_name}")
                params[param_name] = val

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

    return sql, params


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
