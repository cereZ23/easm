"""
Enrichment pipeline tasks for asset enrichment

Implements HTTP fingerprinting (HTTPx), port scanning (Naabu), TLS/SSL
analysis (TLSx), and web crawling / endpoint discovery (Katana) with
comprehensive security controls and tiered enrichment based on asset priority.

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
from urllib.parse import urlparse, parse_qs

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

    Orchestrates parallel execution of HTTPx + Naabu + TLSx, then Katana
    endpoint discovery, then Nuclei.

    Args:
        tenant_id: Tenant ID
        asset_ids: Optional list of specific asset IDs to enrich
        priority: Optional priority level to enrich (critical, high, normal, low)
        force_refresh: If True, enrich even if recently enriched

    Returns:
        Dict with enrichment statistics

    Architecture:
        Phase 1 (Parallel): HTTPx + Naabu + TLSx run concurrently
        Phase 2: run_katana crawls live web services and populates Endpoints
        Phase 3: run_nuclei_scan (also crawls with Katana internally, then scans)
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

        # Phase 2: Run Katana endpoint discovery after enrichment completes
        # Phase 3: Run Nuclei after Katana (if enabled)
        # chord(group_of_tasks, callback) - callback runs after ALL group tasks complete
        from celery import chord

        if settings.feature_nuclei_enabled:
            from app.tasks.scanning import run_nuclei_scan

            # Wait for all enrichment tasks, then run Katana, then Nuclei
            # chord() returns an AsyncResult when called, don't call apply_async() again
            result = chord(parallel_tasks)(
                chain(
                    run_katana.si(tenant_id, candidates),
                    run_nuclei_scan.si(tenant_id, candidates, ['critical', 'high', 'medium'])
                )
            )
        else:
            # Wait for all enrichment tasks, then run Katana endpoint discovery
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
                    '-irh',                     # Include response headers (for header/cookie tech hints)
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


def _tech_from_headers(headers: Dict) -> List[str]:
    """Infer additional technologies from HTTP response headers and cookies.

    httpx's -tech-detect (Wappalyzer-style) often only sees the CDN edge. Response
    headers frequently leak the real origin server (Via), backend runtime
    (X-Powered-By), CMS (X-Generator/X-Drupal-*), and framework (session cookie
    names). This fills that gap.
    """
    tech: List[str] = []
    if not isinstance(headers, dict):
        return tech

    # Normalise header keys (httpx uses lowercase + underscores already)
    h = {str(k).lower().replace('-', '_'): v for k, v in headers.items()}

    def add(name):
        name = (name or '').strip()
        if name and name not in tech:
            tech.append(name)

    # Via header reveals proxy/origin server chain (e.g. "1.1 Caddy")
    via = str(h.get('via', '') or '')
    for proxy in ('Caddy', 'Varnish', 'nginx', 'Apache', 'HAProxy', 'Envoy', 'squid', 'Traefik'):
        if proxy.lower() in via.lower():
            add(proxy)

    # Backend runtime / framework from X-Powered-By (e.g. "PHP/8.1", "Express")
    xpb = str(h.get('x_powered_by', '') or '')
    if xpb:
        add(xpb.split('/')[0])
    if h.get('x_aspnet_version') or h.get('x_aspnetmvc_version'):
        add('ASP.NET')
    if h.get('x_drupal_cache') or h.get('x_drupal_dynamic_cache'):
        add('Drupal')
    if h.get('x_generator'):
        add(str(h['x_generator']).split(' ')[0])
    if h.get('x_shopify_stage'):
        add('Shopify')

    # Framework hints from session cookie names
    cookies = str(h.get('set_cookie', '') or '').lower()
    cookie_map = {
        'phpsessid': 'PHP', 'laravel_session': 'Laravel', 'ci_session': 'CodeIgniter',
        'jsessionid': 'Java', 'csrftoken': 'Django', 'django': 'Django',
        'connect.sid': 'Express', '_rails': 'Ruby on Rails', 'wordpress_': 'WordPress',
        'wp-': 'WordPress', 'asp.net_sessionid': 'ASP.NET',
    }
    for marker, name in cookie_map.items():
        if marker in cookies:
            add(name)

    return tech


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

        # Raw headers are used for tech fingerprinting BEFORE redaction (cookie
        # names like PHPSESSID reveal the stack); sanitized copy is stored.
        raw_headers = result.get('header', {})
        if isinstance(raw_headers, dict):
            sanitized_headers = sanitize_http_headers(raw_headers)
        else:
            raw_headers = {}
            sanitized_headers = {}

        # Extract technologies (list of strings). httpx emits this under the
        # 'tech' key; older builds/schemas used 'technologies' — accept both.
        technologies = result.get('tech') or result.get('technologies') or []
        if not isinstance(technologies, list):
            technologies = list(technologies) if technologies else []

        # Enrich with tech inferred from response headers/cookies — this surfaces
        # the origin/backend stack that -tech-detect misses behind a CDN
        # (e.g. Caddy via the Via header, PHP/Express via X-Powered-By/cookies).
        technologies = list(dict.fromkeys(technologies + _tech_from_headers(raw_headers)))

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

        # Build host list + host -> asset_id map for attributing discovered ports
        hosts = []
        host_to_asset_id = {}
        domain_validator = DomainValidator()

        for asset in assets:
            if asset.type in [AssetType.DOMAIN, AssetType.SUBDOMAIN]:
                is_valid, _ = domain_validator.validate_domain(asset.identifier)
                if is_valid:
                    hosts.append(asset.identifier)
                    host_to_asset_id[asset.identifier.lower()] = asset.id
            elif asset.type == AssetType.IP:
                # Validate IP is not in blocklist
                if is_ip_allowed(asset.identifier, tenant_logger):
                    hosts.append(asset.identifier)
                    host_to_asset_id[asset.identifier.lower()] = asset.id

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
                # naabu's -top-ports expects a number (100/1000) or 'full',
                # NOT a "top-1000" string. Normalise the configured value.
                top_ports = (settings.naabu_default_ports or '1000').strip()
                if top_ports.startswith('top-'):
                    top_ports = top_ports[len('top-'):]
                args.extend(['-top-ports', top_ports])

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

            # Attribute each discovered port to its asset and persist as a service.
            service_repo = ServiceRepository(db)

            services_by_asset = {}
            for svc in services_data:
                host = (svc.get('host') or '').lower()
                port = svc.get('port')
                asset_id = host_to_asset_id.get(host)
                if not asset_id or not port:
                    continue
                # dedupe by port within an asset (unique constraint asset_id+port)
                services_by_asset.setdefault(asset_id, {})[port] = {
                    'port': port,
                    'protocol': svc.get('protocol', 'tcp'),
                    'enrichment_source': 'naabu',
                }

            total_created = 0
            total_updated = 0
            for asset_id, port_map in services_by_asset.items():
                res = service_repo.bulk_upsert(asset_id, list(port_map.values()))
                total_created += res['created']
                total_updated += res['updated']

            db.commit()

            tenant_logger.info(
                f"Naabu: {len(services_data)} open ports -> {total_created} new, "
                f"{total_updated} updated services (tenant {tenant_id})"
            )

            return {
                'ports_discovered': len(services_data),
                'services_created': total_created,
                'services_updated': total_updated,
                'hosts_scanned': len(hosts),
                'status': 'success'
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
    from app.repositories.service_repository import ServiceRepository

    db = SessionLocal()
    service_repo = ServiceRepository(db)
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

        # Build host list (only domains/IPs with potential HTTPS) and a
        # host -> asset_id map so parsed certificates can be attributed.
        hosts = []
        host_to_asset_id = {}
        domain_validator = DomainValidator()

        for asset in assets:
            if asset.type in [AssetType.DOMAIN, AssetType.SUBDOMAIN]:
                is_valid, _ = domain_validator.validate_domain(asset.identifier)
                if is_valid:
                    hosts.append(asset.identifier)
                    host_to_asset_id[asset.identifier.lower()] = asset.id
            elif asset.type == AssetType.IP:
                if is_ip_allowed(asset.identifier, tenant_logger):
                    hosts.append(asset.identifier)
                    host_to_asset_id[asset.identifier.lower()] = asset.id

        if not hosts:
            tenant_logger.warning(f"No valid hosts for TLSx (tenant {tenant_id})")
            return {'certificates_discovered': 0}

        tenant_logger.info(f"Running TLSx on {len(hosts)} hosts (tenant {tenant_id})")

        # Execute TLSx with secure executor
        with SecureToolExecutor(tenant_id) as executor:
            # Use stdin instead of file input
            hosts_content = '\n'.join(hosts)

            # Execute TLSx with stdin
            # NOTE: tlsx's default -json output already includes SANs, CN,
            # cipher, TLS version, issuer, validity dates, etc. The -san/-cn
            # flags are exclusive "probe" modes that error when combined with
            # other options ("san or cn flag cannot be used with other probes"),
            # so we rely on the rich default JSON plus -hash for a fingerprint.
            returncode, stdout, stderr = executor.execute(
                'tlsx',
                [
                    '-json',
                    '-silent',
                    '-hash', 'sha256',    # Certificate SHA-256 fingerprint
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

            # Attribute each certificate to its asset and persist it.
            from app.repositories.certificate_repository import CertificateRepository
            cert_repo = CertificateRepository(db)

            certs_by_asset = {}
            for cert in certificates_data:
                host = (cert.get('host') or '').lower()
                asset_id = host_to_asset_id.get(host)
                if not asset_id:
                    continue
                # dedupe by serial within an asset (unique constraint)
                certs_by_asset.setdefault(asset_id, {})[cert['serial_number']] = cert

            total_created = 0
            total_updated = 0
            for asset_id, serial_map in certs_by_asset.items():
                res = cert_repo.bulk_upsert(asset_id, list(serial_map.values()))
                total_created += res['created']
                total_updated += res['updated']

                # Mark the asset's HTTPS services as TLS-enabled
                for svc in service_repo.get_web_services(asset_id, only_live=False):
                    if svc.port in (443, 8443) or svc.protocol == 'https':
                        svc.has_tls = True

            db.commit()

            tenant_logger.info(
                f"TLSx: {total_created} new, {total_updated} updated certificates "
                f"across {len(certs_by_asset)} assets (tenant {tenant_id})"
            )

            return {
                'certificates_created': total_created,
                'certificates_updated': total_updated,
                'certificates_discovered': len(certificates_data),
                'hosts_analyzed': len(hosts),
                'private_key_detected': private_key_detected,
                'status': 'success'
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


def _parse_tls_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse a tlsx ISO-8601 timestamp (e.g. '2026-09-20T13:33:56Z') to naive UTC."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def parse_tlsx_result(result: Dict, tenant_logger) -> Optional[Dict]:
    """Parse a TLSx JSON record into certificate data for CertificateRepository.

    Extracts the full certificate detail tlsx provides by default: subject CN,
    SANs, issuer, serial, validity window, cipher/TLS version, fingerprint, and
    derives is_expired / days_until_expiry / is_wildcard / is_self_signed.
    """
    try:
        serial = result.get('serial')
        if not serial:
            return None  # serial_number is the unique key; skip records without it

        subject_cn = result.get('subject_cn') or result.get('subject_dn')
        san_domains = result.get('subject_an') or []
        issuer = result.get('issuer_cn') or result.get('issuer_dn')
        if not issuer:
            issuer_org = result.get('issuer_org')
            issuer = issuer_org[0] if isinstance(issuer_org, list) and issuer_org else None

        not_before = _parse_tls_datetime(result.get('not_before'))
        not_after = _parse_tls_datetime(result.get('not_after'))

        is_expired = False
        days_until_expiry = None
        if not_after:
            delta = not_after - datetime.utcnow()
            days_until_expiry = delta.days
            is_expired = delta.total_seconds() < 0

        # Wildcard if any SAN or the CN starts with '*.'
        names = list(san_domains) + ([subject_cn] if subject_cn else [])
        is_wildcard = any(isinstance(n, str) and n.startswith('*.') for n in names)

        # Self-signed heuristic: subject == issuer
        is_self_signed = bool(
            result.get('self_signed')
            or (subject_cn and issuer and subject_cn == issuer)
        )

        cipher = result.get('cipher')
        fingerprint = result.get('fingerprint_hash') or {}
        sha256_fp = fingerprint.get('sha256') if isinstance(fingerprint, dict) else None

        return {
            'host': result.get('host'),
            'serial_number': serial,
            'subject_cn': subject_cn,
            'issuer': issuer,
            'not_before': not_before,
            'not_after': not_after,
            'is_expired': is_expired,
            'days_until_expiry': days_until_expiry,
            'san_domains': san_domains or None,
            'signature_algorithm': result.get('signature_algorithm'),
            'public_key_algorithm': result.get('public_key_algorithm'),
            'cipher_suites': [cipher] if cipher else None,
            'is_self_signed': is_self_signed,
            'is_wildcard': is_wildcard,
            'raw_data': {
                'tls_version': result.get('tls_version'),
                'cipher': cipher,
                'sha256_fingerprint': sha256_fp,
                'issuer_dn': result.get('issuer_dn'),
                'subject_dn': result.get('subject_dn'),
            },
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
    Run Katana for web crawling and endpoint discovery.

    For each asset with live HTTP services (discovered by HTTPx), runs the
    katana crawler through SecureToolExecutor, parses the JSONL output, and
    persists discovered endpoints via EndpointRepository. Populates the
    Endpoint inventory used by the /endpoints API.

    Discovers and classifies:
    - API endpoints (is_api)
    - Web pages and paths
    - Forms (potential XSS/CSRF targets)
    - External links (is_external)
    - Static files

    Respects the crawl depth / rate limits configured in settings
    (katana_max_depth, katana_timeout, katana_rate_limit if set).

    Args:
        tenant_id: Tenant ID
        asset_ids: List of asset IDs to crawl (must have live HTTP services)

    Returns:
        Dict with crawl results:
        {'endpoints_created', 'endpoints_updated', 'assets_crawled',
         'total_endpoints', 'status'}
    """
    from app.database import SessionLocal
    from app.repositories.service_repository import ServiceRepository
    from app.repositories.endpoint_repository import EndpointRepository

    db = SessionLocal()
    tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})

    try:
        assets = db.query(Asset).filter(
            Asset.id.in_(asset_ids),
            Asset.tenant_id == tenant_id
        ).all()

        if not assets:
            tenant_logger.warning(f"No assets found for Katana (IDs: {asset_ids})")
            return {'endpoints_created': 0, 'endpoints_updated': 0,
                    'assets_crawled': 0, 'total_endpoints': 0, 'status': 'no_assets'}

        service_repo = ServiceRepository(db)
        endpoint_repo = EndpointRepository(db)
        url_validator = URLValidator()

        total_created = 0
        total_updated = 0
        assets_crawled = 0
        all_raw = []

        for asset in assets:
            # Build the list of live web URLs to crawl for this asset.
            # Prefer live services discovered by HTTPx; fall back to the
            # asset identifier for domain/subdomain assets.
            seed_urls = []
            for svc in service_repo.get_web_services(asset.id, only_live=True):
                scheme = 'https' if (svc.has_tls or svc.port in (443, 8443)) else 'http'
                host = asset.identifier
                port_suffix = '' if svc.port in (80, 443) else f":{svc.port}"
                seed_urls.append(f"{scheme}://{host}{port_suffix}")

            if not seed_urls and asset.type in (AssetType.DOMAIN, AssetType.SUBDOMAIN):
                seed_urls.append(f"https://{asset.identifier}")

            # Validate + dedupe seeds (SSRF-safe)
            seeds = []
            for u in dict.fromkeys(seed_urls):
                is_valid, _ = url_validator.validate_url(u)
                if is_valid:
                    seeds.append(u)

            if not seeds:
                continue

            base_host = (asset.identifier or '').lower()
            endpoints_data = []

            with SecureToolExecutor(tenant_id) as executor:
                for seed in seeds:
                    try:
                        returncode, stdout, stderr = executor.execute(
                            'katana',
                            [
                                '-u', seed,
                                '-jsonl',                                  # structured output
                                '-silent',
                                '-no-color',
                                '-jc',                                     # crawl JS files
                                '-d', str(settings.katana_max_depth),      # crawl depth
                                '-timeout', '10',                          # per-request timeout
                                '-rate-limit', str(getattr(settings, 'katana_rate_limit', 150)),
                            ],
                            timeout=settings.katana_timeout
                        )
                    except ToolExecutionError as e:
                        tenant_logger.warning(f"Katana failed for {seed}: {e}")
                        continue

                    if returncode != 0:
                        tenant_logger.warning(
                            f"Katana non-zero exit ({returncode}) for {seed}: {stderr[:200]}"
                        )

                    for line in stdout.strip().split('\n'):
                        if not line.strip():
                            continue
                        parsed = parse_katana_line(line, seed, base_host)
                        if parsed:
                            endpoints_data.append(parsed)

            if not endpoints_data:
                assets_crawled += 1
                continue

            # Deduplicate by (url, method) to satisfy the unique constraint
            deduped = {}
            for ep in endpoints_data:
                deduped[(ep['url'], ep.get('method', 'GET'))] = ep

            result = endpoint_repo.bulk_upsert(asset.id, list(deduped.values()))
            total_created += result['created']
            total_updated += result['updated']
            assets_crawled += 1
            all_raw.append({'asset_id': asset.id, 'endpoints': len(deduped)})

            tenant_logger.info(
                f"Katana crawled asset {asset.id} ({asset.identifier}): "
                f"{result['created']} new, {result['updated']} updated endpoints"
            )

        # Store a summary of the raw crawl in MinIO
        try:
            store_raw_output(tenant_id, 'katana', {'assets': all_raw})
        except Exception as e:
            tenant_logger.warning(f"Failed to store Katana raw output: {e}")

        return {
            'endpoints_created': total_created,
            'endpoints_updated': total_updated,
            'assets_crawled': assets_crawled,
            'total_endpoints': total_created + total_updated,
            'status': 'success'
        }

    except Exception as e:
        tenant_logger.error(f"Katana error: {e}", exc_info=True)
        return {'error': str(e), 'endpoints_discovered': 0}
    finally:
        db.close()


