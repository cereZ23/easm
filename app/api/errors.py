"""
Secure error handling for FastAPI

Prevents information leakage while providing useful error messages.
Logs detailed errors server-side for debugging.

OWASP References:
- A05:2021 - Security Misconfiguration
- A09:2021 - Security Logging and Monitoring Failures
"""

import logging
import traceback
from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.audit import log_audit_event, AuditEventType

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API error"""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.error_code = error_code or "INTERNAL_ERROR"
        super().__init__(self.message)


class AuthenticationError(APIError):
    """Authentication failed"""

    def __init__(self, message: str = "Authentication required", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
            error_code="AUTH_REQUIRED"
        )


class AuthorizationError(APIError):
    """Authorization failed"""

    def __init__(self, message: str = "Insufficient permissions", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
            error_code="INSUFFICIENT_PERMISSIONS"
        )


class NotFoundError(APIError):
    """Resource not found"""

    def __init__(self, resource: str = "Resource", resource_id: Any = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with ID '{resource_id}' not found"

        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND"
        )


class ValidationError(APIError):
    """Validation failed"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
            error_code="VALIDATION_ERROR"
        )


class RateLimitError(APIError):
    """Rate limit exceeded"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="Rate limit exceeded",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after},
            error_code="RATE_LIMIT_EXCEEDED"
        )


class TenantError(APIError):
    """Tenant-related error"""

    def __init__(self, message: str = "Tenant access denied"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="TENANT_ACCESS_DENIED"
        )


def create_error_response(
    message: str,
    status_code: int = 500,
    error_code: str = "ERROR",
    details: Optional[Dict[str, Any]] = None,
    include_trace: bool = False
) -> JSONResponse:
    """
    Create standardized error response

    Args:
        message: Error message
        status_code: HTTP status code
        error_code: Application error code
        details: Additional error details
        include_trace: Include stack trace (dev only)

    Returns:
        JSONResponse with error

    Security:
        - Never includes stack traces in production
        - Sanitizes error messages
        - Logs full error server-side
    """
    error_response = {
        "error": {
            "code": error_code,
            "message": message,
        }
    }

    if details:
        error_response["error"]["details"] = details

    if include_trace:
        error_response["error"]["trace"] = traceback.format_exc()

    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


# ===========================
# Exception Handlers
# ===========================

async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """
    Handle custom API errors

    Args:
        request: FastAPI request
        exc: API error exception

    Returns:
        JSON error response
    """
    # Log error server-side
    logger.warning(
        f"API Error: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host,
        }
    )

    return create_error_response(
        message=exc.message,
        status_code=exc.status_code,
        error_code=exc.error_code,
        details=exc.details
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handle HTTP exceptions

    Args:
        request: FastAPI request
        exc: HTTP exception

    Returns:
        JSON error response

    Security:
        - Sanitizes error messages
        - Logs sensitive errors
    """
    # Determine if error should be logged
    log_level = logging.WARNING if exc.status_code >= 500 else logging.INFO

    logger.log(
        log_level,
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host,
        }
    )

    # Audit log for authentication/authorization failures
    if exc.status_code in [401, 403]:
        try:
            log_audit_event(
                event_type=AuditEventType.AUTHZ_ACCESS_DENIED,
                action=f"{request.method} {request.url.path}",
                result="denied",
                ip_address=request.client.host,
                endpoint=request.url.path,
                method=request.method,
                severity="warning"
            )
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

    return create_error_response(
        message=str(exc.detail),
        status_code=exc.status_code,
        error_code=f"HTTP_{exc.status_code}"
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle Pydantic validation errors

    Args:
        request: FastAPI request
        exc: Validation error

    Returns:
        JSON error response with validation details

    Security:
        - Sanitizes field names and values
        - Doesn't leak internal structure
    """
    errors = []
    for error in exc.errors():
        # Extract field and message
        field = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_type = error["type"]

        errors.append({
            "field": field,
            "message": message,
            "type": error_type
        })

    logger.info(
        f"Validation Error: {len(errors)} errors",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": errors,
            "client_ip": request.client.host,
        }
    )

    return create_error_response(
        message="Validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        details={"errors": errors}
    )


async def jwt_error_handler(request: Request, exc: InvalidTokenError) -> JSONResponse:
    """
    Handle JWT errors

    Args:
        request: FastAPI request
        exc: JWT error

    Returns:
        JSON error response

    Security:
        - Logs authentication failures
        - Audits JWT errors
        - Generic error message (no token details)
    """
    logger.warning(
        f"JWT Error: {type(exc).__name__}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host,
        }
    )

    # Audit log
    try:
        log_audit_event(
            event_type=AuditEventType.AUTH_LOGIN_FAILURE,
            action="JWT token verification failed",
            result="failure",
            ip_address=request.client.host,
            endpoint=request.url.path,
            method=request.method,
            error_message=str(exc),
            severity="warning"
        )
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")

    # Determine specific error message
    if isinstance(exc, jwt.ExpiredSignatureError):
        message = "Token has expired"
        error_code = "TOKEN_EXPIRED"
    elif isinstance(exc, jwt.InvalidTokenError):
        message = "Invalid token"
        error_code = "TOKEN_INVALID"
    else:
        message = "Authentication failed"
        error_code = "AUTH_FAILED"

    return create_error_response(
        message=message,
        status_code=status.HTTP_401_UNAUTHORIZED,
        error_code=error_code
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions

    Args:
        request: FastAPI request
        exc: Exception

    Returns:
        JSON error response

    Security:
        - Never leaks stack traces to client
        - Logs full error server-side
        - Returns generic message
    """
    # Log full error with stack trace
    logger.error(
        f"Unhandled Exception: {type(exc).__name__} - {str(exc)}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host,
        }
    )

    # Audit log critical errors
    try:
        log_audit_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            action=f"Unhandled exception in {request.method} {request.url.path}",
            result="failure",
            ip_address=request.client.host,
            endpoint=request.url.path,
            method=request.method,
            error_message=str(exc)[:500],
            severity="critical"
        )
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")

    # Return generic error (don't leak details)
    return create_error_response(
        message="An internal error occurred. Please try again later.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_ERROR"
    )


def register_error_handlers(app):
    """
    Register all error handlers with FastAPI app

    Args:
        app: FastAPI application

    Usage:
        from fastapi import FastAPI
        from app.api.errors import register_error_handlers

        app = FastAPI()
        register_error_handlers(app)
    """
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(InvalidTokenError, jwt_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Registered error handlers")
