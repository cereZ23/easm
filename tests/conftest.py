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
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load environment variables from .env file for database connection
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Import all models to ensure they're registered with SQLAlchemy
import app.models
from app.models import (
    Base, Tenant, Asset, Seed, Event, Service, Finding,
    AssetType, EventKind, FindingSeverity, FindingStatus
)
from app.models.enrichment import Certificate, Endpoint


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
    """Create PostgreSQL database engine for testing

    Uses the PostgreSQL database from docker-compose.
    Tests run in transactions that are rolled back for isolation.
    """
    # Use the actual PostgreSQL database from docker-compose
    # Connection string matches docker-compose.yml configuration
    # Using 127.0.0.1 instead of localhost to force IPv4
    # Read password from environment (set in .env file)
    db_password = os.environ.get('DB_PASSWORD', 'easm_password')
    database_url = os.environ.get(
        'TEST_DATABASE_URL',
        f'postgresql://easm:{db_password}@127.0.0.1:15432/easm'
    )

    engine = create_engine(database_url, echo=False)

    # Ensure all tables exist
    Base.metadata.create_all(engine)

    yield engine
    engine.dispose()


@pytest.fixture(scope='function')
def db_session(db_engine):
    """Create database session with transaction rollback for test isolation"""
    # Create a connection
    connection = db_engine.connect()

    # Begin a transaction
    transaction = connection.begin()

    # Create a session bound to the connection
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    # Rollback the transaction to undo all changes
    session.close()
    transaction.rollback()
    connection.close()


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
        contact_policy="security@test.com"
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
        contact_policy="security@test.com"
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


