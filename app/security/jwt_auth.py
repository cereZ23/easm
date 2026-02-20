"""
JWT authentication and authorization

Production-grade JWT implementation with:
- RS256/HS256 token signing (asymmetric/symmetric)
- Token creation and validation
- Token revocation support
- Refresh token mechanism
- Role-based access control (RBAC)

Security Enhancement (Sprint 3):
- Integrated RS256 support from app.core.security
- Automatic RSA key generation
- Fallback to HS256 for development
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
import logging

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
import redis

from app.config import settings
from app.core.security import SecurityKeys  # Import RSA key support

logger = logging.getLogger(__name__)


class JWTManager:
    """
    Production-grade JWT authentication manager

    Features:
    - RS256 (asymmetric) or HS256 (symmetric) token signing
    - Automatic RSA key generation and management
    - Secure token generation with rotation
    - Token revocation via Redis
    - Refresh token support
    - Role and permission validation

    Security:
    - Uses RS256 by default for production (private key for signing, public for verification)
    - Falls back to HS256 for development if RSA keys unavailable
    - Supports token revocation via Redis whitelist
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
        redis_client: Optional[redis.Redis] = None
    ):
        """
        Initialize JWT manager with RS256/HS256 support

        Args:
            secret_key: Secret key for HS256 (uses settings if not provided)
            algorithm: JWT signing algorithm (uses settings if not provided)
            redis_client: Redis client for token revocation

        Security:
        - RS256 recommended for production (asymmetric keys)
        - HS256 fallback for development (symmetric secret)
        """
        # Initialize security keys (RS256 or HS256)
        self.security_keys = SecurityKeys()
        self.algorithm = algorithm or self.security_keys.algorithm

        # Legacy secret key support (for HS256 fallback)
        self.secret_key = secret_key or settings.jwt_secret_key

        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        # Redis for token revocation
        if redis_client:
            self.redis_client = redis_client
        else:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True
            )

        self.bearer = HTTPBearer()

    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash

        Args:
            plain_password: Plain text password
            hashed_password: Hashed password

        Returns:
            True if password matches
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(
        self,
        subject: str,
        tenant_id: int,
        roles: list = None,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create JWT access token

        Args:
            subject: Subject (user ID)
            tenant_id: Tenant ID for multi-tenancy
            roles: User roles
            expires_delta: Token expiration time
            additional_claims: Additional JWT claims

        Returns:
            JWT token string
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

        expire = datetime.utcnow() + expires_delta
        jti = secrets.token_urlsafe(32)  # JWT ID for revocation

        payload = {
            "sub": subject,
            "tenant_id": tenant_id,
            "roles": roles or ["user"],
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
            "jti": jti,
        }

        if additional_claims:
            payload.update(additional_claims)

        # Encode token with appropriate key (RS256 or HS256)
        signing_key = self.security_keys.get_signing_key()
        token = jwt.encode(payload, signing_key, algorithm=self.algorithm)

        # Store in Redis for revocation capability
        try:
            self.redis_client.setex(
                f"jwt:access:{jti}",
                int(expires_delta.total_seconds()),
                subject
            )
        except Exception as e:
            logger.error(f"Failed to store token in Redis: {e}")
            # Continue anyway - token will still work, just can't be revoked

        logger.info(f"Created access token for user {subject} (tenant {tenant_id})")
        return token

    def create_refresh_token(
        self,
        subject: str,
        tenant_id: int,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT refresh token

        Args:
            subject: Subject (user ID)
            tenant_id: Tenant ID
            expires_delta: Token expiration time

        Returns:
            Refresh token string
        """
        if expires_delta is None:
            expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

        expire = datetime.utcnow() + expires_delta
        jti = secrets.token_urlsafe(32)

        payload = {
            "sub": subject,
            "tenant_id": tenant_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "jti": jti,
        }

        # Encode token with appropriate key (RS256 or HS256)
        signing_key = self.security_keys.get_signing_key()
        token = jwt.encode(payload, signing_key, algorithm=self.algorithm)

        # Store refresh token in Redis
        try:
            self.redis_client.setex(
                f"jwt:refresh:{jti}",
                int(expires_delta.total_seconds()),
                subject
            )
        except Exception as e:
            logger.error(f"Failed to store refresh token in Redis: {e}")

        logger.info(f"Created refresh token for user {subject} (tenant {tenant_id})")
        return token

    def verify_token(self, credentials: HTTPAuthorizationCredentials) -> Dict[str, Any]:
        """
        Verify and decode JWT token

        Args:
            credentials: HTTP authorization credentials

        Returns:
            Decoded token payload

        Raises:
            HTTPException: If token is invalid or revoked
        """
        token = credentials.credentials

        try:
            # Decode token with appropriate verification key
            verification_key = self.security_keys.get_verification_key()
            payload = jwt.decode(
                token,
                verification_key,
                algorithms=[self.algorithm]
            )

            # Check if token is revoked
            jti = payload.get('jti')
            if jti:
                token_type = payload.get('type', 'access')
                key = f"jwt:{token_type}:{jti}"

                if not self.redis_client.exists(key):
                    logger.warning(f"Attempt to use revoked token: {jti}")
                    raise HTTPException(
                        status_code=401,
                        detail="Token has been revoked"
                    )

            logger.debug(f"Token verified for user {payload.get('sub')}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Expired token attempt")
            raise HTTPException(
                status_code=401,
                detail="Token has expired"
            )
        except InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise HTTPException(
                status_code=401,
                detail="Authentication failed"
            )

    def revoke_token(self, jti: str, token_type: str = "access"):
        """
        Revoke a token by its JTI

        Args:
            jti: JWT ID
            token_type: Token type (access or refresh)
        """
        try:
            key = f"jwt:{token_type}:{jti}"
            self.redis_client.delete(key)
            logger.info(f"Revoked {token_type} token: {jti}")
        except Exception as e:
            logger.error(f"Failed to revoke token {jti}: {e}")
            raise

    def refresh_access_token(
        self,
        refresh_token: str
    ) -> Dict[str, str]:
        """
        Create new access token from refresh token

        Args:
            refresh_token: Valid refresh token

        Returns:
            Dict with new access and refresh tokens
        """
        try:
            # Decode refresh token with appropriate verification key
            verification_key = self.security_keys.get_verification_key()
            payload = jwt.decode(
                refresh_token,
                verification_key,
                algorithms=[self.algorithm]
            )

            # Verify it's a refresh token
            if payload.get('type') != 'refresh':
                raise HTTPException(
                    status_code=400,
                    detail="Invalid refresh token"
                )

            # Check if refresh token is still valid in Redis
            jti = payload.get('jti')
            if jti and not self.redis_client.exists(f"jwt:refresh:{jti}"):
                raise HTTPException(
                    status_code=401,
                    detail="Refresh token has been revoked"
                )

            # Create new access token
            access_token = self.create_access_token(
                subject=payload['sub'],
                tenant_id=payload['tenant_id'],
                roles=payload.get('roles', ['user'])
            )

            # Optionally create new refresh token (rotation)
            new_refresh_token = self.create_refresh_token(
                subject=payload['sub'],
                tenant_id=payload['tenant_id']
            )

            # Revoke old refresh token
            if jti:
                self.revoke_token(jti, 'refresh')

            return {
                'access_token': access_token,
                'refresh_token': new_refresh_token,
                'token_type': 'bearer'
            }

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Refresh token has expired"
            )
        except InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token"
            )


# Global JWT manager instance
jwt_manager = JWTManager()


# FastAPI dependencies
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user

    Args:
        credentials: HTTP authorization credentials

    Returns:
        User payload from JWT token
    """
    return jwt_manager.verify_token(credentials)


async def get_current_active_user(
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current active user

    Args:
        current_user: Current user from token

    Returns:
        User payload

    Raises:
        HTTPException: If user is inactive
    """
    # Add logic to check if user is active in database
    # For now, assume all authenticated users are active
    return current_user


def require_permission(required_permission: str):
    """
    Decorator to require specific permission

    Args:
        required_permission: Required permission string

    Returns:
        FastAPI dependency
    """
    async def permission_checker(
        current_user: Dict = Depends(get_current_user)
    ) -> Dict[str, Any]:
        """Check if user has required permission"""
        user_permissions = current_user.get('permissions', [])

        if required_permission not in user_permissions:
            logger.warning(
                f"Permission denied: user {current_user.get('sub')} "
                f"lacks permission {required_permission}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {required_permission} required"
            )

        return current_user

    return permission_checker


def require_role(required_role: str):
    """
    Decorator to require specific role

    Args:
        required_role: Required role string

    Returns:
        FastAPI dependency
    """
    async def role_checker(
        current_user: Dict = Depends(get_current_user)
    ) -> Dict[str, Any]:
        """Check if user has required role"""
        user_roles = current_user.get('roles', [])

        if required_role not in user_roles and 'admin' not in user_roles:
            logger.warning(
                f"Access denied: user {current_user.get('sub')} "
                f"lacks role {required_role}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: {required_role} role required"
            )

        return current_user

    return role_checker