from fastapi import Request
from fastapi.responses import JSONResponse
from app.errors import ErrorType, ERROR_STATUS_MAP


class AppException(Exception):
    """Custom exception that services can raise."""

    def __init__(self, error_type: ErrorType, message: str):
        self.error_type = error_type
        self.message = message
        super().__init__(message)


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    """Global handler for AppException - converts to proper HTTP response."""
    status_code = ERROR_STATUS_MAP.get(exc.error_type, 500)
    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.message}
    )
