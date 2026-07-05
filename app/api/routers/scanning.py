"""
Scanning Router

Manual scanning endpoints for Nuclei vulnerability scanning
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from app.api.dependencies import get_db, verify_tenant_access
from app.api.schemas.common import TaskResponse
from app.tasks.scanning import run_nuclei_scan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/scan", tags=["Scanning"])


@router.post("/nuclei", response_model=TaskResponse)
def trigger_nuclei_scan(
    tenant_id: int,
    asset_ids: Optional[List[int]] = Body(None, description="Specific asset IDs to scan (optional)"),
    scan_level: str = Body('standard', description="Scan level: quick | standard | deep"),
    severity_levels: Optional[List[str]] = Body(None, description="Override severities (defaults from scan_level)"),
    template_paths: Optional[List[str]] = Body(None, description="Specific template paths (optional)"),
    db: Session = Depends(get_db),
    membership = Depends(verify_tenant_access)
):
    """
    Manually trigger a Nuclei vulnerability scan

    Args:
        tenant_id: Tenant ID
        asset_ids: Optional list of specific asset IDs to scan. If not provided, scans all active assets.
        severity_levels: Severity levels to include (critical, high, medium, low, info)
        template_paths: Optional specific Nuclei template paths to use

    Returns:
        TaskResponse with Celery task ID

    Example:
        POST /api/v1/tenants/2/scan/nuclei
        {
            "severity_levels": ["critical", "high"],
            "asset_ids": [1, 2, 3]
        }
    """
    if scan_level not in ('quick', 'standard', 'deep'):
        scan_level = 'standard'
    logger.info(f"Triggering Nuclei scan for tenant {tenant_id} (level: {scan_level}, asset_ids: {asset_ids})")

    # Trigger async Nuclei scan task. severity/templates default from scan_level
    # when not explicitly provided (see SCAN_LEVELS in app.tasks.scanning).
    task = run_nuclei_scan.delay(
        tenant_id=tenant_id,
        asset_ids=asset_ids,
        severity=severity_levels,   # None -> level default
        templates=template_paths,   # None -> level default
        scan_level=scan_level
    )

    return TaskResponse(
        task_id=task.id,
        status='queued',
        message=f'Nuclei scan queued for tenant {tenant_id}'
    )


@router.post("/nuclei/update-templates", response_model=TaskResponse)
def update_nuclei_templates(
    tenant_id: int,
    membership = Depends(verify_tenant_access)
):
    """
    Update Nuclei templates to latest version

    This will pull the latest templates from the Nuclei templates repository.
    Templates are shared across all tenants.

    Returns:
        TaskResponse with task status
    """
    from app.tasks.scanning import update_nuclei_templates as update_task

    logger.info(f"Triggering Nuclei template update (requested by tenant {tenant_id})")

    task = update_task.delay()

    return TaskResponse(
        task_id=task.id,
        status='queued',
        message='Nuclei template update queued'
    )
