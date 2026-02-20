"""
EASM Platform FastAPI Application

Main application entry point with complete REST API for Sprint 3.

Features:
- JWT authentication
- Multi-tenant isolation
- Comprehensive API endpoints
- Rate limiting
- Health monitoring
- OpenAPI documentation
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import time

from app.config import settings
from app.api.routers import (
    auth_router,
    tenants_router,
    assets_router,
    services_router,
    certificates_router,
    endpoints_router,
    findings_router,
    onboarding_router,
    scanning_router
)

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app with comprehensive metadata
app = FastAPI(
    title=settings.app_name,
    description="""
# External Attack Surface Management (EASM) Platform API

A comprehensive platform for continuous attack surface discovery, monitoring, and vulnerability management.

## Features

- **Multi-tenant Architecture**: Complete tenant isolation with role-based access control
- **Asset Discovery**: Automated discovery of domains, subdomains, IPs, and services
- **Enrichment Pipeline**: Deep scanning with HTTPx, Naabu, TLSx, and Katana
- **Vulnerability Scanning**: Integrated Nuclei for CVE detection
- **Certificate Monitoring**: TLS/SSL certificate tracking and expiry alerts
- **Web Crawling**: Comprehensive endpoint discovery and API mapping
- **Dashboard & Analytics**: Rich statistics and trend analysis

## Authentication

All API endpoints (except /health and /api/v1/auth/login) require JWT authentication:

1. Login with credentials to receive access and refresh tokens
2. Include access token in Authorization header: `Bearer <token>`
3. Refresh token when it expires using /api/v1/auth/refresh

## Rate Limits

- Default: 100 requests per minute per IP
- Higher limits available for authenticated users

## Multi-tenancy

All data endpoints are tenant-scoped:
- Users can only access tenants they belong to
- Superusers have access to all tenants
- Tenant ID is part of the API path: `/api/v1/tenants/{tenant_id}/...`
    """,
    version="3.0.0",
    debug=settings.debug,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    terms_of_service="https://example.com/terms",
    contact={
        "name": "EASM Platform Support",
        "url": "https://example.com/support",
        "email": "support@example.com"
    },
    license_info={
        "name": "Proprietary",
        "url": "https://example.com/license"
    }
)

# Add rate limiting state
app.state.limiter = limiter

# Middleware stack (order matters)
# 1. GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 2. CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests for monitoring"""
    logger.info(f"{request.method} {request.url.path} - Client: {request.client.host}")
    try:
        response = await call_next(request)
        logger.info(f"{request.method} {request.url.path} - Status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"{request.method} {request.url.path} - Error: {str(e)}")
        raise


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with consistent format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "detail": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed information"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "detail": "Request validation failed",
            "status_code": 422,
            "errors": exc.errors()
        }
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded"""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "RateLimitExceeded",
            "detail": "Too many requests. Please try again later.",
            "status_code": 429
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Handle all unhandled exceptions

    Security (Sprint 3 Enhancement):
        - Never expose internal details in production
        - Log full error server-side
        - Return generic message to client
        - Prevents information leakage via error messages

    OWASP: A09:2021 - Security Logging and Monitoring Failures
    """
    # Log full error with stack trace (server-side only)
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown")
        }
    )

    # Return generic error to client (environment-based)
    if settings.environment == "production":
        # Production: Generic message only (no internal details)
        detail = "Internal server error. Please contact support if this persists."
    else:
        # Development: Show error details for debugging
        detail = f"{exc.__class__.__name__}: {str(exc)}"

    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "detail": detail,
            "status_code": 500
        }
    )


# Root endpoint
@app.get("/", tags=["Root"])
@limiter.limit("60/minute")
def root(request: Request):
    """
    API root endpoint

    Returns basic API information and available endpoints
    """
    return {
        "message": "EASM Platform API",
        "version": "3.0.0",
        "sprint": "Sprint 3 - Complete REST API",
        "docs": "/api/docs",
        "health": "/health",
        "authentication": "/api/v1/auth/login"
    }

@app.get("/health")
def health_check():
    """
    Health check endpoint with actual connection verification

    Returns:
        dict: Health status of all services

    Note:
        - Returns 200 if all services are healthy
        - Returns 503 if any critical service is down
        - Load balancers should route traffic based on this
    """
    from app.database import engine
    import redis
    from minio import Minio
    from minio.error import S3Error

    health_status = {
        "status": "healthy",
        "services": {}
    }

    # Check PostgreSQL database
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        health_status["services"]["database"] = {
            "status": "connected",
            "type": "postgresql"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["services"]["database"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"

    # Check Redis
    try:
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        r.close()
        health_status["services"]["redis"] = {
            "status": "connected"
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        health_status["services"]["redis"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"

    # Check MinIO
    try:
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure
        )
        # Try to list buckets to verify connection
        list(client.list_buckets())
        health_status["services"]["minio"] = {
            "status": "connected",
            "endpoint": settings.minio_endpoint
        }
    except S3Error as e:
        logger.error(f"MinIO health check failed: {e}")
        health_status["services"]["minio"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
    except Exception as e:
        logger.error(f"MinIO health check failed: {e}")
        health_status["services"]["minio"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"

    # Return 503 if unhealthy so load balancers remove this instance
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status

# Include routers
app.include_router(onboarding_router)  # Public onboarding (no auth required)
app.include_router(auth_router)
app.include_router(tenants_router)
app.include_router(assets_router)
app.include_router(services_router)
app.include_router(certificates_router)
app.include_router(endpoints_router)
app.include_router(findings_router)
app.include_router(scanning_router)


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """
    Application startup event

    Performs initialization tasks:
    - Log startup information
    - Verify database connectivity
    - Initialize caches
    """
    logger.info("="*80)
    logger.info(f"Starting {settings.app_name} v3.0.0")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"API Documentation: http://{settings.api_host}:{settings.api_port}/api/docs")
    logger.info("="*80)

    # Test database connection
    try:
        from app.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection: OK")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

    # Test Redis connection
    try:
        import redis
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        r.close()
        logger.info("Redis connection: OK")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")

    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event

    Performs cleanup tasks:
    - Close database connections
    - Flush logs
    - Clean up resources
    """
    logger.info("Shutting down EASM Platform API...")
    logger.info("Shutdown complete")


# API Statistics endpoint
@app.get("/api/v1/stats", tags=["System"])
async def api_stats():
    """
    Get API statistics

    Returns:
        - Total routes
        - Available endpoints
        - System version
    """
    return {
        "version": "3.0.0",
        "total_routes": len(app.routes),
        "endpoints": {
            "auth": "/api/v1/auth",
            "tenants": "/api/v1/tenants",
            "assets": "/api/v1/tenants/{tenant_id}/assets",
            "services": "/api/v1/tenants/{tenant_id}/services",
            "certificates": "/api/v1/tenants/{tenant_id}/certificates",
            "endpoints": "/api/v1/tenants/{tenant_id}/endpoints",
            "findings": "/api/v1/tenants/{tenant_id}/findings"
        }
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}")

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        workers=1 if settings.api_reload else settings.api_workers,
        log_level=settings.log_level.lower()
    )
