"""
API Routers Package

Sprint 3 - REST API endpoint routers
"""

from .auth import router as auth_router
from .tenants import router as tenants_router
from .assets import router as assets_router
from .services import router as services_router
from .certificates import router as certificates_router
from .endpoints import router as endpoints_router
from .findings import router as findings_router
from .onboarding import router as onboarding_router
from .scanning import router as scanning_router

__all__ = [
    "auth_router",
    "tenants_router",
    "assets_router",
    "services_router",
    "certificates_router",
    "endpoints_router",
    "findings_router",
    "onboarding_router",
    "scanning_router",
]
