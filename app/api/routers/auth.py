"""
Authentication Router

Handles user authentication, token management, and user operations
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.api.dependencies import get_db, get_current_user, require_admin
from app.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserResponse,
    UserCreate,
    UserUpdate,
    ChangePasswordRequest
)
from app.models.auth import User
from app.security.jwt_auth import jwt_manager
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens

    Returns:
        - Access token (30 minutes)
        - Refresh token (7 days)
        - User information

    Raises:
        - 401: Invalid credentials
        - 403: Account inactive
    """
    # Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user:
        logger.warning(f"Login attempt with non-existent email: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not user.verify_password(credentials.password):
        logger.warning(f"Failed login attempt for user: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if user is active
    if not user.is_active:
        logger.warning(f"Login attempt for inactive user: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Get user's first tenant (for multi-tenant support)
    # In production, you might want to handle multiple tenants differently
    tenant_id = 1  # Default tenant
    tenant_role = "user"  # Default role
    if user.tenant_memberships:
        tenant_id = user.tenant_memberships[0].tenant_id
        tenant_role = user.tenant_memberships[0].role  # Get actual tenant role

    # Determine user roles
    roles = [tenant_role]  # Use tenant role instead of hardcoded "user"
    if user.is_superuser:
        roles.append("admin")

    # Create tokens
    access_token = jwt_manager.create_access_token(
        subject=str(user.id),
        tenant_id=tenant_id,
        roles=roles
    )

    refresh_token = jwt_manager.create_refresh_token(
        subject=str(user.id),
        tenant_id=tenant_id
    )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    logger.info(f"User {user.email} logged in successfully")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(
    request: RefreshTokenRequest
):
    """
    Refresh access token using refresh token

    Returns new access and refresh tokens (token rotation)

    Raises:
        - 401: Invalid or expired refresh token
    """
    try:
        result = jwt_manager.refresh_access_token(request.refresh_token)

        logger.info("Token refreshed successfully")

        return RefreshTokenResponse(
            access_token=result['access_token'],
            refresh_token=result['refresh_token'],
            token_type=result['token_type'],
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to refresh token"
        )


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout user (revoke tokens)

    Note: Client should also discard tokens locally

    Returns:
        - Success message
    """
    # In production, you might want to implement token blacklisting
    # For now, tokens will expire naturally

    logger.info(f"User {current_user.email} logged out")

    return {
        "success": True,
        "message": "Logged out successfully"
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information

    Returns user profile based on JWT token

    Raises:
        - 401: Invalid or expired token
    """
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_current_user(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user profile

    Allows users to update their own information

    Raises:
        - 401: Invalid or expired token
        - 400: Invalid update data
    """
    # Apply updates
    if updates.email is not None:
        # Check if email is already in use
        existing = db.query(User).filter(
            User.email == updates.email,
            User.id != current_user.id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )

        current_user.email = updates.email

    if updates.full_name is not None:
        current_user.full_name = updates.full_name

    if updates.is_active is not None:
        # Users can't deactivate themselves
        if not updates.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account"
            )

    db.commit()
    db.refresh(current_user)

    logger.info(f"User {current_user.email} updated their profile")

    return UserResponse.model_validate(current_user)


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user password

    Requires current password for verification

    Raises:
        - 401: Invalid current password
        - 400: Invalid new password
    """
    # Verify current password
    if not current_user.verify_password(request.current_password):
        logger.warning(f"Failed password change attempt for user: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    # Update password
    current_user.hashed_password = User.hash_password(request.new_password)
    db.commit()

    logger.info(f"User {current_user.email} changed their password")

    return {
        "success": True,
        "message": "Password changed successfully"
    }


# Admin endpoints
@router.post("/users", response_model=UserResponse)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Create new user (admin only)

    Raises:
        - 403: Not admin
        - 400: Email or username already exists
    """
    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if username exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Create user
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=User.hash_password(user_data.password),
        full_name=user_data.full_name,
        is_superuser=user_data.is_superuser
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"Admin {admin.email} created user {user.email}")

    return UserResponse.model_validate(user)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    List all users (admin only)

    Raises:
        - 403: Not admin
    """
    users = db.query(User).offset(skip).limit(limit).all()

    return [UserResponse.model_validate(u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Get user by ID (admin only)

    Raises:
        - 403: Not admin
        - 404: User not found
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse.model_validate(user)
