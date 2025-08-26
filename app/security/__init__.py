"""
Security module for EASM platform

Provides comprehensive security controls including:
- JWT authentication and authorization
- API security middleware
- Multi-tenant isolation
- Threat detection
"""

from .jwt_auth import JWTManager, get_current_user, require_permission
from .api_security import APISecurityMiddleware, setup_security
from .multitenancy import TenantIsolation, get_tenant_context

__all__ = [
    'JWTManager',
    'get_current_user',
    'require_permission',
    'APISecurityMiddleware',
    'setup_security',
    'TenantIsolation',
    'get_tenant_context',
]