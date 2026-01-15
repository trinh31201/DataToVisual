"""
Query endpoint - simple raw SQL approach.
LLM generates SQL directly, no MCP or function calling.
"""
import logging
from fastapi import APIRouter

from app.schemas.query import QueryRequest, QueryResponse
from app.services.llm_service import llm_service
from app.db.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Simple flow:
    1. Send question to LLM
    2. LLM returns raw SQL + chart_type
    3. Execute SQL
    4. Return result
    """
    logger.info(f"Question: {request.question}")

    # 1. Get SQL from LLM
    result = llm_service.generate_sql(request.question)

    # 2. Execute SQL
    rows = await db.execute_query(result["sql"])

    logger.info(f"Result: chart_type={result['chart_type']}, rows={len(rows)}")

    return QueryResponse(
        question=request.question,
        chart_type=result["chart_type"],
        rows=rows
    )
