"""
Query endpoint using full MCP integration.
Tools are discovered automatically from MCP server.
"""
import logging
from fastapi import APIRouter

from app.schemas.query import QueryRequest, QueryResponse
from app.mcp.client import mcp_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Convert natural language question to data visualization.

    Full MCP flow:
    1. Connect to MCP server
    2. Discover tools via list_tools()
    3. AI picks tool and args
    4. Execute via call_tool()
    5. Return result
    """
    logger.info(f"Question: {request.question}")

    # Full MCP query - tools discovered automatically
    result = await mcp_client.query(request.question)

    logger.info(f"Result: chart_type={result['chart_type']}, rows={len(result['rows'])}")

    return QueryResponse(
        question=request.question,
        chart_type=result["chart_type"],
        rows=result["rows"]
    )
