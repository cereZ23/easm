"""
Tenants Router

Handles tenant management, dashboard, and statistics
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict
import logging

from app.api.dependencies import (
    get_db,
    get_current_user,
    verify_tenant_access,
    require_admin
)
from app.api.schemas.tenant import (
    TenantResponse,
    TenantCreate,
    TenantUpdate,
    TenantDashboard,
    TenantStats,
    RecentActivity
)
from app.models.database import Tenant, Asset, Service, Finding, Event, AssetType, FindingSeverity, FindingStatus
from app.models.enrichment import Certificate, Endpoint
from app.models.auth import User
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tenants", tags=["Tenants"])


@router.get("", response_model=list[TenantResponse])
def list_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all tenants accessible to current user

    Superusers see all tenants, regular users see their tenants

    Returns:
        List of tenant objects
    """
    if current_user.is_superuser:
        tenants = db.query(Tenant).all()
    else:
        # Get tenants where user has membership
        tenants = [
            membership.tenant
            for membership in current_user.tenant_memberships
            if membership.is_active
        ]

    return [TenantResponse.model_validate(t) for t in tenants]


@router.post("", response_model=TenantResponse)
def create_tenant(
    tenant_data: TenantCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Create new tenant (admin only)

    Raises:
        - 403: Not admin
        - 400: Slug already exists
    """
    # Check if slug exists
    existing = db.query(Tenant).filter(Tenant.slug == tenant_data.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant slug already exists"
        )

    tenant = Tenant(
        name=tenant_data.name,
        slug=tenant_data.slug,
        contact_policy=tenant_data.contact_policy
    )

    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    logger.info(f"Admin {admin.email} created tenant {tenant.name}")

    return TenantResponse.model_validate(tenant)


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get tenant by ID

    Requires tenant membership

    Raises:
        - 403: No access to tenant
        - 404: Tenant not found
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    return TenantResponse.model_validate(tenant)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: int,
    updates: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update tenant

    Requires admin permission for tenant

    Raises:
        - 403: No admin access
        - 404: Tenant not found
    """
    # Verify admin access
    await verify_tenant_access(tenant_id, current_user, db, "admin")

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    # Apply updates
    if updates.name is not None:
        tenant.name = updates.name

    if updates.contact_policy is not None:
        tenant.contact_policy = updates.contact_policy

    db.commit()
    db.refresh(tenant)

    logger.info(f"User {current_user.email} updated tenant {tenant.name}")

    return TenantResponse.model_validate(tenant)


@router.get("/{tenant_id}/dashboard", response_model=TenantDashboard)
def get_tenant_dashboard(
    tenant_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get tenant dashboard with statistics and recent activity

    Comprehensive view for main dashboard page

    Returns:
        - Tenant info
        - Statistics
        - Recent activity
        - Risk distribution
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    # Calculate statistics
    stats = _calculate_tenant_stats(db, tenant_id)

    # Get recent activity (last 50 events)
    recent_events = db.query(Event).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).order_by(Event.created_at.desc()).limit(50).all()

    recent_activity = [
        RecentActivity(
            id=event.id,
            type=event.kind.value,
            description=_format_event_description(event),
            timestamp=event.created_at,
            metadata={"asset_id": event.asset_id}
        )
        for event in recent_events
    ]

    # Risk distribution
    risk_buckets = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    assets = db.query(Asset).filter(Asset.tenant_id == tenant_id).all()

    for asset in assets:
        if asset.risk_score is not None:
            if asset.risk_score >= 80:
                risk_buckets["critical"] += 1
            elif asset.risk_score >= 60:
                risk_buckets["high"] += 1
            elif asset.risk_score >= 40:
                risk_buckets["medium"] += 1
            else:
                risk_buckets["low"] += 1
        else:
            # Assets without risk score default to low
            risk_buckets["low"] += 1

    return TenantDashboard(
        tenant=TenantResponse.model_validate(tenant),
        stats=stats,
        recent_activity=recent_activity,
        trending_assets=[],
        risk_distribution=risk_buckets
    )


@router.get("/{tenant_id}/stats", response_model=TenantStats)
def get_tenant_stats(
    tenant_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get detailed tenant statistics

    Returns comprehensive metrics for analytics

    Raises:
        - 403: No access to tenant
    """
    return _calculate_tenant_stats(db, tenant_id)


def _calculate_tenant_stats(db: Session, tenant_id: int) -> TenantStats:
    """Calculate comprehensive tenant statistics"""

    # Asset statistics
    total_assets = db.query(Asset).filter(Asset.tenant_id == tenant_id).count()

    assets_by_type = {}
    for asset_type in AssetType:
        count = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.type == asset_type
        ).count()
        assets_by_type[asset_type.value] = count

    # Service count
    total_services = db.query(Service).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).count()

    # Certificate count
    total_certificates = db.query(Certificate).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).count()

    # Endpoint count
    total_endpoints = db.query(Endpoint).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).count()

    # Finding statistics
    total_findings = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).count()

    findings_by_severity = {}
    for severity in FindingSeverity:
        count = db.query(Finding).join(Asset).filter(
            Asset.tenant_id == tenant_id,
            Finding.severity == severity
        ).count()
        findings_by_severity[severity.value] = count

    open_findings = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Finding.status == FindingStatus.OPEN
    ).count()

    critical_findings = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Finding.severity == FindingSeverity.CRITICAL,
        Finding.status == FindingStatus.OPEN
    ).count()

    high_findings = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Finding.severity == FindingSeverity.HIGH,
        Finding.status == FindingStatus.OPEN
    ).count()

    # Expiring certificates (within 30 days)
    thirty_days_from_now = datetime.utcnow() + timedelta(days=30)
    expiring_certificates = db.query(Certificate).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Certificate.is_expired == False,
        Certificate.not_after <= thirty_days_from_now
    ).count()

    # Average risk score
    avg_risk = db.query(func.avg(Asset.risk_score)).filter(
        Asset.tenant_id == tenant_id
    ).scalar() or 0.0

    return TenantStats(
        total_assets=total_assets,
        assets_by_type=assets_by_type,
        total_services=total_services,
        total_certificates=total_certificates,
        total_endpoints=total_endpoints,
        total_findings=total_findings,
        findings_by_severity=findings_by_severity,
        open_findings=open_findings,
        critical_findings=critical_findings,
        high_findings=high_findings,
        expiring_certificates=expiring_certificates,
        average_risk_score=round(float(avg_risk), 2)
    )


def _format_event_description(event: Event) -> str:
    """Format event description for display"""
    descriptions = {
        "new_asset": f"New asset discovered: {event.asset.identifier}",
        "open_port": f"New open port detected on {event.asset.identifier}",
        "new_cert": f"New certificate issued for {event.asset.identifier}",
        "new_path": f"New endpoint discovered on {event.asset.identifier}",
        "tech_change": f"Technology change detected on {event.asset.identifier}"
    }

    return descriptions.get(event.kind.value, f"Event on {event.asset.identifier}")
