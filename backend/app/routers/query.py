import logging
from fastapi import APIRouter, HTTPException
from app.schemas.query import QueryRequest, QueryResponse
from app.services.llm_service import llm_service
from app.services.chart_service import format_chart_data
from app.db.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Convert natural language question to SQL and return chart data."""
    # 1. Generate SQL from question (raises AppException on error)
    result = llm_service.generate_sql(request.question)

    sql = result["sql"]
    chart_type = result["chart_type"]

    # Log for debugging
    logger.info(f"Question: {request.question}")
    logger.info(f"Generated SQL: {sql}")

    # 2. Execute SQL
    try:
        rows = await db.execute_query(sql)
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute query")

    # 3. Format for Chart.js
    chart_data = format_chart_data(rows)

    return QueryResponse(
        question=request.question,
        chart_type=chart_type,
        data=chart_data
    )
