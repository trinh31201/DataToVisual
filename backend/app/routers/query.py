"""Query endpoint - converts natural language to chart data via MCP."""
import logging
from fastapi import APIRouter

from app.schemas.query import QueryRequest, QueryResponse
from app.mcp.client import mcp_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Convert natural language question to chart visualization."""
    logger.info(f"Question: {request.question}")

    result = await mcp_client.query(request.question)

    logger.info(f"Result: chart_type={result['chart_type']}, rows={len(result['rows'])}")

    return QueryResponse(
        question=request.question,
        chart_type=result["chart_type"],
        rows=result["rows"]
    )
