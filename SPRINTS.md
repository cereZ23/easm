# EASM Platform - 4 Sprint Development Plan

## Sprint 1: Core Infrastructure & Discovery Pipeline (Weeks 1-3)

### Goal
Establish foundational infrastructure and implement the core discovery pipeline with basic data persistence.

### Infrastructure Setup

#### 1.1 Docker Compose Environment
**Files to create:**
- `docker-compose.yml` - Multi-service orchestration
- `Dockerfile.api` - FastAPI application container
- `Dockerfile.worker` - Celery worker with ProjectDiscovery tools
- `.env.example` - Environment variables template

**Services:**
```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: easm
      POSTGRES_USER: easm
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    depends_on:
      - postgres
      - redis
      - minio
    environment:
      DATABASE_URL: postgresql://easm:${DB_PASSWORD}@postgres:5432/easm
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    depends_on:
      - postgres
      - redis
      - minio
    environment:
      DATABASE_URL: postgresql://easm:${DB_PASSWORD}@postgres:5432/easm
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./app:/app
      - ./nuclei-templates:/root/nuclei-templates

  beat:
    build:
      context: .
      dockerfile: Dockerfile.worker
    command: celery -A app.celery beat --loglevel=info
    depends_on:
      - redis
      - postgres
```

#### 1.2 Database Schema Implementation
**File:** `app/models/database.py`

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum, Float, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class Tenant(Base):
    __tablename__ = 'tenants'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    contact_policy = Column(Text)
    api_keys = Column(Text)  # JSON encrypted field for OSINT providers
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assets = relationship("Asset", back_populates="tenant", cascade="all, delete-orphan")
    seeds = relationship("Seed", back_populates="tenant", cascade="all, delete-orphan")

class AssetType(enum.Enum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP = "ip"
    URL = "url"
    SERVICE = "service"

class Asset(Base):
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    type = Column(Enum(AssetType), nullable=False)
    identifier = Column(String(500), nullable=False)  # Domain, IP, URL
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    risk_score = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    metadata = Column(Text)  # JSON field for flexible attrs

    tenant = relationship("Tenant", back_populates="assets")
    services = relationship("Service", back_populates="asset", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="asset", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="asset", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_tenant_type', 'tenant_id', 'type'),
        Index('idx_identifier', 'identifier'),
    )

class Service(Base):
    __tablename__ = 'services'

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey('assets.id'), nullable=False)
    port = Column(Integer)
    protocol = Column(String(50))
    product = Column(String(255))
    version = Column(String(100))
    tls_fingerprint = Column(String(255))
    http_title = Column(String(500))
    http_status = Column(Integer)
    technologies = Column(Text)  # JSON array
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="services")

class FindingStatus(enum.Enum):
    OPEN = "open"
    SUPPRESSED = "suppressed"
    FIXED = "fixed"

class FindingSeverity(enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Finding(Base):
    __tablename__ = 'findings'

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey('assets.id'), nullable=False)
    source = Column(String(50), default='nuclei')  # nuclei, manual, custom
    template_id = Column(String(255))
    name = Column(String(500), nullable=False)
    severity = Column(Enum(FindingSeverity), nullable=False)
    cvss_score = Column(Float)
    cve_id = Column(String(50))
    evidence = Column(Text)  # JSON
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(FindingStatus), default=FindingStatus.OPEN)

    asset = relationship("Asset", back_populates="findings")

    __table_args__ = (
        Index('idx_asset_severity', 'asset_id', 'severity'),
        Index('idx_status', 'status'),
    )

class EventKind(enum.Enum):
    NEW_ASSET = "new_asset"
    OPEN_PORT = "open_port"
    NEW_CERT = "new_cert"
    NEW_PATH = "new_path"
    TECH_CHANGE = "tech_change"

class Event(Base):
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey('assets.id'), nullable=False)
    kind = Column(Enum(EventKind), nullable=False)
    payload = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="events")

    __table_args__ = (
        Index('idx_created_at', 'created_at'),
    )

class Seed(Base):
    __tablename__ = 'seeds'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    type = Column(String(50))  # domain, asn, ip_range, keyword
    value = Column(String(500), nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="seeds")
```

**Migration file:** `alembic/versions/001_initial_schema.py`

#### 1.3 Celery Configuration
**File:** `app/celery.py`

```python
from celery import Celery
from celery.schedules import crontab
import os

