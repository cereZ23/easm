"""
Authentication utilities for JWT tokens and API key validation

Provides secure token generation, validation, and user authentication.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
import hashlib
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models.auth import User, APIKey, TenantMembership


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails"""
    pass


def create_access_token(
    user_id: int,
    email: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token

    Args:
        user_id: User ID
        email: User email
        expires_delta: Optional custom expiration time

    Returns:
        JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def create_refresh_token(user_id: int, email: str) -> str:
    """
    Create JWT refresh token

    Args:
        user_id: User ID
        email: User email

    Returns:
        JWT refresh token string
    """
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)

    to_encode = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        AuthenticationError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def get_current_user(db: Session, token: str) -> User:
    """
    Get current user from JWT token

    Args:
        db: Database session
        token: JWT token

    Returns:
        User object

    Raises:
        AuthenticationError: If authentication fails
    """
    try:
        payload = verify_token(token)

        # Verify token type
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")

        user_id = int(payload.get("sub"))
        if not user_id:
            raise AuthenticationError("Invalid token payload")

        # Get user from database
        user = db.query(User).filter_by(id=user_id, is_active=True).first()
        if not user:
            raise AuthenticationError("User not found or inactive")

        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()

        return user

    except (JWTError, ValueError) as e:
        raise AuthenticationError(f"Authentication failed: {str(e)}")


def generate_api_key() -> str:
    """
    Generate a secure API key

    Returns:
        API key string (64 characters)
    """
    # Generate 32 random bytes and convert to hex (64 characters)
    return secrets.token_hex(32)


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage

    Args:
        api_key: Plain API key

    Returns:
        Hashed API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(db: Session, api_key: str) -> tuple[User, int]:
    """
    Verify API key and return associated user and tenant

    Args:
        db: Database session
        api_key: API key string

    Returns:
        Tuple of (User, tenant_id)

    Raises:
        AuthenticationError: If API key is invalid
    """
    # Hash the provided key
    hashed_key = hash_api_key(api_key)

    # Find API key in database
    api_key_obj = db.query(APIKey).filter_by(
        key=hashed_key,
        is_active=True
    ).first()

    if not api_key_obj:
        raise AuthenticationError("Invalid API key")

    # Check if expired
    if api_key_obj.is_expired():
        raise AuthenticationError("API key expired")

    # Update last used timestamp
    api_key_obj.last_used_at = datetime.utcnow()
    db.commit()

    # Get associated user
    user = db.query(User).filter_by(id=api_key_obj.user_id, is_active=True).first()
    if not user:
        raise AuthenticationError("User not found or inactive")

    return user, api_key_obj.tenant_id


def check_tenant_access(
    db: Session,
    user: User,
    tenant_id: int,
    required_permission: str = "read"
) -> bool:
    """
    Check if user has access to a tenant with required permission

    Args:
        db: Database session
        user: User object
        tenant_id: Tenant ID to check access for
        required_permission: Required permission level (read, write, admin)

    Returns:
        True if user has access

    Raises:
        AuthorizationError: If user doesn't have access
    """
    # Superusers have access to all tenants
    if user.is_superuser:
        return True

    # Check tenant membership
    membership = db.query(TenantMembership).filter_by(
        user_id=user.id,
        tenant_id=tenant_id,
        is_active=True
    ).first()

    if not membership:
        raise AuthorizationError(f"User does not have access to tenant {tenant_id}")

    # Check permission level
    if not membership.has_permission(required_permission):
        raise AuthorizationError(
            f"User does not have '{required_permission}' permission for tenant {tenant_id}"
        )

    return True


def authenticate_user(db: Session, email: str, password: str) -> User:
    """
    Authenticate user with email and password

    Args:
        db: Database session
        email: User email
        password: Plain text password

    Returns:
        User object

    Raises:
        AuthenticationError: If authentication fails
    """
    user = db.query(User).filter_by(email=email, is_active=True).first()

    if not user:
        raise AuthenticationError("Invalid credentials")

    if not user.verify_password(password):
        raise AuthenticationError("Invalid credentials")

    return user


def create_user(
    db: Session,
    email: str,
    username: str,
    password: str,
    full_name: Optional[str] = None,
    is_superuser: bool = False
) -> User:
    """
    Create a new user

    Args:
        db: Database session
        email: User email
        username: Username
        password: Plain text password
        full_name: Optional full name
        is_superuser: Whether user is a superuser

    Returns:
        Created user

    Raises:
        ValueError: If user already exists
    """
    # Check if user exists
    existing = db.query(User).filter(
        (User.email == email) | (User.username == username)
    ).first()

    if existing:
        raise ValueError("User with this email or username already exists")

    # Create user
    user = User(
        email=email,
        username=username,
        hashed_password=User.hash_password(password),
        full_name=full_name,
        is_superuser=is_superuser
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user
