import logging
from fastapi import APIRouter, HTTPException
from app.schemas.query import QueryRequest, QueryResponse, ChartData
from app.services.llm_service import llm_service
from app.db.database import db
from app.errors import ErrorType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])

# Map error types to HTTP status codes
ERROR_STATUS_MAP = {
    ErrorType.RATE_LIMIT: 429,
    ErrorType.NOT_CONFIGURED: 503,
    ErrorType.INVALID_RESPONSE: 400,
    ErrorType.DANGEROUS_SQL: 400,
    ErrorType.API_ERROR: 503,
}


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    # 1. Generate SQL from question
    result = llm_service.generate_sql(request.question)

    if not result["success"]:
        error_type = result.get("error_type", ErrorType.API_ERROR)
        status_code = ERROR_STATUS_MAP.get(error_type, 500)
        raise HTTPException(status_code=status_code, detail=result.get("error", "Unknown error"))

    sql = result["sql"]
    chart_type = result["chart_type"]

    # Log SQL for debugging
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
        success=True,
        question=request.question,
        chart_type=chart_type,
        data=chart_data
    )


def format_chart_data(rows: list[dict]) -> ChartData:
    if not rows:
        return ChartData(labels=[], datasets=[])

    columns = list(rows[0].keys())
    labels = [str(row[columns[0]]) for row in rows]

    datasets = []
    for col in columns[1:]:
        datasets.append({
            "label": col.replace("_", " ").title(),
            "data": [float(row[col]) if row[col] else 0 for row in rows]
        })

    return ChartData(labels=labels, datasets=datasets)
