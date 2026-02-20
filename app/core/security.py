"""
Production-grade security module for EASM Platform

Implements:
- RS256 JWT authentication (asymmetric keys for production)
- HS256 JWT for development (fallback)
- Password hashing with bcrypt (cost factor 12)
- API key generation and validation
- Token revocation via Redis
- Refresh token rotation

OWASP References:
- A02:2021 - Cryptographic Failures
- A07:2021 - Identification and Authentication Failures
"""

import secrets
import hmac
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

import jwt
from passlib.context import CryptContext
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import redis

from app.config import settings

logger = logging.getLogger(__name__)

# Password hashing context with bcrypt cost factor 12 (OWASP recommended)
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Cost factor for bcrypt (higher = slower but more secure)
)


class SecurityKeys:
    """
    Manage JWT signing keys (RSA for production, HMAC for development)

    Production: Uses RS256 with RSA key pairs (private key for signing, public for verification)
    Development: Uses HS256 with symmetric secret (fallback for easier setup)
    """

    def __init__(self):
        self.algorithm = settings.jwt_algorithm
        self.private_key = None
        self.public_key = None
        self.secret_key = None

        if self.algorithm.startswith('RS'):
            # RSA keys for production (asymmetric)
            self._load_or_generate_rsa_keys()
        else:
            # Symmetric secret for development (HS256)
            self.secret_key = settings.jwt_secret_key

    def _load_or_generate_rsa_keys(self):
        """Load or generate RSA key pair for JWT signing"""
        private_key_path = Path("keys/jwt_private.pem")
        public_key_path = Path("keys/jwt_public.pem")

        try:
            if private_key_path.exists() and public_key_path.exists():
                # Load existing keys
                with open(private_key_path, "rb") as f:
                    self.private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,
                        backend=default_backend()
                    )
                with open(public_key_path, "rb") as f:
                    self.public_key = serialization.load_pem_public_key(
                        f.read(),
                        backend=default_backend()
                    )
                logger.info("Loaded RSA keys from disk")
            else:
                # Generate new keys
                logger.warning("RSA keys not found, generating new keys")
                self._generate_rsa_keys(private_key_path, public_key_path)
        except Exception as e:
            logger.error(f"Failed to load RSA keys: {e}")
            # Fallback to HMAC
            logger.warning("Falling back to HS256 with symmetric secret")
            self.algorithm = "HS256"
            self.secret_key = settings.jwt_secret_key

    def _generate_rsa_keys(self, private_path: Path, public_path: Path):
        """Generate new RSA key pair"""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Generate public key
        public_key = private_key.public_key()

        # Save keys
        private_path.parent.mkdir(parents=True, exist_ok=True)

        with open(private_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

        with open(public_path, "wb") as f:
            f.write(public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))

        self.private_key = private_key
        self.public_key = public_key
        logger.info("Generated new RSA keys")

    def get_signing_key(self):
        """Get key for signing JWTs"""
        if self.algorithm.startswith('RS'):
            return self.private_key
        return self.secret_key

    def get_verification_key(self):
        """Get key for verifying JWTs"""
        if self.algorithm.startswith('RS'):
            return self.public_key
        return self.secret_key


# Global security keys instance
_security_keys = SecurityKeys()


def get_redis_client() -> redis.Redis:
    """Get Redis client for token revocation"""
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2
    )


