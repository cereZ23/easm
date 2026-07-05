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

# Enrichment models must be imported here so their mappers are registered
# before SQLAlchemy resolves the string-based Asset.certificates /
# Asset.endpoints relationships.
from app.models.enrichment import (
    Certificate,
    Endpoint,
    AssetPriority,
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
    'Certificate',
    'Endpoint',
    'AssetPriority',
]
