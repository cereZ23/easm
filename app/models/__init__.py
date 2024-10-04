"""
Models package - imports all models to ensure they are registered with SQLAlchemy
"""

# Import Base first
from app.models.database import Base

# Import all models to register them with SQLAlchemy
from app.models.database import (
    Tenant,
    Asset,
    AssetType,
    Service,
    Finding,
    FindingStatus,
    FindingSeverity,
    Event,
    EventKind,
    Seed,
)

from app.models.auth import (
    User,
    TenantMembership,
    APIKey,
)

__all__ = [
    'Base',
    'Tenant',
    'Asset',
    'AssetType',
    'Service',
    'Finding',
    'FindingStatus',
    'FindingSeverity',
    'Event',
    'EventKind',
    'Seed',
    'User',
    'TenantMembership',
    'APIKey',
]
