import logging
from fastapi import APIRouter, HTTPException
from app.schemas.query import QueryRequest, QueryResponse
from app.services.ai_service import ai_service
from app.mcp.server import execute_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Convert natural language question to data.

    Works with any AI provider (Claude, Gemini, OpenAI) using MCP tool format.
    """

    # 1. Get function call from AI (works with any provider)
    function_call = ai_service.get_function_call(request.question)

    logger.info(f"Question: {request.question}")
    logger.info(f"Function call: {function_call}")

    # 2. Execute the tool (builds and runs SQL)
    try:
        result = await execute_tool(function_call["name"], function_call["args"])
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")

    # 3. Return result
    return QueryResponse(
        question=request.question,
        chart_type=result["chart_type"],
        rows=result["rows"]
    )
