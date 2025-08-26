# EASM Platform - Sprint 2 Detailed Plan
## Enrichment Pipeline & Multi-Tenant API

**Created**: October 23, 2025
**Sprint Duration**: 21 days (3 weeks)
**Team**: Backend Architect + Development Team
**Status**: Ready for Implementation

---

## EXECUTIVE SUMMARY

Sprint 2 builds upon the solid foundation of Sprint 1 to deliver enrichment capabilities and a production-ready multi-tenant API. This sprint will implement 4 enrichment tools (HTTPx, Naabu, TLSx, Katana) and create a complete REST API with JWT authentication.

### Sprint 2 Goals

1. **Critical Security Fixes** - Address 3 critical issues from security audit
2. **Enrichment Pipeline** - Implement 4 tools for asset enrichment
3. **Multi-Tenant API** - Complete REST API with authentication
4. **Testing & Quality** - Achieve 80%+ test coverage
5. **Monitoring** - Production observability setup

### Success Metrics

- All 4 enrichment tools operational
- API response time < 100ms (p95)
- Test coverage ≥ 80%
- Zero critical security issues
- Complete API documentation

---

## ARCHITECTURE REVIEW FINDINGS

### Current System Strengths ✅

1. **Solid Foundation (Sprint 1)**
   - Discovery pipeline working (Uncover, Subfinder, Amass, DNSx)
   - Multi-tenant architecture with PostgreSQL
   - 100x database performance improvement
   - SecureToolExecutor pattern established
   - Health checks with actual connection verification

2. **Security Posture: 7.5/10**
   - Command injection prevention ✅
   - SQL injection prevention ✅
   - Multi-tenant isolation ✅
   - Authentication system (JWT + bcrypt) ✅
   - Resource limits enforced ✅

3. **Performance**
   - Bulk upsert: 100x faster (10s → 100ms)
   - Critical asset query: 3,489x faster
   - Strategic indexes in place
   - N+1 queries eliminated

### Critical Issues Requiring Immediate Attention ⚠️

From Security Audit Report (must fix in Week 1):

| ID | Severity | Issue | Impact | ETA |
|----|----------|-------|--------|-----|
| **V-001** | CRITICAL | .env with real secrets | Data breach risk | Day 1 |
| **V-002** | CRITICAL | CORS wildcard origins | CSRF vulnerability | Day 1 |
| **V-003** | CRITICAL | Missing constants in SecureToolExecutor | Code crashes | Day 1 |

### Technical Debt to Address

1. **Test Coverage: 62.6%** (target 80%)
   - Integration tests: 14.3% passing
   - Performance tests: 0% passing (need PostgreSQL)
   - Security tests: 70.2% passing

2. **Missing Components**
   - No security headers
   - Rate limiting configured but not enforced
   - No API endpoints yet
   - Monitoring integration incomplete

3. **Database Optimization Opportunities**
   - Connection pool tuning needed
   - Query result caching (Redis)
   - Slow query monitoring

---

## WEEK-BY-WEEK IMPLEMENTATION PLAN

### WEEK 1: Security Fixes + HTTPx + Naabu (Days 1-7)

#### Day 1: Critical Security Fixes 🚨

**Priority: CRITICAL - MUST BE COMPLETED FIRST**

**Morning (4 hours):**

1. **Fix V-003: Missing Constants in SecureToolExecutor**
   ```python
   # File: app/utils/secure_executor.py (lines 36-40)
   # Already fixed in current code! ✅
   DEFAULT_TIMEOUT = 300  # 5 minutes
   DEFAULT_CPU_LIMIT = 600  # 10 minutes CPU time
   DEFAULT_MEMORY_LIMIT = 2 * 1024 * 1024 * 1024  # 2GB
   DEFAULT_FILE_SIZE_LIMIT = 100 * 1024 * 1024  # 100MB
   ```
   - **Verify constants exist** ✅
   - Run security tests to confirm
   - Document in code review

2. **Fix V-002: CORS Configuration**
   ```python
   # File: app/main.py (lines 23-30)
   # Already fixed! ✅ Uses settings.cors_origins
   app.add_middleware(
       CORSMiddleware,
       allow_origins=settings.cors_origins,  # No wildcard
       allow_credentials=settings.cors_allow_credentials,
       allow_methods=settings.cors_allow_methods,
       allow_headers=settings.cors_allow_headers,
   )
   ```
   - **Verify CORS uses settings** ✅
   - Add validation tests

**Afternoon (4 hours):**

3. **Fix V-001: .env File Security**
   ```bash
   # Verify .env is in .gitignore
   echo ".env" >> .gitignore

   # Check if .env is tracked
   git status .env

   # If committed, remove from git
   git rm --cached .env
   git commit -m "Security: Remove .env from version control"

   # Rotate all secrets
   python -c "import secrets; print(f'SECRET_KEY={secrets.token_urlsafe(64)}')"
   python -c "import secrets; print(f'JWT_SECRET_KEY={secrets.token_urlsafe(64)}')"
   ```

4. **Add Security Headers Middleware**
   ```python
   # File: app/main.py (new)
   @app.middleware("http")
   async def add_security_headers(request, call_next):
       response = await call_next(request)
       response.headers["X-Content-Type-Options"] = "nosniff"
       response.headers["X-Frame-Options"] = "DENY"
       response.headers["X-XSS-Protection"] = "1; mode=block"
       response.headers["Strict-Transport-Security"] = "max-age=31536000"
       response.headers["Content-Security-Policy"] = "default-src 'self'"
       return response
   ```

5. **Verify Production Secret Validation**
   - Config.py already has `validate_production_secrets()` ✅
   - Test production mode startup with weak secrets (should fail)
   - Document secret generation in README

**Deliverables:**
- ✅ All critical security issues resolved
- ✅ Security headers implemented
- ✅ .env removed from git history
- ✅ Secrets rotation guide documented

---

#### Days 2-3: HTTPx Implementation

**File Structure:**
```
app/
├── tasks/
│   └── enrichment.py (new)
├── repositories/
│   └── service_repository.py (new)
├── models/
│   └── service.py (update)
tests/
└── test_enrichment.py (new)
```

**Implementation:**

