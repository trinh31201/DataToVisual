import logging
from fastapi import APIRouter
from app.schemas.query import QueryRequest, QueryResponse, ChartData
from app.services.llm_service import llm_service
from app.db.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    try:
        # 1. Generate SQL from question
        result = llm_service.generate_sql(request.question)

        if not result["success"]:
            return QueryResponse(
                success=False,
                question=request.question,
                error=result.get("error", "Failed to generate SQL")
            )

        sql = result["sql"]
        chart_type = result["chart_type"]

        # Log SQL for debugging
        logger.info(f"Question: {request.question}")
        logger.info(f"Generated SQL: {sql}")

        # 2. Execute SQL
        rows = await db.execute_query(sql)

        # 3. Format for Chart.js
        chart_data = format_chart_data(rows)

        return QueryResponse(
            success=True,
            question=request.question,
            chart_type=chart_type,
            data=chart_data
        )

    except Exception as e:
        return QueryResponse(
            success=False,
            question=request.question,
            error=str(e)
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
