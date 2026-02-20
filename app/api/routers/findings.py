"""
Findings Router

Handles vulnerability findings from Nuclei and other sources
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from app.api.dependencies import get_db, verify_tenant_access, PaginationParams
from app.api.schemas.finding import (
    FindingResponse,
    FindingListRequest,
    FindingUpdate,
    FindingDetailResponse,
    FindingStatsResponse,
    SeverityDistribution
)
from app.api.schemas.common import PaginatedResponse
from app.models.database import Asset, Finding, FindingSeverity, FindingStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/findings", tags=["Findings"])


# Severity ordering for filtering
SEVERITY_ORDER = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4
}


@router.get("", response_model=PaginatedResponse[FindingResponse])
def list_findings(
    tenant_id: int,
    asset_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    min_severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    cve_id: Optional[str] = Query(None),
    template_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    min_cvss_score: Optional[float] = Query(None),
    sort_by: str = Query("last_seen"),
    sort_order: str = Query("desc"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    List findings with comprehensive filtering

    Primary use cases:
    - Vulnerability management
    - Security dashboards
    - Compliance reporting
    - Incident response

    Filters:
    - severity: Exact severity level
    - min_severity: Minimum severity (info, low, medium, high, critical)
    - status: open, suppressed, fixed
    - source: nuclei, manual, custom
    - cve_id: Specific CVE
    - search: Full-text search
    """
    # Build query with tenant isolation
    query = db.query(
        Finding,
        Asset.identifier.label('asset_identifier'),
        Asset.type.label('asset_type')
    ).join(Asset).filter(Asset.tenant_id == tenant_id)

    # Apply filters
    if asset_id:
        query = query.filter(Finding.asset_id == asset_id)

    if severity:
        try:
            query = query.filter(Finding.severity == FindingSeverity(severity))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity: {severity}"
            )

    if min_severity:
        if min_severity not in SEVERITY_ORDER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid min_severity: {min_severity}"
            )

        # Filter for severities >= min_severity
        min_level = SEVERITY_ORDER[min_severity]
        valid_severities = [
            sev for sev, level in SEVERITY_ORDER.items()
            if level >= min_level
        ]
        query = query.filter(
            Finding.severity.in_([FindingSeverity(s) for s in valid_severities])
        )

    if status:
        try:
            query = query.filter(Finding.status == FindingStatus(status))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )

    if source:
        query = query.filter(Finding.source == source)

    if cve_id:
        query = query.filter(Finding.cve_id == cve_id)

    if template_id:
        query = query.filter(Finding.template_id == template_id)

    if min_cvss_score is not None:
        query = query.filter(Finding.cvss_score >= min_cvss_score)

    if search:
        query = query.filter(
            or_(
                Finding.name.ilike(f"%{search}%"),
                Finding.cve_id.ilike(f"%{search}%"),
                Finding.template_id.ilike(f"%{search}%")
            )
        )

    # Get total count
    total = query.count()

    # Apply sorting
    if sort_by == "asset_identifier":
        sort_column = Asset.identifier
    else:
        sort_column = getattr(Finding, sort_by, Finding.last_seen)

    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    query = pagination.paginate_query(query)

    results = query.all()

    # Build response with asset info
    items = []
    for finding, asset_identifier, asset_type in results:
        finding_dict = FindingResponse.model_validate(finding).model_dump()
        finding_dict['asset_identifier'] = asset_identifier
        finding_dict['asset_type'] = asset_type.value if asset_type else None
        items.append(finding_dict)

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{finding_id}", response_model=FindingDetailResponse)
def get_finding(
    tenant_id: int,
    finding_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get finding by ID with full details

    Includes:
    - Finding metadata
    - Full evidence
    - Asset information
    - Remediation guidance (if available)

    Raises:
        - 404: Finding not found
    """
    finding = db.query(Finding).join(Asset).filter(
        Finding.id == finding_id,
        Asset.tenant_id == tenant_id
    ).first()

    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found"
        )

    # Build detailed response
    response_data = FindingResponse.model_validate(finding).model_dump()
    response_data['asset'] = {
        'id': finding.asset.id,
        'identifier': finding.asset.identifier,
        'type': finding.asset.type.value
    }

    # TODO: Add remediation guidance from knowledge base
    response_data['remediation'] = None
    response_data['references'] = []
    response_data['tags'] = []

    return response_data


@router.patch("/{finding_id}", response_model=FindingResponse)
def update_finding(
    tenant_id: int,
    finding_id: int,
    updates: FindingUpdate,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Update finding

    Allows:
    - Changing status (open, suppressed, fixed)
    - Adding notes

    Useful for:
    - False positive suppression
    - Tracking remediation
    - Adding context

    Raises:
        - 404: Finding not found
        - 403: No write access
    """
    # Verify write permission
    if not membership.has_permission("write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write permission required"
        )

    finding = db.query(Finding).join(Asset).filter(
        Finding.id == finding_id,
        Asset.tenant_id == tenant_id
    ).first()

    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found"
        )

    # Apply updates
    if updates.status is not None:
        try:
            finding.status = FindingStatus(updates.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {updates.status}"
            )

    # Note: Notes field doesn't exist in current model
    # Would need to add to Finding model or store in evidence JSON

    db.commit()
    db.refresh(finding)

    logger.info(f"Updated finding {finding_id} to status {finding.status.value}")

    return FindingResponse.model_validate(finding)