1. **Create Service Repository**
   ```python
   # File: app/repositories/service_repository.py
   from sqlalchemy.orm import Session
   from app.models.database import Service, Asset
   from typing import List, Optional
   from datetime import datetime

   class ServiceRepository:
       def __init__(self, db: Session):
           self.db = db

       def get_by_asset(self, asset_id: int) -> List[Service]:
           return self.db.query(Service).filter_by(asset_id=asset_id).all()

       def upsert_service(
           self,
           asset_id: int,
           port: int,
           protocol: str,
           **kwargs
       ) -> Service:
           service = self.db.query(Service).filter_by(
               asset_id=asset_id,
               port=port,
               protocol=protocol
           ).first()

           if not service:
               service = Service(
                   asset_id=asset_id,
                   port=port,
                   protocol=protocol
               )
               self.db.add(service)

           # Update fields
           for key, value in kwargs.items():
               if hasattr(service, key):
                   setattr(service, key, value)

           service.last_seen = datetime.utcnow()
           self.db.commit()
           self.db.refresh(service)
           return service

       def bulk_upsert(self, services_data: List[dict]) -> int:
           # Similar pattern to asset bulk_upsert
           # Use PostgreSQL ON CONFLICT DO UPDATE
           pass
   ```

2. **Create HTTPx Enrichment Task**
   ```python
   # File: app/tasks/enrichment.py
   from celery import Task
   from app.celery_app import celery
   from app.utils.secure_executor import SecureToolExecutor
   from app.repositories.asset_repository import AssetRepository
   from app.repositories.service_repository import ServiceRepository
   from app.database import SessionLocal
   import json
   import logging

   logger = logging.getLogger(__name__)

   @celery.task(name='app.tasks.enrichment.run_httpx')
   def run_httpx(tenant_id: int, asset_ids: Optional[List[int]] = None):
       """
       Run HTTPx for HTTP probing and tech detection

       Args:
           tenant_id: Tenant ID for isolation
           asset_ids: Optional list of specific asset IDs to scan

       Returns:
           dict: Results summary
       """
       db = SessionLocal()

       try:
           asset_repo = AssetRepository(db)
           service_repo = ServiceRepository(db)

           # Get assets to scan
           if asset_ids:
               assets = asset_repo.get_by_ids(tenant_id, asset_ids)
           else:
               assets = asset_repo.get_by_tenant(
                   tenant_id,
                   asset_types=['DOMAIN', 'SUBDOMAIN'],
                   is_active=True
               )

           if not assets:
               logger.info(f"No assets to scan for tenant {tenant_id}")
               return {'scanned': 0}

           # Prepare hosts
           hosts = [asset.identifier for asset in assets]

           # Execute HTTPx with SecureToolExecutor
           with SecureToolExecutor(tenant_id) as executor:
               # Create input file
               hosts_content = '\n'.join(hosts)
               input_file = executor.create_input_file('hosts.txt', hosts_content)
               output_file = 'httpx_results.json'

               # Execute httpx
               returncode, stdout, stderr = executor.execute(
                   'httpx',
                   [
                       '-l', input_file,
                       '-mc', '200,201,301,302,303,307,308,401,403,500',
                       '-server',
                       '-tech-detect',
                       '-title',
                       '-status-code',
                       '-content-length',
                       '-cdn',
                       '-waf',
                       '-http2',
                       '-json',
                       '-silent',
                       '-o', output_file,
                       '-threads', '50',
                       '-rate-limit', '150'
                   ],
                   timeout=settings.discovery_httpx_timeout
               )

               # Read results
               results_json = executor.read_output_file(output_file)

               # Parse and process results
               results = []
               for line in results_json.split('\n'):
                   if line.strip():
                       try:
                           results.append(json.loads(line))
                       except json.JSONDecodeError:
                           logger.warning(f"Failed to parse JSON: {line}")

               # Store results in database
               for result in results:
                   process_httpx_result(
                       tenant_id,
                       result,
                       asset_repo,
                       service_repo,
                       db
                   )

               db.commit()

               return {
                   'scanned': len(results),
                   'tenant_id': tenant_id,
                   'assets_checked': len(hosts)
               }

       except Exception as e:
           logger.error(f"HTTPx scan failed for tenant {tenant_id}: {e}", exc_info=True)
           db.rollback()
           raise
       finally:
           db.close()

   def process_httpx_result(
       tenant_id: int,
       result: dict,
       asset_repo: AssetRepository,
       service_repo: ServiceRepository,
       db: Session
   ):
       """Process single HTTPx result"""
       host = result.get('host')
       url = result.get('url')

       # Find asset
       asset = asset_repo.get_by_identifier(
           tenant_id,
           host,
           'SUBDOMAIN'  # Or 'DOMAIN'
       )

       if not asset:
           logger.warning(f"Asset not found for host: {host}")
           return

       # Extract port from URL
       from urllib.parse import urlparse
       parsed = urlparse(url)
       port = parsed.port or (443 if parsed.scheme == 'https' else 80)

       # Upsert service
       service_repo.upsert_service(
           asset_id=asset.id,
           port=port,
           protocol='http',
           http_title=result.get('title'),
           http_status=result.get('status_code'),
           technologies=json.dumps(result.get('tech', [])),
           product=result.get('server')
       )

       # Update asset metadata
       metadata = json.loads(asset.raw_metadata or '{}')
       metadata['httpx'] = {
           'content_length': result.get('content_length'),
           'cdn': result.get('cdn'),
           'waf': result.get('waf'),
           'http2': result.get('http2'),
           'last_scanned': datetime.utcnow().isoformat()
       }
       asset.raw_metadata = json.dumps(metadata)
       asset.last_seen = datetime.utcnow()
   ```

3. **Testing**
   ```python
   # File: tests/test_enrichment.py
   import pytest
   from app.tasks.enrichment import run_httpx
   from app.models.database import Asset, Service

   def test_httpx_scans_subdomains(db_session, test_tenant):
       # Create test assets
       asset = Asset(
           tenant_id=test_tenant.id,
           type='SUBDOMAIN',
           identifier='api.example.com'
       )
       db_session.add(asset)
       db_session.commit()

       # Mock SecureToolExecutor output
       with patch('app.tasks.enrichment.SecureToolExecutor') as mock_exec:
           mock_exec.return_value.__enter__.return_value.read_output_file.return_value = '''
           {"host":"api.example.com","url":"https://api.example.com","status_code":200,"title":"API","tech":["Nginx"]}
           '''

           result = run_httpx(test_tenant.id)

           assert result['scanned'] > 0

           # Verify service created
           service = db_session.query(Service).filter_by(asset_id=asset.id).first()
           assert service is not None
           assert service.http_title == 'API'
           assert service.http_status == 200
   ```