# Enrichment-specific Fixtures
@pytest.fixture
def mock_tenant(db_session):
    """Create a test tenant for enrichment tests"""
    tenant = Tenant(
        name="Mock Tenant",
        slug="mock-tenant",
        contact_policy="security@mock.com"
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def mock_asset(db_session, mock_tenant):
    """Create a mock asset for enrichment tests"""
    asset = Asset(
        tenant_id=mock_tenant.id,
        identifier="test.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=5.0,
        is_active=True,
        priority='normal',
        enrichment_status='pending'
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


@pytest.fixture
def mock_assets(db_session, mock_tenant):
    """Create multiple mock assets with different priorities"""
    from datetime import datetime, timedelta

    assets = [
        Asset(
            tenant_id=mock_tenant.id,
            identifier="critical.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=9.0,
            is_active=True,
            priority='critical',
            enrichment_status='pending',
            last_enriched_at=None
        ),
        Asset(
            tenant_id=mock_tenant.id,
            identifier="high.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=7.0,
            is_active=True,
            priority='high',
            enrichment_status='pending',
            last_enriched_at=None
        ),
        Asset(
            tenant_id=mock_tenant.id,
            identifier="normal.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=5.0,
            is_active=True,
            priority='normal',
            enrichment_status='pending',
            last_enriched_at=None
        ),
        Asset(
            tenant_id=mock_tenant.id,
            identifier="low.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=2.0,
            is_active=True,
            priority='low',
            enrichment_status='pending',
            last_enriched_at=None
        ),
    ]
    db_session.add_all(assets)
    db_session.commit()
    for a in assets:
        db_session.refresh(a)
    return assets


@pytest.fixture
def mock_tenant_logger():
    """Mock tenant logger for security logging"""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.critical = MagicMock()
    return logger


# API Testing Fixtures (Sprint 3)

@pytest.fixture
def client(db_session):
    """FastAPI test client with test database"""
    from fastapi.testclient import TestClient

    # Import app and database dependency
    try:
        from app.api.main import app
        from app.database import get_db

        # Override database dependency
        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        test_client = TestClient(app)
        yield test_client

        # Clear overrides after test
        app.dependency_overrides.clear()
    except ImportError:
        # Fallback if app not yet created
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        yield TestClient(app)


@pytest.fixture
def test_tenant(db_session):
    """Create test tenant for API tests"""
    tenant = Tenant(
        name="Test Tenant",
        slug="test-tenant",
        contact_policy="security@test.com"
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def test_user(db_session, test_tenant):
    """Create test user with hashed password"""
    try:
        from app.models.user import User
    except ImportError:
        # Create minimal User class if not exists
        from sqlalchemy import Column, Integer, String, Boolean
        class User(Base):
            __tablename__ = 'users'
            id = Column(Integer, primary_key=True)
            email = Column(String, unique=True, nullable=False)
            username = Column(String, unique=True, nullable=False)
            hashed_password = Column(String, nullable=False)
            is_active = Column(Boolean, default=True)
            is_superuser = Column(Boolean, default=False)

    try:
        from app.security.auth import get_password_hash
    except ImportError:
        # Fallback password hash
        import bcrypt
        def get_password_hash(password: str) -> str:
            return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create tenant membership
    try:
        from app.models.user import TenantMembership
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=test_tenant.id,
            role="member"
        )
        db_session.add(membership)
        db_session.commit()
    except ImportError:
        pass

    return user


@pytest.fixture
def admin_user(db_session, test_tenant):
    """Create admin user"""
    try:
        from app.models.user import User
    except ImportError:
        from sqlalchemy import Column, Integer, String, Boolean
        class User(Base):
            __tablename__ = 'users'
            id = Column(Integer, primary_key=True)
            email = Column(String, unique=True, nullable=False)
            username = Column(String, unique=True, nullable=False)
            hashed_password = Column(String, nullable=False)
            is_active = Column(Boolean, default=True)
            is_superuser = Column(Boolean, default=False)

    try:
        from app.security.auth import get_password_hash
    except ImportError:
        import bcrypt
        def get_password_hash(password: str) -> str:
            return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

    user = User(
        email="admin@example.com",
        username="admin",
        hashed_password=get_password_hash("admin123"),
        is_active=True,
        is_superuser=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create tenant membership with admin role
    try:
        from app.models.user import TenantMembership
        membership = TenantMembership(
            user_id=user.id,
            tenant_id=test_tenant.id,
            role="admin"
        )
        db_session.add(membership)
        db_session.commit()
    except ImportError:
        pass

    return user


@pytest.fixture
def auth_headers(client, test_user):
    """Generate JWT token for authenticated requests"""
    try:
        response = client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "password123"
        })
        if response.status_code == 200:
            token = response.json()["access_token"]
            return {"Authorization": f"Bearer {token}"}
    except Exception:
        pass

    # Fallback: generate token directly
    try:
        from datetime import timedelta
        from app.security.auth import create_access_token
        token_data = {"sub": test_user.email, "user_id": test_user.id}
        token = create_access_token(token_data, expires_delta=timedelta(hours=1))
        return {"Authorization": f"Bearer {token}"}
    except Exception:
        # Last resort: mock token for testing
        return {"Authorization": "Bearer test-token"}


@pytest.fixture
def admin_headers(client, admin_user):
    """Generate JWT token for admin user"""
    try:
        response = client.post("/api/v1/auth/login", json={
            "email": admin_user.email,
            "password": "admin123"
        })
        if response.status_code == 200:
            token = response.json()["access_token"]
            return {"Authorization": f"Bearer {token}"}
    except Exception:
        pass

    # Fallback: generate token directly
    try:
        from datetime import timedelta
        from app.security.auth import create_access_token
        token_data = {"sub": admin_user.email, "user_id": admin_user.id, "is_superuser": True}
        token = create_access_token(token_data, expires_delta=timedelta(hours=1))
        return {"Authorization": f"Bearer {token}"}
    except Exception:
        return {"Authorization": "Bearer admin-test-token"}


@pytest.fixture
def refresh_token(client, test_user):
    """Generate refresh token for token refresh tests"""
    try:
        response = client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "password123"
        })
        if response.status_code == 200:
            return response.json().get("refresh_token")
    except Exception:
        pass

    # Fallback: generate refresh token directly
    try:
        from datetime import timedelta
        from app.security.auth import create_refresh_token
        token_data = {"sub": test_user.email, "user_id": test_user.id}
        return create_refresh_token(token_data, expires_delta=timedelta(days=7))
    except Exception:
        return "test-refresh-token"


