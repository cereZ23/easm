"""
Vulnerability scanning tasks with Nuclei integration

Sprint 3: Implements comprehensive Nuclei vulnerability scanning:
- URL-based scanning from HTTPx enrichment results
- Template management and customization
- Severity-based filtering
- Finding deduplication and storage
- False positive suppression
- Risk score calculation
- Integration with enrichment pipeline
"""

import logging
import asyncio
from typing import List, Optional, Dict
from datetime import datetime

from app.celery_app import celery
from app.models.database import Asset, FindingSeverity
from app.services.scanning.nuclei_service import NucleiService, calculate_risk_score_from_findings
from app.services.scanning.suppression_service import SuppressionService
from app.repositories.finding_repository import FindingRepository
from app.repositories.service_repository import ServiceRepository
from app.utils.logger import TenantLoggerAdapter

logger = logging.getLogger(__name__)


@celery.task(name='app.tasks.scanning.run_nuclei_scan')
def run_nuclei_scan(
    tenant_id: int,
    asset_ids: Optional[List[int]] = None,
    severity: Optional[List[str]] = None,
    templates: Optional[List[str]] = None,
    rate_limit: int = 300
):
    """
    Execute Nuclei vulnerability scan on assets

    Workflow:
    1. Get URLs from assets (from HTTPx enrichment results)
    2. Execute Nuclei scan with specified templates/severity
    3. Parse JSON output
    4. Apply suppression rules (filter false positives)
    5. Store findings with deduplication (bulk upsert)
    6. Update asset risk scores based on findings
    7. Log results and stats

    Args:
        tenant_id: Tenant ID
        asset_ids: Optional list of specific asset IDs to scan
        severity: Severity filter (critical, high, medium, low, info)
        templates: Optional template paths/categories
        rate_limit: Requests per second (default: 300)

    Returns:
        Dict with scan results and statistics
    """
    from app.database import SessionLocal
    db = SessionLocal()
    tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})

    try:
        tenant_logger.info(
            f"Starting Nuclei scan (assets: {len(asset_ids) if asset_ids else 'all'}, "
            f"severity: {severity}, templates: {templates})"
        )

        # Get assets to scan
        query = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.is_active == True
        )

        if asset_ids:
            query = query.filter(Asset.id.in_(asset_ids))

        assets = query.all()

        if not assets:
            tenant_logger.warning("No assets found for Nuclei scan")
            return {
                'assets_scanned': 0,
                'findings_created': 0,
                'findings_updated': 0,
                'status': 'no_assets'
            }

        # Get URLs from services (HTTPx enrichment results)
        service_repo = ServiceRepository(db)
        urls_by_asset = {}

        for asset in assets:
            # Get web services for this asset
            web_services = service_repo.get_web_services(asset.id, only_live=True)

            for service in web_services:
                # Build URL from service
                scheme = service.protocol or ('https' if service.has_tls else 'http')
                port = service.port

                # Construct URL
                if port in [80, 443]:
                    url = f"{scheme}://{asset.identifier}"
                else:
                    url = f"{scheme}://{asset.identifier}:{port}"

                if asset.id not in urls_by_asset:
                    urls_by_asset[asset.id] = []

                urls_by_asset[asset.id].append(url)

        if not urls_by_asset:
            tenant_logger.warning("No live web services found for scanning")
            return {
                'assets_scanned': len(assets),
                'findings_created': 0,
                'findings_updated': 0,
                'status': 'no_urls'
            }

        # Flatten URLs for scanning
        all_urls = []
        url_to_asset = {}
        for asset_id, urls in urls_by_asset.items():
            for url in urls:
                all_urls.append(url)
                url_to_asset[url] = asset_id

        tenant_logger.info(f"Scanning {len(all_urls)} URLs across {len(assets)} assets")

        # Step 1: Crawl URLs with Katana to discover endpoints with parameters
        tenant_logger.info("Running Katana crawler to discover vulnerable endpoints...")
        from app.utils.secure_executor import SecureToolExecutor

        crawled_urls = []
        for url in all_urls:
            tenant_logger.debug(f"Crawling {url}...")

            try:
                with SecureToolExecutor(tenant_id) as executor:
                    # Run Katana to discover endpoints
                    returncode, stdout, stderr = executor.execute(
                        'katana',
                        ['-u', url, '-d', '2', '-jc', '-silent'],
                        timeout=300
                    )

                    if returncode == 0 and stdout:
                        # Extract URLs with parameters
                        for line in stdout.strip().split('\n'):
                            if line and '?' in line:  # Has query parameters
                                crawled_urls.append(line.strip())
                                tenant_logger.debug(f"Discovered: {line.strip()}")
            except Exception as e:
                tenant_logger.warning(f"Katana crawl failed for {url}: {e}")
                continue

        # Combine base URLs + crawled URLs with parameters
        scan_targets = list(set(all_urls + crawled_urls))
        tenant_logger.info(f"Total scan targets: {len(scan_targets)} ({len(all_urls)} base + {len(crawled_urls)} crawled)")

        # Step 2: Execute Nuclei scan
        nuclei_service = NucleiService(tenant_id)

        # Use asyncio to run async method
        scan_result = asyncio.run(
            nuclei_service.scan_urls(
                urls=scan_targets,  # Scan both base URLs and crawled endpoints
                templates=templates,
                severity=severity or ['critical', 'high', 'medium'],
                rate_limit=rate_limit
            )
        )

        findings = scan_result['findings']
        stats = scan_result['stats']
        errors = scan_result.get('errors', [])

        tenant_logger.info(
            f"Nuclei scan complete: {stats['findings_count']} findings discovered"
        )

        if errors:
            tenant_logger.warning(f"Scan had {len(errors)} validation errors")

        # Map findings to assets
        for finding in findings:
            matched_url = finding.get('matched_at')
            if matched_url and matched_url in url_to_asset:
                finding['asset_id'] = url_to_asset[matched_url]
            else:
                # Try to match by host
                host = finding.get('host')
                if host:
                    asset = db.query(Asset).filter(
                        Asset.tenant_id == tenant_id,
                        Asset.identifier == host
                    ).first()
                    if asset:
                        finding['asset_id'] = asset.id

        # Filter out findings without asset mapping
        findings_with_assets = [f for f in findings if 'asset_id' in f]

        if len(findings_with_assets) < len(findings):
            unmapped = len(findings) - len(findings_with_assets)
            tenant_logger.warning(f"Could not map {unmapped} findings to assets")

        # Apply suppression rules (filter false positives)
        suppression_service = SuppressionService(db, tenant_id)
        unsuppressed, suppressed = suppression_service.filter_findings(findings_with_assets)

        tenant_logger.info(
            f"Suppression filtering: {len(unsuppressed)} unsuppressed, "
            f"{len(suppressed)} suppressed"
        )

        # Store findings in database
        finding_repo = FindingRepository(db)
        upsert_result = finding_repo.bulk_upsert_findings(unsuppressed, tenant_id)

        tenant_logger.info(
            f"Stored findings: {upsert_result['created']} created, "
            f"{upsert_result['updated']} updated"
        )

        # Update asset risk scores
        assets_updated = update_asset_risk_scores(tenant_id, list(urls_by_asset.keys()), db)

        tenant_logger.info(f"Updated risk scores for {assets_updated} assets")

        return {
            'tenant_id': tenant_id,
            'assets_scanned': len(assets),
            'urls_scanned': len(all_urls),
            'findings_discovered': stats['findings_count'],
            'findings_suppressed': len(suppressed),
            'findings_created': upsert_result['created'],
            'findings_updated': upsert_result['updated'],
            'assets_risk_updated': assets_updated,
            'stats': stats,
            'status': 'success'
        }

    except Exception as e:
        tenant_logger.error(f"Nuclei scan failed: {e}", exc_info=True)
        return {
            'tenant_id': tenant_id,
            'error': str(e),
            'status': 'failed'
        }
    finally:
        db.close()


