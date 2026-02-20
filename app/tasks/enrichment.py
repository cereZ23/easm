"""
Enrichment pipeline tasks for asset enrichment

Sprint 2: Implements HTTP fingerprinting (HTTPx), port scanning (Naabu),
TLS/SSL analysis (TLSx), and web crawling (Katana) with comprehensive
security controls and tiered enrichment based on asset priority.

Security Features:
- Input validation (DomainValidator, URLValidator)
- SSRF prevention (network blocklists)
- Output sanitization (private key detection, credential redaction)
- Resource limits (timeout, memory, CPU)
- Rate limiting per tenant
- Secure subprocess execution
"""

from celery import chain, group
import logging
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from app.celery_app import celery
from app.models.database import Asset, AssetType
from app.models.enrichment import Certificate, Endpoint
from app.utils.storage import store_raw_output
from app.utils.logger import TenantLoggerAdapter
from app.utils.validators import DomainValidator, URLValidator
from app.utils.secure_executor import SecureToolExecutor, ToolExecutionError
from app.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# ENRICHMENT ORCHESTRATION
# =============================================================================

@celery.task(name='app.tasks.enrichment.run_enrichment_pipeline')
def run_enrichment_pipeline(
    tenant_id: int,
    asset_ids: Optional[List[int]] = None,
    priority: Optional[str] = None,
    force_refresh: bool = False
):
    """
    Run complete enrichment pipeline for assets

    Orchestrates parallel execution of HTTPx + Naabu + TLSx,
    followed by sequential Katana (which depends on HTTPx results).

    Args:
        tenant_id: Tenant ID
        asset_ids: Optional list of specific asset IDs to enrich
        priority: Optional priority level to enrich (critical, high, normal, low)
        force_refresh: If True, enrich even if recently enriched

    Returns:
        Dict with enrichment statistics

    Architecture:
        Phase 1 (Parallel): HTTPx + Naabu + TLSx run concurrently
        Phase 2 (Sequential): Katana runs after HTTPx completes
    """
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})
        tenant_logger.info(f"Starting enrichment pipeline (priority: {priority}, force: {force_refresh})")

        # Get enrichment candidates
        candidates = get_enrichment_candidates(
            tenant_id=tenant_id,
            asset_ids=asset_ids,
            priority=priority,
            force_refresh=force_refresh,
            db=db
        )

        if not candidates:
            tenant_logger.info("No assets need enrichment")
            return {'assets_enriched': 0, 'status': 'no_candidates'}

        tenant_logger.info(f"Enriching {len(candidates)} assets")

        # Phase 1: Run HTTPx + Naabu + TLSx in parallel using chord
        # IMPORTANT: chord() waits for all group tasks to complete before callback
        # group() + chain() doesn't wait, it proceeds after first task completes!
        parallel_tasks = [
            run_httpx.si(tenant_id, candidates),
            run_naabu.si(tenant_id, candidates),
            run_tlsx.si(tenant_id, candidates)
        ]

        # Phase 2: Run Katana after all enrichment completes
        # Phase 3: Run Nuclei after Katana (if enabled)
        # chord(group_of_tasks, callback) - callback runs after ALL group tasks complete
        from celery import chord

        if settings.feature_nuclei_enabled:
            from app.tasks.scanning import run_nuclei_scan

            # Use chord to wait for ALL enrichment tasks, then run Katana, then Nuclei
            # chord() returns an AsyncResult when called, don't call apply_async() again
            result = chord(parallel_tasks)(
                chain(
                    run_katana.si(tenant_id, candidates),
                    run_nuclei_scan.si(tenant_id, candidates, ['critical', 'high', 'medium'])
                )
            )
        else:
            # Use chord to wait for ALL enrichment tasks, then run Katana
            result = chord(parallel_tasks)(
                run_katana.si(tenant_id, candidates)
            )

        return {
            'tenant_id': tenant_id,
            'assets_queued': len(candidates),
            'status': 'started',
            'task_id': result.id
        }

    except Exception as e:
        logger.error(f"Error starting enrichment pipeline for tenant {tenant_id}: {e}", exc_info=True)
        return {'error': str(e), 'status': 'failed'}
    finally:
        db.close()


