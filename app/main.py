"""
EASM Platform FastAPI Application

Main application entry point with health checks and CORS configuration.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="External Attack Surface Management Platform",
    version=settings.app_version,
    debug=settings.debug
)

# CORS middleware - uses configuration from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "EASM Platform API",
        "version": "1.0.0",
        "sprint": "Sprint 1 - Discovery Pipeline"
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

# Sprint 1: Basic endpoints will be added here
# Sprint 2: Will add full API with authentication and multi-tenant endpoints

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