# ===========================
# Password Security Functions
# ===========================

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt with cost factor 12

    Args:
        password: Plain text password

    Returns:
        Hashed password (bcrypt hash)

    Security:
        - Bcrypt automatically generates and stores salt
        - Cost factor 12 = ~250ms hashing time (OWASP recommended)
        - Resistant to rainbow table attacks
    """
    if not password:
        raise ValueError("Password cannot be empty")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against bcrypt hash

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash to compare against

    Returns:
        True if password matches, False otherwise

    Security:
        - Uses constant-time comparison to prevent timing attacks
        - Automatically handles salt extraction from hash
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.warning(f"Password verification failed: {e}")
        return False


# ===========================
# JWT Token Functions
# ===========================

def create_access_token(
    subject: str,
    tenant_id: int,
    roles: list[str] = None,
    scopes: list[str] = None,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create JWT access token

    Args:
        subject: User ID or identifier
        tenant_id: Tenant ID for multi-tenancy
        roles: User roles (admin, user, read-only)
        scopes: API scopes for fine-grained permissions
        expires_delta: Custom expiration time (default: 15 minutes)
        additional_claims: Additional JWT claims

    Returns:
        JWT token string

    Security:
        - Uses RS256 in production (asymmetric), HS256 in dev (symmetric)
        - Includes JTI (JWT ID) for token revocation
        - Short expiration time (15 min) to limit exposure
        - Stored in Redis for revocation capability

    OWASP: A07:2021 - Identification and Authentication Failures
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    expire = datetime.utcnow() + expires_delta
    jti = secrets.token_urlsafe(32)  # JWT ID for revocation

    payload = {
        "sub": str(subject),
        "tenant_id": tenant_id,
        "roles": roles or ["user"],
        "scopes": scopes or [],
        "exp": expire,
        "iat": datetime.utcnow(),
        "nbf": datetime.utcnow(),  # Not before
        "type": "access",
        "jti": jti,
    }

    if additional_claims:
        payload.update(additional_claims)

    # Sign token
    token = jwt.encode(
        payload,
        _security_keys.get_signing_key(),
        algorithm=_security_keys.algorithm
    )

    # Store in Redis for revocation capability
    try:
        redis_client = get_redis_client()
        redis_client.setex(
            f"jwt:active:{jti}",
            int(expires_delta.total_seconds()),
            subject
        )
        redis_client.close()
    except Exception as e:
        logger.error(f"Failed to store token in Redis: {e}")
        # Continue anyway - token will still work, just can't be revoked

    logger.info(f"Created access token for user {subject} (tenant {tenant_id}, expires in {expires_delta})")
    return token


def create_refresh_token(
    subject: str,
    tenant_id: int,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT refresh token for token rotation

    Args:
        subject: User ID or identifier
        tenant_id: Tenant ID
        expires_delta: Custom expiration time (default: 7 days)

    Returns:
        Refresh token string

    Security:
        - Longer expiration (7 days) for better UX
        - Single-use tokens with rotation (old token revoked on refresh)
        - Stored in Redis for revocation
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    expire = datetime.utcnow() + expires_delta
    jti = secrets.token_urlsafe(32)

    payload = {
        "sub": str(subject),
        "tenant_id": tenant_id,
        "exp": expire,
        "iat": datetime.utcnow(),
        "nbf": datetime.utcnow(),
        "type": "refresh",
        "jti": jti,
    }

    token = jwt.encode(
        payload,
        _security_keys.get_signing_key(),
        algorithm=_security_keys.algorithm
    )

    # Store refresh token in Redis
    try:
        redis_client = get_redis_client()
        redis_client.setex(
            f"jwt:refresh:{jti}",
            int(expires_delta.total_seconds()),
            subject
        )
        redis_client.close()
    except Exception as e:
        logger.error(f"Failed to store refresh token in Redis: {e}")

    logger.info(f"Created refresh token for user {subject} (tenant {tenant_id})")
    return token


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid
        ValueError: If token is revoked

    Security:
        - Verifies signature using public key (RS256) or secret (HS256)
        - Checks expiration, not-before, and issued-at claims
        - Verifies token hasn't been revoked (Redis check)
    """
    try:
        # Decode and verify token
        payload = jwt.decode(
            token,
            _security_keys.get_verification_key(),
            algorithms=[_security_keys.algorithm],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "require": ["exp", "iat", "sub"],
            }
        )

        # Check if token is revoked
        jti = payload.get('jti')
        if jti:
            token_type = payload.get('type', 'access')
            key = f"jwt:{token_type}:{jti}"

            try:
                redis_client = get_redis_client()
                exists = redis_client.exists(key)
                redis_client.close()

                if not exists:
                    logger.warning(f"Attempt to use revoked token: {jti}")
                    raise ValueError("Token has been revoked")
            except redis.RedisError as e:
                logger.error(f"Redis check failed during token verification: {e}")
                # Continue without revocation check if Redis is down

        logger.debug(f"Token verified for user {payload.get('sub')}")
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("Expired token attempt")
        raise
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise


def revoke_token(jti: str, token_type: str = "access"):
    """
    Revoke a token by its JTI (JWT ID)

    Args:
        jti: JWT ID from token payload
        token_type: Token type (access or refresh)

    Security:
        - Removes token from Redis whitelist
        - Future verification attempts will fail
    """
    try:
        redis_client = get_redis_client()
        key = f"jwt:{token_type}:{jti}"
        redis_client.delete(key)
        redis_client.close()
        logger.info(f"Revoked {token_type} token: {jti}")
    except Exception as e:
        logger.error(f"Failed to revoke token {jti}: {e}")
        raise