celery = Celery(
    'easm',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    include=['app.tasks.discovery', 'app.tasks.enrichment', 'app.tasks.scanning']
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

# Celery Beat Schedule
celery.conf.beat_schedule = {
    'daily-full-discovery': {
        'task': 'app.tasks.discovery.run_full_discovery',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
    'critical-asset-watch': {
        'task': 'app.tasks.discovery.watch_critical_assets',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
}
```

### Discovery Pipeline Implementation

#### 1.4 Core Discovery Tasks
**File:** `app/tasks/discovery.py`

```python
from celery import chain, group
from app.celery import celery
from app.models.database import Tenant, Asset, Seed, Event, AssetType
from app.utils.storage import store_raw_output
from sqlalchemy.orm import Session
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
        for tenant in tenants:
            chain(
                collect_seeds.si(tenant.id),
                run_subfinder.s(tenant.id),
                run_dnsx.s(tenant.id),
                process_discovery_results.s(tenant.id)
            ).apply_async()
    finally:
        db.close()

@celery.task(name='app.tasks.discovery.collect_seeds')
def collect_seeds(tenant_id: int):
    """Collect seeds from database and optionally run uncover"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        tenant = db.query(Tenant).filter_by(id=tenant_id).first()
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

        # Run uncover if keywords are present and API keys configured
        if seed_data['keywords'] and tenant.api_keys:
            uncover_results = run_uncover(tenant_id, seed_data['keywords'])
            seed_data['domains'].extend(uncover_results)

        return seed_data
    finally:
        db.close()

def run_uncover(tenant_id: int, keywords: list) -> list:
    """Run uncover for OSINT discovery"""
    results = []

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        output_file = f.name

    try:
        for keyword in keywords:
            cmd = [
                'uncover',
                '-q', f'org:"{keyword}"',
                '-e', 'shodan,censys,fofa',
                '-silent',
                '-o', output_file
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            with open(output_file, 'r') as f:
                results.extend([line.strip() for line in f if line.strip()])

        # Store raw output in MinIO
        store_raw_output(tenant_id, 'uncover', results)

        return list(set(results))
    finally:
        os.unlink(output_file)

@celery.task(name='app.tasks.discovery.run_subfinder')
def run_subfinder(seed_data: dict, tenant_id: int):
    """Run subfinder for subdomain enumeration"""

    if not seed_data['domains']:
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

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        with open(output_file, 'r') as f:
            subdomains = [line.strip() for line in f if line.strip()]

        # Store raw output
        store_raw_output(tenant_id, 'subfinder', subdomains)

        return {
            'subdomains': subdomains,
            'tenant_id': tenant_id
        }
    finally:
        os.unlink(domains_file)
        os.unlink(output_file)

@celery.task(name='app.tasks.discovery.run_dnsx')
def run_dnsx(subfinder_result: dict, tenant_id: int):
    """Run dnsx for DNS resolution"""

    subdomains = subfinder_result['subdomains']

    if not subdomains:
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

        subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        resolved_records = []
        with open(output_file, 'r') as f:
            for line in f:
                if line.strip():
                    resolved_records.append(json.loads(line))

        # Store raw output
        store_raw_output(tenant_id, 'dnsx', resolved_records)

        return {
            'resolved': resolved_records,
            'tenant_id': tenant_id
        }
    finally:
        os.unlink(subdomains_file)
        os.unlink(output_file)

@celery.task(name='app.tasks.discovery.process_discovery_results')
def process_discovery_results(dnsx_result: dict, tenant_id: int):
    """Process discovery results and store in database"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        resolved = dnsx_result['resolved']
        new_assets = []

        for record in resolved:
            host = record.get('host')

            # Determine asset type
            asset_type = AssetType.SUBDOMAIN
            if not any(c.isalpha() for c in host):
                asset_type = AssetType.IP

            # Check if asset exists
            existing = db.query(Asset).filter_by(
                tenant_id=tenant_id,
                identifier=host,
                type=asset_type
            ).first()

            if existing:
                existing.last_seen = datetime.utcnow()
            else:
                asset = Asset(
                    tenant_id=tenant_id,
                    type=asset_type,
                    identifier=host,
                    metadata=json.dumps(record)
                )
                db.add(asset)
                new_assets.append(host)

                # Create event
                event = Event(
                    asset=asset,
                    kind=EventKind.NEW_ASSET,
                    payload=json.dumps({'record': record})
                )
                db.add(event)

        db.commit()

        return {
            'new_assets': len(new_assets),
            'total_resolved': len(resolved),
            'tenant_id': tenant_id
        }
    finally:
        db.close()
```

#### 1.5 Storage Utilities
**File:** `app/utils/storage.py`

```python
from minio import Minio
from datetime import datetime
import json
import os

def get_minio_client():
    return Minio(
        os.getenv('MINIO_ENDPOINT', 'localhost:9000'),
        access_key=os.getenv('MINIO_USER'),
        secret_key=os.getenv('MINIO_PASSWORD'),
        secure=False
    )

def store_raw_output(tenant_id: int, tool: str, data: any):
    """Store raw tool output in MinIO"""
    client = get_minio_client()
    bucket_name = f'tenant-{tenant_id}'

    # Ensure bucket exists
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)

    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    object_name = f'{tool}/{timestamp}.json'

    data_bytes = json.dumps(data, indent=2).encode('utf-8')

    client.put_object(
        bucket_name,
        object_name,
        data=data_bytes,
        length=len(data_bytes),
        content_type='application/json'
    )
```

### Testing & Validation

#### 1.6 Unit Tests
**File:** `tests/test_discovery.py`

```python
import pytest
from unittest.mock import patch, MagicMock
from app.tasks.discovery import run_subfinder, run_dnsx, process_discovery_results

def test_run_subfinder():
    seed_data = {'domains': ['example.com'], 'asns': [], 'ip_ranges': [], 'keywords': []}

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        # Mock file operations
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = 'sub1.example.com\nsub2.example.com'

            result = run_subfinder(seed_data, 1)

            assert 'subdomains' in result
            assert result['tenant_id'] == 1
```

### Sprint 1 Deliverables

- [ ] Docker Compose environment with all services
- [ ] PostgreSQL database with complete schema
- [ ] Celery worker and beat scheduler configured
- [ ] MinIO storage for raw outputs
- [ ] Discovery pipeline: uncover → subfinder → dnsx
- [ ] Asset persistence in database
- [ ] Event tracking for new assets
- [ ] Unit tests for discovery tasks
- [ ] Basic logging and error handling

---

## Sprint 2: Enrichment Pipeline & Multi-Tenant API (Weeks 4-6)

### Goal
Implement enrichment tools (httpx, naabu, tlsx, katana), build FastAPI backend with JWT authentication, and create multi-tenant API endpoints.

### Enrichment Tasks Implementation

#### 2.1 HTTP Enrichment
**File:** `app/tasks/enrichment.py`

```python
from celery import chain
from app.celery import celery
from app.models.database import Asset, Service, Event, EventKind
from app.utils.storage import store_raw_output
import subprocess
import json
import tempfile
import os

@celery.task(name='app.tasks.enrichment.run_httpx')
def run_httpx(tenant_id: int, asset_ids: list = None):
    """Run httpx for HTTP probing and tech detection"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        # Get assets to probe
        query = db.query(Asset).filter_by(tenant_id=tenant_id, is_active=True)
        if asset_ids:
            query = query.filter(Asset.id.in_(asset_ids))

        assets = query.filter(Asset.type.in_(['subdomain', 'domain', 'url'])).all()

        if not assets:
            return {'probed': 0, 'tenant_id': tenant_id}

        # Prepare input file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            hosts_file = f.name
            f.write('\n'.join([a.identifier for a in assets]))

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name

        try:
            cmd = [
                'httpx',
                '-l', hosts_file,
                '-mc', '200,301,302,303,307,308,401,403,500',
                '-server',
                '-tech-detect',
                '-title',
                '-status-code',
                '-content-length',
                '-follow-redirects',
                '-cdn',
                '-waf',
                '-http2',
                '-pipeline',
                '-json',
                '-silent',
                '-o', output_file,
                '-threads', '50',
                '-rate-limit', '150'
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

            # Parse results
            http_results = []
            with open(output_file, 'r') as f:
                for line in f:
                    if line.strip():
                        http_results.append(json.loads(line))

            # Store raw output
            store_raw_output(tenant_id, 'httpx', http_results)

            # Process and store in database
            process_httpx_results(tenant_id, http_results, db)

            return {
                'probed': len(http_results),
                'tenant_id': tenant_id
            }
        finally:
            os.unlink(hosts_file)
            os.unlink(output_file)
    finally:
        db.close()

def process_httpx_results(tenant_id: int, results: list, db):
    """Process httpx results and update services"""
    for result in results:
        url = result.get('url')
        host = result.get('host')

        # Find asset
        asset = db.query(Asset).filter_by(
            tenant_id=tenant_id,
            identifier=host
        ).first()

        if not asset:
            continue

        # Extract port from URL
        port = result.get('port', 443 if 'https' in url else 80)

        # Check if service exists
        service = db.query(Service).filter_by(
            asset_id=asset.id,
            port=port,
            protocol='http'
        ).first()

        if not service:
            service = Service(
                asset_id=asset.id,
                port=port,
                protocol='http'
            )
            db.add(service)

        # Update service details
        service.http_title = result.get('title')
        service.http_status = result.get('status_code')
        service.technologies = json.dumps(result.get('tech', []))
        service.last_seen = datetime.utcnow()

        # Update asset metadata
        metadata = json.loads(asset.metadata or '{}')
        metadata['httpx'] = {
            'server': result.get('server'),
            'content_length': result.get('content_length'),
            'cdn': result.get('cdn'),
            'waf': result.get('waf'),
            'http2': result.get('http2')
        }
        asset.metadata = json.dumps(metadata)
        asset.last_seen = datetime.utcnow()

    db.commit()

@celery.task(name='app.tasks.enrichment.run_naabu')
def run_naabu(tenant_id: int, asset_ids: list = None, full_scan: bool = False):
    """Run naabu for port scanning"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        # Get IP assets
        query = db.query(Asset).filter_by(tenant_id=tenant_id, is_active=True)
        if asset_ids:
            query = query.filter(Asset.id.in_(asset_ids))

        assets = query.filter(Asset.type == 'ip').all()

        if not assets:
            # Try to get IPs from domains
            assets = query.filter(Asset.type.in_(['subdomain', 'domain'])).all()

        if not assets:
            return {'scanned': 0, 'tenant_id': tenant_id}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            hosts_file = f.name
            f.write('\n'.join([a.identifier for a in assets]))

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name

        try:
            cmd = [
                'naabu',
                '-l', hosts_file,
                '-json',
                '-silent',
                '-o', output_file,
                '-rate', '8000'
            ]

            if full_scan:
                cmd.extend(['-p', '-'])  # Full port scan
            else:
                cmd.extend(['-top-ports', '1000'])

            subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

            # Parse results
            port_results = []
            with open(output_file, 'r') as f:
                for line in f:
                    if line.strip():
                        port_results.append(json.loads(line))

            store_raw_output(tenant_id, 'naabu', port_results)
            process_naabu_results(tenant_id, port_results, db)

            return {
                'scanned': len(port_results),
                'tenant_id': tenant_id
            }
        finally:
            os.unlink(hosts_file)
            os.unlink(output_file)
    finally:
        db.close()

def process_naabu_results(tenant_id: int, results: list, db):
    """Process naabu results and create service records"""
    for result in results:
        host = result.get('host') or result.get('ip')
        port = result.get('port')

        # Find asset
        asset = db.query(Asset).filter_by(
            tenant_id=tenant_id,
            identifier=host
        ).first()

        if not asset:
            continue

        # Check if service exists
        service = db.query(Service).filter_by(
            asset_id=asset.id,
            port=port
        ).first()

        if not service:
            service = Service(
                asset_id=asset.id,
                port=port,
                protocol='tcp'
            )
            db.add(service)

            # Create event for new port
            event = Event(
                asset_id=asset.id,
                kind=EventKind.OPEN_PORT,
                payload=json.dumps({'port': port})
            )
            db.add(event)

        service.last_seen = datetime.utcnow()

    db.commit()

@celery.task(name='app.tasks.enrichment.run_tlsx')
def run_tlsx(tenant_id: int, asset_ids: list = None):
    """Run tlsx for TLS/SSL certificate intelligence"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        query = db.query(Asset).filter_by(tenant_id=tenant_id, is_active=True)
        if asset_ids:
            query = query.filter(Asset.id.in_(asset_ids))

        assets = query.filter(Asset.type.in_(['subdomain', 'domain'])).all()

        if not assets:
            return {'scanned': 0, 'tenant_id': tenant_id}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            hosts_file = f.name
            f.write('\n'.join([a.identifier for a in assets]))

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name

        try:
            cmd = [
                'tlsx',
                '-l', hosts_file,
                '-cn',
                '-san',
                '-issuer',
                '-expiry',
                '-serial',
                '-alpn',
                '-ja3',
                '-cipher',
                '-tls-version',
                '-json',
                '-silent',
                '-o', output_file
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

            tls_results = []
            with open(output_file, 'r') as f:
                for line in f:
                    if line.strip():
                        tls_results.append(json.loads(line))

            store_raw_output(tenant_id, 'tlsx', tls_results)
            process_tlsx_results(tenant_id, tls_results, db)

            return {
                'scanned': len(tls_results),
                'tenant_id': tenant_id
            }
        finally:
            os.unlink(hosts_file)
            os.unlink(output_file)
    finally:
        db.close()

def process_tlsx_results(tenant_id: int, results: list, db):
    """Process tlsx results"""
    for result in results:
        host = result.get('host')
        port = result.get('port', 443)

        asset = db.query(Asset).filter_by(
            tenant_id=tenant_id,
            identifier=host
        ).first()

        if not asset:
            continue

        # Find or create service
        service = db.query(Service).filter_by(
            asset_id=asset.id,
            port=port
        ).first()

        if not service:
            service = Service(
                asset_id=asset.id,
                port=port,
                protocol='https'
            )
            db.add(service)

        # Store TLS fingerprint
        service.tls_fingerprint = result.get('ja3')
        service.last_seen = datetime.utcnow()

        # Update asset metadata with cert info
        metadata = json.loads(asset.metadata or '{}')
        metadata['tls'] = {
            'issuer': result.get('issuer'),
            'cn': result.get('cn'),
            'san': result.get('san'),
            'expiry': result.get('not_after'),
            'cipher': result.get('cipher'),
            'tls_version': result.get('tls_version')
        }
        asset.metadata = json.dumps(metadata)

        # Create event if cert is new
        event = Event(
            asset_id=asset.id,
            kind=EventKind.NEW_CERT,
            payload=json.dumps(metadata['tls'])
        )
        db.add(event)

    db.commit()

@celery.task(name='app.tasks.enrichment.run_katana')
def run_katana(tenant_id: int):
    """Run katana for web crawling"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        # Get HTTP services
        services = db.query(Service).join(Asset).filter(
            Asset.tenant_id == tenant_id,
            Service.protocol == 'http',
            Service.http_status.in_([200, 301, 302])
        ).all()

        if not services:
            return {'crawled': 0, 'tenant_id': tenant_id}

        # Build URLs from services
        urls = []
        for service in services:
            protocol = 'https' if service.port == 443 else 'http'
            port_suffix = '' if service.port in [80, 443] else f':{service.port}'
            url = f'{protocol}://{service.asset.identifier}{port_suffix}'
            urls.append(url)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            urls_file = f.name
            f.write('\n'.join(urls))

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name

        try:
            cmd = [
                'katana',
                '-list', urls_file,
                '-js-crawl',
                '-depth', '3',
                '-json',
                '-silent',
                '-o', output_file,
                '-concurrency', '10',
                '-rate-limit', '150',
                '-timeout', '10'
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

            crawl_results = []
            with open(output_file, 'r') as f:
                for line in f:
                    if line.strip():
                        crawl_results.append(json.loads(line))

            store_raw_output(tenant_id, 'katana', crawl_results)
            process_katana_results(tenant_id, crawl_results, db)

            return {
                'crawled': len(crawl_results),
                'tenant_id': tenant_id
            }
        finally:
            os.unlink(urls_file)
            os.unlink(output_file)
    finally:
        db.close()

def process_katana_results(tenant_id: int, results: list, db):
    """Process katana crawl results"""
    for result in results:
        url = result.get('url')
        source = result.get('source')

        # Create URL asset if not exists
        existing = db.query(Asset).filter_by(
            tenant_id=tenant_id,
            identifier=url,
            type=AssetType.URL
        ).first()

        if not existing:
            asset = Asset(
                tenant_id=tenant_id,
                type=AssetType.URL,
                identifier=url,
                metadata=json.dumps(result)
            )
            db.add(asset)

            event = Event(
                asset=asset,
                kind=EventKind.NEW_PATH,
                payload=json.dumps({'url': url, 'source': source})
            )
            db.add(event)

    db.commit()
```

### FastAPI Backend Implementation

#### 2.2 API Core Setup
**File:** `app/main.py`

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import jwt
from datetime import datetime, timedelta
import os

from app.database import SessionLocal, engine
from app.models import database
from app.routers import tenants, assets, findings, seeds

# Create tables
database.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EASM Platform API",
    description="External Attack Surface Management Platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and return payload"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

def get_current_tenant(
    token_payload: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get current tenant from token"""
    tenant_id = token_payload.get('tenant_id')
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Invalid token")

    tenant = db.query(database.Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return tenant

# Include routers
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["tenants"])
app.include_router(assets.router, prefix="/api/v1/tenants/{tenant_id}/assets", tags=["assets"])
app.include_router(findings.router, prefix="/api/v1/tenants/{tenant_id}/findings", tags=["findings"])
app.include_router(seeds.router, prefix="/api/v1/tenants/{tenant_id}/seeds", tags=["seeds"])

@app.get("/")
def root():
    return {"message": "EASM Platform API", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

#### 2.3 Assets Router
**File:** `app/routers/assets.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.main import get_db, get_current_tenant
from app.models.database import Asset, Service, Event, Tenant, AssetType

router = APIRouter()

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

class ServiceResponse(BaseModel):
    id: int
    port: int
    protocol: str
    product: Optional[str]
    http_title: Optional[str]
    http_status: Optional[int]

    class Config:
        from_attributes = True

@router.get("", response_model=List[AssetResponse])
def get_assets(
    tenant_id: int,
    asset_type: Optional[str] = None,
    changed_since: Optional[datetime] = None,
    is_active: bool = True,
    skip: int = 0,
    limit: int = 100,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get assets for tenant with optional filters"""

    if current_tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(Asset).filter_by(tenant_id=tenant_id, is_active=is_active)

    if asset_type:
        query = query.filter_by(type=AssetType[asset_type.upper()])

    if changed_since:
        query = query.filter(Asset.last_seen >= changed_since)

    assets = query.order_by(Asset.risk_score.desc()).offset(skip).limit(limit).all()

    return assets

@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    tenant_id: int,
    asset_id: int,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get specific asset"""

    if current_tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    asset = db.query(Asset).filter_by(id=asset_id, tenant_id=tenant_id).first()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    return asset

@router.get("/{asset_id}/services", response_model=List[ServiceResponse])
def get_asset_services(
    tenant_id: int,
    asset_id: int,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get services for an asset"""

    if current_tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    asset = db.query(Asset).filter_by(id=asset_id, tenant_id=tenant_id).first()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    services = db.query(Service).filter_by(asset_id=asset_id).all()

    return services

@router.get("/stats/summary")
def get_asset_summary(
    tenant_id: int,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get asset statistics summary"""

    if current_tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    total = db.query(Asset).filter_by(tenant_id=tenant_id, is_active=True).count()

    by_type = {}
    for asset_type in AssetType:
        count = db.query(Asset).filter_by(
            tenant_id=tenant_id,
            type=asset_type,
            is_active=True
        ).count()
        by_type[asset_type.value] = count

    # New assets in last 24h
    yesterday = datetime.utcnow() - timedelta(days=1)
    new_24h = db.query(Asset).filter(
        Asset.tenant_id == tenant_id,
        Asset.first_seen >= yesterday
    ).count()

    return {
        'total_assets': total,
        'by_type': by_type,
        'new_last_24h': new_24h
    }
```

### Sprint 2 Deliverables

- [ ] Enrichment tasks: httpx, naabu, tlsx, katana
- [ ] Service records with HTTP/TLS metadata
- [ ] FastAPI application with JWT authentication
- [ ] Multi-tenant isolation at API level
- [ ] Asset and service REST endpoints
- [ ] Query filters (changed_since, type, status)
- [ ] Statistics and summary endpoints
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Integration tests for enrichment pipeline
- [ ] API endpoint tests

---

## Sprint 3: Vulnerability Scanning & Risk Scoring (Weeks 7-9)

### Goal
Integrate Nuclei for vulnerability scanning, implement risk scoring algorithm, build finding management system with status tracking, and add historical comparison features.

### Nuclei Integration

#### 3.1 Scanning Tasks
**File:** `app/tasks/scanning.py`

```python
from celery import chain
from app.celery import celery
from app.models.database import Asset, Finding, FindingSeverity, FindingStatus, Service
from app.utils.storage import store_raw_output
from app.utils.risk_scoring import calculate_asset_risk
import subprocess
import json
import tempfile
import os
from datetime import datetime

@celery.task(name='app.tasks.scanning.run_nuclei')
def run_nuclei(
    tenant_id: int,
    asset_ids: list = None,
    severity_filter: list = ['critical', 'high', 'medium'],
    templates: list = None
):
    """Run Nuclei vulnerability scanner"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        # Get assets with HTTP services
        query = db.query(Asset).join(Service).filter(
            Asset.tenant_id == tenant_id,
            Asset.is_active == True,
            Service.protocol.in_(['http', 'https'])
        )

        if asset_ids:
            query = query.filter(Asset.id.in_(asset_ids))

        assets = query.distinct().all()

        if not assets:
            return {'findings': 0, 'tenant_id': tenant_id}

        # Build URLs from assets and services
        urls = []
        for asset in assets:
            for service in asset.services:
                if service.protocol in ['http', 'https']:
                    protocol = service.protocol
                    port_suffix = '' if service.port in [80, 443] else f':{service.port}'
                    url = f'{protocol}://{asset.identifier}{port_suffix}'
                    urls.append(url)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            urls_file = f.name
            f.write('\n'.join(urls))

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name

        try:
            cmd = [
                'nuclei',
                '-l', urls_file,
                '-severity', ','.join(severity_filter),
                '-json',
                '-silent',
                '-o', output_file,
                '-rate-limit', '300',
                '-bulk-size', '50',
                '-concurrency', '50',
                '-timeout', '10',
                '-retries', '1'
            ]

            # Add template filters
            if templates:
                for template in templates:
                    cmd.extend(['-t', template])
            else:
                # Default safe templates
                cmd.extend([
                    '-t', 'cves/',
                    '-t', 'exposed-panels/',
                    '-t', 'misconfiguration/',
                    '-t', 'vulnerabilities/',
                    '-exclude-templates', 'fuzzing/',
                    '-exclude-templates', 'dos/'
                ])

            subprocess.run(cmd, capture_output=True, text=True, timeout=7200)  # 2 hour timeout

            # Parse results
            findings = []
            with open(output_file, 'r') as f:
                for line in f:
                    if line.strip():
                        findings.append(json.loads(line))

            store_raw_output(tenant_id, 'nuclei', findings)
            process_nuclei_results(tenant_id, findings, db)

            return {
                'findings': len(findings),
                'tenant_id': tenant_id
            }
        finally:
            os.unlink(urls_file)
            os.unlink(output_file)
    finally:
        db.close()

def process_nuclei_results(tenant_id: int, results: list, db):
    """Process Nuclei findings and store in database"""
    for result in results:
        # Extract finding details
        template_id = result.get('template-id')
        name = result.get('info', {}).get('name', template_id)
        severity = result.get('info', {}).get('severity', 'info')
        matched_at = result.get('matched-at')
        host = result.get('host')

        # Find asset
        # Extract hostname from URL
        from urllib.parse import urlparse
        parsed = urlparse(matched_at or host)
        hostname = parsed.netloc.split(':')[0] if parsed.netloc else host

        asset = db.query(Asset).filter_by(
            tenant_id=tenant_id,
            identifier=hostname
        ).first()

        if not asset:
            continue

        # Map severity
        severity_map = {
            'info': FindingSeverity.INFO,
            'low': FindingSeverity.LOW,
            'medium': FindingSeverity.MEDIUM,
            'high': FindingSeverity.HIGH,
            'critical': FindingSeverity.CRITICAL
        }

        finding_severity = severity_map.get(severity.lower(), FindingSeverity.INFO)

        # Check if finding already exists
        existing = db.query(Finding).filter_by(
            asset_id=asset.id,
            template_id=template_id,
            status=FindingStatus.OPEN
        ).first()

        if existing:
            # Update last seen
            existing.last_seen = datetime.utcnow()
            existing.evidence = json.dumps(result)
        else:
            # Create new finding
            finding = Finding(
                asset_id=asset.id,
                source='nuclei',
                template_id=template_id,
                name=name,
                severity=finding_severity,
                cvss_score=result.get('info', {}).get('classification', {}).get('cvss-score'),
                cve_id=result.get('info', {}).get('classification', {}).get('cve-id'),
                evidence=json.dumps(result),
                status=FindingStatus.OPEN
            )
            db.add(finding)

        # Recalculate asset risk score
        asset.risk_score = calculate_asset_risk(asset, db)

    db.commit()
```

#### 3.2 Risk Scoring Algorithm
**File:** `app/utils/risk_scoring.py`

```python
from app.models.database import Asset, Finding, FindingSeverity, Service, Event, EventKind
from sqlalchemy import func
from datetime import datetime, timedelta
import json

def calculate_asset_risk(asset, db) -> float:
    """Calculate risk score for an asset"""

    score = 0.0

    # 1. Severity-based scoring from findings
    severity_weights = {
        FindingSeverity.CRITICAL: 100,
        FindingSeverity.HIGH: 50,
        FindingSeverity.MEDIUM: 20,
        FindingSeverity.LOW: 5,
        FindingSeverity.INFO: 1
    }

    findings = db.query(Finding).filter_by(
        asset_id=asset.id,
        status='open'
    ).all()

    max_severity_score = 0
    total_findings_score = 0

    for finding in findings:
        finding_score = severity_weights.get(finding.severity, 0)
        max_severity_score = max(max_severity_score, finding_score)
        total_findings_score += finding_score * 0.1  # Diminishing returns

    score += max_severity_score + total_findings_score

    # 2. New asset bonus (recently discovered assets get higher priority)
    if asset.first_seen:
        days_old = (datetime.utcnow() - asset.first_seen).days
        if days_old <= 7:
            score += 30
        elif days_old <= 30:
            score += 15

    # 3. TLS/Certificate issues
    metadata = json.loads(asset.metadata or '{}')
    tls_info = metadata.get('tls', {})

    if tls_info:
        # Expiring certificate
        expiry_str = tls_info.get('expiry')
        if expiry_str:
            try:
                expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                days_until_expiry = (expiry - datetime.utcnow()).days
                if days_until_expiry < 0:
                    score += 20  # Expired
                elif days_until_expiry < 30:
                    score += 10  # Expiring soon
            except:
                pass

        # Weak TLS version
        tls_version = tls_info.get('tls_version', '')
        if 'TLS1.0' in tls_version or 'SSL' in tls_version:
            score += 15

    # 4. Internet-exposed services
    services = db.query(Service).filter_by(asset_id=asset.id).all()

    high_risk_ports = {
        22: 5,    # SSH
        23: 10,   # Telnet
        445: 10,  # SMB
        3389: 10, # RDP
        1433: 8,  # MSSQL
        3306: 8,  # MySQL
        5432: 8,  # PostgreSQL
        27017: 8, # MongoDB
        6379: 8,  # Redis
        9200: 8   # Elasticsearch
    }

    for service in services:
        if service.port in high_risk_ports:
            score += high_risk_ports[service.port]

    # 5. Sensitive technology detection
    for service in services:
        if service.technologies:
            tech_list = json.loads(service.technologies)
            sensitive_tech = ['WordPress', 'Joomla', 'phpMyAdmin', 'Webmin']

            for tech in tech_list:
                if any(st in tech for st in sensitive_tech):
                    score += 5

    # 6. Login panels exposed
    http_title = None
    for service in services:
        if service.http_title:
            http_title = service.http_title.lower()
            break

    if http_title:
        login_keywords = ['login', 'admin', 'dashboard', 'panel', 'console']
        if any(keyword in http_title for keyword in login_keywords):
            score += 12

    # 7. Recent activity (new ports, new paths)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_events = db.query(Event).filter(
        Event.asset_id == asset.id,
        Event.created_at >= week_ago,
        Event.kind.in_([EventKind.OPEN_PORT, EventKind.NEW_PATH, EventKind.TECH_CHANGE])
    ).count()

    score += recent_events * 3

    # Cap the score at a reasonable maximum
    return min(score, 500.0)

def recalculate_all_risk_scores(tenant_id: int, db):
    """Recalculate risk scores for all assets of a tenant"""

    assets = db.query(Asset).filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).all()

    for asset in assets:
        asset.risk_score = calculate_asset_risk(asset, db)

    db.commit()

    return len(assets)
```

#### 3.3 Finding Management
**File:** `app/routers/findings.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.main import get_db, get_current_tenant
from app.models.database import Finding, Asset, Tenant, FindingSeverity, FindingStatus

router = APIRouter()

class FindingResponse(BaseModel):
    id: int
    asset_id: int
    source: str
    template_id: Optional[str]
    name: str
    severity: str
    cvss_score: Optional[float]
    cve_id: Optional[str]
    first_seen: datetime
    last_seen: datetime
    status: str

    class Config:
        from_attributes = True

class SuppressionCreate(BaseModel):
    template_id: str
    reason: str
    expires_at: Optional[datetime] = None

@router.get("", response_model=List[FindingResponse])
def get_findings(
    tenant_id: int,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    asset_id: Optional[int] = None,
    cve_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get findings with filters"""

    if current_tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Join with Asset to filter by tenant
    query = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id
    )

    if severity:
        severities = severity.split(',')
        query = query.filter(Finding.severity.in_([FindingSeverity[s.upper()] for s in severities]))

    if status:
        query = query.filter_by(status=FindingStatus[status.upper()])

    if asset_id:
        query = query.filter_by(asset_id=asset_id)

    if cve_id:
        query = query.filter_by(cve_id=cve_id)

    findings = query.order_by(Finding.severity.desc(), Finding.first_seen.desc()).offset(skip).limit(limit).all()

    return findings

@router.patch("/{finding_id}/status")
def update_finding_status(
    tenant_id: int,
    finding_id: int,
    status: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Update finding status (open, suppressed, fixed)"""

    if current_tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    finding = db.query(Finding).join(Asset).filter(
        Finding.id == finding_id,
        Asset.tenant_id == tenant_id
    ).first()

    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    try:
        finding.status = FindingStatus[status.upper()]
        db.commit()

        # Recalculate asset risk
        from app.utils.risk_scoring import calculate_asset_risk
        finding.asset.risk_score = calculate_asset_risk(finding.asset, db)
        db.commit()

        return {"message": "Status updated", "new_status": status}
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

@router.get("/stats/summary")
def get_findings_summary(
    tenant_id: int,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get findings summary statistics"""

    if current_tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Count by severity
    by_severity = {}
    for sev in FindingSeverity:
        count = db.query(Finding).join(Asset).filter(
            Asset.tenant_id == tenant_id,
            Finding.severity == sev,
            Finding.status == FindingStatus.OPEN
        ).count()
        by_severity[sev.value] = count

    # Total open findings
    total_open = sum(by_severity.values())

    # CVE count
    cve_count = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Finding.cve_id.isnot(None),
        Finding.status == FindingStatus.OPEN
    ).count()

    return {
        'total_open': total_open,
        'by_severity': by_severity,
        'cve_count': cve_count
    }

@router.get("/risk/scorecard")
def get_risk_scorecard(
    tenant_id: int,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get risk scorecard with top risky assets"""

    if current_tenant.id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Top 10 risky assets
    top_assets = db.query(Asset).filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).order_by(Asset.risk_score.desc()).limit(10).all()

    # Average risk score
    from sqlalchemy import func
    avg_risk = db.query(func.avg(Asset.risk_score)).filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).scalar() or 0.0

    return {
        'average_risk_score': round(avg_risk, 2),
        'top_risky_assets': [
            {
                'id': a.id,
                'identifier': a.identifier,
                'type': a.type.value,
                'risk_score': a.risk_score
            }
            for a in top_assets
        ]
    }
```

#### 3.4 Historical Comparison
**File:** `app/utils/comparison.py`

```python
from app.models.database import Asset, Finding, Service, Event
from datetime import datetime, timedelta
from sqlalchemy import func

def get_asset_delta(tenant_id: int, hours: int, db):
    """Get new/changed assets in the last N hours"""

    cutoff = datetime.utcnow() - timedelta(hours=hours)

    # New assets
    new_assets = db.query(Asset).filter(
        Asset.tenant_id == tenant_id,
        Asset.first_seen >= cutoff
    ).all()

    # Changed assets (last_seen updated but not new)
    changed_assets = db.query(Asset).filter(
        Asset.tenant_id == tenant_id,
        Asset.last_seen >= cutoff,
        Asset.first_seen < cutoff
    ).all()

    # New findings
    new_findings = db.query(Finding).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Finding.first_seen >= cutoff
    ).all()

    # New events
    new_events = db.query(Event).join(Asset).filter(
        Asset.tenant_id == tenant_id,
        Event.created_at >= cutoff
    ).all()

    return {
        'new_assets': len(new_assets),
        'changed_assets': len(changed_assets),
        'new_findings': len(new_findings),
        'new_events': len(new_events),
        'assets': [{'id': a.id, 'identifier': a.identifier} for a in new_assets],
        'findings': [{'id': f.id, 'name': f.name, 'severity': f.severity.value} for f in new_findings]
    }
```

### Sprint 3 Deliverables

- [ ] Nuclei integration with template selection
- [ ] Severity filtering and rate limiting
- [ ] Finding persistence and deduplication
- [ ] Risk scoring algorithm implementation
- [ ] Finding management endpoints (CRUD)
- [ ] Status transitions (open → suppressed → fixed)
- [ ] Risk scorecard endpoint
- [ ] Historical delta/comparison API
- [ ] Automated risk recalculation on finding updates
- [ ] Unit tests for risk scoring
- [ ] Integration tests for Nuclei pipeline

---

## Sprint 4: UI, Alerting & Automation (Weeks 10-12)

### Goal
Build Vue.js dashboard, implement alerting with Notify, configure Celery Beat scheduler for continuous monitoring, and complete end-to-end testing.

### Vue.js Frontend

#### 4.1 Project Setup
**File:** `ui/package.json`

```json
{
  "name": "easm-ui",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "serve": "vue-cli-service serve",
    "build": "vue-cli-service build",
    "lint": "vue-cli-service lint"
  },
  "dependencies": {
    "vue": "^3.3.0",
    "vue-router": "^4.2.0",
    "vuex": "^4.1.0",
    "axios": "^1.4.0",
    "chart.js": "^4.3.0",
    "vue-chartjs": "^5.2.0",
    "date-fns": "^2.30.0",
    "@heroicons/vue": "^2.0.18",
    "tailwindcss": "^3.3.0"
  },
  "devDependencies": {
    "@vue/cli-service": "^5.0.8",
    "@vue/compiler-sfc": "^3.3.0"
  }
}
```

#### 4.2 Attack Surface Map Component
**File:** `ui/src/components/AttackSurfaceMap.vue`

```vue
<template>
  <div class="attack-surface-map">
    <h2 class="text-2xl font-bold mb-4">Attack Surface Map</h2>

    <div class="stats-grid grid grid-cols-4 gap-4 mb-6">
      <div class="stat-card bg-blue-50 p-4 rounded">
        <div class="text-3xl font-bold">{{ stats.total_assets }}</div>
        <div class="text-sm text-gray-600">Total Assets</div>
      </div>
      <div class="stat-card bg-green-50 p-4 rounded">
        <div class="text-3xl font-bold">{{ stats.domains }}</div>
        <div class="text-sm text-gray-600">Domains</div>
      </div>
      <div class="stat-card bg-yellow-50 p-4 rounded">
        <div class="text-3xl font-bold">{{ stats.subdomains }}</div>
        <div class="text-sm text-gray-600">Subdomains</div>
      </div>
      <div class="stat-card bg-purple-50 p-4 rounded">
        <div class="text-3xl font-bold">{{ stats.services }}</div>
        <div class="text-sm text-gray-600">Services</div>
      </div>
    </div>

    <div class="asset-tree">
      <div v-for="domain in domains" :key="domain.id" class="domain-node mb-4">
        <div class="domain-header bg-gray-100 p-3 rounded cursor-pointer flex justify-between"
             @click="toggleDomain(domain.id)">
          <span class="font-semibold">{{ domain.identifier }}</span>
          <span class="badge" :class="riskClass(domain.risk_score)">
            Risk: {{ domain.risk_score.toFixed(1) }}
          </span>
        </div>

        <div v-if="expandedDomains.includes(domain.id)" class="subdomains ml-6 mt-2">
          <div v-for="subdomain in domain.subdomains" :key="subdomain.id"
               class="subdomain-node bg-white border p-2 rounded mb-2">
            <div class="flex justify-between items-center">
              <span>{{ subdomain.identifier }}</span>
              <button @click="viewAsset(subdomain.id)" class="text-blue-600 text-sm">
                View Details
              </button>
            </div>

            <div v-if="subdomain.services.length" class="services mt-2 ml-4">
              <div v-for="service in subdomain.services" :key="service.id"
                   class="service-item text-sm text-gray-600 flex items-center">
                <span class="port">:{{ service.port }}</span>
                <span class="protocol ml-2">{{ service.protocol }}</span>
                <span v-if="service.http_title" class="title ml-2 truncate">
                  - {{ service.http_title }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'AttackSurfaceMap',
  data() {
    return {
      stats: {
        total_assets: 0,
        domains: 0,
        subdomains: 0,
        services: 0
      },
      domains: [],
      expandedDomains: []
    };
  },
  mounted() {
    this.loadData();
  },
  methods: {
    async loadData() {
      try {
        // Load stats
        const statsResp = await axios.get(`/api/v1/tenants/${this.$route.params.tenantId}/assets/stats/summary`);
        this.stats = {
          total_assets: statsResp.data.total_assets,
          domains: statsResp.data.by_type.domain || 0,
          subdomains: statsResp.data.by_type.subdomain || 0,
          services: 0  // Calculate separately
        };

        // Load domains
        const domainsResp = await axios.get(`/api/v1/tenants/${this.$route.params.tenantId}/assets`, {
          params: { asset_type: 'domain', limit: 100 }
        });

        // For each domain, load subdomains and services
        for (const domain of domainsResp.data) {
          const subdomainsResp = await axios.get(`/api/v1/tenants/${this.$route.params.tenantId}/assets`, {
            params: { asset_type: 'subdomain', limit: 1000 }
          });

          // Filter subdomains for this domain
          domain.subdomains = subdomainsResp.data.filter(sub =>
            sub.identifier.endsWith(domain.identifier)
          );

          // Load services for each subdomain
          for (const subdomain of domain.subdomains) {
            const servicesResp = await axios.get(
              `/api/v1/tenants/${this.$route.params.tenantId}/assets/${subdomain.id}/services`
            );
            subdomain.services = servicesResp.data;
            this.stats.services += servicesResp.data.length;
          }
        }

        this.domains = domainsResp.data;
      } catch (error) {
        console.error('Failed to load attack surface data:', error);
      }
    },
    toggleDomain(domainId) {
      const index = this.expandedDomains.indexOf(domainId);
      if (index > -1) {
        this.expandedDomains.splice(index, 1);
      } else {
        this.expandedDomains.push(domainId);
      }
    },
    viewAsset(assetId) {
      this.$router.push({ name: 'AssetDetail', params: { assetId } });
    },
    riskClass(score) {
      if (score >= 100) return 'bg-red-500 text-white';
      if (score >= 50) return 'bg-orange-500 text-white';
      if (score >= 20) return 'bg-yellow-500';
      return 'bg-green-500 text-white';
    }
  }
};
</script>

<style scoped>
.badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.875rem;
}
</style>
```

#### 4.3 Findings Dashboard
**File:** `ui/src/components/FindingsBoard.vue`

```vue
<template>
  <div class="findings-board">
    <h2 class="text-2xl font-bold mb-4">Vulnerability Findings</h2>

    <!-- Summary Cards -->
    <div class="summary grid grid-cols-5 gap-4 mb-6">
      <div class="card bg-red-50 p-4 rounded">
        <div class="text-3xl font-bold text-red-600">{{ summary.critical }}</div>
        <div class="text-sm">Critical</div>
      </div>
      <div class="card bg-orange-50 p-4 rounded">
        <div class="text-3xl font-bold text-orange-600">{{ summary.high }}</div>
        <div class="text-sm">High</div>
      </div>
      <div class="card bg-yellow-50 p-4 rounded">
        <div class="text-3xl font-bold text-yellow-600">{{ summary.medium }}</div>
        <div class="text-sm">Medium</div>
      </div>
      <div class="card bg-blue-50 p-4 rounded">
        <div class="text-3xl font-bold text-blue-600">{{ summary.low }}</div>
        <div class="text-sm">Low</div>
      </div>
      <div class="card bg-gray-50 p-4 rounded">
        <div class="text-3xl font-bold text-gray-600">{{ summary.info }}</div>
        <div class="text-sm">Info</div>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters mb-4 flex gap-4">
      <select v-model="filters.severity" class="border rounded px-3 py-2">
        <option value="">All Severities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>

      <select v-model="filters.status" class="border rounded px-3 py-2">
        <option value="open">Open</option>
        <option value="suppressed">Suppressed</option>
        <option value="fixed">Fixed</option>
      </select>

      <button @click="loadFindings" class="bg-blue-600 text-white px-4 py-2 rounded">
        Apply Filters
      </button>
    </div>

    <!-- Findings Table -->
    <div class="findings-table">
      <table class="w-full border-collapse">
        <thead>
          <tr class="bg-gray-100">
            <th class="border p-2 text-left">Severity</th>
            <th class="border p-2 text-left">Finding</th>
            <th class="border p-2 text-left">Asset</th>
            <th class="border p-2 text-left">CVE</th>
            <th class="border p-2 text-left">First Seen</th>
            <th class="border p-2 text-left">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="finding in findings" :key="finding.id" class="hover:bg-gray-50">
            <td class="border p-2">
              <span class="badge" :class="severityClass(finding.severity)">
                {{ finding.severity }}
              </span>
            </td>
            <td class="border p-2">{{ finding.name }}</td>
            <td class="border p-2">
              <a :href="`/assets/${finding.asset_id}`" class="text-blue-600">
                Asset #{{ finding.asset_id }}
              </a>
            </td>
            <td class="border p-2">{{ finding.cve_id || '-' }}</td>
            <td class="border p-2">{{ formatDate(finding.first_seen) }}</td>
            <td class="border p-2">
              <select @change="updateStatus(finding.id, $event.target.value)"
                      :value="finding.status"
                      class="border rounded px-2 py-1 text-sm">
                <option value="open">Open</option>
                <option value="suppressed">Suppress</option>
                <option value="fixed">Fixed</option>
              </select>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import { format } from 'date-fns';

export default {
  name: 'FindingsBoard',
  data() {
    return {
      summary: {
        critical: 0,
        high: 0,
        medium: 0,
        low: 0,
        info: 0
      },
      findings: [],
      filters: {
        severity: '',
        status: 'open'
      }
    };
  },
  mounted() {
    this.loadSummary();
    this.loadFindings();
  },
  methods: {
    async loadSummary() {
      try {
        const resp = await axios.get(
          `/api/v1/tenants/${this.$route.params.tenantId}/findings/stats/summary`
        );
        this.summary = resp.data.by_severity;
      } catch (error) {
        console.error('Failed to load summary:', error);
      }
    },
    async loadFindings() {
      try {
        const params = {};
        if (this.filters.severity) params.severity = this.filters.severity;
        if (this.filters.status) params.status = this.filters.status;

        const resp = await axios.get(
          `/api/v1/tenants/${this.$route.params.tenantId}/findings`,
          { params }
        );
        this.findings = resp.data;
      } catch (error) {
        console.error('Failed to load findings:', error);
      }
    },
    async updateStatus(findingId, newStatus) {
      try {
        await axios.patch(
          `/api/v1/tenants/${this.$route.params.tenantId}/findings/${findingId}/status`,
          null,
          { params: { status: newStatus } }
        );
        await this.loadFindings();
        await this.loadSummary();
      } catch (error) {
        console.error('Failed to update status:', error);
      }
    },
    formatDate(dateStr) {
      return format(new Date(dateStr), 'MMM d, yyyy HH:mm');
    },
    severityClass(severity) {
      const classes = {
        critical: 'bg-red-600 text-white',
        high: 'bg-orange-600 text-white',
        medium: 'bg-yellow-500',
        low: 'bg-blue-500 text-white',
        info: 'bg-gray-400'
      };
      return classes[severity] || '';
    }
  }
};
</script>

<style scoped>
.badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  text-transform: uppercase;
  font-weight: 600;
}
</style>
```

### Alerting System

#### 4.4 Notify Integration
**File:** `app/tasks/alerting.py`

```python
from celery import chain
from app.celery import celery
from app.models.database import Finding, Asset, FindingSeverity
from datetime import datetime, timedelta
import subprocess
import tempfile
import os
import json

@celery.task(name='app.tasks.alerting.send_critical_alerts')
def send_critical_alerts(tenant_id: int):
    """Send alerts for critical findings"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        # Get critical findings from last hour (to avoid spam)
        hour_ago = datetime.utcnow() - timedelta(hours=1)

        findings = db.query(Finding).join(Asset).filter(
            Asset.tenant_id == tenant_id,
            Finding.severity == FindingSeverity.CRITICAL,
            Finding.first_seen >= hour_ago,
            Finding.status == 'open'
        ).all()

        if not findings:
            return {'alerts_sent': 0}

        # Format findings for notify
        messages = []
        for finding in findings:
            message = {
                'severity': finding.severity.value,
                'name': finding.name,
                'asset': finding.asset.identifier,
                'template_id': finding.template_id,
                'cve': finding.cve_id or 'N/A'
            }
            messages.append(message)

        # Send via notify
        send_notify_alert(tenant_id, messages)

        return {'alerts_sent': len(messages)}
    finally:
        db.close()

def send_notify_alert(tenant_id: int, messages: list):
    """Send alert using ProjectDiscovery notify"""

    # Prepare notify config
    config = {
        'slack': [{
            'id': 'slack-webhook',
            'slack_webhook_url': os.getenv(f'TENANT_{tenant_id}_SLACK_WEBHOOK')
        }],
        'discord': [{
            'id': 'discord-webhook',
            'discord_webhook_url': os.getenv(f'TENANT_{tenant_id}_DISCORD_WEBHOOK')
        }]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config_file = f.name
        import yaml
        yaml.dump(config, f)

    try:
        for msg in messages:
            alert_text = f"🚨 CRITICAL FINDING\n" \
                        f"Name: {msg['name']}\n" \
                        f"Asset: {msg['asset']}\n" \
                        f"CVE: {msg['cve']}\n" \
                        f"Template: {msg['template_id']}"

            cmd = [
                'notify',
                '-provider-config', config_file,
                '-data', alert_text,
                '-silent'
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(config_file)

@celery.task(name='app.tasks.alerting.send_new_asset_alerts')
def send_new_asset_alerts(tenant_id: int):
    """Alert on new assets discovered"""
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        # Assets discovered in last hour
        hour_ago = datetime.utcnow() - timedelta(hours=1)

        new_assets = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.first_seen >= hour_ago
        ).all()

        if not new_assets:
            return {'new_assets': 0}

        messages = []
        for asset in new_assets:
            messages.append({
                'type': asset.type.value,
                'identifier': asset.identifier,
                'risk_score': asset.risk_score
            })

        # Send summary
        summary = f"📡 {len(new_assets)} new assets discovered:\n"
        for msg in messages[:10]:  # Limit to 10 in notification
            summary += f"- {msg['type']}: {msg['identifier']} (Risk: {msg['risk_score']})\n"

        if len(messages) > 10:
            summary += f"... and {len(messages) - 10} more"

        # Use notify
        config_file = get_notify_config(tenant_id)
        subprocess.run([
            'notify',
            '-provider-config', config_file,
            '-data', summary
        ], capture_output=True, timeout=30)

        return {'new_assets': len(new_assets)}
    finally:
        db.close()

def get_notify_config(tenant_id: int) -> str:
    """Get or create notify config file for tenant"""
    # Implementation depends on how you want to store configs
    # For now, return path to tenant-specific config
    return f'/app/configs/notify-tenant-{tenant_id}.yaml'
```

#### 4.5 Scheduler Configuration
**Update:** `app/celery.py`

```python
# Add to beat_schedule:
celery.conf.beat_schedule.update({
    'critical-alerts-check': {
        'task': 'app.tasks.alerting.send_critical_alerts',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'new-asset-alerts': {
        'task': 'app.tasks.alerting.send_new_asset_alerts',
        'schedule': crontab(hour='*', minute=0),  # Hourly
    },
    'full-port-scan-critical': {
        'task': 'app.tasks.enrichment.run_naabu',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Weekly Sunday 3 AM
        'kwargs': {'full_scan': True}
    },
    'nuclei-scan-daily': {
        'task': 'app.tasks.scanning.run_nuclei',
        'schedule': crontab(hour=1, minute=0),  # Daily 1 AM
    }
})
```

### Sprint 4 Deliverables

- [ ] Vue.js project setup with Tailwind CSS
- [ ] Attack Surface Map component with hierarchical view
- [ ] Findings Board with filters and status management
- [ ] Delta View showing recent changes
- [ ] TLS Hygiene dashboard
- [ ] Tech Radar component
- [ ] Notify integration for critical alerts
- [ ] New asset notifications
- [ ] Celery Beat schedule for continuous scanning
- [ ] Complete Docker Compose setup with UI service
- [ ] End-to-end integration tests
- [ ] User documentation
- [ ] API documentation (Swagger UI)
- [ ] Deployment guide

---

## Post-Sprint: Production Readiness

### Additional Considerations

1. **Security Hardening**
   - Implement rate limiting on API endpoints
   - Add input validation and sanitization
   - Secure MinIO with access policies
   - Rotate JWT secrets
   - Implement API key management for OSINT providers

2. **Performance Optimization**
   - Add database indexes for common queries
   - Implement caching (Redis) for frequently accessed data
   - Optimize Nuclei template selection
   - Batch processing for large scans

3. **Monitoring & Logging**
   - Centralized logging (ELK stack or similar)
   - Metrics collection (Prometheus + Grafana)
   - Task monitoring dashboard
   - Error tracking (Sentry)

4. **Scalability**
   - Horizontal scaling for Celery workers
   - Database connection pooling
   - Load balancing for API
   - Consider Kubernetes deployment

5. **Backup & Recovery**
   - Automated PostgreSQL backups
   - MinIO bucket replication
   - Disaster recovery procedures
   - Data retention policies
