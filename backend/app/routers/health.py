from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