def get_enrichment_candidates(
    tenant_id: int,
    asset_ids: Optional[List[int]],
    priority: Optional[str],
    force_refresh: bool,
    db
) -> List[int]:
    """
    Get list of asset IDs that need enrichment

    Implements tiered enrichment with priority-based TTL:
    - critical: 1 day TTL
    - high: 3 days TTL
    - normal: 7 days TTL
    - low: 14 days TTL

    Args:
        tenant_id: Tenant ID
        asset_ids: Optional specific assets to enrich
        priority: Optional priority filter
        force_refresh: If True, return all active assets
        db: Database session

    Returns:
        List of asset IDs to enrich
    """
    # If specific asset IDs provided, use those
    if asset_ids:
        assets = db.query(Asset).filter(
            Asset.id.in_(asset_ids),
            Asset.tenant_id == tenant_id,
            Asset.is_active == True
        ).all()
        return [asset.id for asset in assets]

    # Get TTL for priority level
    ttl_map = {
        'critical': 1,   # 1 day
        'high': 3,       # 3 days
        'normal': 7,     # 7 days
        'low': 14        # 14 days
    }

    if force_refresh:
        # Return all active assets for this priority
        query = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.is_active == True
        )
        if priority:
            query = query.filter(Asset.priority == priority)

        assets = query.order_by(Asset.risk_score.desc()).limit(settings.enrichment_batch_size).all()
        return [asset.id for asset in assets]

    # Normal operation: Check TTL
    if priority:
        ttl_days = ttl_map.get(priority, 7)
        cutoff = datetime.utcnow() - timedelta(days=ttl_days)

        assets = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.is_active == True,
            Asset.priority == priority,
            (Asset.last_enriched_at.is_(None)) | (Asset.last_enriched_at < cutoff)
        ).order_by(Asset.risk_score.desc()).limit(settings.enrichment_batch_size).all()
    else:
        # No priority specified, enrich stale assets from all priorities
        # Most efficient: use single query with OR conditions for each priority
        from sqlalchemy import or_, and_

        priority_conditions = []
        for pri, days in ttl_map.items():
            cutoff = datetime.utcnow() - timedelta(days=days)
            priority_conditions.append(
                and_(
                    Asset.priority == pri,
                    (Asset.last_enriched_at.is_(None)) | (Asset.last_enriched_at < cutoff)
                )
            )

        assets = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.is_active == True,
            or_(*priority_conditions)
        ).order_by(Asset.risk_score.desc()).limit(settings.enrichment_batch_size).all()

    return [asset.id for asset in assets]


# =============================================================================
# HTTPX - HTTP TECHNOLOGY FINGERPRINTING
# =============================================================================

