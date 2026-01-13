from pydantic import BaseModel
from typing import Any


class QueryRequest(BaseModel):
    question: str


class ChartData(BaseModel):
    labels: list[str]
    datasets: list[dict[str, Any]]


class QueryResponse(BaseModel):
    success: bool
    question: str
    sql: str | None = None
    chart_type: str | None = None
    data: ChartData | None = None
    error: str | None = None
