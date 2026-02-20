from __future__ import annotations

"""
Service Schemas

Pydantic models for service data
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime


class ServiceResponse(BaseModel):
    """Service response"""

    id: int = Field(..., description="Service ID")
    asset_id: int = Field(..., description="Asset ID")
    port: Optional[int] = Field(None, description="Port number")
    protocol: Optional[str] = Field(None, description="Protocol (tcp/udp)")
    product: Optional[str] = Field(None, description="Product name")
    version: Optional[str] = Field(None, description="Product version")
    http_title: Optional[str] = Field(None, description="HTTP page title")
    http_status: Optional[int] = Field(None, description="HTTP status code")
    web_server: Optional[str] = Field(None, description="Web server (nginx, Apache, etc)")
    http_technologies: Optional[List[str]] = Field(None, description="Detected technologies")
    response_time_ms: Optional[int] = Field(None, description="Response time in milliseconds")
    content_length: Optional[int] = Field(None, description="Content length in bytes")
    redirect_url: Optional[str] = Field(None, description="Redirect URL if any")
    has_tls: bool = Field(default=False, description="Has TLS/SSL")
    tls_version: Optional[str] = Field(None, description="TLS version")
    first_seen: datetime = Field(..., description="First seen timestamp")
    last_seen: datetime = Field(..., description="Last seen timestamp")
    enriched_at: Optional[datetime] = Field(None, description="Last enrichment timestamp")
    enrichment_source: Optional[str] = Field(None, description="Enrichment source (httpx, naabu, tlsx)")

    @field_validator('http_technologies', mode='before')
    @classmethod
    def extract_technologies(cls, v: Union[Dict, List, None]) -> Optional[List[str]]:
        """
        Extract technologies from httpx JSON format

        httpx stores technologies as: {"technologies": [...], "cdn": bool, "cdn_name": str}
        We need to extract just the list of technologies
        """
        if v is None:
            return None

        # If it's already a list, return as is
        if isinstance(v, list):
            return v

        # If it's a dict with 'technologies' key, extract the list
        if isinstance(v, dict) and 'technologies' in v:
            return v['technologies']

        return None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 456,
                "asset_id": 123,
                "port": 443,
                "protocol": "tcp",
                "product": "nginx",
                "version": "1.21.0",
                "http_title": "API Documentation",
                "http_status": 200,
                "web_server": "nginx",
                "http_technologies": ["PHP", "React", "jQuery"],
                "response_time_ms": 145,
                "content_length": 52480,
                "redirect_url": None,
                "has_tls": True,
                "tls_version": "TLSv1.3",
                "first_seen": "2024-01-01T00:00:00Z",
                "last_seen": "2024-01-15T12:00:00Z",
                "enriched_at": "2024-01-15T10:00:00Z",
                "enrichment_source": "httpx"
            }
        }
    )


class ServiceListRequest(BaseModel):
    """Service list filter parameters"""

    asset_id: Optional[int] = Field(None, description="Filter by asset ID")
    port: Optional[int] = Field(None, description="Filter by port")
    protocol: Optional[str] = Field(None, description="Filter by protocol")
    has_tls: Optional[bool] = Field(None, description="Filter by TLS status")
    product: Optional[str] = Field(None, description="Filter by product name")
    enrichment_source: Optional[str] = Field(None, description="Filter by enrichment source")
    search: Optional[str] = Field(None, description="Search in product, web_server, http_title")
    sort_by: Optional[str] = Field("last_seen", description="Sort field")
    sort_order: Optional[str] = Field("desc", description="Sort order (asc/desc)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "asset_id": 123,
                "port": 443,
                "has_tls": True,
                "product": "nginx",
                "sort_by": "last_seen",
                "sort_order": "desc"
            }
        }
    )


class TechnologyStackResponse(BaseModel):
    """Technology stack summary for a tenant"""

    technology: str = Field(..., description="Technology name")
    count: int = Field(..., description="Number of assets using this technology")
    versions: Dict[str, int] = Field(..., description="Version distribution")
    risk_level: Optional[str] = Field(None, description="Risk level (low, medium, high, critical)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "technology": "nginx",
                "count": 150,
                "versions": {
                    "1.21.0": 50,
                    "1.20.2": 75,
                    "1.19.6": 25
                },
                "risk_level": "medium"
            }
        }
    )


class PortDistributionResponse(BaseModel):
    """Port distribution statistics"""

    port: int = Field(..., description="Port number")
    count: int = Field(..., description="Number of services")
    protocols: List[str] = Field(..., description="Protocols detected")
    common_products: List[str] = Field(..., description="Common products on this port")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "port": 443,
                "count": 350,
                "protocols": ["tcp"],
                "common_products": ["nginx", "Apache", "IIS"]
            }
        }
    )
