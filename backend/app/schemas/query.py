from pydantic import BaseModel
from typing import Any


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    chart_type: str
    rows: list[dict[str, Any]]