# File extensions treated as static files / downloads
_STATIC_EXTENSIONS = (
    '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff',
    '.woff2', '.ttf', '.eot', '.map', '.pdf', '.zip', '.gz', '.tar', '.mp4',
    '.webp', '.xml', '.txt'
)

# Path fragments / tags that indicate an API endpoint
_API_HINTS = ('/api/', '/v1/', '/v2/', '/v3/', '/graphql', '/rest/', '/gql', '.json')


def parse_katana_line(line: str, source_url: str, base_host: str) -> Optional[Dict]:
    """
    Parse a single line of Katana output into an endpoint dict.

    Handles Katana's ``-jsonl`` structured output; falls back to treating the
    line as a bare URL if it is not valid JSON. Returns a dict shaped for
    ``EndpointRepository.bulk_upsert`` or None if the line yields no usable URL.

    Args:
        line: One line of katana stdout
        source_url: The seed URL this crawl started from
        base_host: Lowercased host of the asset (used for internal/external check)

    Returns:
        Endpoint dict or None
    """
    method = 'GET'
    status_code = None
    content_type = None
    content_length = None
    tag = None
    raw = None
    url = None

    line = line.strip()
    if not line:
        return None

    if line.startswith('{'):
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            return None

        request = raw.get('request', raw)
        response = raw.get('response', {}) or {}

        url = request.get('endpoint') or request.get('url') or raw.get('endpoint')
        method = (request.get('method') or 'GET').upper()
        tag = request.get('tag') or request.get('source')

        status_code = response.get('status_code')
        content_length = response.get('content_length')
        content_type = response.get('content_type')
        if not content_type:
            headers = response.get('headers') or {}
            # katana lowercases/normalises header keys differently across versions
            content_type = headers.get('content_type') or headers.get('Content-Type')
    else:
        # Plain-text output: the line is the URL itself
        url = line

    if not url or not isinstance(url, str):
        return None
    if not url.startswith(('http://', 'https://')):
        return None

    parsed = urlparse(url)
    path = parsed.path or '/'
    query_params = None
    if parsed.query:
        # parse_qs returns lists; flatten single-value params for readability
        query_params = {
            k: (v[0] if len(v) == 1 else v)
            for k, v in parse_qs(parsed.query).items()
        }

    host = (parsed.hostname or '').lower()
    is_external = bool(host) and base_host and host != base_host and not host.endswith('.' + base_host)

    # Normalise content-type (strip charset etc.)
    if content_type:
        content_type = content_type.split(';')[0].strip()[:200]

    endpoint_type, is_api = _classify_endpoint(
        path=path,
        query_params=query_params,
        tag=tag,
        status_code=status_code,
        content_type=content_type,
        is_external=is_external,
    )

    return {
        'url': url[:2048],
        'method': method[:10],
        'path': path[:1024],
        'query_params': query_params,
        'status_code': status_code,
        'content_type': content_type,
        'content_length': content_length,
        'endpoint_type': endpoint_type,
        'is_external': is_external,
        'is_api': is_api,
        'source_url': source_url[:2048],
        'raw_data': raw,
    }


def _classify_endpoint(path, query_params, tag, status_code, content_type, is_external):
    """Return (endpoint_type, is_api) from the parsed signals."""
    lower_path = (path or '').lower()

    if tag and str(tag).lower() == 'form':
        return 'form', False

    if is_external:
        return 'external', False

    looks_api = (
        any(hint in lower_path for hint in _API_HINTS)
        or (content_type is not None and 'json' in content_type)
        or bool(query_params)
    )
    if looks_api:
        return 'api', True

    if lower_path.endswith(_STATIC_EXTENSIONS):
        return 'file', False

    if status_code is not None and 300 <= status_code < 400:
        return 'redirect', False

    return 'static', False
