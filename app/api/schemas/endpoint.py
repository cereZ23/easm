from __future__ import annotations

"""
Endpoint Schemas

Pydantic models for web endpoints discovered by Katana
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class EndpointResponse(BaseModel):
    """Endpoint response"""

    id: int = Field(..., description="Endpoint ID")
    asset_id: int = Field(..., description="Asset ID")
    url: str = Field(..., description="Full URL")
    path: Optional[str] = Field(None, description="URL path")
    method: str = Field(default="GET", description="HTTP method")
    query_params: Optional[Dict[str, Any]] = Field(None, description="Query parameters")
    body_params: Optional[Dict[str, Any]] = Field(None, description="Body parameters")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    content_type: Optional[str] = Field(None, description="Content type")
    content_length: Optional[int] = Field(None, description="Content length in bytes")
    endpoint_type: Optional[str] = Field(None, description="Endpoint type (api, form, file, etc)")
    is_external: bool = Field(default=False, description="Is external link")
    is_api: bool = Field(default=False, description="Appears to be API endpoint")
    source_url: Optional[str] = Field(None, description="Source page where found")
    depth: int = Field(default=0, description="Crawl depth from seed")
    first_seen: datetime = Field(..., description="First seen timestamp")
    last_seen: datetime = Field(..., description="Last seen timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 12345,
                "asset_id": 123,
                "url": "https://api.example.com/v1/users",
                "path": "/v1/users",
                "method": "GET",
                "query_params": {"page": "1", "limit": "10"},
                "body_params": None,
                "status_code": 200,
                "content_type": "application/json",
                "content_length": 2048,
                "endpoint_type": "api",
                "is_external": False,
                "is_api": True,
                "source_url": "https://api.example.com/",
                "depth": 1,
                "first_seen": "2024-01-10T00:00:00Z",
                "last_seen": "2024-01-15T12:00:00Z"
            }
        }
    )


class EndpointListRequest(BaseModel):
    """Endpoint list filter parameters"""

    asset_id: Optional[int] = Field(None, description="Filter by asset ID")
    method: Optional[str] = Field(None, description="Filter by HTTP method")
    endpoint_type: Optional[str] = Field(None, description="Filter by endpoint type")
    is_api: Optional[bool] = Field(None, description="Filter API endpoints only")
    is_external: Optional[bool] = Field(None, description="Filter external links")
    status_code: Optional[int] = Field(None, description="Filter by status code")
    search: Optional[str] = Field(None, description="Search in URL, path")
    max_depth: Optional[int] = Field(None, description="Maximum crawl depth")
    sort_by: Optional[str] = Field("last_seen", description="Sort field")
    sort_order: Optional[str] = Field("desc", description="Sort order (asc/desc)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "asset_id": 123,
                "endpoint_type": "api",
                "is_api": True,
                "method": "GET",
                "sort_by": "last_seen",
                "sort_order": "desc"
            }
        }
    )


class EndpointStatsResponse(BaseModel):
    """Endpoint statistics"""

    total_endpoints: int = Field(..., description="Total number of endpoints")
    by_type: Dict[str, int] = Field(..., description="Distribution by endpoint type")
    by_method: Dict[str, int] = Field(..., description="Distribution by HTTP method")
    api_endpoints: int = Field(..., description="Number of API endpoints")
    external_links: int = Field(..., description="Number of external links")
    sensitive_endpoints: int = Field(..., description="Number of potentially sensitive endpoints")
    average_depth: float = Field(..., description="Average crawl depth")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_endpoints": 12000,
                "by_type": {
                    "api": 2500,
                    "form": 450,
                    "static": 8000,
                    "file": 350,
                    "redirect": 500,
                    "external": 200
                },
                "by_method": {
                    "GET": 10500,
                    "POST": 1200,
                    "PUT": 150,
                    "DELETE": 100,
                    "PATCH": 50
                },
                "api_endpoints": 2500,
                "external_links": 200,
                "sensitive_endpoints": 85,
                "average_depth": 2.3
            }
        }
    )


class APIEndpointSummary(BaseModel):
    """API endpoint summary for discovery"""

    path: str = Field(..., description="API path pattern")
    methods: List[str] = Field(..., description="Supported HTTP methods")
    count: int = Field(..., description="Number of endpoints matching this pattern")
    example_url: str = Field(..., description="Example full URL")
    requires_auth: Optional[bool] = Field(None, description="Appears to require authentication")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "path": "/api/v1/users",
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "count": 8,
                "example_url": "https://api.example.com/v1/users",
                "requires_auth": True
            }
        }
    )