@router.get("/stats", response_model=FindingStatsResponse)
def get_finding_stats(
    tenant_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get finding statistics

    Comprehensive metrics:
    - Total findings
    - Distribution by severity/status/source
    - Open findings by severity
    - Average CVSS score
    - Top CVEs

    Essential for security dashboards
    """
    # Total findings
    total = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).count()

    # Distribution by severity
    by_severity = {}
    for severity in FindingSeverity:
        count = db.query(Finding).join(Asset).filter(
            Asset.tenant_id == tenant_id,
            Finding.severity == severity
        ).count()
        by_severity[severity.value] = count

    # Distribution by status
    by_status = {}
    for finding_status in FindingStatus:
        count = db.query(Finding).join(Asset).filter(
            Asset.tenant_id == tenant_id,
            Finding.status == finding_status
        ).count()
        by_status[finding_status.value] = count

    # Distribution by source
    sources = db.query(
        Finding.source,
        func.count(Finding.id).label('count')
    ).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).group_by(Finding.source).all()

    by_source = {source: count for source, count in sources}

    # Open findings
    open_findings = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Finding.status == FindingStatus.OPEN
    ).count()

    # Critical and high open findings
    critical_open = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Finding.severity == FindingSeverity.CRITICAL,
        Finding.status == FindingStatus.OPEN
    ).count()

    high_open = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Finding.severity == FindingSeverity.HIGH,
        Finding.status == FindingStatus.OPEN
    ).count()

    # Average CVSS score
    avg_cvss = db.query(func.avg(Finding.cvss_score)).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Finding.cvss_score.isnot(None)
    ).scalar()

    # Top CVEs
    top_cves = db.query(
        Finding.cve_id,
        func.count(Finding.id).label('count')
    ).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Finding.cve_id.isnot(None)
    ).group_by(Finding.cve_id).order_by(func.count(Finding.id).desc()).limit(10).all()

    top_cves_list = [
        {"cve_id": cve_id, "count": count}
        for cve_id, count in top_cves
    ]

    return FindingStatsResponse(
        total_findings=total,
        by_severity=by_severity,
        by_status=by_status,
        by_source=by_source,
        open_findings=open_findings,
        critical_open=critical_open,
        high_open=high_open,
        average_cvss=round(float(avg_cvss), 2) if avg_cvss else None,
        top_cves=top_cves_list
    )


@router.get("/trends/severity", response_model=List[SeverityDistribution])
def get_severity_trends(
    tenant_id: int,
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get severity distribution trends over time

    Shows how findings evolve over specified period

    Useful for:
    - Trend analysis
    - Reporting
    - Measuring security posture improvement

    Returns:
        Daily severity counts for the specified period
    """
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # This is a simplified version
    # In production, you'd want to cache this or use time-series data
    trends = []

    for day_offset in range(days):
        date = start_date + timedelta(days=day_offset)
        next_date = date + timedelta(days=1)

        # Count findings by severity for this day
        severity_counts = {}
        for severity in FindingSeverity:
            count = db.query(Finding).join(Asset).filter(
                Asset.tenant_id == tenant_id,
                Finding.severity == severity,
                Finding.first_seen <= next_date,
                or_(
                    Finding.last_seen >= date,
                    Finding.status == FindingStatus.OPEN
                )
            ).count()
            severity_counts[severity.value] = count

        trends.append(SeverityDistribution(
            date=date,
            critical=severity_counts.get('critical', 0),
            high=severity_counts.get('high', 0),
            medium=severity_counts.get('medium', 0),
            low=severity_counts.get('low', 0),
            info=severity_counts.get('info', 0)
        ))

    return trends