@celery.task(name='app.tasks.enrichment.run_httpx')
def run_httpx(tenant_id: int, asset_ids: List[int]):
    """
    Run HTTPx for HTTP technology fingerprinting

    Probes HTTP/HTTPS services to detect:
    - Web servers (nginx, Apache, IIS)
    - Technologies (WordPress, PHP, Node.js)
    - HTTP status codes and redirects
    - Response times and headers
    - TLS configuration

    Security Controls:
    - URL validation (URLValidator)
    - SSRF prevention (network blocklists)
    - Response size limits (1MB max)
    - Timeout limits (15 minutes max)
    - Credential redaction from headers

    Args:
        tenant_id: Tenant ID
        asset_ids: List of asset IDs to probe

    Returns:
        Dict with enrichment results
    """
    from app.database import SessionLocal
    from app.repositories.service_repository import ServiceRepository

    db = SessionLocal()
    tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})

    try:
        # Get assets
        assets = db.query(Asset).filter(
            Asset.id.in_(asset_ids),
            Asset.tenant_id == tenant_id
        ).all()

        if not assets:
            tenant_logger.warning(f"No assets found for HTTPx (IDs: {asset_ids})")
            return {'services_enriched': 0}

        # Build URL list from assets and maintain asset_id mapping
        # HTTPx accepts domains, IPs, and URLs
        urls = []
        url_to_asset_id = {}  # Map URLs to asset IDs for later matching
        url_validator = URLValidator()

        for asset in assets:
            if asset.type in [AssetType.DOMAIN, AssetType.SUBDOMAIN]:
                # Try both http and https
                for scheme in ['http', 'https']:
                    url = f"{scheme}://{asset.identifier}"
                    is_valid, _ = url_validator.validate_url(url)
                    if is_valid:
                        urls.append(url)
                        url_to_asset_id[asset.identifier.lower()] = asset.id  # Map host to asset_id
            elif asset.type == AssetType.IP:
                # Try common web ports
                for port in [80, 443, 8080, 8443]:
                    scheme = 'https' if port in [443, 8443] else 'http'
                    url = f"{scheme}://{asset.identifier}:{port}"
                    is_valid, _ = url_validator.validate_url(url)
                    if is_valid:
                        urls.append(url)
                        url_to_asset_id[asset.identifier.lower()] = asset.id  # Map IP to asset_id
            elif asset.type == AssetType.URL:
                is_valid, _ = url_validator.validate_url(asset.identifier)
                if is_valid:
                    urls.append(asset.identifier)
                    # For URL type, extract host for mapping
                    parsed = urlparse(asset.identifier)
                    if parsed.hostname:
                        url_to_asset_id[parsed.hostname.lower()] = asset.id

        if not urls:
            tenant_logger.warning(f"No valid URLs for HTTPx (tenant {tenant_id})")
            return {'services_enriched': 0}

        tenant_logger.info(f"Running HTTPx on {len(urls)} URLs (tenant {tenant_id})")
        tenant_logger.info(f"HTTPx URLs: {urls[:5]}...")  # Log first 5 URLs

        # Execute HTTPx with secure executor
        with SecureToolExecutor(tenant_id) as executor:
            # Use stdin instead of file to avoid HTTPx memory leak with -l flag
            urls_content = '\n'.join(urls)

            # Execute HTTPx with stdin
            returncode, stdout, stderr = executor.execute(
                'httpx',
                [
                    '-json',                    # JSON output
                    '-status-code',             # Include status code
                    '-title',                   # Include page title
                    '-web-server',              # Detect web server
                    '-tech-detect',             # Detect technologies (safe in v1.6.8)
                    '-response-time',           # Include response time
                    '-content-length',          # Include content length
                    '-follow-redirects',        # Follow redirects
                    '-max-redirects', '3',      # Limit redirects
                    '-no-color',                # Disable colors
                    '-silent',                  # Minimal output
                    '-threads', '10',           # Use 10 threads for better performance
                    '-timeout', str(settings.httpx_timeout),
                    '-rate-limit', str(settings.httpx_rate_limit)
                ],
                timeout=settings.httpx_timeout,
                stdin_data=urls_content        # Pass URLs via stdin
            )

            if returncode != 0:
                tenant_logger.warning(f"HTTPx returned non-zero exit code: {returncode}")
                tenant_logger.warning(f"HTTPx stderr: {stderr}")
                tenant_logger.warning(f"HTTPx stdout length: {len(stdout)}")

            # Parse JSON output
            services_data = []
            for line in stdout.strip().split('\n'):
                if not line:
                    continue

                try:
                    result = json.loads(line)

                    # Extract service data
                    service_data = parse_httpx_result(result, tenant_logger)
                    if service_data:
                        # Match host to asset_id using our mapping
                        host = service_data.get('host', '').lower()
                        asset_id = url_to_asset_id.get(host)
                        if asset_id:
                            service_data['asset_id'] = asset_id
                            services_data.append(service_data)
                        else:
                            tenant_logger.warning(f"No asset found for host: {host}")

                except json.JSONDecodeError as e:
                    tenant_logger.warning(f"Failed to parse HTTPx JSON: {e}")
                    continue

            # Store raw output in MinIO
            try:
                store_raw_output(tenant_id, 'httpx', {'urls': urls, 'results': services_data})
            except Exception as e:
                tenant_logger.warning(f"Failed to store HTTPx raw output: {e}")

            # Upsert services to database
            service_repo = ServiceRepository(db)
            total_created = 0
            total_updated = 0

            # Group services by asset and deduplicate by port
            # HTTPx may return duplicate results (e.g., redirects, multiple probes)
            services_by_asset = {}
            for service in services_data:
                asset_id = service['asset_id']
                port = service['port']

                if asset_id not in services_by_asset:
                    services_by_asset[asset_id] = {}

                # Deduplicate by port - keep latest result
                # This prevents PostgreSQL CardinalityViolation errors
                services_by_asset[asset_id][port] = service

            for asset_id, services_dict in services_by_asset.items():
                # Convert dict back to list for bulk_upsert
                asset_services = list(services_dict.values())
                result = service_repo.bulk_upsert(asset_id, asset_services)
                total_created += result['created']
                total_updated += result['updated']

                # Update asset enrichment tracking
                asset = db.query(Asset).filter_by(id=asset_id).first()
                if asset:
                    asset.last_enriched_at = datetime.utcnow()
                    asset.enrichment_status = 'enriched'

            db.commit()

            tenant_logger.info(
                f"HTTPx complete: {total_created} new services, {total_updated} updated "
                f"(tenant {tenant_id})"
            )

            return {
                'services_created': total_created,
                'services_updated': total_updated,
                'total_processed': total_created + total_updated
            }

    except ToolExecutionError as e:
        tenant_logger.error(f"HTTPx execution failed: {e}")
        return {'error': str(e), 'services_enriched': 0}
    except Exception as e:
        tenant_logger.error(f"HTTPx error: {e}", exc_info=True)
        return {'error': str(e), 'services_enriched': 0}
    finally:
        db.close()