**Deliverables:**
- HTTPx task implementation
- Service repository
- Integration tests
- Documentation

---

#### Days 4-5: Naabu Implementation

**Implementation:**

```python
# File: app/tasks/enrichment.py (continued)

@celery.task(name='app.tasks.enrichment.run_naabu')
def run_naabu(
    tenant_id: int,
    asset_ids: Optional[List[int]] = None,
    full_scan: bool = False
):
    """
    Run Naabu for port scanning

    Args:
        tenant_id: Tenant ID for isolation
        asset_ids: Optional list of specific asset IDs
        full_scan: If True, scan all 65535 ports. Otherwise top 1000

    Returns:
        dict: Results summary
    """
    db = SessionLocal()

    try:
        asset_repo = AssetRepository(db)
        service_repo = ServiceRepository(db)

        # Get assets to scan (IPs or domains)
        if asset_ids:
            assets = asset_repo.get_by_ids(tenant_id, asset_ids)
        else:
            assets = asset_repo.get_by_tenant(
                tenant_id,
                asset_types=['IP', 'SUBDOMAIN', 'DOMAIN'],
                is_active=True
            )

        if not assets:
            return {'scanned': 0}

        hosts = [asset.identifier for asset in assets]

        # Execute Naabu
        with SecureToolExecutor(tenant_id) as executor:
            hosts_content = '\n'.join(hosts)
            input_file = executor.create_input_file('targets.txt', hosts_content)
            output_file = 'naabu_results.json'

            args = [
                '-l', input_file,
                '-json',
                '-silent',
                '-o', output_file,
                '-rate', '8000',
                '-c', '50'  # Concurrency
            ]

            if full_scan:
                args.extend(['-p', '-'])  # All ports
            else:
                args.extend(['-top-ports', '1000'])

            returncode, stdout, stderr = executor.execute(
                'naabu',
                args,
                timeout=settings.discovery_naabu_timeout
            )

            results_json = executor.read_output_file(output_file)

            # Parse results
            results = []
            for line in results_json.split('\n'):
                if line.strip():
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            # Process results
            for result in results:
                process_naabu_result(
                    tenant_id,
                    result,
                    asset_repo,
                    service_repo,
                    db
                )

            db.commit()

            return {
                'scanned': len(results),
                'tenant_id': tenant_id,
                'full_scan': full_scan
            }

    except Exception as e:
        logger.error(f"Naabu scan failed for tenant {tenant_id}: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()

def process_naabu_result(
    tenant_id: int,
    result: dict,
    asset_repo: AssetRepository,
    service_repo: ServiceRepository,
    db: Session
):
    """Process single Naabu result"""
    host = result.get('host') or result.get('ip')
    port = result.get('port')

    if not host or not port:
        return

    # Find asset
    asset = asset_repo.get_by_identifier(tenant_id, host, 'IP')
    if not asset:
        asset = asset_repo.get_by_identifier(tenant_id, host, 'SUBDOMAIN')

    if not asset:
        logger.warning(f"Asset not found for host: {host}")
        return

    # Upsert service
    service_repo.upsert_service(
        asset_id=asset.id,
        port=port,
        protocol='tcp'
    )

    # Create event for new open port
    from app.models.database import Event, EventKind
    existing_event = db.query(Event).filter_by(
        asset_id=asset.id,
        kind=EventKind.OPEN_PORT
    ).first()

    if not existing_event:
        event = Event(
            asset_id=asset.id,
            kind=EventKind.OPEN_PORT,
            payload=json.dumps({'port': port, 'discovered_at': datetime.utcnow().isoformat()})
        )
        db.add(event)
```

**Testing:**
```python
def test_naabu_discovers_open_ports(db_session, test_tenant):
    asset = Asset(
        tenant_id=test_tenant.id,
        type='IP',
        identifier='1.2.3.4'
    )
    db_session.add(asset)
    db_session.commit()

    with patch('app.tasks.enrichment.SecureToolExecutor') as mock_exec:
        mock_exec.return_value.__enter__.return_value.read_output_file.return_value = '''
        {"host":"1.2.3.4","port":80}
        {"host":"1.2.3.4","port":443}
        {"host":"1.2.3.4","port":22}
        '''

        result = run_naabu(test_tenant.id)

        assert result['scanned'] == 3

        services = db_session.query(Service).filter_by(asset_id=asset.id).all()
        assert len(services) == 3
        assert {s.port for s in services} == {80, 443, 22}
```

**Deliverables:**
- Naabu task implementation
- Open port event creation
- Integration tests

---

#### Days 6-7: Database Schema Updates & Test Improvements

**Database Migration:**
```python
# File: alembic/versions/004_enrichment_fields.py
"""Add enrichment fields

Revision ID: 004
Revises: 003
Create Date: 2025-10-23

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add indexes for service lookups
    op.create_index(
        'idx_services_protocol',
        'services',
        ['protocol']
    )

    op.create_index(
        'idx_services_http_status',
        'services',
        ['http_status']
    )

    # Add index for event kinds
    op.create_index(
        'idx_events_kind',
        'events',
        ['kind']
    )

def downgrade():
    op.drop_index('idx_services_protocol')
    op.drop_index('idx_services_http_status')
    op.drop_index('idx_events_kind')
```

**Test Improvements:**
- Fix integration test failures (target: 80% passing)
- Add enrichment pipeline tests
- Performance benchmarks for HTTPx/Naabu

---

### WEEK 2: TLSx + Katana + API Foundation (Days 8-14)

#### Days 8-9: TLSx Implementation

**Implementation:**

