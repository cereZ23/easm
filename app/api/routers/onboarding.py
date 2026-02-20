"""
Onboarding Router

Handles self-service customer onboarding
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import List
import logging
import re

from app.api.dependencies import get_db, require_admin
from app.models.database import Tenant, Seed
from app.models.auth import User, TenantMembership
from app.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/onboarding", tags=["Admin Onboarding"])


class OnboardingRequest(BaseModel):
    """Self-service onboarding request"""

    company_name: str = Field(..., min_length=2, max_length=255, description="Company name")
    email: EmailStr = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, description="Admin password")
    domains: List[str] = Field(..., min_items=1, max_items=10, description="Domains to monitor")

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "Less Is More",
                "email": "admin@lessismore.fun",
                "password": "SecurePass123!",
                "domains": ["lessismore.fun"]
            }
        }


class OnboardingResponse(BaseModel):
    """Onboarding response"""

    tenant_id: int = Field(..., description="Created tenant ID")
    tenant_name: str = Field(..., description="Tenant name")
    tenant_slug: str = Field(..., description="Tenant slug")
    user_id: int = Field(..., description="Created user ID")
    domains_added: int = Field(..., description="Number of domains added")
    scan_triggered: bool = Field(..., description="Whether initial scan was triggered")
    message: str = Field(..., description="Success message")


def generate_slug(name: str) -> str:
    """Generate URL-safe slug from company name"""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


def validate_domain(domain: str) -> bool:
    """Validate domain format"""
    # Basic domain validation
    pattern = r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$'
    return bool(re.match(pattern, domain.lower()))


@router.post("/register", response_model=OnboardingResponse)
def register_organization(
    request: OnboardingRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Admin-only customer onboarding

    Allows platform admins to onboard new customers through the UI dashboard.

    Creates:
    - Tenant
    - Customer admin user account
    - Tenant membership
    - Seed domains
    - Triggers initial scan

    Returns:
        Onboarding response with tenant and user details

    Raises:
        - 403: Not admin (authentication required)
        - 400: Invalid data or duplicate slug/email
        - 500: Internal error during creation
    """
    logger.info(f"Admin {admin.email} starting onboarding for {request.company_name} ({request.email})")

    try:
        # 1. Validate all domains
        for domain in request.domains:
            if not validate_domain(domain):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid domain format: {domain}"
                )

        # 2. Generate slug and check uniqueness
        base_slug = generate_slug(request.company_name)
        slug = base_slug
        counter = 1

        while db.query(Tenant).filter(Tenant.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # 3. Check if email already exists
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already registered"
            )

        # 4. Create tenant
        tenant = Tenant(
            name=request.company_name,
            slug=slug
        )
        db.add(tenant)
        db.flush()  # Get tenant ID without committing

        logger.info(f"Created tenant: {tenant.name} (ID: {tenant.id}, slug: {tenant.slug})")

        # 5. Create admin user with unique username
        # Generate unique username from email (handle duplicates)
        base_username = request.email.split('@')[0]
        username = base_username
        counter = 1

        # Check if username exists and increment until unique
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1

        user = User(
            email=request.email,
            username=username,
            hashed_password=User.hash_password(request.password),
            is_active=True,
            is_superuser=False
        )
        db.add(user)
        db.flush()

        logger.info(f"Created user: {user.email} (ID: {user.id})")

        # 6. Create tenant membership (owner role)
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            role='owner',
            is_active=True
        )
        db.add(membership)

        # 7. Add seed domains
        domains_added = 0
        for domain in request.domains:
            seed = Seed(
                tenant_id=tenant.id,
                type='domain',
                value=domain.lower().strip(),
                enabled=True
            )
            db.add(seed)
            domains_added += 1

        logger.info(f"Added {domains_added} domains for tenant {tenant.id}")

        # 8. Commit all changes
        db.commit()
        db.refresh(tenant)
        db.refresh(user)

        # 9. Trigger complete initial scan pipeline (async)
        scan_triggered = False
        try:
            from app.tasks.discovery import run_tenant_discovery
            from app.tasks.enrichment import run_enrichment_pipeline
            from app.tasks.scanning import run_nuclei_scan, calculate_comprehensive_risk_scores
            from celery import chain

            # Build complete pipeline: Discovery → Enrichment → Nuclei → Risk Scoring
            # This ensures new customers get full reconnaissance including vulnerability detection
            complete_pipeline = chain(
                run_tenant_discovery.si(tenant.id),                      # 1. Subdomain discovery (Amass + Subfinder + DNSx)
                run_enrichment_pipeline.si(                              # 2. Enrichment (HTTPx, Naabu, TLSx, Katana)
                    tenant_id=tenant.id,
                    asset_ids=None,  # All assets
                    priority='high',
                    force_refresh=True
                ),
                run_nuclei_scan.si(                                      # 3. Vulnerability scanning
                    tenant_id=tenant.id,
                    asset_ids=None,  # All assets
                    severity=['critical', 'high', 'medium', 'low']
                ),
                calculate_comprehensive_risk_scores.si(tenant.id)        # 4. Calculate risk scores
            )

            # Execute pipeline asynchronously
            task = complete_pipeline.apply_async()
            scan_triggered = True
            logger.info(f"Triggered complete onboarding pipeline for tenant {tenant.id}: chain {task.id}")

        except Exception as scan_error:
            # Don't fail registration if scan trigger fails
            logger.error(f"Failed to trigger initial scan pipeline: {scan_error}")

        logger.info(f"Onboarding complete for {tenant.name}")

        return OnboardingResponse(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            tenant_slug=tenant.slug,
            user_id=user.id,
            domains_added=domains_added,
            scan_triggered=scan_triggered,
            message=f"Successfully registered {tenant.name}! Your initial scan has been started and will complete in 1-2 hours."
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        db.rollback()
        raise

    except Exception as e:
        # Rollback and log unexpected errors
        db.rollback()
        logger.error(f"Onboarding failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.get("/check-availability/{slug}")
def check_slug_availability(
    slug: str,
    db: Session = Depends(get_db)
):
    """
    Check if tenant slug is available

    Returns:
        {"available": true/false}
    """
    existing = db.query(Tenant).filter(Tenant.slug == slug).first()
    return {"available": existing is None, "slug": slug}
