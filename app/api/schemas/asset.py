from __future__ import annotations

"""
Asset Schemas

Pydantic models for asset management
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class AssetResponse(BaseModel):
    """Asset response"""

    id: int = Field(..., description="Asset ID")
    tenant_id: int = Field(..., description="Tenant ID")
    type: str = Field(..., description="Asset type")
    identifier: str = Field(..., description="Asset identifier (domain, IP, URL)")
    first_seen: datetime = Field(..., description="First seen timestamp")
    last_seen: datetime = Field(..., description="Last seen timestamp")
    risk_score: Optional[float] = Field(None, description="Risk score (0-100)")
    is_active: bool = Field(..., description="Active status")
    last_enriched_at: Optional[datetime] = Field(None, description="Last enrichment timestamp")
    enrichment_status: str = Field(..., description="Enrichment status")
    priority: str = Field(..., description="Asset priority")
    priority_updated_at: Optional[datetime] = Field(None, description="Priority update timestamp")
    priority_auto_calculated: bool = Field(..., description="Auto-calculated priority")

    # Counts for related data
    service_count: Optional[int] = Field(None, description="Number of services")
    certificate_count: Optional[int] = Field(None, description="Number of certificates")
    endpoint_count: Optional[int] = Field(None, description="Number of endpoints")
    finding_count: Optional[int] = Field(None, description="Number of findings")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 123,
                "tenant_id": 1,
                "type": "subdomain",
                "identifier": "api.example.com",
                "first_seen": "2024-01-01T00:00:00Z",
                "last_seen": "2024-01-15T12:00:00Z",
                "risk_score": 65.5,
                "is_active": True,
                "last_enriched_at": "2024-01-15T10:00:00Z",
                "enrichment_status": "enriched",
                "priority": "high",
                "priority_updated_at": "2024-01-15T08:00:00Z",
                "priority_auto_calculated": True,
                "service_count": 5,
                "certificate_count": 2,
                "endpoint_count": 150,
                "finding_count": 3
            }
        }
    )


class AssetCreate(BaseModel):
    """Create asset request"""

    type: str = Field(..., description="Asset type (domain, subdomain, ip, url)")
    identifier: str = Field(..., description="Asset identifier")
    priority: Optional[str] = Field("normal", description="Asset priority")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "subdomain",
                "identifier": "api.example.com",
                "priority": "high"
            }
        }
    )


class AssetUpdate(BaseModel):
    """Update asset request"""

    priority: Optional[str] = Field(None, description="Asset priority")
    is_active: Optional[bool] = Field(None, description="Active status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "priority": "critical",
                "is_active": True
            }
        }
    )


class AssetListRequest(BaseModel):
    """Asset list filter parameters"""

    asset_type: Optional[str] = Field(None, description="Filter by asset type")
    priority: Optional[str] = Field(None, description="Filter by priority")
    enrichment_status: Optional[str] = Field(None, description="Filter by enrichment status")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    search: Optional[str] = Field(None, description="Search in identifier")
    min_risk_score: Optional[float] = Field(None, description="Minimum risk score")
    max_risk_score: Optional[float] = Field(None, description="Maximum risk score")
    changed_since: Optional[datetime] = Field(None, description="Changed since timestamp")
    sort_by: Optional[str] = Field("last_seen", description="Sort field")
    sort_order: Optional[str] = Field("desc", description="Sort order (asc/desc)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "asset_type": "subdomain",
                "priority": "high",
                "enrichment_status": "enriched",
                "is_active": True,
                "search": "api",
                "min_risk_score": 50.0,
                "sort_by": "risk_score",
                "sort_order": "desc"
            }
        }
    )


class AssetDetailResponse(AssetResponse):
    """Detailed asset response with related data"""

    services: List[Any] = Field(default_factory=list, description="Associated services")
    certificates: List[Any] = Field(default_factory=list, description="Associated certificates")
    endpoints: List[Any] = Field(default_factory=list, description="Associated endpoints (limited)")
    findings: List[Any] = Field(default_factory=list, description="Associated findings")
    events: List[Any] = Field(default_factory=list, description="Recent events")

    model_config = ConfigDict(from_attributes=True)


class AssetTreeNode(BaseModel):
    """Asset tree node for hierarchical view"""

    id: int = Field(..., description="Asset ID")
    identifier: str = Field(..., description="Asset identifier")
    type: str = Field(..., description="Asset type")
    risk_score: Optional[float] = Field(None, description="Risk score")
    is_active: bool = Field(..., description="Active status")
    children: List["AssetTreeNode"] = Field(default_factory=list, description="Child assets")
    service_count: int = Field(default=0, description="Number of services")
    finding_count: int = Field(default=0, description="Number of findings")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "identifier": "example.com",
                "type": "domain",
                "risk_score": 45.0,
                "is_active": True,
                "service_count": 0,
                "finding_count": 0,
                "children": [
                    {
                        "id": 2,
                        "identifier": "api.example.com",
                        "type": "subdomain",
                        "risk_score": 65.5,
                        "is_active": True,
                        "service_count": 5,
                        "finding_count": 3,
                        "children": []
                    }
                ]
            }
        }
    )


class SeedCreate(BaseModel):
    """Create seed request"""

    type: str = Field(..., description="Seed type (domain, asn, ip_range, keyword)")
    value: str = Field(..., description="Seed value")
    enabled: bool = Field(default=True, description="Enabled status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "domain",
                "value": "example.com",
                "enabled": True
            }
        }
    )


class SeedResponse(BaseModel):
    """Seed response"""

    id: int = Field(..., description="Seed ID")
    tenant_id: int = Field(..., description="Tenant ID")
    type: str = Field(..., description="Seed type")
    value: str = Field(..., description="Seed value")
    enabled: bool = Field(..., description="Enabled status")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class BulkAssetCreate(BaseModel):
    """Bulk asset creation request"""

    assets: List[AssetCreate] = Field(..., description="List of assets to create")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assets": [
                    {"type": "domain", "identifier": "example.com"},
                    {"type": "subdomain", "identifier": "api.example.com"}
                ]
            }
        }
    )
