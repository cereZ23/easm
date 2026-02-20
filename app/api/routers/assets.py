"""
Assets Router

Handles asset management, discovery, and hierarchy
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional
from datetime import datetime
import logging

from app.api.dependencies import (
    get_db,
    verify_tenant_access,
    PaginationParams
)
from app.api.schemas.asset import (
    AssetResponse,
    AssetCreate,
    AssetUpdate,
    AssetListRequest,
    AssetDetailResponse,
    AssetTreeNode,
    SeedCreate,
    SeedResponse,
    BulkAssetCreate
)
from app.api.schemas.common import PaginatedResponse, BulkOperationResult
from app.models.database import Asset, AssetType, Seed
from app.repositories.asset_repository import AssetRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/assets", tags=["Assets"])


@router.get("", response_model=PaginatedResponse[AssetResponse])
def list_assets(
    tenant_id: int,
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    enrichment_status: Optional[str] = Query(None, description="Filter by enrichment status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in identifier"),
    min_risk_score: Optional[float] = Query(None, description="Minimum risk score"),
    max_risk_score: Optional[float] = Query(None, description="Maximum risk score"),
    changed_since: Optional[datetime] = Query(None, description="Changed since timestamp"),
    sort_by: str = Query("last_seen", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    List assets with filtering, search, and pagination

    Supports:
    - Type filtering (domain, subdomain, ip, url)
    - Priority filtering (critical, high, normal, low)
    - Risk score range
    - Search by identifier
    - Changed since timestamp (for delta queries)
    - Sorting and pagination

    Returns:
        Paginated list of assets
    """
    # Build query
    query = db.query(Asset).filter(Asset.tenant_id == tenant_id)

    # Apply filters
    if asset_type:
        try:
            query = query.filter(Asset.type == AssetType(asset_type))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid asset type: {asset_type}"
            )

    if priority:
        query = query.filter(Asset.priority == priority)

    if enrichment_status:
        query = query.filter(Asset.enrichment_status == enrichment_status)

    if is_active is not None:
        query = query.filter(Asset.is_active == is_active)

    if search:
        query = query.filter(Asset.identifier.ilike(f"%{search}%"))

    if min_risk_score is not None:
        query = query.filter(Asset.risk_score >= min_risk_score)

    if max_risk_score is not None:
        query = query.filter(Asset.risk_score <= max_risk_score)

    if changed_since:
        query = query.filter(
            or_(
                Asset.last_seen >= changed_since,
                Asset.last_enriched_at >= changed_since
            )
        )

    # Get total count before pagination
    total = query.count()

    # Apply sorting
    sort_column = getattr(Asset, sort_by, Asset.last_seen)
    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    query = pagination.paginate_query(query)

    # Execute query
    assets = query.all()

    # Add counts for related data
    items = []
    for asset in assets:
        asset_dict = AssetResponse.model_validate(asset).model_dump()
        # Use database queries for counts since relationships are disabled
        from app.models.database import Service, Finding
        asset_dict['service_count'] = db.query(Service).filter(Service.asset_id == asset.id).count()
        asset_dict['certificate_count'] = 0  # TODO: Re-enable after fixing circular import
        asset_dict['endpoint_count'] = 0  # TODO: Re-enable after fixing circular import
        asset_dict['finding_count'] = db.query(Finding).filter(Finding.asset_id == asset.id).count()
        items.append(asset_dict)

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{asset_id}", response_model=AssetDetailResponse)
def get_asset(
    tenant_id: int,
    asset_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get asset by ID with full details

    Includes:
    - Asset metadata
    - Services (all)
    - Certificates (all)
    - Endpoints (limited to 100 most recent)
    - Findings (all)
    - Events (last 50)

    Raises:
        - 404: Asset not found
        - 403: No access to tenant
    """
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.tenant_id == tenant_id
    ).first()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    # Build response with related data
    response_data = AssetResponse.model_validate(asset).model_dump()

    # Convert SQLAlchemy objects to dictionaries for serialization
    from pydantic import BaseModel

    response_data['services'] = [
        {
            'id': s.id,
            'asset_id': s.asset_id,
            'port': s.port,
            'protocol': s.protocol,
            'product': s.product,
            'version': s.version,
            'tls_fingerprint': s.tls_fingerprint,
            'http_title': s.http_title,
            'http_status': s.http_status,
            'technologies': s.technologies,
            'web_server': s.web_server,
            'has_tls': s.has_tls,
            'tls_version': s.tls_version,
            'first_seen': s.first_seen.isoformat() if s.first_seen else None,
            'last_seen': s.last_seen.isoformat() if s.last_seen else None,
        }
        for s in asset.services
    ]

    response_data['certificates'] = []  # TODO: Re-enable after fixing circular import
    response_data['endpoints'] = []  # TODO: Re-enable after fixing circular import

    response_data['findings'] = [
        {
            'id': f.id,
            'asset_id': f.asset_id,
            'source': f.source,
            'template_id': f.template_id,
            'name': f.name,
            'severity': f.severity.value if hasattr(f.severity, 'value') else str(f.severity),
            'cvss_score': f.cvss_score,
            'cve_id': f.cve_id,
            'status': f.status.value if hasattr(f.status, 'value') else str(f.status),
            'matched_at': f.matched_at,
            'host': f.host,
            'matcher_name': f.matcher_name,
            'first_seen': f.first_seen.isoformat() if f.first_seen else None,
            'last_seen': f.last_seen.isoformat() if f.last_seen else None,
        }
        for f in asset.findings
    ]

    response_data['events'] = [
        {
            'id': e.id,
            'asset_id': e.asset_id,
            'kind': e.kind.value if hasattr(e.kind, 'value') else str(e.kind),
            'payload': e.payload,
            'created_at': e.created_at.isoformat() if e.created_at else None,
        }
        for e in sorted(asset.events, key=lambda e: e.created_at, reverse=True)[:50]
    ]

    return response_data


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(
    tenant_id: int,
    asset_data: AssetCreate,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Create new asset

    Validates asset type and identifier format

    Raises:
        - 400: Invalid asset data or duplicate
        - 403: No write access to tenant
    """
    # Verify write permission
    if not membership.has_permission("write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write permission required"
        )

    # Check if asset already exists
    existing = db.query(Asset).filter(
        Asset.tenant_id == tenant_id,
        Asset.identifier == asset_data.identifier,
        Asset.type == AssetType(asset_data.type)
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset already exists"
        )

    # Create asset
    asset = Asset(
        tenant_id=tenant_id,
        type=AssetType(asset_data.type),
        identifier=asset_data.identifier,
        priority=asset_data.priority or "normal"
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)

    logger.info(f"Created asset {asset.identifier} for tenant {tenant_id}")

    return AssetResponse.model_validate(asset)


@router.patch("/{asset_id}", response_model=AssetResponse)
def update_asset(
    tenant_id: int,
    asset_id: int,
    updates: AssetUpdate,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Update asset

    Allows updating priority and active status

    Raises:
        - 404: Asset not found
        - 403: No write access
    """
    # Verify write permission
    if not membership.has_permission("write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write permission required"
        )

    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.tenant_id == tenant_id
    ).first()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    # Apply updates
    if updates.priority is not None:
        asset.priority = updates.priority
        asset.priority_updated_at = datetime.utcnow()
        asset.priority_auto_calculated = False

    if updates.is_active is not None:
        asset.is_active = updates.is_active

    db.commit()
    db.refresh(asset)

    logger.info(f"Updated asset {asset.identifier}")

    return AssetResponse.model_validate(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    tenant_id: int,
    asset_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Delete asset (soft delete - mark as inactive)

    Raises:
        - 404: Asset not found
        - 403: No write access
    """
    # Verify write permission
    if not membership.has_permission("write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write permission required"
        )

    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.tenant_id == tenant_id
    ).first()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    # Soft delete
    asset.is_active = False
    db.commit()

    logger.info(f"Deleted asset {asset.identifier}")


@router.get("/tree", response_model=List[AssetTreeNode])
def get_asset_tree(
    tenant_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get hierarchical asset tree

    Returns:
        Tree structure: domains -> subdomains -> IPs/URLs

    Useful for visualization and navigation
    """
    # Get all domains
    domains = db.query(Asset).filter(
        Asset.tenant_id == tenant_id,
        Asset.type == AssetType.DOMAIN,
        Asset.is_active == True
    ).all()

    tree = []

    for domain in domains:
        domain_node = _build_asset_node(domain, db)

        # Get subdomains
        subdomains = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.type == AssetType.SUBDOMAIN,
            Asset.identifier.like(f"%.{domain.identifier}"),
            Asset.is_active == True
        ).all()

        domain_node['children'] = [
            _build_asset_node(subdomain, db)
            for subdomain in subdomains
        ]

        tree.append(domain_node)

    return tree


@router.post("/bulk", response_model=BulkOperationResult)
def bulk_create_assets(
    tenant_id: int,
    bulk_data: BulkAssetCreate,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Bulk create assets

    Creates multiple assets in one request
    Returns summary of successes and failures

    Raises:
        - 403: No write access
    """
    # Verify write permission
    if not membership.has_permission("write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write permission required"
        )

    success_count = 0
    failure_count = 0
    errors = []

    for asset_data in bulk_data.assets:
        try:
            # Check if exists
            existing = db.query(Asset).filter(
                Asset.tenant_id == tenant_id,
                Asset.identifier == asset_data.identifier,
                Asset.type == AssetType(asset_data.type)
            ).first()

            if existing:
                errors.append(f"Asset '{asset_data.identifier}' already exists")
                failure_count += 1
                continue

            # Create asset
            asset = Asset(
                tenant_id=tenant_id,
                type=AssetType(asset_data.type),
                identifier=asset_data.identifier,
                priority=asset_data.priority or "normal"
            )

            db.add(asset)
            success_count += 1

        except Exception as e:
            errors.append(f"Failed to create '{asset_data.identifier}': {str(e)}")
            failure_count += 1

    db.commit()

    logger.info(f"Bulk created {success_count} assets for tenant {tenant_id}")

    return BulkOperationResult(
        success_count=success_count,
        failure_count=failure_count,
        errors=errors
    )


# Seeds endpoints
@router.get("/seeds", response_model=List[SeedResponse])
def list_seeds(
    tenant_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    List all seeds for tenant

    Seeds are root domains, ASNs, IP ranges used for discovery

    Returns:
        List of seed objects
    """
    seeds = db.query(Seed).filter(
        Seed.tenant_id == tenant_id
    ).order_by(Seed.created_at.desc()).all()

    return [SeedResponse.model_validate(s) for s in seeds]


@router.post("/seeds", response_model=SeedResponse, status_code=status.HTTP_201_CREATED)
def create_seed(
    tenant_id: int,
    seed_data: SeedCreate,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Create new seed

    Seeds trigger discovery pipeline

    Raises:
        - 403: No write access
        - 400: Invalid seed data
    """
    # Verify write permission
    if not membership.has_permission("write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write permission required"
        )

    # Create seed
    seed = Seed(
        tenant_id=tenant_id,
        type=seed_data.type,
        value=seed_data.value,
        enabled=seed_data.enabled
    )

    db.add(seed)
    db.commit()
    db.refresh(seed)

    logger.info(f"Created seed {seed.value} for tenant {tenant_id}")

    return SeedResponse.model_validate(seed)


def _build_asset_node(asset: Asset, db: Session) -> dict:
    """Build asset tree node with counts"""
    return {
        "id": asset.id,
        "identifier": asset.identifier,
        "type": asset.type.value,
        "risk_score": asset.risk_score,
        "is_active": asset.is_active,
        "service_count": len(asset.services),
        "finding_count": len(asset.findings),
        "children": []
    }
