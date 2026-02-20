"""
Authentication and authorization models

Provides User and APIKey models for multi-tenant access control.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from passlib.context import CryptContext

from app.models.database import Base

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    """User model for authentication"""

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)

    # Relationships
    tenant_memberships = relationship("TenantMembership", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"

    def verify_password(self, password: str) -> bool:
        """
        Verify password against hash

        Args:
            password: Plain text password

        Returns:
            True if password matches
        """
        return pwd_context.verify(password, self.hashed_password)

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        return pwd_context.hash(password)


class TenantMembership(Base):
    """
    Association between users and tenants with role-based access

    Supports multi-tenancy where users can belong to multiple tenants
    with different roles.
    """

    __tablename__ = 'tenant_memberships'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    role = Column(String(50), nullable=False)  # admin, member, viewer
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="tenant_memberships")
    tenant = relationship("Tenant", back_populates="memberships")

    __table_args__ = (
        Index('idx_user_tenant', 'user_id', 'tenant_id', unique=True),
        Index('idx_tenant_role', 'tenant_id', 'role'),
    )

    def __repr__(self):
        return f"<TenantMembership(user_id={self.user_id}, tenant_id={self.tenant_id}, role='{self.role}')>"

    def has_permission(self, permission: str) -> bool:
        """
        Check if membership has a specific permission

        Args:
            permission: Permission to check (read, write, admin)

        Returns:
            True if user has permission
        """
        role_permissions = {
            'viewer': ['read'],
            'member': ['read', 'write'],
            'admin': ['read', 'write', 'admin'],
            'owner': ['read', 'write', 'admin']  # Owner has all permissions
        }
        return permission in role_permissions.get(self.role, [])


class APIKey(Base):
    """
    API Key model for programmatic access

    Supports tenant-scoped API keys for automation and integrations.
    """

    __tablename__ = 'api_keys'

    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    scopes = Column(Text)  # JSON array of scopes
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime)
    last_used_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="api_keys")
    tenant = relationship("Tenant", back_populates="api_key_objects")

    __table_args__ = (
        Index('idx_tenant_active', 'tenant_id', 'is_active'),
    )

    def __repr__(self):
        return f"<APIKey(id={self.id}, name='{self.name}', tenant_id={self.tenant_id})>"

    def is_expired(self) -> bool:
        """Check if API key is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if API key is valid (active and not expired)"""
        return self.is_active and not self.is_expired()
