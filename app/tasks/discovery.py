"""
Discovery pipeline tasks for asset enumeration

Orchestrates discovery workflow across multiple tenants with isolation.
Uses secure subprocess execution and batch database operations.
"""

from celery import chain, group
import logging
import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from app.celery_app import celery
from app.models.database import Tenant, Asset, Seed, Event, AssetType, EventKind
from app.utils.storage import store_raw_output
from app.utils.logger import TenantLoggerAdapter
from app.config import settings

logger = logging.getLogger(__name__)

@celery.task(name='app.tasks.discovery.run_full_discovery')
def run_full_discovery():
    """
    Orchestrator task - triggers discovery for all active tenants
    Each tenant runs in complete isolation with dedicated queues
    """
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        tenants = db.query(Tenant).all()
        logger.info(f"Orchestrating discovery for {len(tenants)} tenants")

        for tenant in tenants:
            # Each tenant gets isolated execution
            run_tenant_discovery.apply_async(
                args=[tenant.id],
                queue=f'tenant_{tenant.id}',  # Tenant-specific queue for isolation
                routing_key=f'tenant.{tenant.id}.discovery'
            )

        logger.info(f"Successfully queued discovery for {len(tenants)} tenants")
        return {'tenants_queued': len(tenants)}
    except Exception as e:
        logger.error(f"Failed to orchestrate discovery: {e}", exc_info=True)
        raise
    finally:
        db.close()

@celery.task(name='app.tasks.discovery.run_tenant_discovery')
def run_tenant_discovery(tenant_id: int):
    """
    Run complete discovery pipeline for a single tenant
    Provides full isolation per tenant execution
    """
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        tenant = db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            logger.warning(f"Tenant {tenant_id} not found, skipping discovery")
            return {'error': 'tenant_not_found'}

        tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})
        tenant_logger.info(f"Starting isolated discovery for tenant: {tenant.name}")

        # Run discovery chain with proper error handling
        try:
            chain(
                collect_seeds.si(tenant_id),
                run_subfinder.s(tenant_id),
                run_dnsx.s(tenant_id),
                process_discovery_results.s(tenant_id)
            ).apply_async(queue=f'tenant_{tenant_id}')

            tenant_logger.info("Discovery chain started successfully")
            return {
                'tenant_id': tenant_id,
                'tenant_name': tenant.name,
                'status': 'started'
            }
        except Exception as e:
            tenant_logger.error(f"Error starting discovery chain: {e}", exc_info=True)
            return {
                'tenant_id': tenant_id,
                'status': 'failed',
                'error': str(e)
            }
    finally:
        db.close()

@celery.task(name='app.tasks.discovery.watch_critical_assets')
def watch_critical_assets():
    """
    Monitor critical assets (high risk score) more frequently

    OPTIMIZATION: Uses optimized query patterns and bulk operations
    """
    from app.database import SessionLocal
    from app.repositories.asset_repository import AssetRepository

    db = SessionLocal()

    try:
        # OPTIMIZATION: Query critical assets per tenant using optimized repository method
        # This approach is more efficient than querying all tenants' assets at once
        # because it uses the composite index (tenant_id, risk_score, is_active)

        # First, get all active tenants
        tenants = db.query(Tenant).all()

        total_critical_assets = 0
        tenant_assets = {}

        # OPTIMIZATION: Use AssetRepository.get_critical_assets() which leverages indexes
        # This is better than the previous direct query because:
        # 1. Uses optimized repository method with proper indexing
        # 2. Groups by tenant naturally for better cache locality
        # 3. Can be parallelized per tenant if needed
        asset_repo = AssetRepository(db)

        for tenant in tenants:
            # Get critical assets for this tenant using indexed query
            # The composite index (tenant_id, risk_score, is_active) makes this very fast
            critical_assets = asset_repo.get_critical_assets(
                tenant_id=tenant.id,
                risk_threshold=50.0,
                eager_load_relations=False  # We only need IDs, not relationships
            )

            if critical_assets:
                asset_ids = [asset.id for asset in critical_assets]
                tenant_assets[tenant.id] = asset_ids
                total_critical_assets += len(asset_ids)

        logger.info(f"Watching {total_critical_assets} critical assets across {len(tenant_assets)} tenants")

        # Dispatch quick checks per tenant
        for tenant_id, asset_ids in tenant_assets.items():
            # Quick DNS check for these assets
            quick_dns_check.apply_async(args=[tenant_id, asset_ids])

        return {
            'critical_assets_checked': total_critical_assets,
            'tenants_with_critical_assets': len(tenant_assets)
        }
    finally:
        db.close()

