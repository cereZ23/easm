from celery import chain, group
from app.celery_app import celery
from app.models.database import Tenant, Asset, Seed, Event, AssetType, EventKind
from app.utils.storage import store_raw_output
from datetime import datetime
import subprocess
import json
import tempfile
import os

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
        print(f"Orchestrating discovery for {len(tenants)} tenants")

        for tenant in tenants:
            # Each tenant gets isolated execution
            run_tenant_discovery.apply_async(
                args=[tenant.id],
                queue=f'tenant_{tenant.id}',  # Tenant-specific queue for isolation
                routing_key=f'tenant.{tenant.id}.discovery'
            )

        return {'tenants_queued': len(tenants)}
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
            print(f"Tenant {tenant_id} not found, skipping discovery")
            return {'error': 'tenant_not_found'}

        print(f"Starting isolated discovery for tenant {tenant_id}: {tenant.name}")

        # Run discovery chain with proper error handling
        try:
            chain(
                collect_seeds.si(tenant_id),
                run_subfinder.s(tenant_id),
                run_dnsx.s(tenant_id),
                process_discovery_results.s(tenant_id)
            ).apply_async(queue=f'tenant_{tenant_id}')

            return {
                'tenant_id': tenant_id,
                'tenant_name': tenant.name,
                'status': 'started'
            }
        except Exception as e:
            print(f"Error starting discovery chain for tenant {tenant_id}: {e}")
            return {
                'tenant_id': tenant_id,
                'status': 'failed',
                'error': str(e)
            }
    finally:
        db.close()