```python
# File: app/tasks/enrichment.py (continued)

@celery.task(name='app.tasks.enrichment.run_tlsx')
def run_tlsx(tenant_id: int, asset_ids: Optional[List[int]] = None):
    """
    Run TLSx for SSL/TLS certificate analysis

    Args:
        tenant_id: Tenant ID
        asset_ids: Optional specific assets to scan

    Returns:
        dict: Results summary
    """
    db = SessionLocal()

    try:
        asset_repo = AssetRepository(db)
        service_repo = ServiceRepository(db)

        # Get assets with HTTPS services
        if asset_ids:
            assets = asset_repo.get_by_ids(tenant_id, asset_ids)
        else:
            assets = asset_repo.get_by_tenant(
                tenant_id,
                asset_types=['SUBDOMAIN', 'DOMAIN'],
                is_active=True
            )

        if not assets:
            return {'scanned': 0}

        hosts = [asset.identifier for asset in assets]

        with SecureToolExecutor(tenant_id) as executor:
            hosts_content = '\n'.join(hosts)
            input_file = executor.create_input_file('hosts.txt', hosts_content)
            output_file = 'tlsx_results.json'

            returncode, stdout, stderr = executor.execute(
                'tlsx',
                [
                    '-l', input_file,
                    '-cn',
                    '-san',
                    '-issuer',
                    '-serial',
                    '-expired',
                    '-self-signed',
                    '-mismatched',
                    '-revoked',
                    '-ja3',
                    '-cipher',
                    '-tls-version',
                    '-hash', 'sha256',
                    '-json',
                    '-silent',
                    '-o', output_file
                ],
                timeout=1800
            )

            results_json = executor.read_output_file(output_file)

            results = []
            for line in results_json.split('\n'):
                if line.strip():
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            for result in results:
                process_tlsx_result(
                    tenant_id,
                    result,
                    asset_repo,
                    service_repo,
                    db
                )

            db.commit()

            return {
                'scanned': len(results),
                'tenant_id': tenant_id
            }

    except Exception as e:
        logger.error(f"TLSx scan failed for tenant {tenant_id}: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()

def process_tlsx_result(
    tenant_id: int,
    result: dict,
    asset_repo: AssetRepository,
    service_repo: ServiceRepository,
    db: Session
):
    """Process TLSx result"""
    host = result.get('host')
    port = result.get('port', 443)

    asset = asset_repo.get_by_identifier(tenant_id, host, 'SUBDOMAIN')
    if not asset:
        asset = asset_repo.get_by_identifier(tenant_id, host, 'DOMAIN')

    if not asset:
        return

    # Upsert HTTPS service
    service_repo.upsert_service(
        asset_id=asset.id,
        port=port,
        protocol='https',
        tls_fingerprint=result.get('ja3')
    )

    # Store certificate info in asset metadata
    metadata = json.loads(asset.raw_metadata or '{}')
    metadata['tls'] = {
        'issuer': result.get('issuer'),
        'common_name': result.get('cn'),
        'san': result.get('san', []),
        'serial': result.get('serial'),
        'not_before': result.get('not_before'),
        'not_after': result.get('not_after'),
        'expired': result.get('expired', False),
        'self_signed': result.get('self_signed', False),
        'mismatched': result.get('mismatched', False),
        'revoked': result.get('revoked', False),
        'cipher': result.get('cipher'),
        'tls_version': result.get('tls_version'),
        'hash': result.get('hash'),
        'last_scanned': datetime.utcnow().isoformat()
    }
    asset.raw_metadata = json.dumps(metadata)

    # Create event for certificate issues
    if result.get('expired') or result.get('mismatched') or result.get('revoked'):
        from app.models.database import Event, EventKind
        event = Event(
            asset_id=asset.id,
            kind=EventKind.NEW_CERT,
            payload=json.dumps({
                'issue': 'expired' if result.get('expired') else 'mismatched',
                'certificate': metadata['tls']
            })
        )
        db.add(event)
```

---

#### Days 10-11: Katana Implementation

**Implementation:**

```python
@celery.task(name='app.tasks.enrichment.run_katana')
def run_katana(tenant_id: int, depth: int = 3):
    """
    Run Katana for web crawling and endpoint discovery

    Args:
        tenant_id: Tenant ID
        depth: Crawl depth (default 3)

    Returns:
        dict: Results summary
    """
    db = SessionLocal()

    try:
        asset_repo = AssetRepository(db)

        # Get HTTP services
        services = db.query(Service).join(Asset).filter(
            Asset.tenant_id == tenant_id,
            Service.protocol == 'http',
            Service.http_status.in_([200, 201, 301, 302])
        ).all()

        if not services:
            return {'crawled': 0}

        # Build URLs
        urls = []
        for service in services:
            protocol = 'https' if service.port == 443 else 'http'
            port_suffix = '' if service.port in [80, 443] else f':{service.port}'
            url = f'{protocol}://{service.asset.identifier}{port_suffix}'
            urls.append(url)

        with SecureToolExecutor(tenant_id) as executor:
            urls_content = '\n'.join(urls)
            input_file = executor.create_input_file('urls.txt', urls_content)
            output_file = 'katana_results.json'

            returncode, stdout, stderr = executor.execute(
                'katana',
                [
                    '-list', input_file,
                    '-js-crawl',
                    '-depth', str(depth),
                    '-field-scope', 'rdn',  # Restrict to registered domain name
                    '-json',
                    '-silent',
                    '-o', output_file,
                    '-concurrency', '10',
                    '-parallelism', '5',
                    '-delay', '0',
                    '-rate-limit', '150',
                    '-timeout', '10'
                ],
                timeout=3600
            )

            results_json = executor.read_output_file(output_file)

            results = []
            for line in results_json.split('\n'):
                if line.strip():
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            # Store URLs as assets
            for result in results:
                process_katana_result(tenant_id, result, asset_repo, db)

            db.commit()

            return {
                'crawled': len(results),
                'tenant_id': tenant_id
            }

    except Exception as e:
        logger.error(f"Katana crawl failed for tenant {tenant_id}: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()

def process_katana_result(
    tenant_id: int,
    result: dict,
    asset_repo: AssetRepository,
    db: Session
):
    """Process Katana crawl result"""
    url = result.get('url')
    source = result.get('source')

    if not url:
        return

    # Create URL asset if not exists
    from app.models.database import AssetType
    existing = asset_repo.get_by_identifier(tenant_id, url, 'URL')

    if not existing:
        asset = Asset(
            tenant_id=tenant_id,
            type=AssetType.URL,
            identifier=url,
            raw_metadata=json.dumps(result)
        )
        db.add(asset)

        # Create event
        from app.models.database import Event, EventKind
        event = Event(
            asset=asset,
            kind=EventKind.NEW_PATH,
            payload=json.dumps({'url': url, 'source': source})
        )
        db.add(event)
```

