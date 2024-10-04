"""
Pytest configuration and shared fixtures for EASM tests

Provides:
- Database fixtures
- Mock fixtures
- Test data factories
- Configuration for test execution
"""
import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import all models to ensure they're registered with SQLAlchemy
import app.models
from app.models import (
    Base, Tenant, Asset, Seed, Event, Service, Finding,
    AssetType, EventKind, FindingSeverity, FindingStatus
)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (slower)"
    )
    config.addinivalue_line(
        "markers", "security: mark test as security test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "benchmark: mark test as benchmark"
    )


# Database Fixtures
@pytest.fixture(scope='function')
def db_engine():
    """Create in-memory SQLite database engine"""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope='function')
def db_session(db_engine):
    """Create database session"""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope='function')
def test_db(db_session):
    """Alias for db_session for backward compatibility"""
    return db_session


# Tenant Fixtures
@pytest.fixture
def tenant(db_session):
    """Create a test tenant"""
    tenant = Tenant(
        name="Test Tenant",
        slug="test-tenant",
        contact_policy="security@test.com",
        osint_api_keys=None
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def tenant_with_api_keys(db_session):
    """Create tenant with API keys configured"""
    tenant = Tenant(
        name="Tenant With Keys",
        slug="tenant-keys",
        contact_policy="security@test.com",
        osint_api_keys='{"shodan": "test_key", "censys": "test_key"}'
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def multiple_tenants(db_session):
    """Create multiple tenants for isolation testing"""
    tenants = [
        Tenant(name=f"Tenant {i}", slug=f"tenant-{i}")
        for i in range(3)
    ]
    db_session.add_all(tenants)
    db_session.commit()
    for t in tenants:
        db_session.refresh(t)
    return tenants


# Asset Fixtures
@pytest.fixture
def sample_asset(db_session, tenant):
    """Create a sample asset"""
    asset = Asset(
        tenant_id=tenant.id,
        identifier="test.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=10.0,
        is_active=True,
        raw_metadata='{"test": "data"}'
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


@pytest.fixture
def multiple_assets(db_session, tenant):
    """Create multiple assets for testing"""
    assets = [
        Asset(
            tenant_id=tenant.id,
            identifier=f"sub{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=float(i * 10),
            is_active=True
        )
        for i in range(10)
    ]
    db_session.add_all(assets)
    db_session.commit()
    for a in assets:
        db_session.refresh(a)
    return assets


@pytest.fixture
def critical_assets(db_session, tenant):
    """Create critical assets with high risk scores"""
    assets = [
        Asset(
            tenant_id=tenant.id,
            identifier=f"critical{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=75.0 + i,
            is_active=True
        )
        for i in range(5)
    ]
    db_session.add_all(assets)
    db_session.commit()
    for a in assets:
        db_session.refresh(a)
    return assets


# Seed Fixtures
@pytest.fixture
def sample_seeds(db_session, tenant):
    """Create sample seeds"""
    seeds = [
        Seed(tenant_id=tenant.id, type='domain', value='example.com', enabled=True),
        Seed(tenant_id=tenant.id, type='domain', value='test.org', enabled=True),
        Seed(tenant_id=tenant.id, type='keyword', value='TestCorp', enabled=True),
        Seed(tenant_id=tenant.id, type='asn', value='AS12345', enabled=True),
        Seed(tenant_id=tenant.id, type='ip_range', value='192.168.1.0/24', enabled=True),
    ]
    db_session.add_all(seeds)
    db_session.commit()
    for s in seeds:
        db_session.refresh(s)
    return seeds


@pytest.fixture
def disabled_seed(db_session, tenant):
    """Create a disabled seed"""
    seed = Seed(
        tenant_id=tenant.id,
        type='domain',
        value='disabled.com',
        enabled=False
    )
    db_session.add(seed)
    db_session.commit()
    db_session.refresh(seed)
    return seed


# Event Fixtures
@pytest.fixture
def sample_events(db_session, sample_asset):
    """Create sample events"""
    events = [
        Event(
            asset_id=sample_asset.id,
            kind=EventKind.NEW_ASSET,
            payload='{"discovered": true}'
        ),
        Event(
            asset_id=sample_asset.id,
            kind=EventKind.OPEN_PORT,
            payload='{"port": 443, "protocol": "https"}'
        ),
        Event(
            asset_id=sample_asset.id,
            kind=EventKind.NEW_CERT,
            payload='{"cert": "data"}'
        ),
    ]
    db_session.add_all(events)
    db_session.commit()
    for e in events:
        db_session.refresh(e)
    return events


# Service Fixtures
@pytest.fixture
def sample_service(db_session, sample_asset):
    """Create a sample service"""
    service = Service(
        asset_id=sample_asset.id,
        port=443,
        protocol="https",
        product="nginx",
        version="1.18.0",
        http_title="Test Page",
        http_status=200
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


# Finding Fixtures
@pytest.fixture
def sample_finding(db_session, sample_asset):
    """Create a sample finding"""
    finding = Finding(
        asset_id=sample_asset.id,
        source="nuclei",
        template_id="CVE-2021-12345",
        name="Test Vulnerability",
        severity=FindingSeverity.HIGH,
        cvss_score=7.5,
        cve_id="CVE-2021-12345",
        evidence='{"proof": "data"}',
        status=FindingStatus.OPEN
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


# Mock Fixtures
@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run"""
    with patch('subprocess.run') as mock:
        mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock


@pytest.fixture
def mock_minio():
    """Mock MinIO client"""
    with patch('app.utils.storage.get_minio_client') as mock:
        client = MagicMock()
        client.bucket_exists.return_value = True
        mock.return_value = client
        yield client


@pytest.fixture
def mock_celery():
    """Mock Celery task execution"""
    with patch('celery.Task.apply_async') as mock:
        mock.return_value = MagicMock(id='test-task-id')
        yield mock


@pytest.fixture
def mock_secure_executor():
    """Mock SecureToolExecutor"""
    with patch('app.utils.secure_executor.SecureToolExecutor') as mock:
        executor = MagicMock()
        executor.execute.return_value = (0, "", "")
        executor.read_output_file.return_value = ""
        executor.temp_dir = tempfile.mkdtemp()
        mock.return_value.__enter__.return_value = executor
        yield executor


# Data Factory Fixtures
@pytest.fixture
def asset_factory():
    """Factory for creating asset data"""
    def _create_asset_data(count=1, tenant_id=1, base_name="test"):
        return [
            {
                'identifier': f'{base_name}{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{"index": ' + str(i) + '}'
            }
            for i in range(count)
        ]
    return _create_asset_data


@pytest.fixture
def discovery_result_factory():
    """Factory for creating discovery results"""
    def _create_discovery_result(count=10, base_name="sub"):
        return {
            'resolved': [
                {
                    'host': f'{base_name}{i}.example.com',
                    'a': [f'1.2.3.{i}'],
                    'status': 'NOERROR'
                }
                for i in range(count)
            ],
            'tenant_id': 1
        }
    return _create_discovery_result


@pytest.fixture
def seed_data_factory():
    """Factory for creating seed data"""
    def _create_seed_data(domains=None, keywords=None, asns=None, ip_ranges=None):
        return {
            'domains': domains or ['example.com', 'test.org'],
            'keywords': keywords or ['TestCorp'],
            'asns': asns or ['AS12345'],
            'ip_ranges': ip_ranges or ['192.168.1.0/24']
        }
    return _create_seed_data


# Temporary File Fixtures
@pytest.fixture
def temp_file():
    """Create temporary file that gets cleaned up"""
    files = []

    def _create_temp_file(content="", suffix=".txt"):
        f = tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False)
        f.write(content)
        f.close()
        files.append(f.name)
        return f.name

    yield _create_temp_file

    # Cleanup
    for f in files:
        if os.path.exists(f):
            os.unlink(f)


@pytest.fixture
def temp_dir():
    """Create temporary directory that gets cleaned up"""
    dirs = []

    def _create_temp_dir():
        d = tempfile.mkdtemp()
        dirs.append(d)
        return d

    yield _create_temp_dir

    # Cleanup
    import shutil
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d)


# Environment Fixtures
@pytest.fixture
def test_env():
    """Set up test environment variables"""
    original_env = os.environ.copy()

    # Set test environment variables
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['MINIO_ENDPOINT'] = 'localhost:9000'
    os.environ['MINIO_USER'] = 'test'
    os.environ['MINIO_PASSWORD'] = 'testpass'

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# Time-based Fixtures
@pytest.fixture
def freeze_time():
    """Freeze time for consistent testing"""
    fixed_time = datetime(2024, 1, 15, 12, 0, 0)

    with patch('app.repositories.asset_repository.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = fixed_time
        yield fixed_time


# Cleanup Fixtures
@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Automatically cleanup temp files after each test"""
    yield
    # Cleanup happens after test
    # This ensures test isolation


# Assertion Helper Fixtures
@pytest.fixture
def assert_asset_equal():
    """Helper to assert asset equality"""
    def _assert_equal(asset1, asset2, ignore_fields=None):
        ignore_fields = ignore_fields or ['id', 'first_seen', 'last_seen']
        for field in ['tenant_id', 'identifier', 'type']:
            if field not in ignore_fields:
                assert getattr(asset1, field) == getattr(asset2, field), \
                    f"Field {field} does not match"
    return _assert_equal


# Performance Testing Fixtures
@pytest.fixture
def performance_timer():
    """Timer for performance testing"""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.elapsed = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            if self.start_time is None:
                raise RuntimeError("Timer not started")
            self.elapsed = time.time() - self.start_time
            return self.elapsed

        def assert_faster_than(self, seconds, message=""):
            if self.elapsed is None:
                raise RuntimeError("Timer not stopped")
            assert self.elapsed < seconds, \
                f"{message} Expected < {seconds}s, got {self.elapsed:.3f}s"

    return Timer()


# Database State Fixtures
@pytest.fixture
def db_with_data(db_session, tenant, sample_seeds, multiple_assets):
    """Database pre-populated with common test data"""
    return {
        'db': db_session,
        'tenant': tenant,
        'seeds': sample_seeds,
        'assets': multiple_assets
    }


# Logging Fixtures
@pytest.fixture
def capture_logs():
    """Capture log output for testing"""
    import logging
    from io import StringIO

    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)

    logger = logging.getLogger('app')
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    yield log_capture

    logger.removeHandler(handler)


# Configuration Fixtures
@pytest.fixture
def test_config():
    """Test configuration"""
    return {
        'batch_size': 100,
        'timeout': 600,
        'max_retries': 3,
        'memory_limit': 1024 * 1024 * 1024,  # 1GB
    }


# Mark slow tests
def pytest_collection_modifyitems(config, items):
    """Automatically mark slow tests"""
    for item in items:
        if 'performance' in item.nodeid or 'integration' in item.nodeid:
            item.add_marker(pytest.mark.slow)
