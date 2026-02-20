from __future__ import annotations

"""
Tenant Schemas

Pydantic models for tenant management
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class TenantResponse(BaseModel):
    """Tenant response"""

    id: int = Field(..., description="Tenant ID")
    name: str = Field(..., description="Tenant name")
    slug: str = Field(..., description="Tenant slug")
    contact_policy: Optional[str] = Field(None, description="Contact policy")
    created_at: datetime = Field(..., description="Creation date")
    updated_at: datetime = Field(..., description="Last update date")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Acme Corporation",
                "slug": "acme-corp",
                "contact_policy": "Contact security@acme.com for vulnerabilities",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }
    )


class TenantCreate(BaseModel):
    """Create tenant request"""

    name: str = Field(..., min_length=1, max_length=255, description="Tenant name")
    slug: str = Field(..., min_length=1, max_length=100, description="Tenant slug")
    contact_policy: Optional[str] = Field(None, description="Contact policy")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Acme Corporation",
                "slug": "acme-corp",
                "contact_policy": "Contact security@acme.com for vulnerabilities"
            }
        }
    )


class TenantUpdate(BaseModel):
    """Update tenant request"""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Tenant name")
    contact_policy: Optional[str] = Field(None, description="Contact policy")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Acme Corporation Updated",
                "contact_policy": "New contact policy"
            }
        }
    )


class TenantStats(BaseModel):
    """Tenant statistics"""

    total_assets: int = Field(..., description="Total number of assets")
    assets_by_type: Dict[str, int] = Field(..., description="Assets grouped by type")
    total_services: int = Field(..., description="Total number of services")
    total_certificates: int = Field(..., description="Total number of certificates")
    total_endpoints: int = Field(..., description="Total number of endpoints")
    total_findings: int = Field(..., description="Total number of findings")
    findings_by_severity: Dict[str, int] = Field(..., description="Findings grouped by severity")
    open_findings: int = Field(..., description="Number of open findings")
    critical_findings: int = Field(..., description="Number of critical findings")
    high_findings: int = Field(..., description="Number of high severity findings")
    expiring_certificates: int = Field(..., description="Number of certificates expiring soon")
    average_risk_score: float = Field(..., description="Average risk score across assets")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_assets": 1250,
                "assets_by_type": {
                    "domain": 50,
                    "subdomain": 800,
                    "ip": 300,
                    "url": 100
                },
                "total_services": 3500,
                "total_certificates": 450,
                "total_endpoints": 12000,
                "total_findings": 235,
                "findings_by_severity": {
                    "critical": 5,
                    "high": 25,
                    "medium": 80,
                    "low": 100,
                    "info": 25
                },
                "open_findings": 180,
                "critical_findings": 5,
                "high_findings": 25,
                "expiring_certificates": 12,
                "average_risk_score": 42.5
            }
        }
    )


class RecentActivity(BaseModel):
    """Recent activity item"""

    id: int = Field(..., description="Activity ID")
    type: str = Field(..., description="Activity type")
    description: str = Field(..., description="Activity description")
    timestamp: datetime = Field(..., description="Activity timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "type": "new_asset",
                "description": "New subdomain discovered: api.example.com",
                "timestamp": "2024-01-15T10:30:00Z",
                "metadata": {"asset_id": 123, "asset_type": "subdomain"}
            }
        }
    )


class TenantDashboard(BaseModel):
    """Tenant dashboard data"""

    tenant: TenantResponse = Field(..., description="Tenant information")
    stats: TenantStats = Field(..., description="Statistics")
    recent_activity: list[RecentActivity] = Field(..., description="Recent activity")
    trending_assets: list[Any] = Field(default_factory=list, description="Trending assets")
    risk_distribution: Dict[str, int] = Field(..., description="Risk score distribution")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tenant": {
                    "id": 1,
                    "name": "Acme Corporation",
                    "slug": "acme-corp"
                },
                "stats": {
                    "total_assets": 1250,
                    "total_findings": 235
                },
                "recent_activity": [],
                "trending_assets": [],
                "risk_distribution": {
                    "critical": 15,
                    "high": 125,
                    "medium": 650,
                    "low": 460
                }
            }
        }
    )
