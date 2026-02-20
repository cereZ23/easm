"""
FastAPI Dependencies

Common dependencies for authentication, database sessions, pagination, and multi-tenant isolation.
"""

from typing import Optional, Dict, Any, Generator
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import logging

from app.database import SessionLocal
from app.security.jwt_auth import jwt_manager
from app.models.auth import User, TenantMembership

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer()


# Database session dependency
def get_db() -> Generator[Session, None, None]:
    """
    Dependency to provide database session

    Yields:
        Database session

    Ensures:
        - Session is properly closed after request
        - Transactions are committed or rolled back
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Authentication dependencies
async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Get current user payload from JWT token

    Args:
        credentials: HTTP authorization credentials

    Returns:
        User payload from JWT token

    Raises:
        HTTPException: If token is invalid
    """
    return jwt_manager.verify_token(credentials)


async def get_current_user(
    payload: Dict[str, Any] = Depends(get_current_user_payload),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from database

    Args:
        payload: JWT token payload
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If user not found or inactive
    """
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID"
        )

    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (alias for compatibility)

    Args:
        current_user: Current user

    Returns:
        User object
    """
    return current_user


# Tenant access control
async def verify_tenant_access(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    required_permission: str = "read"
) -> TenantMembership:
    """
    Verify user has access to tenant with required permission

    Args:
        tenant_id: Tenant ID to access
        current_user: Current authenticated user
        db: Database session
        required_permission: Required permission (read, write, admin)

    Returns:
        TenantMembership object

    Raises:
        HTTPException: If user doesn't have access or permission
    """
    # Superusers have access to all tenants
    if current_user.is_superuser:
        # Return a mock membership for superusers
        mock_membership = TenantMembership(
            user_id=current_user.id,
            tenant_id=tenant_id,
            role="admin"
        )
        return mock_membership

    # Check tenant membership
    membership = db.query(TenantMembership).filter(
        TenantMembership.user_id == current_user.id,
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.is_active == True
    ).first()

    if not membership:
        logger.warning(
            f"User {current_user.id} attempted to access tenant {tenant_id} without membership"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: not a member of this tenant"
        )

    # Check permission
    if not membership.has_permission(required_permission):
        logger.warning(
            f"User {current_user.id} lacks {required_permission} permission for tenant {tenant_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {required_permission} permission required"
        )

    return membership


def require_tenant_permission(permission: str = "read"):
    """
    Factory to create tenant permission dependency

    Args:
        permission: Required permission level

    Returns:
        Dependency function
    """
    async def dependency(
        tenant_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> TenantMembership:
        return await verify_tenant_access(tenant_id, current_user, db, permission)

    return dependency


# Pagination
class PaginationParams:
    """
    Standard pagination parameters

    Provides consistent pagination across all endpoints
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (starts at 1)"),
        page_size: int = Query(50, ge=1, le=1000, description="Items per page")
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size

    @property
    def limit(self) -> int:
        """Get limit for query"""
        return self.page_size

    def paginate_query(self, query):
        """
        Apply pagination to SQLAlchemy query

        Args:
            query: SQLAlchemy query

        Returns:
            Paginated query
        """
        return query.offset(self.offset).limit(self.limit)


# Search and filter helpers
class SearchParams:
    """
    Standard search parameters
    """

    def __init__(
        self,
        q: Optional[str] = Query(None, description="Search query"),
        sort_by: Optional[str] = Query(None, description="Sort field"),
        sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order")
    ):
        self.query = q
        self.sort_by = sort_by
        self.sort_order = sort_order


# Admin role requirement
async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to be superuser/admin

    Args:
        current_user: Current authenticated user

    Returns:
        User object

    Raises:
        HTTPException: If user is not admin
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return current_user


# Rate limiting (placeholder for future implementation)
async def rate_limit_dependency():
    """
    Rate limiting dependency

    TODO: Implement actual rate limiting with Redis
    For now, this is a placeholder
    """
    pass
