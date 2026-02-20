"""
Authentication Schemas

Pydantic models for authentication and authorization
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import datetime


class LoginRequest(BaseModel):
    """Login request"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePassword123"
            }
        }
    )


class LoginResponse(BaseModel):
    """Login response with tokens"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: "UserResponse" = Field(..., description="User information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
                "user": {
                    "id": 1,
                    "email": "user@example.com",
                    "username": "user",
                    "full_name": "John Doe"
                }
            }
        }
    )


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str = Field(..., description="JWT refresh token")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    )


class RefreshTokenResponse(BaseModel):
    """Refresh token response"""

    access_token: str = Field(..., description="New JWT access token")
    refresh_token: str = Field(..., description="New JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }
    )


class TokenPayload(BaseModel):
    """JWT token payload"""

    sub: str = Field(..., description="Subject (user ID)")
    tenant_id: int = Field(..., description="Tenant ID")
    roles: List[str] = Field(..., description="User roles")
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(..., description="Issued at time")
    type: str = Field(..., description="Token type (access/refresh)")


class UserResponse(BaseModel):
    """User response"""

    id: int = Field(..., description="User ID")
    email: EmailStr = Field(..., description="Email address")
    username: str = Field(..., description="Username")
    full_name: Optional[str] = Field(None, description="Full name")
    is_active: bool = Field(..., description="Active status")
    is_superuser: bool = Field(..., description="Superuser status")
    created_at: datetime = Field(..., description="Account creation date")
    last_login: Optional[datetime] = Field(None, description="Last login date")

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Create user request"""

    email: EmailStr = Field(..., description="Email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=8, description="Password")
    full_name: Optional[str] = Field(None, description="Full name")
    is_superuser: bool = Field(default=False, description="Superuser status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "SecurePassword123",
                "full_name": "John Doe",
                "is_superuser": False
            }
        }
    )


class UserUpdate(BaseModel):
    """Update user request"""

    email: Optional[EmailStr] = Field(None, description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")
    is_active: Optional[bool] = Field(None, description="Active status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "updated@example.com",
                "full_name": "John Updated Doe",
                "is_active": True
            }
        }
    )


class ChangePasswordRequest(BaseModel):
    """Change password request"""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_password": "OldPassword123",
                "new_password": "NewSecurePassword456"
            }
        }
    )


# Rebuild models to resolve forward references
LoginResponse.model_rebuild()
RefreshTokenResponse.model_rebuild()