@pytest.fixture
def other_tenant(db_session):
    """Create another tenant for isolation testing"""
    tenant = Tenant(
        name="Other Tenant",
        slug="other-tenant",
        contact_policy="other@test.com"
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def other_tenant_user(db_session, other_tenant):
    """Create user belonging to other tenant"""
    try:
        from app.models.user import User, TenantMembership
    except ImportError:
        return None

    try:
        from app.security.auth import get_password_hash
    except ImportError:
        import bcrypt
        def get_password_hash(password: str) -> str:
            return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

    user = User(
        email="other@example.com",
        username="otheruser",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=other_tenant.id,
        role="member"
    )
    db_session.add(membership)
    db_session.commit()

    return user


@pytest.fixture
def test_assets(db_session, test_tenant):
    """Create test assets for querying"""
    from datetime import datetime, timedelta

    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier="example.com",
            type=AssetType.DOMAIN,
            risk_score=30.0,
            is_active=True,
            first_seen=datetime.utcnow() - timedelta(days=30),
            last_seen=datetime.utcnow()
        ),
        Asset(
            tenant_id=test_tenant.id,
            identifier="www.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=45.0,
            is_active=True,
            first_seen=datetime.utcnow() - timedelta(days=10),
            last_seen=datetime.utcnow()
        ),
        Asset(
            tenant_id=test_tenant.id,
            identifier="api.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=75.0,
            is_active=True,
            first_seen=datetime.utcnow() - timedelta(hours=2),
            last_seen=datetime.utcnow()
        ),
        Asset(
            tenant_id=test_tenant.id,
            identifier="192.168.1.10",
            type=AssetType.IP,
            risk_score=60.0,
            is_active=True,
            first_seen=datetime.utcnow() - timedelta(days=5),
            last_seen=datetime.utcnow()
        ),
        Asset(
            tenant_id=test_tenant.id,
            identifier="https://app.example.com/login",
            type=AssetType.URL,
            risk_score=85.0,
            is_active=True,
            first_seen=datetime.utcnow() - timedelta(hours=1),
            last_seen=datetime.utcnow()
        ),
    ]
    db_session.add_all(assets)
    db_session.commit()
    for a in assets:
        db_session.refresh(a)
    return assets


@pytest.fixture
def test_services(db_session, test_assets):
    """Create test services"""
    services = [
        Service(
            asset_id=test_assets[1].id,  # www.example.com
            port=443,
            protocol="https",
            product="nginx",
            version="1.21.0",
            http_title="Example Site",
            http_status=200
        ),
        Service(
            asset_id=test_assets[1].id,
            port=80,
            protocol="http",
            product="nginx",
            version="1.21.0",
            http_status=301
        ),
        Service(
            asset_id=test_assets[2].id,  # api.example.com
            port=443,
            protocol="https",
            product="apache",
            version="2.4.41",
            http_title="API Server",
            http_status=200
        ),
    ]
    db_session.add_all(services)
    db_session.commit()
    for s in services:
        db_session.refresh(s)
    return services


@pytest.fixture
def test_certs(db_session, test_assets):
    """Create test certificates"""
    from datetime import datetime, timedelta

    certs = [
        Certificate(
            asset_id=test_assets[1].id,  # www.example.com
            common_name="www.example.com",
            subject_alternative_names=["www.example.com", "example.com"],
            issuer="Let's Encrypt",
            not_before=datetime.utcnow() - timedelta(days=60),
            not_after=datetime.utcnow() + timedelta(days=30),
            is_wildcard=False,
            is_self_signed=False
        ),
        Certificate(
            asset_id=test_assets[2].id,  # api.example.com
            common_name="*.example.com",
            subject_alternative_names=["*.example.com", "example.com"],
            issuer="DigiCert",
            not_before=datetime.utcnow() - timedelta(days=180),
            not_after=datetime.utcnow() + timedelta(days=10),  # Expiring soon
            is_wildcard=True,
            is_self_signed=False
        ),
    ]
    db_session.add_all(certs)
    db_session.commit()
    for c in certs:
        db_session.refresh(c)
    return certs


