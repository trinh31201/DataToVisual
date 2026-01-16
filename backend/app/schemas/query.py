from pydantic import BaseModel
from typing import Any, Optional


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    # Chart data (from query tool)
    chart_type: Optional[str] = None
    rows: Optional[list[dict[str, Any]]] = None
    # Table list (from list_tables tool)
    tables: Optional[list[str]] = None
    # Table schema (from describe_table tool)
    table: Optional[str] = None
    columns: Optional[list[dict[str, Any]]] = None
