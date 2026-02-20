"""
API Schemas Package

Pydantic models for request validation and response serialization
"""

from .common import *
from .auth import *
from .tenant import *
from .asset import *
from .service import *
from .certificate import *
from .endpoint import *
from .finding import *

__all__ = [
    # Common
    "PaginatedResponse",
    "ErrorResponse",
    "SuccessResponse",

    # Auth
    "LoginRequest",
    "LoginResponse",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "TokenPayload",
    "UserResponse",
    "UserCreate",
    "UserUpdate",
    "ChangePasswordRequest",

    # Tenant
    "TenantResponse",
    "TenantCreate",
    "TenantUpdate",
    "TenantDashboard",
    "TenantStats",

    # Asset
    "AssetResponse",
    "AssetCreate",
    "AssetUpdate",
    "AssetListRequest",
    "AssetTreeNode",
    "SeedCreate",

    # Service
    "ServiceResponse",
    "ServiceListRequest",

    # Certificate
    "CertificateResponse",
    "CertificateListRequest",

    # Endpoint
    "EndpointResponse",
    "EndpointListRequest",

    # Finding
    "FindingResponse",
    "FindingListRequest",
    "FindingUpdate",
]