@pytest.fixture
def test_findings(db_session, test_assets):
    """Create test findings"""
    findings = [
        Finding(
            asset_id=test_assets[2].id,  # api.example.com
            tenant_id=test_assets[2].tenant_id,
            source="nuclei",
            template_id="CVE-2021-44228",
            name="Apache Log4j RCE",
            severity=FindingSeverity.CRITICAL,
            cvss_score=10.0,
            cve_id="CVE-2021-44228",
            evidence='{"url": "https://api.example.com", "matched": "log4j"}',
            status=FindingStatus.OPEN
        ),
        Finding(
            asset_id=test_assets[4].id,  # login URL
            tenant_id=test_assets[4].tenant_id,
            source="nuclei",
            template_id="exposed-panels/login-panel",
            name="Exposed Login Panel",
            severity=FindingSeverity.MEDIUM,
            cvss_score=5.3,
            evidence='{"url": "https://app.example.com/login"}',
            status=FindingStatus.OPEN
        ),
        Finding(
            asset_id=test_assets[1].id,  # www.example.com
            tenant_id=test_assets[1].tenant_id,
            source="nuclei",
            template_id="http-missing-security-headers",
            name="Missing Security Headers",
            severity=FindingSeverity.LOW,
            cvss_score=3.1,
            evidence='{"headers": ["X-Frame-Options", "X-Content-Type-Options"]}',
            status=FindingStatus.SUPPRESSED
        ),
    ]
    db_session.add_all(findings)
    db_session.commit()
    for f in findings:
        db_session.refresh(f)
    return findings


@pytest.fixture
def api_client():
    """Alias for client fixture (backward compatibility)"""
    pass  # Will be overridden by client fixture


@pytest.fixture
def authenticated_client(client, auth_headers):
    """Test client with JWT token pre-configured"""
    client.headers.update(auth_headers)
    return client