def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    """
    Create new access token from refresh token (token rotation)

    Args:
        refresh_token: Valid refresh token

    Returns:
        Dict with new access_token and refresh_token

    Security:
        - Revokes old refresh token (single-use)
        - Issues new refresh token (rotation)
        - Prevents token replay attacks

    Raises:
        jwt.InvalidTokenError: If refresh token is invalid
        ValueError: If refresh token is revoked or wrong type
    """
    # Decode refresh token
    payload = verify_token(refresh_token)

    # Verify it's a refresh token
    if payload.get('type') != 'refresh':
        raise ValueError("Invalid token type - expected refresh token")

    # Extract user info
    subject = payload['sub']
    tenant_id = payload['tenant_id']

    # Create new access token
    access_token = create_access_token(
        subject=subject,
        tenant_id=tenant_id,
        roles=payload.get('roles', ['user']),
        scopes=payload.get('scopes', [])
    )

    # Create new refresh token (rotation)
    new_refresh_token = create_refresh_token(
        subject=subject,
        tenant_id=tenant_id
    )

    # Revoke old refresh token
    old_jti = payload.get('jti')
    if old_jti:
        revoke_token(old_jti, 'refresh')

    return {
        'access_token': access_token,
        'refresh_token': new_refresh_token,
        'token_type': 'bearer'
    }


# ===========================
# API Key Functions
# ===========================

def generate_api_key(prefix: str = "easm") -> Tuple[str, str]:
    """
    Generate secure API key with prefix

    Args:
        prefix: Key prefix for identification (e.g., "easm", "test")

    Returns:
        Tuple of (api_key, api_key_hash)
        - api_key: The actual key to give to user (only shown once)
        - api_key_hash: Hash to store in database

    Format: {prefix}_{random_bytes}
    Example: easm_abc123def456...

    Security:
        - 256-bit random key (cryptographically secure)
        - Hash stored in DB (bcrypt), not plaintext
        - Prefix allows key rotation by version
    """
    # Generate 256-bit random key
    random_part = secrets.token_urlsafe(32)
    api_key = f"{prefix}_{random_part}"

    # Hash for storage (bcrypt)
    api_key_hash = hash_password(api_key)

    return api_key, api_key_hash


def verify_api_key(api_key: str, api_key_hash: str) -> bool:
    """
    Verify API key against stored hash

    Args:
        api_key: Plain API key from request
        api_key_hash: Bcrypt hash from database

    Returns:
        True if API key is valid

    Security:
        - Constant-time comparison (via bcrypt)
        - Prevents timing attacks
    """
    return verify_password(api_key, api_key_hash)


def generate_api_key_simple(length: int = 32) -> str:
    """
    Generate simple API key (legacy support)

    Args:
        length: Number of bytes for key

    Returns:
        URL-safe random string

    Note:
        Prefer generate_api_key() for new implementations.
        This is for backward compatibility.
    """
    return secrets.token_urlsafe(length)


# ===========================
# Cryptographic Utilities
# ===========================

def constant_time_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison

    Args:
        a: First string
        b: Second string

    Returns:
        True if strings are equal

    Security:
        - Prevents timing attacks
        - Use for comparing secrets, tokens, hashes
    """
    return hmac.compare_digest(a.encode(), b.encode())


def generate_random_token(nbytes: int = 32) -> str:
    """
    Generate cryptographically secure random token

    Args:
        nbytes: Number of random bytes

    Returns:
        URL-safe random string

    Use cases:
        - CSRF tokens
        - Password reset tokens
        - Email verification tokens
        - Session identifiers
    """
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """
    Hash token for storage (SHA-256)

    Args:
        token: Token to hash

    Returns:
        Hex-encoded SHA-256 hash

    Use case:
        - Store hashed version of reset tokens in DB
        - Prevents token leakage if DB is compromised
    """
    return hashlib.sha256(token.encode()).hexdigest()


# ===========================
# Initialization
# ===========================

def initialize_security():
    """
    Initialize security subsystem

    - Loads/generates RSA keys
    - Validates configuration
    - Tests Redis connection
    """
    logger.info(f"Initializing security subsystem with algorithm: {_security_keys.algorithm}")

    # Test Redis connection
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        redis_client.close()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        logger.warning("Token revocation will not work without Redis")

    logger.info("Security subsystem initialized")


# Initialize on module load
initialize_security()
