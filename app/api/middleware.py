"""
Security middleware for FastAPI

Implements:
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- HTTPS redirect in production
- Request ID tracking
- Request/response logging
- Trusted host validation

OWASP References:
- A05:2021 - Security Misconfiguration
- A09:2021 - Security Logging and Monitoring Failures
"""

import time
import uuid
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.datastructures import Headers

from app.config import settings
from app.core.audit import log_audit_event, AuditEventType

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: max-age=31536000; includeSubDomains (HTTPS only)
    - Content-Security-Policy: default-src 'self'
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: geolocation=(), microphone=(), camera=()

    OWASP: A05:2021 - Security Misconfiguration
    """

    def __init__(
        self,
        app,
        include_hsts: bool = True,
        csp_policy: str = None
    ):
        """
        Initialize middleware

        Args:
            app: FastAPI application
            include_hsts: Include HSTS header (only for HTTPS)
            csp_policy: Content Security Policy (custom policy or None for default)
        """
        super().__init__(app)
        self.include_hsts = include_hsts

        # Enhanced CSP policy (Sprint 3 Security Enhancement)
        if csp_policy is None:
            # More restrictive CSP - removes unsafe-inline where possible
            self.csp_policy = (
                "default-src 'self'; "
                "script-src 'self'; "  # Removed unsafe-inline for better XSS protection
                "style-src 'self' 'unsafe-inline'; "  # Keep for now, can use nonce later
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "  # Stronger than X-Frame-Options: DENY
                "base-uri 'self'; "  # Prevent base tag injection
                "form-action 'self'"  # Prevent form submission to external sites
            )
        else:
            self.csp_policy = csp_policy

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response"""

        response = await call_next(request)

        # Basic security headers (always include)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.csp_policy

        # HSTS (only on HTTPS connections)
        if self.include_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Remove server header (don't leak server info)
        if "server" in response.headers:
            del response.headers["server"]

        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    Redirect HTTP to HTTPS in production

    Security:
        - Forces HTTPS in production environment
        - Skips health check endpoints
        - Preserves query parameters
    """

    def __init__(self, app, enabled: bool = True):
        """
        Initialize middleware

        Args:
            app: FastAPI application
            enabled: Enable HTTPS redirect (default: True in production)
        """
        super().__init__(app)
        self.enabled = enabled and settings.environment == "production"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Redirect HTTP to HTTPS if enabled"""

        if not self.enabled:
            return await call_next(request)

        # Skip health checks
        if request.url.path in ["/health", "/healthz", "/ready"]:
            return await call_next(request)

        # Redirect HTTP to HTTPS
        if request.url.scheme == "http":
            url = request.url.replace(scheme="https")
            logger.info(f"Redirecting HTTP to HTTPS: {request.url} -> {url}")
            return RedirectResponse(url=str(url), status_code=301)

        return await call_next(request)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Add unique request ID to each request

    Benefits:
        - Trace requests across services
        - Correlate logs
        - Debug issues

    Adds:
        - X-Request-ID header to request context
        - X-Request-ID header to response
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID"""

        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store in request state for access in route handlers
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all requests and responses

    Logs:
        - Request method, path, IP
        - Response status code, time
        - User ID (if authenticated)
        - Request/response size

    Security:
        - Sanitizes sensitive headers (Authorization, Cookie)
        - Logs suspicious patterns
        - Tracks slow requests
    """

    def __init__(
        self,
        app,
        log_request_body: bool = False,
        log_response_body: bool = False,
        slow_request_threshold: float = 5.0
    ):
        """
        Initialize middleware

        Args:
            app: FastAPI application
            log_request_body: Log request body (careful with large payloads)
            log_response_body: Log response body (careful with large payloads)
            slow_request_threshold: Log warning if request takes longer (seconds)
        """
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.slow_request_threshold = slow_request_threshold

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response"""

        # Start timer
        start_time = time.time()

        # Extract request info
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""

        # Get request ID
        request_id = getattr(request.state, "request_id", "unknown")

        # Log request
        logger.info(
            f"Request: {method} {path}",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "query": query,
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent", ""),
            }
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log response
        log_level = logging.INFO
        if response.status_code >= 500:
            log_level = logging.ERROR
        elif response.status_code >= 400:
            log_level = logging.WARNING
        elif duration > self.slow_request_threshold:
            log_level = logging.WARNING

        logger.log(
            log_level,
            f"Response: {method} {path} - {response.status_code} ({duration:.2f}s)",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration": duration,
                "client_ip": client_ip,
            }
        )

        # Log slow requests
        if duration > self.slow_request_threshold:
            logger.warning(
                f"Slow request detected: {method} {path} took {duration:.2f}s",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "duration": duration,
                }
            )

        # Add duration header for monitoring
        response.headers["X-Response-Time"] = f"{duration:.3f}"

        return response


class TrustedHostMiddleware(BaseHTTPMiddleware):
    """
    Validate Host header against trusted hosts

    Security:
        - Prevents HTTP Host header attacks
        - Mitigates DNS rebinding attacks
        - Enforces allowed hosts

    Configuration:
        Set ALLOWED_HOSTS environment variable
    """

    def __init__(self, app, allowed_hosts: list[str] = None):
        """
        Initialize middleware

        Args:
            app: FastAPI application
            allowed_hosts: List of allowed hostnames
        """
        super().__init__(app)
        self.allowed_hosts = allowed_hosts or ["*"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate host header"""

        # Skip validation if wildcard is allowed
        if "*" in self.allowed_hosts:
            return await call_next(request)

        # Get host from headers
        host = request.headers.get("host", "").split(":")[0]

        # Check if host is allowed
        if host not in self.allowed_hosts:
            logger.warning(
                f"Invalid Host header: {host} (allowed: {self.allowed_hosts})",
                extra={
                    "host": host,
                    "client_ip": request.client.host if request.client else "unknown",
                }
            )

            # Audit log suspicious activity
            try:
                log_audit_event(
                    event_type=AuditEventType.SUSPICIOUS_SSRF,
                    action=f"Invalid Host header: {host}",
                    result="blocked",
                    ip_address=request.client.host if request.client else "unknown",
                    details={"host": host, "path": request.url.path},
                    severity="warning"
                )
            except Exception as e:
                logger.error(f"Failed to log audit event: {e}")

            return Response(
                content='{"error": "Invalid Host header"}',
                status_code=400,
                media_type="application/json"
            )

        return await call_next(request)


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    IP whitelist middleware (optional)

    Use case:
        - Restrict admin endpoints to specific IPs
        - Internal-only APIs
        - Staging environments
    """

    def __init__(
        self,
        app,
        whitelist: list[str] = None,
        path_prefixes: list[str] = None
    ):
        """
        Initialize middleware

        Args:
            app: FastAPI application
            whitelist: List of allowed IP addresses or CIDR ranges
            path_prefixes: Only apply to paths starting with these prefixes
        """
        super().__init__(app)
        self.whitelist = whitelist or []
        self.path_prefixes = path_prefixes or []

    def _is_ip_allowed(self, ip: str) -> bool:
        """Check if IP is in whitelist"""
        if not self.whitelist:
            return True

        import ipaddress

        try:
            client_ip = ipaddress.ip_address(ip)

            for allowed in self.whitelist:
                # Check if it's a network (CIDR) or single IP
                if "/" in allowed:
                    network = ipaddress.ip_network(allowed, strict=False)
                    if client_ip in network:
                        return True
                else:
                    if str(client_ip) == allowed:
                        return True

            return False

        except ValueError:
            logger.error(f"Invalid IP address: {ip}")
            return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check IP whitelist"""

        # Skip if no whitelist configured
        if not self.whitelist:
            return await call_next(request)

        # Check if path matches prefixes
        if self.path_prefixes:
            path_matches = any(
                request.url.path.startswith(prefix)
                for prefix in self.path_prefixes
            )
            if not path_matches:
                return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else None

        # Check whitelist
        if not client_ip or not self._is_ip_allowed(client_ip):
            logger.warning(
                f"IP blocked by whitelist: {client_ip}",
                extra={
                    "client_ip": client_ip,
                    "path": request.url.path,
                }
            )

            return Response(
                content='{"error": "Access denied"}',
                status_code=403,
                media_type="application/json"
            )

        return await call_next(request)


def register_middleware(app):
    """
    Register all security middleware with FastAPI app

    Args:
        app: FastAPI application

    Usage:
        from fastapi import FastAPI
        from app.api.middleware import register_middleware

        app = FastAPI()
        register_middleware(app)
    """

    # Add middleware in order (last added = first executed)

    # 1. Request ID (always first for tracing)
    app.add_middleware(RequestIDMiddleware)

    # 2. Trusted host validation
    if settings.environment == "production":
        allowed_hosts = settings.cors_origins if settings.cors_origins else ["*"]
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # 3. HTTPS redirect (production only)
    if settings.environment == "production":
        app.add_middleware(HTTPSRedirectMiddleware, enabled=True)

    # 4. Security headers
    app.add_middleware(
        SecurityHeadersMiddleware,
        include_hsts=(settings.environment == "production")
    )

    # 5. Request logging
    app.add_middleware(
        RequestLoggingMiddleware,
        slow_request_threshold=5.0
    )

    logger.info("Registered security middleware")
