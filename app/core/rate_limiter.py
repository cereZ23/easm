"""
Distributed rate limiting using Redis

Implements token bucket algorithm with multiple rate limit tiers:
- Per-user rate limits
- Per-IP rate limits
- Per-endpoint rate limits
- Global rate limits

OWASP References:
- API4:2023 - Unrestricted Resource Consumption
- A05:2021 - Security Misconfiguration
"""

import time
import logging
from typing import Optional, Tuple
from functools import wraps

import redis
from fastapi import Request, HTTPException, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter using Redis

    Algorithm:
    - Tokens are added to bucket at fixed rate
    - Each request consumes 1 token
    - If bucket is empty, request is rejected
    - Bucket has maximum capacity

    Benefits:
    - Allows bursts while maintaining average rate
    - Distributed across multiple API servers
    - Low latency (single Redis call)
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        default_limit: int = 100,
        default_window: int = 60
    ):
        """
        Initialize rate limiter

        Args:
            redis_client: Redis client instance
            default_limit: Default number of requests per window
            default_window: Default time window in seconds
        """
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )

        self.default_limit = default_limit
        self.default_window = default_window

    def _get_key(self, identifier: str, scope: str = "global") -> str:
        """
        Get Redis key for rate limit tracking

        Args:
            identifier: User ID, IP address, API key, etc.
            scope: Rate limit scope (global, user, ip, endpoint)

        Returns:
            Redis key string
        """
        return f"ratelimit:{scope}:{identifier}"

    def check_rate_limit(
        self,
        identifier: str,
        limit: int = None,
        window: int = None,
        scope: str = "global"
    ) -> Tuple[bool, int, int]:
        """
        Check if request is within rate limit

        Args:
            identifier: Unique identifier (user_id, ip, etc.)
            limit: Maximum requests per window
            window: Time window in seconds
            scope: Rate limit scope

        Returns:
            Tuple of (is_allowed, remaining, reset_time)
            - is_allowed: True if request is allowed
            - remaining: Number of requests remaining
            - reset_time: Unix timestamp when limit resets

        Uses sliding window algorithm with Redis:
        - More accurate than fixed window
        - Prevents burst at window boundaries
        """
        limit = limit or self.default_limit
        window = window or self.default_window

        key = self._get_key(identifier, scope)
        now = time.time()
        window_start = now - window

        try:
            # Use Redis pipeline for atomicity
            pipe = self.redis.pipeline()

            # Remove old entries outside current window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(now): now})

            # Set expiration on key
            pipe.expire(key, window)

            # Execute pipeline
            results = pipe.execute()

            # Get current count (before adding new request)
            current_count = results[1]

            # Calculate remaining and reset time
            remaining = max(0, limit - current_count - 1)
            reset_time = int(now + window)

            # Check if limit exceeded
            is_allowed = current_count < limit

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for {identifier} "
                    f"(scope={scope}, limit={limit}/{window}s)"
                )

            return is_allowed, remaining, reset_time

        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            # Fail open - allow request if Redis is down
            return True, limit, int(now + window)

    def reset_limit(self, identifier: str, scope: str = "global"):
        """
        Reset rate limit for identifier

        Args:
            identifier: Identifier to reset
            scope: Rate limit scope

        Use case:
            - Admin override
            - Testing
            - Manual reset after false positive
        """
        key = self._get_key(identifier, scope)
        try:
            self.redis.delete(key)
            logger.info(f"Reset rate limit for {identifier} (scope={scope})")
        except redis.RedisError as e:
            logger.error(f"Failed to reset rate limit: {e}")

    def get_usage(self, identifier: str, scope: str = "global") -> int:
        """
        Get current usage count

        Args:
            identifier: Identifier to check
            scope: Rate limit scope

        Returns:
            Number of requests in current window
        """
        key = self._get_key(identifier, scope)
        now = time.time()
        window_start = now - self.default_window

        try:
            # Count entries in current window
            count = self.redis.zcount(key, window_start, now)
            return count
        except redis.RedisError as e:
            logger.error(f"Failed to get rate limit usage: {e}")
            return 0