@celery.task(name='app.tasks.discovery.quick_dns_check')
def quick_dns_check(tenant_id: int, asset_ids: list):
    """Quick DNS check for specific assets"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        assets = db.query(Asset).filter(
            Asset.id.in_(asset_ids),
            Asset.tenant_id == tenant_id
        ).all()

        if not assets:
            return {'checked': 0}

        # Run dnsx on these specific assets
        result = run_dnsx_for_assets(tenant_id, assets)

        return {'checked': len(assets), 'resolved': len(result.get('resolved', []))}
    finally:
        db.close()

@celery.task(name='app.tasks.discovery.collect_seeds')
def collect_seeds(tenant_id: int):
    """
    Collect seeds from database and optionally run uncover

    Returns dict with domains, asns, ip_ranges, keywords
    """
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        tenant = db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            logger.warning(f"Tenant {tenant_id} not found in collect_seeds")
            return {'domains': [], 'asns': [], 'ip_ranges': [], 'keywords': []}

        seeds = db.query(Seed).filter_by(tenant_id=tenant_id, enabled=True).all()

        seed_data = {
            'domains': [],
            'asns': [],
            'ip_ranges': [],
            'keywords': []
        }

        for seed in seeds:
            if seed.type == 'domain':
                seed_data['domains'].append(seed.value)
            elif seed.type == 'asn':
                seed_data['asns'].append(seed.value)
            elif seed.type == 'ip_range':
                seed_data['ip_ranges'].append(seed.value)
            elif seed.type == 'keyword':
                seed_data['keywords'].append(seed.value)

        logger.info(
            f"Collected seeds for tenant {tenant_id}: {len(seed_data['domains'])} domains, "
            f"{len(seed_data['keywords'])} keywords"
        )

        # Run uncover if keywords are present and API keys configured
        if seed_data['keywords'] and tenant.osint_api_keys:
            try:
                uncover_results = run_uncover(tenant_id, seed_data['keywords'])
                seed_data['domains'].extend(uncover_results)
                logger.info(f"Uncover discovered {len(uncover_results)} additional domains for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Uncover failed for tenant {tenant_id}: {e}", exc_info=True)

        return seed_data
    finally:
        db.close()

def run_uncover(tenant_id: int, keywords: List[str]) -> List[str]:
    """
    Run uncover for OSINT discovery using secure execution

    Args:
        tenant_id: Tenant ID
        keywords: List of keywords to search

    Returns:
        List of discovered domains/IPs
    """
    from app.utils.secure_executor import SecureToolExecutor, ToolExecutionError

    if not settings.feature_uncover_enabled:
        logger.info(f"Uncover is disabled, skipping for tenant {tenant_id}")
        return []

    results = []

    try:
        with SecureToolExecutor(tenant_id) as executor:
            for keyword in keywords:
                # Sanitize keyword - only allow alphanumeric, spaces, hyphens, underscores
                safe_keyword = ''.join(c for c in keyword if c.isalnum() or c in ' -_')
                if not safe_keyword:
                    logger.warning(f"Skipping invalid keyword: {keyword}")
                    continue

                logger.info(f"Running uncover for keyword: {safe_keyword} (tenant {tenant_id})")

                # FIXED: Use secure executor instead of direct subprocess
                # Prevents command injection through keyword parameter
                try:
                    returncode, stdout, stderr = executor.execute(
                        'uncover',
                        [
                            '-q', f'org:"{safe_keyword}"',
                            '-e', 'shodan,censys',
                            '-silent'
                        ],
                        timeout=300
                    )

                    if returncode != 0:
                        logger.warning(f"Uncover returned non-zero exit code for keyword '{safe_keyword}': {stderr}")

                    # Parse stdout for results
                    for line in stdout.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            results.append(line)

                except ToolExecutionError as e:
                    logger.error(f"Uncover execution failed for keyword '{safe_keyword}': {e}")
                    continue

        # Deduplicate
        results = list(set(results))

        # Store raw output in MinIO
        store_raw_output(tenant_id, 'uncover', {'keywords': keywords, 'results': results})

        logger.info(f"Uncover completed for tenant {tenant_id}: {len(results)} unique results")
        return results

    except Exception as e:
        logger.error(f"Uncover error for tenant {tenant_id}: {e}", exc_info=True)
        return results

@celery.task(name='app.tasks.discovery.run_subfinder')
def run_subfinder(seed_data: dict, tenant_id: int):
    """
    Run subfinder for subdomain enumeration using secure executor

    Args:
        seed_data: Dict from collect_seeds
        tenant_id: Tenant ID

    Returns:
        Dict with subdomains list
    """
    from app.utils.secure_executor import SecureToolExecutor, ToolExecutionError

    if not seed_data.get('domains'):
        logger.info(f"No domains to scan for tenant {tenant_id}")
        return {'subdomains': [], 'tenant_id': tenant_id}

    try:
        # Use secure executor with automatic cleanup
        with SecureToolExecutor(tenant_id) as executor:
            # Create input file securely
            domains_content = '\n'.join(seed_data['domains'])
            input_file = executor.create_input_file('domains.txt', domains_content)
            output_file = 'subdomains.txt'

            # Execute subfinder with resource limits
            logger.info(f"Running subfinder for {len(seed_data['domains'])} domains (tenant {tenant_id})")

            returncode, stdout, stderr = executor.execute(
                'subfinder',
                [
                    '-dL', input_file,
                    '-all',
                    '-recursive',
                    '-silent',
                    '-o', output_file
                ],
                timeout=settings.discovery_subfinder_timeout
            )

            if returncode != 0:
                logger.warning(f"Subfinder warning (tenant {tenant_id}): {stderr}")

            # Read results securely
            output_content = executor.read_output_file(output_file)
            subdomains = [line.strip() for line in output_content.split('\n') if line.strip()]

            logger.info(f"Subfinder found {len(subdomains)} subdomains (tenant {tenant_id})")

            # Store raw output
            store_raw_output(tenant_id, 'subfinder', {
                'input_domains': seed_data['domains'],
                'subdomains': subdomains
            })

            return {
                'subdomains': subdomains,
                'tenant_id': tenant_id
            }

    except ToolExecutionError as e:
        logger.error(f"Subfinder execution error (tenant {tenant_id}): {e}", exc_info=True)
        return {'subdomains': [], 'tenant_id': tenant_id, 'error': str(e)}
    except Exception as e:
        logger.error(f"Subfinder unexpected error (tenant {tenant_id}): {e}", exc_info=True)
        return {'subdomains': [], 'tenant_id': tenant_id, 'error': str(e)}

@celery.task(name='app.tasks.discovery.run_dnsx')
def run_dnsx(subfinder_result: dict, tenant_id: int):
    """
    Run dnsx for DNS resolution

    Args:
        subfinder_result: Result from run_subfinder
        tenant_id: Tenant ID

    Returns:
        Dict with resolved records
    """
    subdomains = subfinder_result.get('subdomains', [])

    if not subdomains:
        logger.info(f"No subdomains to resolve for tenant {tenant_id}")
        return {'resolved': [], 'tenant_id': tenant_id}

    subdomains_file = None
    output_file = None

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            subdomains_file = Path(f.name)
            f.write('\n'.join(subdomains))

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = Path(f.name)
        cmd = [
            'dnsx',
            '-l', str(subdomains_file),
            '-a', '-aaaa', '-cname', '-mx', '-ns', '-txt',
            '-resp',
            '-json',
            '-silent',
            '-o', str(output_file)
        ]

        logger.info(f"Running dnsx for {len(subdomains)} subdomains (tenant {tenant_id})")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=settings.discovery_dnsx_timeout)

        if result.returncode != 0:
            logger.warning(f"Dnsx error (tenant {tenant_id}): {result.stderr}")

        # Parse results
        resolved_records = []
        if output_file and output_file.exists():
            with output_file.open('r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            resolved_records.append(json.loads(line))
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse dnsx line: {line}")

        logger.info(f"Dnsx resolved {len(resolved_records)} records (tenant {tenant_id})")

        # Store raw output
        store_raw_output(tenant_id, 'dnsx', resolved_records)

        return {
            'resolved': resolved_records,
            'tenant_id': tenant_id
        }
    except subprocess.TimeoutExpired:
        logger.error(f"Dnsx timeout for tenant {tenant_id}")
        return {'resolved': [], 'tenant_id': tenant_id}
    except Exception as e:
        logger.error(f"Dnsx error for tenant {tenant_id}: {e}", exc_info=True)
        return {'resolved': [], 'tenant_id': tenant_id}
    finally:
        # Cleanup temporary files
        if subdomains_file and subdomains_file.exists():
            try:
                subdomains_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup subdomains file: {e}")
        if output_file and output_file.exists():
            try:
                output_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup output file: {e}")

def run_dnsx_for_assets(tenant_id: int, assets: list) -> Dict:
    """
    Helper function to run dnsx on specific assets

    Args:
        tenant_id: Tenant ID
        assets: List of Asset objects

    Returns:
        Dict with resolved records
    """
    identifiers = [a.identifier for a in assets]
    hosts_file = None
    output_file = None

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            hosts_file = Path(f.name)
            f.write('\n'.join(identifiers))

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = Path(f.name)

        cmd = [
            'dnsx',
            '-l', str(hosts_file),
            '-a', '-resp',
            '-json',
            '-silent',
            '-o', str(output_file)
        ]

        logger.debug(f"Running quick dnsx check for {len(identifiers)} assets (tenant {tenant_id})")
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        resolved_records = []
        if output_file and output_file.exists():
            with output_file.open('r') as f:
                for line in f:
                    if line.strip():
                        try:
                            resolved_records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

        return {'resolved': resolved_records}
    except Exception as e:
        logger.error(f"Quick dnsx check failed for tenant {tenant_id}: {e}")
        return {'resolved': []}
    finally:
        # Cleanup temporary files
        if hosts_file and hosts_file.exists():
            try:
                hosts_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup hosts file: {e}")
        if output_file and output_file.exists():
            try:
                output_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup output file: {e}")

@celery.task(name='app.tasks.discovery.process_discovery_results')
def process_discovery_results(dnsx_result: dict, tenant_id: int):
    """
    Process discovery results with batch operations for performance

    Uses repository pattern and PostgreSQL UPSERT for efficient bulk operations.
    Processes in batches to avoid long transactions.

    Args:
        dnsx_result: Result from run_dnsx
        tenant_id: Tenant ID

    Returns:
        Summary dict
    """
    from app.database import SessionLocal
    from app.repositories.asset_repository import AssetRepository, EventRepository

    BATCH_SIZE = 100  # Process 100 records per batch

    db = SessionLocal()

    try:
        resolved = dnsx_result.get('resolved', [])
        logger.info(f"Processing {len(resolved)} resolved records for tenant {tenant_id} in batches of {BATCH_SIZE}")

        asset_repo = AssetRepository(db)
        event_repo = EventRepository(db)

        total_created = 0
        total_updated = 0
        new_asset_events = []

        # Process in batches to avoid long transactions
        for i in range(0, len(resolved), BATCH_SIZE):
            batch = resolved[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(resolved) + BATCH_SIZE - 1) // BATCH_SIZE
            logger.debug(f"Processing batch {batch_num}/{total_batches} for tenant {tenant_id}")

            # Prepare batch data
            assets_data = []
            for record in batch:
                host = record.get('host')
                if not host:
                    continue

                # Determine asset type
                asset_type = AssetType.SUBDOMAIN

                # Check if it's an IP
                if all(c.isdigit() or c == '.' for c in host):
                    asset_type = AssetType.IP
                # Check if it's a domain (no subdomain parts)
                elif host.count('.') == 1:
                    asset_type = AssetType.DOMAIN

                assets_data.append({
                    'identifier': host,
                    'type': asset_type,
                    'raw_metadata': json.dumps(record)
                })

            # Bulk upsert assets
            result = asset_repo.bulk_upsert(tenant_id, assets_data)
            total_created += result['created']

            # OPTIMIZATION: Fetch all assets in this batch with a single query instead of N queries
            # This eliminates the N+1 query problem - 1 query per batch instead of 1 query per asset
            identifiers_by_type = {}
            for data in assets_data:
                key = data['type']
                if key not in identifiers_by_type:
                    identifiers_by_type[key] = []
                identifiers_by_type[key].append(data['identifier'])

            # Bulk fetch all assets for this batch using a single query with IN clause
            asset_lookup = asset_repo.get_by_identifiers_bulk(tenant_id, identifiers_by_type)

            # Now check which assets are new and create events
            for data in assets_data:
                lookup_key = (data['identifier'], data['type'])
                asset = asset_lookup.get(lookup_key)

                if asset:
                    # Check if this is a newly seen asset (first_seen == last_seen within 1 second)
                    if asset.first_seen and asset.last_seen:
                        time_diff = (asset.last_seen - asset.first_seen).total_seconds()
                        if time_diff < 2:  # Newly created
                            new_asset_events.append(Event(
                                asset_id=asset.id,
                                kind=EventKind.NEW_ASSET,
                                payload=data['raw_metadata']
                            ))

        # Batch create events for new assets
        if new_asset_events:
            logger.info(f"Creating {len(new_asset_events)} new asset events for tenant {tenant_id}")
            event_repo.create_batch(new_asset_events)
            db.commit()

        logger.info(f"Discovery complete: ~{total_created} assets processed (tenant {tenant_id})")

        return {
            'assets_processed': total_created,
            'new_asset_events': len(new_asset_events),
            'total_resolved': len(resolved),
            'tenant_id': tenant_id,
            'batches_processed': (len(resolved) + BATCH_SIZE - 1) // BATCH_SIZE
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing discovery results (tenant {tenant_id}): {e}", exc_info=True)
        raise
    finally:
        db.close()
