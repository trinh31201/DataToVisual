from enum import Enum


class ErrorType(Enum):
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    INVALID_RESPONSE = "invalid_response"
    NOT_CONFIGURED = "not_configured"
    DANGEROUS_SQL = "dangerous_sql"


# Map error types to HTTP status codes
ERROR_STATUS_MAP = {
    ErrorType.RATE_LIMIT: 429,
    ErrorType.NOT_CONFIGURED: 503,
    ErrorType.INVALID_RESPONSE: 400,
    ErrorType.DANGEROUS_SQL: 400,
    ErrorType.API_ERROR: 503,
}
