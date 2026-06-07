from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Base custom exception class
class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request"):
        self.message = message
        self.status_code = status_code
        self.code = code

# Specific exception classes
class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404, code="not_found")

class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(message, status_code=401, code="unauthorized")

class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden access"):
        super().__init__(message, status_code=403, code="forbidden")

class ValidationException(AppException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=422, code="validation_error")

class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, status_code=409, code="conflict")

# Global exception handler
async def app_exception_handler(request: Request, exc: AppException):
    logger.error(f"AppException: {exc.message} (status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )

def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(AppException, app_exception_handler)
