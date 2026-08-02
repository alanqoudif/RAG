from typing import Any


class AppError(Exception):
    """Base application error mapped to a stable error code and safe message.

    Never pass raw driver exceptions, secrets, or stack traces into `message`.
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message)


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"

    def __init__(self, message: str = "Access denied"):
        super().__init__(message)


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message)


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"

    def __init__(self, message: str = "Invalid request"):
        super().__init__(message)


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message)


class SQLValidationError(AppError):
    status_code = 422
    code = "SQL_VALIDATION_FAILED"

    def __init__(self, message: str = "The generated query could not be executed safely."):
        super().__init__(message)


class ConnectionTestError(AppError):
    status_code = 400
    code = "CONNECTION_TEST_FAILED"

    def __init__(self, message: str = "Could not connect to the target database."):
        super().__init__(message)


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"

    def __init__(self, message: str = "Too many requests"):
        super().__init__(message)


def error_body(code: str, message: str, request_id: str | None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}
