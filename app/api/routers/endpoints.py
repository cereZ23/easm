"""
Endpoints Router

Handles web endpoints discovered by Katana crawler
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List
import logging

from app.api.dependencies import get_db, verify_tenant_access, PaginationParams
from app.api.schemas.endpoint import (
    EndpointResponse,
    EndpointListRequest,
    EndpointStatsResponse,
    APIEndpointSummary
)
from app.api.schemas.common import PaginatedResponse
from app.models.database import Asset
from app.models.enrichment import Endpoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/endpoints", tags=["Endpoints"])


@router.get("", response_model=PaginatedResponse[EndpointResponse])
def list_endpoints(
    tenant_id: int,
    asset_id: Optional[int] = Query(None),
    method: Optional[str] = Query(None),
    endpoint_type: Optional[str] = Query(None),
    is_api: Optional[bool] = Query(None),
    is_external: Optional[bool] = Query(None),
    status_code: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    max_depth: Optional[int] = Query(None),
    sort_by: str = Query("last_seen"),
    sort_order: str = Query("desc"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    List endpoints with filtering

    Endpoints are URLs discovered through web crawling

    Useful for:
    - API discovery
    - Attack surface mapping
    - Form analysis
    - Sensitive path detection
    """
    # Build query with tenant isolation
    query = db.query(Endpoint).join(Asset).filter(Asset.tenant_id == tenant_id)

    # Apply filters
    if asset_id:
        query = query.filter(Endpoint.asset_id == asset_id)

    if method:
        query = query.filter(Endpoint.method == method.upper())

    if endpoint_type:
        query = query.filter(Endpoint.endpoint_type == endpoint_type)

    if is_api is not None:
        query = query.filter(Endpoint.is_api == is_api)

    if is_external is not None:
        query = query.filter(Endpoint.is_external == is_external)

    if status_code:
        query = query.filter(Endpoint.status_code == status_code)

    if max_depth is not None:
        query = query.filter(Endpoint.depth <= max_depth)

    if search:
        query = query.filter(
            or_(
                Endpoint.url.ilike(f"%{search}%"),
                Endpoint.path.ilike(f"%{search}%")
            )
        )

    # Get total count
    total = query.count()

    # Apply sorting
    sort_column = getattr(Endpoint, sort_by, Endpoint.last_seen)
    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    query = pagination.paginate_query(query)

    endpoints = query.all()

    return PaginatedResponse(
        items=[EndpointResponse.model_validate(e) for e in endpoints],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{endpoint_id}", response_model=EndpointResponse)
def get_endpoint(
    tenant_id: int,
    endpoint_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get endpoint by ID

    Returns full endpoint details

    Raises:
        - 404: Endpoint not found
    """
    endpoint = db.query(Endpoint).join(Asset).filter(
        Endpoint.id == endpoint_id,
        Asset.tenant_id == tenant_id
    ).first()

    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found"
        )

    return EndpointResponse.model_validate(endpoint)


@router.get("/stats", response_model=EndpointStatsResponse)
def get_endpoint_stats(
    tenant_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get endpoint statistics

    Aggregated metrics:
    - Total endpoints
    - Distribution by type/method
    - API endpoint count
    - External links
    - Sensitive endpoints
    """
    # Total endpoints
    total = db.query(Endpoint).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).count()

    # Distribution by type
    by_type = {}
    types = db.query(
        Endpoint.endpoint_type,
        func.count(Endpoint.id).label('count')
    ).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Endpoint.endpoint_type.isnot(None)
    ).group_by(Endpoint.endpoint_type).all()

    for endpoint_type, count in types:
        by_type[endpoint_type] = count

    # Distribution by method
    by_method = {}
    methods = db.query(
        Endpoint.method,
        func.count(Endpoint.id).label('count')
    ).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).group_by(Endpoint.method).all()

    for method, count in methods:
        by_method[method] = count

    # API endpoints
    api_endpoints = db.query(Endpoint).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Endpoint.is_api == True
    ).count()

    # External links
    external_links = db.query(Endpoint).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Endpoint.is_external == True
    ).count()

    # Sensitive endpoints (check URL for sensitive keywords)
    # This is done in the property, so we need to fetch and check
    all_endpoints = db.query(Endpoint).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).all()

    sensitive_count = sum(1 for e in all_endpoints if e.is_sensitive_endpoint)

    # Average depth
    avg_depth = db.query(func.avg(Endpoint.depth)).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).scalar() or 0.0

    return EndpointStatsResponse(
        total_endpoints=total,
        by_type=by_type,
        by_method=by_method,
        api_endpoints=api_endpoints,
        external_links=external_links,
        sensitive_endpoints=sensitive_count,
        average_depth=round(float(avg_depth), 2)
    )


@router.get("/api/summary", response_model=List[APIEndpointSummary])
def get_api_summary(
    tenant_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get API endpoint summary

    Groups API endpoints by path pattern

    Useful for API inventory and documentation

    Returns:
        List of API path patterns with methods and examples
    """
    # Get all API endpoints
    api_endpoints = db.query(Endpoint).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Endpoint.is_api == True
    ).all()

    # Group by path pattern
    path_patterns = {}

    for endpoint in api_endpoints:
        # Simple pattern extraction (remove IDs, UUIDs, etc)
        # In production, use more sophisticated pattern detection
        path = endpoint.path or endpoint.url

        # Group similar paths
        # This is a simplified version
        if path not in path_patterns:
            path_patterns[path] = {
                'path': path,
                'methods': set(),
                'count': 0,
                'example_url': endpoint.url,
                'requires_auth': None
            }

        path_patterns[path]['methods'].add(endpoint.method)
        path_patterns[path]['count'] += 1

    # Convert to response format
    return [
        APIEndpointSummary(
            path=data['path'],
            methods=sorted(list(data['methods'])),
            count=data['count'],
            example_url=data['example_url'],
            requires_auth=data['requires_auth']
        )
        for data in sorted(path_patterns.values(), key=lambda x: x['count'], reverse=True)[:100]
    ]