@celery.task(name='app.tasks.scanning.scan_single_asset')
def scan_single_asset(
    tenant_id: int,
    asset_id: int,
    severity: Optional[List[str]] = None,
    templates: Optional[List[str]] = None
):
    """
    Scan a single asset (convenience wrapper)

    Args:
        tenant_id: Tenant ID
        asset_id: Asset ID to scan
        severity: Severity filter
        templates: Template paths

    Returns:
        Dict with scan results
    """
    return run_nuclei_scan(
        tenant_id=tenant_id,
        asset_ids=[asset_id],
        severity=severity,
        templates=templates
    )


@celery.task(name='app.tasks.scanning.scan_critical_assets')
def scan_critical_assets(tenant_id: int):
    """
    Scan assets with critical priority

    Triggered automatically for high-priority assets.

    Args:
        tenant_id: Tenant ID

    Returns:
        Dict with scan results
    """
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        # Get critical priority assets
        assets = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.priority == 'critical',
            Asset.is_active == True
        ).all()

        if not assets:
            return {
                'assets_scanned': 0,
                'status': 'no_critical_assets'
            }

        asset_ids = [asset.id for asset in assets]

        # Scan with critical/high severity only
        return run_nuclei_scan(
            tenant_id=tenant_id,
            asset_ids=asset_ids,
            severity=['critical', 'high']
        )

    finally:
        db.close()