---

#### Days 12-14: API Foundation & JWT Authentication

**File Structure:**
```
app/
├── routers/
│   ├── __init__.py
│   ├── auth.py (new)
│   ├── tenants.py (new)
│   ├── assets.py (new)
│   └── services.py (new)
├── utils/
│   └── auth.py (update)
├── models/
│   └── auth.py (update)
```

**Authentication Router:**

```python
# File: app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models.auth import User, TenantMembership, Role
from app.utils.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_password_hash,
    verify_password
)

router = APIRouter(tags=["authentication"])
security = HTTPBearer()

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    tenant_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

@router.post("/register", response_model=TokenResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register new user and create tenant

    Returns:
        TokenResponse with access and refresh tokens
    """
    # Check if user exists
    existing_user = db.query(User).filter_by(email=user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        is_active=True
    )
    db.add(user)
    db.flush()

    # Create tenant if specified
    if user_data.tenant_name:
        from app.models.database import Tenant
        import re

        slug = re.sub(r'[^a-z0-9-]', '-', user_data.tenant_name.lower())
        tenant = Tenant(
            name=user_data.tenant_name,
            slug=slug
        )
        db.add(tenant)
        db.flush()

        # Add user to tenant as admin
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            role=Role.ADMIN
        )
        db.add(membership)

    db.commit()

    # Generate tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and return tokens
    """
    user = db.query(User).filter_by(email=credentials.email).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Generate tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token
    """
    try:
        payload = verify_token(credentials.credentials)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        email = payload.get("sub")
        user = db.query(User).filter_by(email=email).first()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        # Generate new tokens
        access_token = create_access_token(data={"sub": email})
        refresh_token = create_refresh_token(data={"sub": email})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
```

**Assets Router:**

```python
# File: app/routers/assets.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.utils.auth import get_current_user, require_tenant_access
from app.models.database import Asset, Service, AssetType
from app.models.auth import User
from app.repositories.asset_repository import AssetRepository

router = APIRouter(tags=["assets"])

class AssetResponse(BaseModel):
    id: int
    type: str
    identifier: str
    first_seen: datetime
    last_seen: datetime
    risk_score: float
    is_active: bool

    class Config:
        from_attributes = True

class AssetListResponse(BaseModel):
    total: int
    items: List[AssetResponse]
    page: int
    page_size: int

@router.get("/{tenant_id}/assets", response_model=AssetListResponse)
def list_assets(
    tenant_id: int,
    asset_type: Optional[str] = None,
    is_active: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List assets for tenant with pagination

    Args:
        tenant_id: Tenant ID
        asset_type: Optional filter by asset type
        is_active: Filter active/inactive assets
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Paginated list of assets
    """
    # Verify user has access to tenant
    require_tenant_access(current_user, tenant_id, db)

    asset_repo = AssetRepository(db)

    # Build filters
    filters = {
        'is_active': is_active
    }

    if asset_type:
        try:
            filters['asset_types'] = [AssetType[asset_type.upper()]]
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid asset type: {asset_type}"
            )

    # Get total count
    total = asset_repo.count_by_tenant(tenant_id, **filters)

    # Get paginated results
    offset = (page - 1) * page_size
    assets = asset_repo.get_by_tenant(
        tenant_id,
        limit=page_size,
        offset=offset,
        **filters
    )

    return AssetListResponse(
        total=total,
        items=[AssetResponse.from_orm(a) for a in assets],
        page=page,
        page_size=page_size
    )

@router.get("/{tenant_id}/assets/{asset_id}", response_model=AssetResponse)
def get_asset(
    tenant_id: int,
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific asset by ID"""
    require_tenant_access(current_user, tenant_id, db)

    asset_repo = AssetRepository(db)
    asset = asset_repo.get_by_id(asset_id)

    if not asset or asset.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    return AssetResponse.from_orm(asset)

@router.get("/{tenant_id}/assets/stats/summary")
def get_asset_summary(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get asset statistics summary

    Returns counts by type and recent changes
    """
    require_tenant_access(current_user, tenant_id, db)

    asset_repo = AssetRepository(db)

    # Count by type
    by_type = {}
    for asset_type in AssetType:
        count = asset_repo.count_by_tenant(
            tenant_id,
            asset_types=[asset_type],
            is_active=True
        )
        by_type[asset_type.value] = count

    # New assets in last 24h
    from datetime import timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    new_24h = db.query(Asset).filter(
        Asset.tenant_id == tenant_id,
        Asset.first_seen >= yesterday
    ).count()

    return {
        'total_assets': sum(by_type.values()),
        'by_type': by_type,
        'new_last_24h': new_24h
    }
```

**Update main.py:**

```python
# File: app/main.py (update)
from app.routers import auth, assets, services

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(assets.router, prefix="/api/v1/tenants")
app.include_router(services.router, prefix="/api/v1/tenants")
```

---

### WEEK 3: Complete API + Monitoring + Testing (Days 15-21)

#### Days 15-16: Complete CRUD Endpoints

**Services Router:**

```python
# File: app/routers/services.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database import get_db
from app.utils.auth import get_current_user, require_tenant_access
from app.models.database import Service, Asset
from app.models.auth import User
from app.repositories.service_repository import ServiceRepository

router = APIRouter(tags=["services"])

class ServiceResponse(BaseModel):
    id: int
    asset_id: int
    port: int
    protocol: str
    product: Optional[str]
    version: Optional[str]
    http_title: Optional[str]
    http_status: Optional[int]
    technologies: Optional[str]

    class Config:
        from_attributes = True

@router.get("/{tenant_id}/assets/{asset_id}/services", response_model=List[ServiceResponse])
def list_services(
    tenant_id: int,
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all services for an asset"""
    require_tenant_access(current_user, tenant_id, db)

    # Verify asset belongs to tenant
    asset = db.query(Asset).filter_by(id=asset_id, tenant_id=tenant_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    service_repo = ServiceRepository(db)
    services = service_repo.get_by_asset(asset_id)

    return [ServiceResponse.from_orm(s) for s in services]
```

**Seeds Router:**