@celery.task(name='app.tasks.discovery.watch_critical_assets')
def watch_critical_assets():
    """Monitor critical assets (high risk score) more frequently"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        # Get assets with risk score > 50
        critical_assets = db.query(Asset).filter(
            Asset.risk_score > 50,
            Asset.is_active == True
        ).all()

        print(f"Watching {len(critical_assets)} critical assets")

        # Group by tenant and run quick checks
        tenant_assets = {}
        for asset in critical_assets:
            if asset.tenant_id not in tenant_assets:
                tenant_assets[asset.tenant_id] = []
            tenant_assets[asset.tenant_id].append(asset.id)

        for tenant_id, asset_ids in tenant_assets.items():
            # Quick DNS check for these assets
            quick_dns_check.apply_async(args=[tenant_id, asset_ids])

        return {'critical_assets_checked': len(critical_assets)}
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
            print(f"Tenant {tenant_id} not found")
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

        print(f"Collected seeds for tenant {tenant_id}: {len(seed_data['domains'])} domains, "
              f"{len(seed_data['keywords'])} keywords")

        # Run uncover if keywords are present and API keys configured
        if seed_data['keywords'] and tenant.api_keys:
            try:
                uncover_results = run_uncover(tenant_id, seed_data['keywords'])
                seed_data['domains'].extend(uncover_results)
                print(f"Uncover discovered {len(uncover_results)} additional domains")
            except Exception as e:
                print(f"Uncover failed: {e}")

        return seed_data
    finally:
        db.close()

def run_uncover(tenant_id: int, keywords: list) -> list:
    """
    Run uncover for OSINT discovery

    Args:
        tenant_id: Tenant ID
        keywords: List of keywords to search

    Returns:
        List of discovered domains/IPs
    """
    results = []

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        output_file = f.name

    try:
        for keyword in keywords:
            cmd = [
                'uncover',
                '-q', f'org:"{keyword}"',
                '-e', 'shodan,censys',
                '-silent',
                '-o', output_file
            ]

            print(f"Running uncover for keyword: {keyword}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                print(f"Uncover error: {result.stderr}")

            # Read results
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            results.append(line)

        # Deduplicate
        results = list(set(results))

        # Store raw output in MinIO
        store_raw_output(tenant_id, 'uncover', {'keywords': keywords, 'results': results})

        return results
    except subprocess.TimeoutExpired:
        print(f"Uncover timeout for keywords: {keywords}")
        return results
    except Exception as e:
        print(f"Uncover error: {e}")
        return results
    finally:
        if os.path.exists(output_file):
            os.unlink(output_file)

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
        print(f"No domains to scan for tenant {tenant_id}")
        return {'subdomains': [], 'tenant_id': tenant_id}

    try:
        # Use secure executor with automatic cleanup
        with SecureToolExecutor(tenant_id) as executor:
            # Create input file securely
            domains_content = '\n'.join(seed_data['domains'])
            input_file = executor.create_input_file('domains.txt', domains_content)
            output_file = 'subdomains.txt'

            # Execute subfinder with resource limits
            print(f"Running subfinder for {len(seed_data['domains'])} domains (tenant {tenant_id})")

            returncode, stdout, stderr = executor.execute(
                'subfinder',
                [
                    '-dL', input_file,
                    '-all',
                    '-recursive',
                    '-silent',
                    '-o', output_file
                ],
                timeout=600
            )

            if returncode != 0:
                print(f"Subfinder warning (tenant {tenant_id}): {stderr}")

            # Read results securely
            output_content = executor.read_output_file(output_file)
            subdomains = [line.strip() for line in output_content.split('\n') if line.strip()]

            print(f"Subfinder found {len(subdomains)} subdomains (tenant {tenant_id})")

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
        print(f"Subfinder execution error (tenant {tenant_id}): {e}")
        return {'subdomains': [], 'tenant_id': tenant_id, 'error': str(e)}
    except Exception as e:
        print(f"Subfinder unexpected error (tenant {tenant_id}): {e}")
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
        print(f"No subdomains to resolve for tenant {tenant_id}")
        return {'resolved': [], 'tenant_id': tenant_id}

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        subdomains_file = f.name
        f.write('\n'.join(subdomains))

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        output_file = f.name

    try:
        cmd = [
            'dnsx',
            '-l', subdomains_file,
            '-a', '-aaaa', '-cname', '-mx', '-ns', '-txt',
            '-resp',
            '-json',
            '-silent',
            '-o', output_file
        ]

        print(f"Running dnsx for {len(subdomains)} subdomains")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            print(f"Dnsx error: {result.stderr}")

        # Parse results
        resolved_records = []
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            resolved_records.append(json.loads(line))
                        except json.JSONDecodeError:
                            print(f"Failed to parse dnsx line: {line}")

        print(f"Dnsx resolved {len(resolved_records)} records")

        # Store raw output
        store_raw_output(tenant_id, 'dnsx', resolved_records)

        return {
            'resolved': resolved_records,
            'tenant_id': tenant_id
        }
    except subprocess.TimeoutExpired:
        print(f"Dnsx timeout")
        return {'resolved': [], 'tenant_id': tenant_id}
    except Exception as e:
        print(f"Dnsx error: {e}")
        return {'resolved': [], 'tenant_id': tenant_id}
    finally:
        if os.path.exists(subdomains_file):
            os.unlink(subdomains_file)
        if os.path.exists(output_file):
            os.unlink(output_file)

def run_dnsx_for_assets(tenant_id: int, assets: list):
    """Helper function to run dnsx on specific assets"""
    identifiers = [a.identifier for a in assets]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        hosts_file = f.name
        f.write('\n'.join(identifiers))

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        output_file = f.name

    try:
        cmd = [
            'dnsx',
            '-l', hosts_file,
            '-a', '-resp',
            '-json',
            '-silent',
            '-o', output_file
        ]

        subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        resolved_records = []
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            resolved_records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

        return {'resolved': resolved_records}
    finally:
        if os.path.exists(hosts_file):
            os.unlink(hosts_file)
        if os.path.exists(output_file):
            os.unlink(output_file)

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
        print(f"Processing {len(resolved)} resolved records for tenant {tenant_id} in batches of {BATCH_SIZE}")

        asset_repo = AssetRepository(db)
        event_repo = EventRepository(db)

        total_created = 0
        total_updated = 0
        new_asset_events = []

        # Process in batches to avoid long transactions
        for i in range(0, len(resolved), BATCH_SIZE):
            batch = resolved[i:i + BATCH_SIZE]
            print(f"Processing batch {i // BATCH_SIZE + 1}/{(len(resolved) + BATCH_SIZE - 1) // BATCH_SIZE}")

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

            # For new assets, we'll create events in a follow-up query
            # This is a simplification - in production you'd want to track which are truly new
            # For now, we'll create events for all in this batch as an approximation
            for data in assets_data:
                # Get the asset to create event
                asset = asset_repo.get_by_identifier(
                    tenant_id,
                    data['identifier'],
                    data['type']
                )
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
            print(f"Creating {len(new_asset_events)} new asset events")
            event_repo.create_batch(new_asset_events)
            db.commit()

        print(f"Discovery complete: ~{total_created} assets processed (tenant {tenant_id})")

        return {
            'assets_processed': total_created,
            'new_asset_events': len(new_asset_events),
            'total_resolved': len(resolved),
            'tenant_id': tenant_id,
            'batches_processed': (len(resolved) + BATCH_SIZE - 1) // BATCH_SIZE
        }

    except Exception as e:
        db.rollback()
        print(f"Error processing discovery results (tenant {tenant_id}): {e}")
        raise
    finally:
        db.close()