def update_asset_risk_scores(
    tenant_id: int,
    asset_ids: List[int],
    db
) -> int:
    """
    Update risk scores for assets based on their findings

    Risk scoring algorithm:
    - Base score from existing risk_score
    - Add points for findings by severity:
        - Critical: +3.0
        - High: +2.0
        - Medium: +1.0
        - Low: +0.5
        - Info: +0.1
    - Cap at 10.0

    Args:
        tenant_id: Tenant ID
        asset_ids: List of asset IDs to update
        db: Database session

    Returns:
        Number of assets updated
    """
    finding_repo = FindingRepository(db)
    updated_count = 0

    for asset_id in asset_ids:
        # Get asset
        asset = db.query(Asset).filter_by(id=asset_id, tenant_id=tenant_id).first()
        if not asset:
            continue

        # Get open findings for asset
        findings = finding_repo.get_findings(
            tenant_id=tenant_id,
            asset_id=asset_id,
            status=['open']
        )

        # Convert to dicts for scoring function
        findings_dicts = [
            {'severity': f.severity.value}
            for f in findings
        ]

        # Calculate risk score from findings
        findings_score = calculate_risk_score_from_findings(findings_dicts)

        # Update asset risk score
        # Note: We could also factor in other risk signals here
        # (e.g., exposed services, weak TLS, etc.)
        asset.risk_score = min(findings_score, 10.0)

        # Update priority based on risk score if auto-calculated
        if asset.priority_auto_calculated:
            if asset.risk_score >= 7.0:
                asset.priority = 'critical'
            elif asset.risk_score >= 5.0:
                asset.priority = 'high'
            elif asset.risk_score >= 2.0:
                asset.priority = 'normal'
            else:
                asset.priority = 'low'

            asset.priority_updated_at = datetime.utcnow()

        updated_count += 1

    db.commit()

    return updated_count


@celery.task(name='app.tasks.scanning.update_nuclei_templates')
def update_nuclei_templates():
    """
    Update Nuclei templates from ProjectDiscovery repository

    Should be run periodically (e.g., daily) to get latest templates.

    Returns:
        Dict with update results
    """
    from app.services.scanning.template_manager import template_manager

    logger.info("Updating Nuclei templates...")

    try:
        result = template_manager.update_templates()

        if result['success']:
            logger.info("Nuclei templates updated successfully")
        else:
            logger.error(f"Template update failed: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"Failed to update templates: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@celery.task(name='app.tasks.scanning.calculate_comprehensive_risk_scores')
def calculate_comprehensive_risk_scores(tenant_id: int):
    """
    Calculate comprehensive risk scores for all tenant assets

    Sprint 5: Comprehensive risk scoring engine considering:
    - Vulnerability findings (Nuclei)
    - Certificate/TLS issues (expiry, mismatches)
    - Exposed high-risk ports (SSH, RDP, databases)
    - Service security (login pages, HTTP vs HTTPS)
    - Asset age (new assets get monitoring bonus)

    This task should be run after enrichment pipelines complete.

    Args:
        tenant_id: Tenant ID to calculate scores for

    Returns:
        Dict with calculation results and statistics
    """
    from app.database import SessionLocal
    from app.services.risk_scoring import batch_calculate_risk_scores

    db = SessionLocal()
    tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})

    try:
        tenant_logger.info("Starting comprehensive risk score calculation")

        # Calculate risk scores for all assets
        result = batch_calculate_risk_scores(db, tenant_id, batch_size=100)

        tenant_logger.info(
            f"Risk scoring complete: {result['updated']}/{result['total_assets']} "
            f"assets updated"
        )

        return {
            'tenant_id': tenant_id,
            'success': True,
            **result,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        tenant_logger.error(f"Risk scoring failed: {e}", exc_info=True)
        return {
            'tenant_id': tenant_id,
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
    finally:
        db.close()


@celery.task(name='app.tasks.scanning.calculate_all_tenant_risk_scores')
def calculate_all_tenant_risk_scores():
    """
    Calculate comprehensive risk scores for all tenants

    This is a scheduled task that runs periodically to update
    risk scores across all tenants.

    Should be run after enrichment and scanning pipelines.

    Returns:
        Dict with overall statistics
    """
    from app.database import SessionLocal
    from app.models.database import Tenant

    db = SessionLocal()

    try:
        tenants = db.query(Tenant).all()
        logger.info(f"Calculating risk scores for {len(tenants)} tenants")

        results = []

        for tenant in tenants:
            try:
                result = calculate_comprehensive_risk_scores.delay(tenant.id).get()
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to calculate risk scores for tenant {tenant.id}: {e}")
                results.append({
                    'tenant_id': tenant.id,
                    'success': False,
                    'error': str(e)
                })

        successful = sum(1 for r in results if r.get('success'))
        failed = len(results) - successful

        logger.info(f"Risk scoring complete: {successful} successful, {failed} failed")

        return {
            'total_tenants': len(tenants),
            'successful': successful,
            'failed': failed,
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to calculate risk scores for all tenants: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
    finally:
        db.close()