# Global rate limiter instance
_rate_limiter = RateLimiter()


def rate_limit(
    limit: int = 100,
    window: int = 60,
    scope: str = "user",
    key_func = None
):
    """
    Rate limit decorator for FastAPI endpoints

    Args:
        limit: Maximum requests per window
        window: Time window in seconds
        scope: Rate limit scope (user, ip, endpoint)
        key_func: Custom function to extract identifier from request

    Usage:
        @app.get("/api/data")
        @rate_limit(limit=10, window=60, scope="user")
        async def get_data(request: Request, user_id: str = Depends(get_current_user)):
            ...

    Security:
        - Prevents brute force attacks
        - Prevents DoS attacks
        - Protects expensive operations
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request is None:
                request = kwargs.get('request')

            if request is None:
                logger.warning("Rate limit decorator: No request object found")
                return await func(*args, **kwargs)

            # Determine identifier
            if key_func:
                identifier = key_func(request)
            elif scope == "ip":
                identifier = request.client.host
            elif scope == "user":
                # Extract user from token (if authenticated)
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    try:
                        from app.core.security import verify_token
                        token = auth_header[7:]
                        payload = verify_token(token)
                        identifier = payload.get("sub", request.client.host)
                    except:
                        identifier = request.client.host
                else:
                    identifier = request.client.host
            elif scope == "endpoint":
                identifier = f"{request.method}:{request.url.path}"
            else:
                identifier = request.client.host

            # Check rate limit
            is_allowed, remaining, reset_time = _rate_limiter.check_rate_limit(
                identifier=identifier,
                limit=limit,
                window=window,
                scope=scope
            )

            # Add rate limit headers to response
            # Note: We'll add these via middleware since decorator can't modify response directly

            if not is_allowed:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": limit,
                        "window": window,
                        "reset_time": reset_time,
                        "retry_after": reset_time - int(time.time())
                    },
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_time),
                        "Retry-After": str(reset_time - int(time.time()))
                    }
                )

            # Execute endpoint
            return await func(*args, **kwargs)

        return wrapper
    return decorator


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Global rate limiting middleware

    Applies rate limits to all requests:
    - Per-IP: 500 requests per minute
    - Per-endpoint: Configurable limits
    - Global: 10,000 requests per minute

    This runs before route handlers and provides baseline protection.
    """

    def __init__(
        self,
        app,
        global_limit: int = 10000,
        ip_limit: int = 500,
        window: int = 60
    ):
        """
        Initialize middleware

        Args:
            app: FastAPI application
            global_limit: Global requests per window
            ip_limit: Per-IP requests per window
            window: Time window in seconds
        """
        super().__init__(app)
        self.global_limit = global_limit
        self.ip_limit = ip_limit
        self.window = window
        self.rate_limiter = _rate_limiter

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""

        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/healthz", "/ready"]:
            return await call_next(request)

        # Skip if rate limiting is disabled
        if not settings.rate_limit_enabled:
            return await call_next(request)

        client_ip = request.client.host

        # Check global rate limit
        is_allowed, remaining, reset_time = self.rate_limiter.check_rate_limit(
            identifier="global",
            limit=self.global_limit,
            window=self.window,
            scope="global"
        )

        if not is_allowed:
            return Response(
                content='{"error": "Global rate limit exceeded"}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "X-RateLimit-Limit": str(self.global_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time - int(time.time()))
                }
            )

        # Check per-IP rate limit
        is_allowed, remaining, reset_time = self.rate_limiter.check_rate_limit(
            identifier=client_ip,
            limit=self.ip_limit,
            window=self.window,
            scope="ip"
        )

        if not is_allowed:
            return Response(
                content='{"error": "IP rate limit exceeded"}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "X-RateLimit-Limit": str(self.ip_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time - int(time.time()))
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(self.ip_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response


def get_rate_limiter() -> RateLimiter:
    """
    Get global rate limiter instance

    Returns:
        RateLimiter instance
    """
    return _rate_limiter