def parse_httpx_result(result: Dict, tenant_logger) -> Optional[Dict]:
    """
    Parse HTTPx JSON output into service data

    Sanitizes output to prevent:
    - Credential exposure (Authorization, Cookie headers)
    - XSS (HTML/JS in title)
    - URL credential leakage

    Args:
        result: HTTPx JSON result
        tenant_logger: Logger instance

    Returns:
        Service data dict or None if parsing fails
    """
    try:
        url = result.get('url')
        if not url:
            return None

        # Parse URL to get host and port
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port

        # Determine default port if not specified
        if not port:
            port = 443 if parsed.scheme == 'https' else 80

        # Sanitize headers - redact sensitive values
        headers = result.get('header', {})
        if isinstance(headers, dict):
            sanitized_headers = sanitize_http_headers(headers)
        else:
            sanitized_headers = {}

        # Extract technologies (list of strings)
        technologies = result.get('technologies', [])
        if not isinstance(technologies, list):
            technologies = []

        # Build service data
        service_data = {
            'port': port,
            'protocol': parsed.scheme,
            'http_status': result.get('status_code'),
            'http_title': sanitize_html(result.get('title', ''))[:500],  # Limit length, sanitize
            'web_server': result.get('webserver', '')[:200],
            'http_technologies': technologies,
            'http_headers': sanitized_headers,
            'response_time_ms': result.get('time', '').replace('ms', '').strip() if result.get('time') else None,
            'content_length': result.get('content_length'),
            'redirect_url': result.get('final_url'),
            'has_tls': parsed.scheme == 'https',
            'enrichment_source': 'httpx',
            'enriched_at': datetime.utcnow()
        }

        # Convert response_time_ms to int
        if service_data['response_time_ms']:
            try:
                service_data['response_time_ms'] = int(float(service_data['response_time_ms']))
            except (ValueError, TypeError):
                service_data['response_time_ms'] = None

        # Find asset ID by matching host
        # This is done by the caller, we just return the host
        service_data['host'] = host

        return service_data

    except Exception as e:
        tenant_logger.warning(f"Failed to parse HTTPx result: {e}")
        return None