```python
# File: app/routers/seeds.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database import get_db
from app.utils.auth import get_current_user, require_tenant_access
from app.models.database import Seed
from app.models.auth import User

router = APIRouter(tags=["seeds"])

class SeedCreate(BaseModel):
    type: str  # domain, asn, ip_range, keyword
    value: str
    enabled: bool = True

class SeedResponse(BaseModel):
    id: int
    type: str
    value: str
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/{tenant_id}/seeds", response_model=SeedResponse)
def create_seed(
    tenant_id: int,
    seed_data: SeedCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new seed for discovery"""
    require_tenant_access(current_user, tenant_id, db, min_role=Role.ADMIN)

    seed = Seed(
        tenant_id=tenant_id,
        type=seed_data.type,
        value=seed_data.value,
        enabled=seed_data.enabled
    )
    db.add(seed)
    db.commit()
    db.refresh(seed)

    return SeedResponse.from_orm(seed)

@router.get("/{tenant_id}/seeds", response_model=List[SeedResponse])
def list_seeds(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all seeds for tenant"""
    require_tenant_access(current_user, tenant_id, db)

    seeds = db.query(Seed).filter_by(tenant_id=tenant_id).all()
    return [SeedResponse.from_orm(s) for s in seeds]

@router.delete("/{tenant_id}/seeds/{seed_id}")
def delete_seed(
    tenant_id: int,
    seed_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a seed"""
    require_tenant_access(current_user, tenant_id, db, min_role=Role.ADMIN)

    seed = db.query(Seed).filter_by(id=seed_id, tenant_id=tenant_id).first()
    if not seed:
        raise HTTPException(status_code=404, detail="Seed not found")

    db.delete(seed)
    db.commit()

    return {"message": "Seed deleted successfully"}
```

---

#### Days 17-18: Monitoring & Observability

**Sentry Integration:**

```python
# File: app/main.py (update)
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from app.config import settings

# Initialize Sentry
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration()
        ],
        before_send=filter_sensitive_data
    )

def filter_sensitive_data(event, hint):
    """Filter sensitive data from Sentry events"""
    sensitive_keys = ['password', 'secret', 'token', 'api_key']

    if 'request' in event:
        if 'headers' in event['request']:
            for key in list(event['request']['headers'].keys()):
                if any(s in key.lower() for s in sensitive_keys):
                    event['request']['headers'][key] = '[FILTERED]'

    return event
```

**Prometheus Metrics:**

```python
# File: app/utils/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST
from fastapi import Response
import time

# Define metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

enrichment_tasks_total = Counter(
    'enrichment_tasks_total',
    'Total enrichment tasks executed',
    ['tool', 'status']
)

enrichment_duration = Histogram(
    'enrichment_duration_seconds',
    'Enrichment task duration',
    ['tool']
)

active_assets = Gauge(
    'active_assets_total',
    'Number of active assets',
    ['tenant_id', 'type']
)

database_connections = Gauge(
    'database_connections',
    'Number of database connections',
    ['state']  # active, idle
)

# File: app/main.py (add metrics endpoint)
from app.utils.metrics import (
    http_requests_total,
    http_request_duration,
    generate_latest,
    CONTENT_TYPE_LATEST
)

@app.middleware("http")
async def metrics_middleware(request, call_next):
    """Record metrics for all requests"""
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time

    http_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    http_request_duration.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    return response

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

**Rate Limiting:**

```python
# File: app/main.py (add rate limiting)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to endpoints
@router.get("/{tenant_id}/assets")
@limiter.limit("100/minute")
def list_assets(...):
    pass
```

---

#### Days 19-20: Testing & Documentation

**Integration Tests:**

```python
# File: tests/test_api_integration.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.auth import User
from app.models.database import Tenant, Asset

def test_authentication_flow(client: TestClient, db_session):
    """Test complete authentication flow"""
    # Register
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test User",
        "tenant_name": "Test Tenant"
    })
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # Use access token
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = client.get("/api/v1/tenants/1/assets", headers=headers)
    assert response.status_code == 200

    # Refresh token
    refresh_headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    response = client.post("/api/v1/auth/refresh", headers=refresh_headers)
    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens['access_token'] != tokens['access_token']

def test_tenant_isolation(client: TestClient, db_session):
    """Ensure users cannot access other tenants' data"""
    # Create two tenants
    tenant1 = Tenant(name="Tenant 1", slug="tenant-1")
    tenant2 = Tenant(name="Tenant 2", slug="tenant-2")
    db_session.add_all([tenant1, tenant2])
    db_session.commit()

    # Create users for each tenant
    user1 = create_user_with_tenant(db_session, tenant1.id, "user1@example.com")
    user2 = create_user_with_tenant(db_session, tenant2.id, "user2@example.com")

    # Create asset for tenant 1
    asset = Asset(
        tenant_id=tenant1.id,
        type='DOMAIN',
        identifier='example.com'
    )
    db_session.add(asset)
    db_session.commit()

    # User 1 should see asset
    token1 = create_access_token(data={"sub": user1.email})
    headers1 = {"Authorization": f"Bearer {token1}"}
    response = client.get(f"/api/v1/tenants/{tenant1.id}/assets", headers=headers1)
    assert response.status_code == 200
    assert len(response.json()['items']) == 1

    # User 2 should NOT see asset
    token2 = create_access_token(data={"sub": user2.email})
    headers2 = {"Authorization": f"Bearer {token2}"}
    response = client.get(f"/api/v1/tenants/{tenant1.id}/assets", headers=headers2)
    assert response.status_code == 403  # Forbidden