@pytest.fixture
def sample_finding(db_session, sample_asset):
    """Create a sample finding"""
    finding = Finding(
        asset_id=sample_asset.id,
        tenant_id=sample_asset.tenant_id,
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


@pytest.fixture
def other_tenant_assets(db_session, other_tenant):
    """Create assets for other tenant"""
    assets = [
        Asset(
            tenant_id=other_tenant.id,
            identifier=f"other{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=50.0,
            is_active=True
        )
        for i in range(3)
    ]
    db_session.add_all(assets)
    db_session.commit()
    for a in assets:
        db_session.refresh(a)
    return assets


@pytest.fixture
def thousand_assets(db_session, test_tenant):
    """Create 1000 assets for performance testing"""
    batch_size = 100
    for batch in range(10):
        assets = [
            Asset(
                tenant_id=test_tenant.id,
                identifier=f"perf{batch * batch_size + i}.example.com",
                type=AssetType.SUBDOMAIN,
                risk_score=float((batch * batch_size + i) % 100),
                is_active=True
            )
            for i in range(batch_size)
        ]
        db_session.add_all(assets)
        db_session.commit()
    return 1000


@pytest.fixture
def test_asset(db_session, test_tenant):
    """Create single test asset for detail tests"""
    asset = Asset(
        tenant_id=test_tenant.id,
        identifier="single.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=50.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


@pytest.fixture
def test_service(db_session, test_asset):
    """Create single test service"""
    service = Service(
        asset_id=test_asset.id,
        port=443,
        protocol="https",
        product="nginx",
        version="1.21.0",
        http_title="Test Service",
        http_status=200
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


@pytest.fixture
def test_cert(db_session, test_asset):
    """Create single test certificate"""
    from datetime import datetime, timedelta
    cert = Certificate(
        asset_id=test_asset.id,
        common_name="single.example.com",
        subject_alternative_names=["single.example.com"],
        issuer="Let's Encrypt",
        not_before=datetime.utcnow() - timedelta(days=60),
        not_after=datetime.utcnow() + timedelta(days=60),
        is_wildcard=False,
        is_self_signed=False
    )
    db_session.add(cert)
    db_session.commit()
    db_session.refresh(cert)
    return cert


@pytest.fixture
def test_finding(db_session, test_asset):
    """Create single test finding"""
    finding = Finding(
        asset_id=test_asset.id,
        tenant_id=test_asset.tenant_id,
        source="nuclei",
        template_id="CVE-2023-12345",
        name="Test Vulnerability",
        severity=FindingSeverity.HIGH,
        cvss_score=7.5,
        cve_id="CVE-2023-12345",
        evidence='{"proof": "test data"}',
        status=FindingStatus.OPEN
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


@pytest.fixture
def other_tenant_asset(db_session, other_tenant):
    """Create single asset for other tenant (for isolation tests)"""
    asset = Asset(
        tenant_id=other_tenant.id,
        identifier="other.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=50.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


@pytest.fixture
def other_tenant_service(db_session, other_tenant_asset):
    """Create service for other tenant"""
    service = Service(
        asset_id=other_tenant_asset.id,
        port=443,
        protocol="https",
        product="nginx",
        version="1.21.0"
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


@pytest.fixture
def other_tenant_cert(db_session, other_tenant_asset):
    """Create certificate for other tenant"""
    from datetime import datetime, timedelta
    cert = Certificate(
        asset_id=other_tenant_asset.id,
        common_name="other.example.com",
        subject_alternative_names=["other.example.com"],
        issuer="Let's Encrypt",
        not_before=datetime.utcnow() - timedelta(days=60),
        not_after=datetime.utcnow() + timedelta(days=60),
        is_wildcard=False,
        is_self_signed=False
    )
    db_session.add(cert)
    db_session.commit()
    db_session.refresh(cert)
    return cert


@pytest.fixture
def other_tenant_finding(db_session, other_tenant_asset):
    """Create finding for other tenant"""
    finding = Finding(
        asset_id=other_tenant_asset.id,
        tenant_id=other_tenant_asset.tenant_id,
        source="nuclei",
        template_id="CVE-2023-99999",
        name="Other Tenant Vulnerability",
        severity=FindingSeverity.HIGH,
        cvss_score=7.5,
        status=FindingStatus.OPEN
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


@pytest.fixture
def sample_nuclei_output():
    """Sample Nuclei JSON output for parsing tests"""
    return '''[
  {
    "template": "CVE-2021-44228",
    "template-url": "https://cloud.projectdiscovery.io/templates/CVE-2021-44228",
    "template-id": "CVE-2021-44228",
    "info": {
      "name": "Apache Log4j RCE",
      "author": ["melbadry9","dhiyaneshDK"],
      "severity": "critical",
      "tags": ["cve","cve2021","rce","log4j","apache"]
    },
    "type": "http",
    "host": "https://api.example.com",
    "matched-at": "https://api.example.com/",
    "extracted-results": ["vulnerable"],
    "timestamp": "2024-01-15T12:00:00Z",
    "matcher-status": true,
    "cvss-metrics": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
    "cvss-score": 10.0,
    "cve-id": "CVE-2021-44228"
  }
]'''


@pytest.fixture
def test_assets_with_tech(db_session, test_tenant):
    """Create assets with detected technologies for smart template filtering"""
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier="wordpress.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=50.0,
            is_active=True,
            raw_metadata='{"technologies": ["WordPress", "PHP"]}'
        ),
        Asset(
            tenant_id=test_tenant.id,
            identifier="drupal.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=50.0,
            is_active=True,
            raw_metadata='{"technologies": ["Drupal", "PHP"]}'
        ),
        Asset(
            tenant_id=test_tenant.id,
            identifier="apache.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=50.0,
            is_active=True,
            raw_metadata='{"technologies": ["Apache", "Tomcat"]}'
        ),
    ]
    db_session.add_all(assets)
    db_session.commit()
    for a in assets:
        db_session.refresh(a)
    return assets


@pytest.fixture
def existing_finding(db_session, test_asset):
    """Create an existing finding for update tests"""
    from datetime import datetime, timedelta
    finding = Finding(
        asset_id=test_asset.id,
        tenant_id=test_asset.tenant_id,
        source="nuclei",
        template_id="CVE-2023-00001",
        name="Existing Vulnerability",
        severity=FindingSeverity.MEDIUM,
        cvss_score=6.5,
        cve_id="CVE-2023-00001",
        evidence='{"initial": "data"}',
        status=FindingStatus.OPEN,
        first_seen=datetime.utcnow() - timedelta(days=7),
        last_seen=datetime.utcnow() - timedelta(days=7)
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


@pytest.fixture
def large_finding_set():
    """Generate 1000+ findings for bulk upsert performance tests"""
    findings = []
    for i in range(1500):
        findings.append({
            "template_id": f"nuclei-template-{i % 100}",
            "name": f"Vulnerability {i}",
            "severity": ["critical", "high", "medium", "low"][i % 4],
            "cvss_score": float(3.0 + (i % 8)),
            "cve_id": f"CVE-2023-{10000 + i}" if i % 3 == 0 else None,
            "evidence": f'{{"finding": {i}}}',
            "host": f"https://host{i % 50}.example.com",
            "matched_at": f"https://host{i % 50}.example.com/path{i}"
        })
    return findings


# Mark slow tests
def pytest_collection_modifyitems(config, items):
    """Automatically mark slow tests"""
    for item in items:
        if 'performance' in item.nodeid or 'integration' in item.nodeid:
            item.add_marker(pytest.mark.slow)