def sanitize_http_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Sanitize HTTP headers to prevent credential exposure

    Redacts sensitive headers:
    - Authorization
    - Cookie
    - Set-Cookie
    - X-API-Key
    - API-Key
    - Token
    - Secret

    Args:
        headers: HTTP headers dict

    Returns:
        Sanitized headers dict
    """
    sensitive_headers = [
        'authorization', 'cookie', 'set-cookie',
        'x-api-key', 'api-key', 'token', 'secret'
    ]

    sanitized = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if any(s in key_lower for s in sensitive_headers):
            sanitized[key] = '[REDACTED]'
        else:
            sanitized[key] = value

    return sanitized


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML/JS to prevent XSS

    Removes:
    - <script> tags
    - <iframe> tags
    - javascript: URLs
    - on* event handlers

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    if not text:
        return ''

    # Remove script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove iframe tags
    text = re.sub(r'<iframe[^>]*>.*?</iframe>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove javascript: URLs
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)

    # Remove event handlers (onclick, onerror, etc.) with their values
    # Matches: on<event>="value" or on<event>='value'
    text = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    # Also handle unquoted values: on<event>=value
    text = re.sub(r'on\w+\s*=\s*\S+', '', text, flags=re.IGNORECASE)

    return text.strip()


# =============================================================================
# NAABU - PORT SCANNING
# =============================================================================

@celery.task(name='app.tasks.enrichment.run_naabu')
def run_naabu(tenant_id: int, asset_ids: List[int], full_scan: bool = False):
    """
    Run Naabu for port scanning

    Scans network ports to discover services.

    IMPORTANT: Port scanning requires user consent and may be legally restricted.
    Only scan assets the tenant owns or has permission to scan.

    Security Controls:
    - IP/domain validation
    - SSRF prevention (RFC1918, cloud metadata, loopback blocked)
    - Port blocklist (22, 445, 3389, etc.)
    - Rate limiting
    - Timeout limits

    Args:
        tenant_id: Tenant ID
        asset_ids: List of asset IDs to scan
        full_scan: If True, scan all 65535 ports (slow). If False, scan top 1000.

    Returns:
        Dict with scan results
    """
    from app.database import SessionLocal
    from app.repositories.service_repository import ServiceRepository

    db = SessionLocal()
    tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})

    try:
        # Get tenant consent for port scanning
        from app.models.database import Tenant
        tenant = db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            return {'error': 'tenant_not_found'}

        # TODO: Implement consent system
        # if not tenant.port_scan_consent:
        #     tenant_logger.warning(f"Port scanning not consented for tenant {tenant_id}")
        #     return {'error': 'port_scan_not_consented'}

        # Get assets
        assets = db.query(Asset).filter(
            Asset.id.in_(asset_ids),
            Asset.tenant_id == tenant_id
        ).all()

        if not assets:
            tenant_logger.warning(f"No assets found for Naabu (IDs: {asset_ids})")
            return {'ports_discovered': 0}

        # Build host list
        hosts = []
        domain_validator = DomainValidator()

        for asset in assets:
            if asset.type in [AssetType.DOMAIN, AssetType.SUBDOMAIN]:
                is_valid, _ = domain_validator.validate_domain(asset.identifier)
                if is_valid:
                    hosts.append(asset.identifier)
            elif asset.type == AssetType.IP:
                # Validate IP is not in blocklist
                if is_ip_allowed(asset.identifier, tenant_logger):
                    hosts.append(asset.identifier)

        if not hosts:
            tenant_logger.warning(f"No valid hosts for Naabu (tenant {tenant_id})")
            return {'ports_discovered': 0}

        tenant_logger.info(f"Running Naabu on {len(hosts)} hosts (tenant {tenant_id})")

        # Execute Naabu with secure executor
        with SecureToolExecutor(tenant_id) as executor:
            # Use stdin instead of file input for better reliability
            hosts_content = '\n'.join(hosts)

            # Build arguments (no -l flag, use stdin)
            args = [
                '-json',
                '-silent',
                '-rate', str(settings.naabu_rate_limit or 1000)
            ]

            # Port selection
            if full_scan:
                args.extend(['-p', '-'])  # All ports
            else:
                args.extend(['-top-ports', settings.naabu_default_ports or '1000'])

            # Exclude blocked ports
            if settings.naabu_blocked_ports:
                exclude_ports = ','.join(map(str, settings.naabu_blocked_ports))
                args.extend(['-exclude-ports', exclude_ports])

            # Execute Naabu with stdin
            returncode, stdout, stderr = executor.execute(
                'naabu',
                args,
                timeout=settings.naabu_timeout,
                stdin_data=hosts_content
            )

            if returncode != 0:
                tenant_logger.warning(f"Naabu returned non-zero exit code: {returncode}")
                tenant_logger.debug(f"Naabu stderr: {stderr}")

            # Parse JSON output
            services_data = []
            for line in stdout.strip().split('\n'):
                if not line:
                    continue

                try:
                    result = json.loads(line)
                    service_data = parse_naabu_result(result, tenant_logger)
                    if service_data:
                        services_data.append(service_data)
                except json.JSONDecodeError:
                    continue

            # Store raw output
            try:
                store_raw_output(tenant_id, 'naabu', {'hosts': hosts, 'results': services_data})
            except Exception as e:
                tenant_logger.warning(f"Failed to store Naabu raw output: {e}")

            # Upsert services to database
            # (Similar to HTTPx, group by asset and bulk upsert)
            service_repo = ServiceRepository(db)
            total_created = 0
            total_updated = 0

            # TODO: Map hosts back to asset IDs
            # For now, log the results
            tenant_logger.info(f"Naabu discovered {len(services_data)} open ports")

            return {
                'ports_discovered': len(services_data),
                'hosts_scanned': len(hosts)
            }

    except ToolExecutionError as e:
        tenant_logger.error(f"Naabu execution failed: {e}")
        return {'error': str(e), 'ports_discovered': 0}
    except Exception as e:
        tenant_logger.error(f"Naabu error: {e}", exc_info=True)
        return {'error': str(e), 'ports_discovered': 0}
    finally:
        db.close()


def parse_naabu_result(result: Dict, tenant_logger) -> Optional[Dict]:
    """Parse Naabu JSON output into service data"""
    try:
        return {
            'host': result.get('host'),
            'port': result.get('port'),
            'protocol': 'tcp',  # Naabu default
            'enrichment_source': 'naabu'
        }
    except Exception as e:
        tenant_logger.warning(f"Failed to parse Naabu result: {e}")
        return None


def is_ip_allowed(ip: str, tenant_logger) -> bool:
    """
    Check if IP is allowed for scanning (SSRF prevention)

    Blocks:
    - RFC1918 private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - Loopback (127.0.0.0/8)
    - Link-local (169.254.0.0/16)
    - Cloud metadata (169.254.169.254, metadata.google.internal)

    Args:
        ip: IP address to check
        tenant_logger: Logger instance

    Returns:
        True if IP is allowed, False otherwise
    """
    import ipaddress

    try:
        ip_obj = ipaddress.ip_address(ip)

        # Check if private
        if ip_obj.is_private:
            tenant_logger.warning(f"Blocked private IP: {ip}")
            return False

        # Check if loopback
        if ip_obj.is_loopback:
            tenant_logger.warning(f"Blocked loopback IP: {ip}")
            return False

        # Check if link-local
        if ip_obj.is_link_local:
            tenant_logger.warning(f"Blocked link-local IP: {ip}")
            return False

        # Check cloud metadata IPs
        if str(ip) == '169.254.169.254':
            tenant_logger.warning(f"Blocked cloud metadata IP: {ip}")
            return False

        return True

    except ValueError:
        tenant_logger.warning(f"Invalid IP address: {ip}")
        return False


# =============================================================================
# TLSX - TLS/SSL CERTIFICATE ANALYSIS
# =============================================================================

@celery.task(name='app.tasks.enrichment.run_tlsx')
def run_tlsx(tenant_id: int, asset_ids: List[int]):
    """
    Run TLSx for TLS/SSL certificate analysis

    CRITICAL SECURITY: This task MUST detect and redact private keys.
    TLSx should NOT output private keys, but defense in depth requires
    detection and redaction if they appear.

    Analyzes:
    - Certificate validity and expiry
    - Subject Alternative Names (SANs)
    - Certificate chain
    - Cipher suites
    - TLS versions
    - Security issues (self-signed, weak signatures, expired)

    Args:
        tenant_id: Tenant ID
        asset_ids: List of asset IDs to analyze

    Returns:
        Dict with analysis results
    """
    from app.database import SessionLocal
    from app.repositories.certificate_repository import CertificateRepository

    db = SessionLocal()
    tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})

    try:
        # Get assets
        assets = db.query(Asset).filter(
            Asset.id.in_(asset_ids),
            Asset.tenant_id == tenant_id
        ).all()

        if not assets:
            tenant_logger.warning(f"No assets found for TLSx (IDs: {asset_ids})")
            return {'certificates_discovered': 0}

        # Build host list (only domains/IPs with potential HTTPS)
        hosts = []
        domain_validator = DomainValidator()

        for asset in assets:
            if asset.type in [AssetType.DOMAIN, AssetType.SUBDOMAIN]:
                is_valid, _ = domain_validator.validate_domain(asset.identifier)
                if is_valid:
                    hosts.append(asset.identifier)
            elif asset.type == AssetType.IP:
                if is_ip_allowed(asset.identifier, tenant_logger):
                    hosts.append(asset.identifier)

        if not hosts:
            tenant_logger.warning(f"No valid hosts for TLSx (tenant {tenant_id})")
            return {'certificates_discovered': 0}

        tenant_logger.info(f"Running TLSx on {len(hosts)} hosts (tenant {tenant_id})")

        # Execute TLSx with secure executor
        with SecureToolExecutor(tenant_id) as executor:
            # Use stdin instead of file input
            hosts_content = '\n'.join(hosts)

            # Execute TLSx with stdin
            returncode, stdout, stderr = executor.execute(
                'tlsx',
                [
                    '-json',
                    '-silent',
                    '-san',               # Include SANs
                    '-cn',                # Include CN
                    '-cipher',            # Include cipher suites
                    '-tls-version',       # Include TLS version
                    '-hash', 'sha256'     # Certificate hash
                ],
                timeout=settings.tlsx_timeout,
                stdin_data=hosts_content
            )

            if returncode != 0:
                tenant_logger.warning(f"TLSx returned non-zero exit code: {returncode}")
                tenant_logger.debug(f"TLSx stderr: {stderr}")

            # CRITICAL: Detect private keys in output
            private_key_detected, sanitized_stdout = detect_and_redact_private_keys(
                stdout,
                tenant_logger
            )

            if private_key_detected:
                # CRITICAL ALERT
                tenant_logger.critical(
                    f"PRIVATE KEY DETECTED in TLSx output for tenant {tenant_id}! "
                    f"This is a critical security incident. Output has been redacted."
                )
                # TODO: Send alert to security team

            # Parse JSON output
            certificates_data = []
            for line in sanitized_stdout.strip().split('\n'):
                if not line:
                    continue

                try:
                    result = json.loads(line)
                    cert_data = parse_tlsx_result(result, tenant_logger)
                    if cert_data:
                        certificates_data.append(cert_data)
                except json.JSONDecodeError:
                    continue

            # Store raw output (sanitized)
            try:
                store_raw_output(
                    tenant_id,
                    'tlsx',
                    {
                        'hosts': hosts,
                        'results': certificates_data,
                        'private_key_detected': private_key_detected
                    }
                )
            except Exception as e:
                tenant_logger.warning(f"Failed to store TLSx raw output: {e}")

            # Upsert certificates to database
            # (Similar pattern to HTTPx/Naabu)
            tenant_logger.info(f"TLSx discovered {len(certificates_data)} certificates")

            return {
                'certificates_discovered': len(certificates_data),
                'hosts_analyzed': len(hosts),
                'private_key_detected': private_key_detected
            }

    except ToolExecutionError as e:
        tenant_logger.error(f"TLSx execution failed: {e}")
        return {'error': str(e), 'certificates_discovered': 0}
    except Exception as e:
        tenant_logger.error(f"TLSx error: {e}", exc_info=True)
        return {'error': str(e), 'certificates_discovered': 0}
    finally:
        db.close()


def detect_and_redact_private_keys(text: str, tenant_logger) -> Tuple[bool, str]:
    """
    CRITICAL SECURITY FUNCTION: Detect and redact private keys

    Searches for PEM-formatted private keys and redacts them.

    Patterns detected:
    - RSA private keys: -----BEGIN RSA PRIVATE KEY-----
    - EC private keys: -----BEGIN EC PRIVATE KEY-----
    - Generic private keys: -----BEGIN PRIVATE KEY-----
    - Encrypted private keys: -----BEGIN ENCRYPTED PRIVATE KEY-----

    Args:
        text: Text to scan
        tenant_logger: Logger instance

    Returns:
        Tuple of (private_key_detected: bool, sanitized_text: str)
    """
    # Patterns for private key detection
    private_key_patterns = [
        r'-----BEGIN RSA PRIVATE KEY-----.*?-----END RSA PRIVATE KEY-----',
        r'-----BEGIN EC PRIVATE KEY-----.*?-----END EC PRIVATE KEY-----',
        r'-----BEGIN PRIVATE KEY-----.*?-----END PRIVATE KEY-----',
        r'-----BEGIN ENCRYPTED PRIVATE KEY-----.*?-----END ENCRYPTED PRIVATE KEY-----'
    ]

    detected = False
    sanitized = text

    for pattern in private_key_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            detected = True
            tenant_logger.critical(
                f"PRIVATE KEY DETECTED! Found {len(matches)} private key(s). REDACTING."
            )

            # Redact the private key
            sanitized = re.sub(
                pattern,
                '[REDACTED: PRIVATE KEY - CRITICAL SECURITY INCIDENT]',
                sanitized,
                flags=re.DOTALL
            )

    return detected, sanitized


def parse_tlsx_result(result: Dict, tenant_logger) -> Optional[Dict]:
    """Parse TLSx JSON output into certificate data"""
    try:
        # TODO: Full implementation
        # Extract certificate fields from TLSx JSON
        return {
            'host': result.get('host'),
            'subject_cn': result.get('subject_cn'),
            'issuer': result.get('issuer'),
            'serial_number': result.get('serial'),
            # ... more fields
        }
    except Exception as e:
        tenant_logger.warning(f"Failed to parse TLSx result: {e}")
        return None


# =============================================================================
# KATANA - WEB CRAWLING
# =============================================================================

@celery.task(name='app.tasks.enrichment.run_katana')
def run_katana(tenant_id: int, asset_ids: List[int]):
    """
    Run Katana for web crawling and endpoint discovery

    IMPORTANT: Respects robots.txt by default. Set katana_respect_robots=False
    in config to disable (not recommended).

    Discovers:
    - API endpoints
    - Web pages and paths
    - Forms (potential XSS/CSRF targets)
    - External links
    - File downloads

    Args:
        tenant_id: Tenant ID
        asset_ids: List of asset IDs to crawl (must have live HTTP services)

    Returns:
        Dict with crawl results
    """
    from app.database import SessionLocal
    from app.repositories.service_repository import ServiceRepository
    from app.repositories.endpoint_repository import EndpointRepository

    db = SessionLocal()
    tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})

    try:
        # Get assets with live HTTP services
        # Katana depends on HTTPx results
        service_repo = ServiceRepository(db)

        # TODO: Implement getting live web services
        # For now, placeholder
        tenant_logger.info(f"Katana crawling not yet fully implemented (tenant {tenant_id})")

        return {
            'endpoints_discovered': 0,
            'status': 'not_implemented'
        }

    except Exception as e:
        tenant_logger.error(f"Katana error: {e}", exc_info=True)
        return {'error': str(e), 'endpoints_discovered': 0}
    finally:
        db.close()
