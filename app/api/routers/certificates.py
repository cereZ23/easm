"""
Certificates Router

Handles TLS/SSL certificate data and monitoring
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from app.api.dependencies import get_db, verify_tenant_access, PaginationParams
from app.api.schemas.certificate import (
    CertificateResponse,
    CertificateListRequest,
    CertificateHealthResponse
)
from app.api.schemas.common import PaginatedResponse
from app.models.database import Asset
from app.models.enrichment import Certificate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/certificates", tags=["Certificates"])


@router.get("", response_model=PaginatedResponse[CertificateResponse])
def list_certificates(
    tenant_id: int,
    asset_id: Optional[int] = Query(None),
    is_expired: Optional[bool] = Query(None),
    is_expiring_soon: Optional[bool] = Query(None),
    is_self_signed: Optional[bool] = Query(None),
    is_wildcard: Optional[bool] = Query(None),
    has_weak_signature: Optional[bool] = Query(None),
    issuer: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("not_after"),
    sort_order: str = Query("asc"),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    List certificates with filtering

    Focus areas:
    - Expiring certificates
    - Self-signed certificates
    - Weak cryptography
    - Wildcard certificates

    Useful for TLS/SSL hygiene and compliance
    """
    # Build query with tenant isolation
    query = db.query(Certificate).join(Asset).filter(Asset.tenant_id == tenant_id)

    # Apply filters
    if asset_id:
        query = query.filter(Certificate.asset_id == asset_id)

    if is_expired is not None:
        query = query.filter(Certificate.is_expired == is_expired)

    if is_expiring_soon:
        thirty_days = datetime.utcnow() + timedelta(days=30)
        query = query.filter(
            and_(
                Certificate.is_expired == False,
                Certificate.not_after <= thirty_days
            )
        )

    if is_self_signed is not None:
        query = query.filter(Certificate.is_self_signed == is_self_signed)

    if is_wildcard is not None:
        query = query.filter(Certificate.is_wildcard == is_wildcard)

    if has_weak_signature is not None:
        query = query.filter(Certificate.has_weak_signature == has_weak_signature)

    if issuer:
        query = query.filter(Certificate.issuer.ilike(f"%{issuer}%"))

    if search:
        query = query.filter(
            Certificate.subject_cn.ilike(f"%{search}%")
        )

    # Get total count
    total = query.count()

    # Apply sorting
    sort_column = getattr(Certificate, sort_by, Certificate.not_after)
    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    query = pagination.paginate_query(query)

    certificates = query.all()

    return PaginatedResponse(
        items=[CertificateResponse.model_validate(c) for c in certificates],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{certificate_id}", response_model=CertificateResponse)
def get_certificate(
    tenant_id: int,
    certificate_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get certificate by ID

    Returns full certificate details

    Raises:
        - 404: Certificate not found
    """
    certificate = db.query(Certificate).join(Asset).filter(
        Certificate.id == certificate_id,
        Asset.tenant_id == tenant_id
    ).first()

    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found"
        )

    return CertificateResponse.model_validate(certificate)


@router.get("/expiring", response_model=List[CertificateResponse])
def get_expiring_certificates(
    tenant_id: int,
    days: int = Query(30, ge=1, le=365, description="Days until expiry"),
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get certificates expiring soon

    Default: 30 days

    Critical for preventing service disruptions

    Returns:
        Certificates expiring within specified days, sorted by expiry date
    """
    expiry_threshold = datetime.utcnow() + timedelta(days=days)

    certificates = db.query(Certificate).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Certificate.is_expired == False,
        Certificate.not_after <= expiry_threshold
    ).order_by(Certificate.not_after.asc()).all()

    return [CertificateResponse.model_validate(c) for c in certificates]


@router.get("/health", response_model=CertificateHealthResponse)
def get_certificate_health(
    tenant_id: int,
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Get certificate health summary

    Aggregated view of certificate posture:
    - Total certificates
    - Expired/expiring
    - Self-signed
    - Weak signatures
    - Distribution by issuer/key size

    Useful for compliance and security dashboards
    """
    # Total certificates
    total = db.query(Certificate).join(Asset).filter(
        Asset.tenant_id == tenant_id
    ).count()

    # Expired certificates
    expired = db.query(Certificate).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Certificate.is_expired == True
    ).count()

    # Expiring soon (30 days)
    thirty_days = datetime.utcnow() + timedelta(days=30)
    expiring_soon = db.query(Certificate).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Certificate.is_expired == False,
        Certificate.not_after <= thirty_days
    ).count()

    # Self-signed
    self_signed = db.query(Certificate).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Certificate.is_self_signed == True
    ).count()

    # Weak signature
    weak_signature = db.query(Certificate).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Certificate.has_weak_signature == True
    ).count()

    # Wildcard certificates
    wildcard = db.query(Certificate).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Certificate.is_wildcard == True
    ).count()

    # Distribution by issuer
    issuers = db.query(
        Certificate.issuer,
        func.count(Certificate.id).label('count')
    ).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Certificate.issuer.isnot(None)
    ).group_by(Certificate.issuer).all()

    by_issuer = {issuer: count for issuer, count in issuers}

    # Distribution by key size
    key_sizes = db.query(
        Certificate.public_key_bits,
        func.count(Certificate.id).label('count')
    ).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Certificate.public_key_bits.isnot(None)
    ).group_by(Certificate.public_key_bits).all()

    by_key_size = {str(size): count for size, count in key_sizes if size}

    return CertificateHealthResponse(
        total_certificates=total,
        expired=expired,
        expiring_soon=expiring_soon,
        self_signed=self_signed,
        weak_signature=weak_signature,
        wildcard=wildcard,
        by_issuer=by_issuer,
        by_key_size=by_key_size
    )
