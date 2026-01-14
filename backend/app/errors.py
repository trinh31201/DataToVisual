from enum import Enum


class ErrorType(Enum):
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    INVALID_RESPONSE = "invalid_response"
    NOT_CONFIGURED = "not_configured"
    DANGEROUS_SQL = "dangerous_sql"
