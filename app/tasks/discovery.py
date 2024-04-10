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
    """Run full discovery for all active tenants"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        tenants = db.query(Tenant).all()
        print(f"Starting full discovery for {len(tenants)} tenants")

        for tenant in tenants:
            # Run discovery chain for each tenant
            chain(
                collect_seeds.si(tenant.id),
                run_subfinder.s(tenant.id),
                run_dnsx.s(tenant.id),
                process_discovery_results.s(tenant.id)
            ).apply_async()

        return {'tenants_processed': len(tenants)}
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
    Run subfinder for subdomain enumeration

    Args:
        seed_data: Dict from collect_seeds
        tenant_id: Tenant ID

    Returns:
        Dict with subdomains list
    """
    if not seed_data.get('domains'):
        print(f"No domains to scan for tenant {tenant_id}")
        return {'subdomains': [], 'tenant_id': tenant_id}

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        domains_file = f.name
        f.write('\n'.join(seed_data['domains']))

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        output_file = f.name

    try:
        cmd = [
            'subfinder',
            '-dL', domains_file,
            '-all',
            '-recursive',
            '-silent',
            '-o', output_file
        ]

        print(f"Running subfinder for {len(seed_data['domains'])} domains")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            print(f"Subfinder error: {result.stderr}")

        # Read results
        subdomains = []
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        subdomains.append(line)

        print(f"Subfinder found {len(subdomains)} subdomains")

        # Store raw output
        store_raw_output(tenant_id, 'subfinder', {'input_domains': seed_data['domains'], 'subdomains': subdomains})

        return {
            'subdomains': subdomains,
            'tenant_id': tenant_id
        }
    except subprocess.TimeoutExpired:
        print(f"Subfinder timeout")
        return {'subdomains': [], 'tenant_id': tenant_id}
    except Exception as e:
        print(f"Subfinder error: {e}")
        return {'subdomains': [], 'tenant_id': tenant_id}
    finally:
        if os.path.exists(domains_file):
            os.unlink(domains_file)
        if os.path.exists(output_file):
            os.unlink(output_file)

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
    Process discovery results and store in database

    Args:
        dnsx_result: Result from run_dnsx
        tenant_id: Tenant ID

    Returns:
        Summary dict
    """
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        resolved = dnsx_result.get('resolved', [])
        new_assets = []
        updated_assets = []

        print(f"Processing {len(resolved)} resolved records for tenant {tenant_id}")

        for record in resolved:
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

            # Check if asset exists
            existing = db.query(Asset).filter_by(
                tenant_id=tenant_id,
                identifier=host,
                type=asset_type
            ).first()

            if existing:
                # Update last seen
                existing.last_seen = datetime.utcnow()
                existing.metadata = json.dumps(record)
                updated_assets.append(host)
            else:
                # Create new asset
                asset = Asset(
                    tenant_id=tenant_id,
                    type=asset_type,
                    identifier=host,
                    metadata=json.dumps(record)
                )
                db.add(asset)
                db.flush()  # Get the ID

                # Create event for new asset
                event = Event(
                    asset_id=asset.id,
                    kind=EventKind.NEW_ASSET,
                    payload=json.dumps({'record': record})
                )
                db.add(event)

                new_assets.append(host)

        db.commit()

        print(f"Discovery complete: {len(new_assets)} new assets, {len(updated_assets)} updated")

        return {
            'new_assets': len(new_assets),
            'updated_assets': len(updated_assets),
            'total_resolved': len(resolved),
            'tenant_id': tenant_id
        }
    except Exception as e:
        db.rollback()
        print(f"Error processing discovery results: {e}")
        raise
    finally:
        db.close()