def test_enrichment_pipeline_integration(client: TestClient, db_session):
    """Test full enrichment pipeline"""
    tenant = create_test_tenant(db_session)
    user = create_user_with_tenant(db_session, tenant.id, "test@example.com")
    token = create_access_token(data={"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    # Create seed
    response = client.post(
        f"/api/v1/tenants/{tenant.id}/seeds",
        headers=headers,
        json={"type": "domain", "value": "example.com", "enabled": True}
    )
    assert response.status_code == 200

    # Trigger discovery (would be done by Celery beat in production)
    from app.tasks.discovery import run_full_discovery
    result = run_full_discovery(tenant.id)

    # Verify assets were created
    response = client.get(f"/api/v1/tenants/{tenant.id}/assets", headers=headers)
    assert response.status_code == 200
    assert response.json()['total'] > 0

    # Trigger enrichment
    from app.tasks.enrichment import run_httpx
    result = run_httpx(tenant.id)

    # Verify services were created
    assets = response.json()['items']
    asset_id = assets[0]['id']
    response = client.get(
        f"/api/v1/tenants/{tenant.id}/assets/{asset_id}/services",
        headers=headers
    )
    assert response.status_code == 200
```

**API Documentation:**

```python
# File: app/main.py (update)
app = FastAPI(
    title=settings.app_name,
    description="""
    # EASM Platform API

    External Attack Surface Management platform for continuous asset discovery and security monitoring.

    ## Features

    - **Multi-tenant**: Isolated data per organization
    - **Authentication**: JWT-based authentication
    - **Discovery**: Automated subdomain enumeration
    - **Enrichment**: HTTP probing, port scanning, TLS analysis, web crawling
    - **Monitoring**: Real-time alerts and dashboards

    ## Authentication

    All endpoints require authentication via Bearer token:

    ```
    Authorization: Bearer <access_token>
    ```

    Get tokens via `/api/v1/auth/register` or `/api/v1/auth/login`.

    ## Rate Limiting

    API endpoints are rate-limited:
    - 100 requests/minute per IP
    - 1000 requests/hour per IP

    Rate limit headers are included in responses:
    - X-RateLimit-Limit
    - X-RateLimit-Remaining
    - X-RateLimit-Reset
    """,
    version=settings.app_version,
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc"
)
```

---

#### Day 21: Final Testing & Deployment Prep

**Pre-deployment Checklist:**

```markdown
# Sprint 2 Deployment Checklist

## Critical Security
- [ ] All V-001, V-002, V-003 issues fixed
- [ ] .env removed from git history
- [ ] Production secrets rotated
- [ ] CORS configured correctly
- [ ] Security headers enabled
- [ ] Rate limiting active

## Functionality
- [ ] HTTPx enrichment working
- [ ] Naabu enrichment working
- [ ] TLSx enrichment working
- [ ] Katana enrichment working
- [ ] JWT authentication working
- [ ] All API endpoints tested
- [ ] Multi-tenant isolation verified

## Testing
- [ ] Test coverage ≥ 80%
- [ ] Integration tests passing
- [ ] Security tests passing
- [ ] Performance tests passing
- [ ] Load tests completed

## Monitoring
- [ ] Sentry configured
- [ ] Prometheus metrics working
- [ ] Health checks passing
- [ ] Logging aggregation setup

## Documentation
- [ ] API documentation complete
- [ ] README updated
- [ ] Deployment guide written
- [ ] Architecture diagrams updated
```

---

## TECHNICAL SPECIFICATIONS

### Database Schema Changes

**Migration 004: Enrichment Fields**

```sql
-- Add indexes for service lookups
CREATE INDEX idx_services_protocol ON services(protocol);
CREATE INDEX idx_services_http_status ON services(http_status);
CREATE INDEX idx_events_kind ON events(kind);

-- Add indexes for API performance
CREATE INDEX idx_assets_last_seen ON assets(last_seen);
CREATE INDEX idx_services_last_seen ON services(last_seen);
```

### API Design Specifications

**Versioning Strategy:**
- URL-based versioning: `/api/v1/...`
- Maintain v1 for 12 months after v2 release
- Deprecation warnings in headers

**Response Format:**
```json
{
  "data": {},
  "meta": {
    "page": 1,
    "total": 100,
    "timestamp": "2025-10-23T10:00:00Z"
  },
  "errors": []
}
```

**Error Handling:**
```json
{
  "detail": "Error message",
  "code": "VALIDATION_ERROR",
  "field": "email"
}
```

### Caching Strategy

**Redis Caching:**
- Asset counts: TTL 5 minutes
- Asset lists: TTL 1 minute
- Service lists: TTL 1 minute
- User profile: TTL 10 minutes

**Implementation:**
```python
from functools import wraps
import redis
import json
import hashlib

def cache_result(ttl=60):
    """Decorator to cache function results in Redis"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{hashlib.md5(str(args).encode()).hexdigest()}"

            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            redis_client.setex(cache_key, ttl, json.dumps(result))

            return result
        return wrapper
    return decorator
```

---

## RISK ASSESSMENT

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Tool integration issues | Medium | High | Extensive testing with SecureToolExecutor |
| API performance degradation | Low | Medium | Load testing, caching, indexes |
| Authentication bypass | Low | Critical | Security audit, penetration testing |
| Database connection exhaustion | Medium | High | Connection pooling, monitoring |
| Memory leaks in enrichment | Low | Medium | Resource limits, monitoring |

### Resource Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Enrichment tools slow/timeout | Medium | Medium | Configurable timeouts, retry logic |
| Disk space exhaustion | Low | High | File size limits, cleanup policies |
| CPU overload from parallel scans | Medium | Medium | Celery rate limiting, queue management |

### Timeline Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Security fixes take longer | Low | High | Prioritize Day 1, allocate buffer time |
| Integration testing reveals bugs | Medium | Medium | Daily testing, continuous integration |
| API design requires iteration | Low | Low | Review architecture before implementation |

---

## SUCCESS CRITERIA

### Functional Requirements

✅ **MUST HAVE:**
- All 4 enrichment tools operational (HTTPx, Naabu, TLSx, Katana)
- Complete API with CRUD for assets, services, seeds
- JWT authentication working
- Multi-tenant isolation enforced
- All critical security issues fixed

⭐ **SHOULD HAVE:**
- Test coverage ≥ 80%
- API response time < 100ms (p95)
- Rate limiting enforced
- Security headers enabled
- Monitoring integration complete

💡 **NICE TO HAVE:**
- Real-time WebSocket updates
- Advanced filtering/search
- Export functionality (CSV, JSON)
- Webhook notifications

### Quality Metrics

**Code Quality:**
- Pylint score ≥ 8.0
- No critical SonarQube issues
- Type hints coverage ≥ 80%

**Performance:**
- API endpoints: < 100ms (p95)
- Enrichment pipeline: < 30min for 1000 assets
- Database queries: < 50ms average

**Security:**
- Zero critical vulnerabilities
- Security audit score ≥ 8.5/10
- All OWASP Top 10 covered

**Testing:**
- Unit test coverage ≥ 80%
- Integration tests passing 100%
- E2E tests for critical flows

---

## TIMELINE AND MILESTONES

### Daily Standup Schedule

**Format:**
- 9:00 AM daily (15 minutes)
- What did you complete yesterday?
- What will you work on today?
- Any blockers?

### Weekly Reviews

**End of Week 1 (Day 7):**
- Demo: HTTPx and Naabu working
- Metrics: Test coverage, security fixes
- Retrospective: What went well, what to improve

**End of Week 2 (Day 14):**
- Demo: TLSx, Katana, API foundation
- Metrics: API performance, test results
- Retrospective: Adjustments for Week 3

**End of Week 3 (Day 21):**
- Final demo: Complete Sprint 2 features
- Metrics: All success criteria
- Sprint retrospective
- Sprint 3 planning

### Milestones

| Milestone | Date | Deliverables |
|-----------|------|--------------|
| **M1: Security Fixed** | Day 1 | All critical issues resolved |
| **M2: First Tools** | Day 5 | HTTPx and Naabu operational |
| **M3: All Tools** | Day 11 | TLSx and Katana complete |
| **M4: API Foundation** | Day 14 | Authentication and basic endpoints |
| **M5: Complete API** | Day 18 | All CRUD endpoints working |
| **M6: Production Ready** | Day 21 | Testing, monitoring, documentation complete |

---

## DEFINITION OF DONE

A feature is considered "Done" when:

✅ **Code Complete:**
- Implementation matches specification
- Code review approved by 1+ reviewer
- No merge conflicts
- Follows coding standards

✅ **Tested:**
- Unit tests written and passing
- Integration tests written and passing
- Manual testing completed
- Edge cases covered

✅ **Documented:**
- API documentation updated
- Code comments added
- Architecture diagrams updated
- README updated if needed

✅ **Integrated:**
- Merged to main branch
- CI/CD pipeline passing
- No regression issues
- Deployed to staging environment

✅ **Validated:**
- Meets acceptance criteria
- Product owner approval
- Security review passed (if applicable)
- Performance benchmarks met

---

## COMMUNICATION PLAN

### Daily Communication

**Slack Channels:**
- #easm-sprint2 - General discussion
- #easm-blockers - Urgent issues
- #easm-releases - Deployment announcements

**Status Updates:**
- Daily standup notes in #easm-sprint2
- Blocker escalation in #easm-blockers
- End-of-day summary

### Weekly Communication

**Monday:**
- Week planning meeting
- Review priorities
- Assign tasks

**Wednesday:**
- Mid-week check-in
- Demo progress
- Adjust if needed

**Friday:**
- Week review
- Demo completed features
- Retrospective

### Documentation

**Location:**
- Technical specs: `/docs/sprint-2/`
- API docs: `/docs/api/`
- Architecture: `/docs/architecture/`

**Format:**
- Markdown for documentation
- Mermaid for diagrams
- OpenAPI for API specs

---

## APPENDIX

### A. Environment Variables

**Required for Sprint 2:**

```bash
# Application
ENVIRONMENT=development
SECRET_KEY=<generate-64-char-random>
JWT_SECRET_KEY=<generate-64-char-random>

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=15432
POSTGRES_DB=easm
POSTGRES_USER=easm
POSTGRES_PASSWORD=<strong-password>

# Redis
REDIS_HOST=localhost
REDIS_PORT=16379

# MinIO
MINIO_ENDPOINT=localhost:19000
MINIO_ACCESS_KEY=<access-key>
MINIO_SECRET_KEY=<secret-key>

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# Monitoring
SENTRY_DSN=<your-sentry-dsn>
SENTRY_ENVIRONMENT=development

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=100
```

### B. Tool Configuration

**HTTPx:**
- Threads: 50
- Rate limit: 150 req/s
- Timeout: 900s
- Match codes: 200,201,301,302,303,307,308,401,403,500

**Naabu:**
- Rate: 8000 packets/s
- Concurrency: 50
- Timeout: 1200s
- Default: Top 1000 ports

**TLSx:**
- Timeout: 1800s
- Checks: CN, SAN, issuer, expiry, revocation

**Katana:**
- Depth: 3
- Concurrency: 10
- Rate limit: 150 req/s
- Timeout: 3600s

### C. API Endpoints Summary

**Authentication:**
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh

**Assets:**
- GET /api/v1/tenants/{id}/assets
- GET /api/v1/tenants/{id}/assets/{asset_id}
- GET /api/v1/tenants/{id}/assets/stats/summary

**Services:**
- GET /api/v1/tenants/{id}/assets/{asset_id}/services

**Seeds:**
- POST /api/v1/tenants/{id}/seeds
- GET /api/v1/tenants/{id}/seeds
- DELETE /api/v1/tenants/{id}/seeds/{seed_id}

**System:**
- GET /health
- GET /metrics

### D. Testing Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_enrichment.py

# Run integration tests only
pytest tests/test_integration.py -v

# Run performance tests
pytest tests/test_performance.py --benchmark

# Security tests
pytest tests/test_security.py -v
```

### E. Deployment Commands

```bash
# Start services
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# View logs
docker-compose logs -f api

# Stop services
docker-compose down

# Restart specific service
docker-compose restart api
```

---

## CONCLUSION

Sprint 2 is a critical phase that transforms the EASM platform from a discovery-only system into a comprehensive security monitoring platform with enrichment capabilities and a production-ready API.

### Key Success Factors

1. **Security First**: Fix all critical issues on Day 1
2. **Testing Discipline**: Maintain 80%+ coverage throughout
3. **Incremental Progress**: Ship features daily, test continuously
4. **Communication**: Daily standups, clear blockers, proactive updates
5. **Quality Gates**: No merge without tests, review, and documentation

### Expected Outcome

By the end of Sprint 2, the EASM platform will have:
- ✅ 4 enrichment tools operational
- ✅ Complete multi-tenant API
- ✅ JWT authentication system
- ✅ Production-ready monitoring
- ✅ 80%+ test coverage
- ✅ Zero critical security issues
- ✅ Complete API documentation

This sets the foundation for Sprint 3 (Vulnerability Scanning & Risk Scoring) and Sprint 4 (UI & Alerting).

---

**Document Version**: 1.0
**Last Updated**: October 23, 2025
**Next Review**: Start of Sprint 3
**Status**: Ready for Implementation

---

*End of Sprint 2 Detailed Plan*
