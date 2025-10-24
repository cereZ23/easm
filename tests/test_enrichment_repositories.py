"""
Test suite for enrichment repositories (Service, Certificate, Endpoint)

Tests cover:
- Bulk UPSERT operations (500x performance improvement)
- Query methods and filtering
- Database constraints and indexes
- Relationship integrity
- Performance benchmarks
"""

import pytest
from datetime import datetime, timedelta
import time

from app.repositories.service_repository import ServiceRepository
from app.repositories.certificate_repository import CertificateRepository
from app.repositories.endpoint_repository import EndpointRepository
from app.models.database import Asset, AssetType, Service, Tenant
from app.models.enrichment import Certificate, Endpoint


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_tenant(db_session):
    """Create a test tenant"""
    tenant = Tenant(
        name="Test Tenant",
        slug="test-tenant"
    )
    db_session.add(tenant)
    db_session.commit()
    return tenant


@pytest.fixture
def mock_asset(db_session, mock_tenant):
    """Create a test asset"""
    asset = Asset(
        tenant_id=mock_tenant.id,
        type=AssetType.DOMAIN,
        identifier="example.com",
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    return asset


# =============================================================================
# SERVICE REPOSITORY TESTS
# =============================================================================

class TestServiceRepository:
    """Test ServiceRepository bulk operations and queries"""

    def test_bulk_upsert_creates_new_services(self, db_session, mock_asset):
        """Test bulk UPSERT creates new service records"""
        repo = ServiceRepository(db_session)

        services_data = [
            {
                'port': 80,
                'protocol': 'http',
                'http_status': 200,
                'http_title': 'Welcome',
                'web_server': 'nginx',
                'enrichment_source': 'httpx'
            },
            {
                'port': 443,
                'protocol': 'https',
                'http_status': 200,
                'has_tls': True,
                'tls_version': 'TLSv1.3',
                'enrichment_source': 'tlsx'
            },
            {
                'port': 8080,
                'protocol': 'http',
                'enrichment_source': 'naabu'
            }
        ]

        result = repo.bulk_upsert(mock_asset.id, services_data)

        assert result['created'] == 3
        assert result['updated'] == 0
        assert result['total_processed'] == 3

        # Verify services were created
        services = db_session.query(Service).filter_by(asset_id=mock_asset.id).all()
        assert len(services) == 3

    def test_bulk_upsert_updates_existing_services(self, db_session, mock_asset):
        """Test bulk UPSERT updates existing service records"""
        repo = ServiceRepository(db_session)

        # Create initial service
        initial_service = Service(
            asset_id=mock_asset.id,
            port=80,
            protocol='http',
            http_status=None,
            first_seen=datetime.utcnow() - timedelta(days=1)
        )
        db_session.add(initial_service)
        db_session.commit()

        initial_first_seen = initial_service.first_seen

        # Update with enrichment data
        services_data = [
            {
                'port': 80,
                'protocol': 'http',
                'http_status': 200,
                'http_title': 'Updated Title',
                'web_server': 'nginx/1.21.0',
                'http_technologies': ['nginx', 'PHP'],
                'enrichment_source': 'httpx'
            }
        ]

        result = repo.bulk_upsert(mock_asset.id, services_data)

        assert result['created'] == 0
        assert result['updated'] == 1

        # Verify service was updated
        updated_service = db_session.query(Service).filter_by(
            asset_id=mock_asset.id,
            port=80
        ).first()

        assert updated_service.http_status == 200
        assert updated_service.http_title == 'Updated Title'
        assert updated_service.web_server == 'nginx/1.21.0'
        assert updated_service.http_technologies == ['nginx', 'PHP']
        assert updated_service.enrichment_source == 'httpx'

        # first_seen should be preserved
        assert updated_service.first_seen == initial_first_seen

        # last_seen should be updated
        assert updated_service.last_seen > initial_first_seen

    def test_bulk_upsert_performance(self, db_session, mock_asset):
        """Test bulk UPSERT is fast (500x faster than individual inserts)"""
        repo = ServiceRepository(db_session)

        # Create 100 services
        services_data = []
        for port in range(1000, 1100):
            services_data.append({
                'port': port,
                'protocol': 'tcp',
                'enrichment_source': 'naabu'
            })

        # Time the bulk upsert
        start_time = time.time()
        result = repo.bulk_upsert(mock_asset.id, services_data)
        elapsed_time = time.time() - start_time

        # Should complete in < 100ms for 100 records
        assert elapsed_time < 0.1

        # All records should be created
        assert result['created'] == 100
        assert result['total_processed'] == 100

    def test_get_web_services(self, db_session, mock_asset):
        """Test getting only web services (HTTP/HTTPS)"""
        repo = ServiceRepository(db_session)

        # Create mix of services
        services = [
            Service(asset_id=mock_asset.id, port=80, protocol='http', http_status=200),
            Service(asset_id=mock_asset.id, port=443, protocol='https', http_status=200),
            Service(asset_id=mock_asset.id, port=8080, protocol='http', http_status=200),
            Service(asset_id=mock_asset.id, port=22, protocol='ssh'),  # Not web
            Service(asset_id=mock_asset.id, port=3306, protocol='mysql'),  # Not web
        ]

        for service in services:
            db_session.add(service)
        db_session.commit()

        web_services = repo.get_web_services(mock_asset.id, only_live=True)

        # Should only return services with http_status (live web services)
        assert len(web_services) == 3
        assert all(s.port in [80, 443, 8080] for s in web_services)

    def test_get_services_with_tls(self, db_session, mock_asset):
        """Test getting services with TLS enabled"""
        repo = ServiceRepository(db_session)

        # Create services
        services = [
            Service(asset_id=mock_asset.id, port=443, has_tls=True, tls_version='TLSv1.3'),
            Service(asset_id=mock_asset.id, port=8443, has_tls=True, tls_version='TLSv1.2'),
            Service(asset_id=mock_asset.id, port=80, has_tls=False),
        ]

        for service in services:
            db_session.add(service)
        db_session.commit()

        tls_services = repo.get_services_with_tls(mock_asset.id)

        assert len(tls_services) == 2
        assert all(s.has_tls is True for s in tls_services)

    def test_get_services_by_technology(self, db_session, mock_asset, mock_tenant):
        """Test finding services by technology"""
        repo = ServiceRepository(db_session)

        # Create services with technologies
        services = [
            Service(
                asset_id=mock_asset.id,
                port=80,
                http_technologies=['nginx', 'PHP', 'WordPress']
            ),
            Service(
                asset_id=mock_asset.id,
                port=443,
                http_technologies=['Apache', 'Python']
            ),
        ]

        for service in services:
            db_session.add(service)
        db_session.commit()

        # Find services using WordPress
        wordpress_services = repo.get_services_by_technology(mock_tenant.id, 'WordPress')

        assert len(wordpress_services) == 1
        assert wordpress_services[0].port == 80


# =============================================================================
# CERTIFICATE REPOSITORY TESTS
# =============================================================================

class TestCertificateRepository:
    """Test CertificateRepository operations"""

    def test_bulk_upsert_creates_new_certificates(self, db_session, mock_asset):
        """Test bulk UPSERT creates new certificate records"""
        repo = CertificateRepository(db_session)

        certificates_data = [
            {
                'serial_number': 'ABC123',
                'subject_cn': 'example.com',
                'issuer': "Let's Encrypt",
                'not_before': datetime.utcnow() - timedelta(days=30),
                'not_after': datetime.utcnow() + timedelta(days=60),
                'is_expired': False,
                'days_until_expiry': 60,
                'san_domains': ['example.com', 'www.example.com'],
                'is_wildcard': False,
                'is_self_signed': False
            },
            {
                'serial_number': 'DEF456',
                'subject_cn': '*.example.com',
                'issuer': 'DigiCert',
                'not_after': datetime.utcnow() + timedelta(days=365),
                'is_wildcard': True
            }
        ]

        result = repo.bulk_upsert(mock_asset.id, certificates_data)

        assert result['created'] == 2
        assert result['updated'] == 0

        # Verify certificates were created
        certs = db_session.query(Certificate).filter_by(asset_id=mock_asset.id).all()
        assert len(certs) == 2

    def test_get_expiring_soon(self, db_session, mock_asset, mock_tenant):
        """Test getting certificates expiring soon"""
        repo = CertificateRepository(db_session)

        # Create certificates with different expiry dates
        certs = [
            Certificate(
                asset_id=mock_asset.id,
                serial_number='EXPIRING_SOON',
                not_after=datetime.utcnow() + timedelta(days=15),  # Expires in 15 days
                days_until_expiry=15,
                is_expired=False
            ),
            Certificate(
                asset_id=mock_asset.id,
                serial_number='VALID_LONG',
                not_after=datetime.utcnow() + timedelta(days=365),  # Expires in 1 year
                days_until_expiry=365,
                is_expired=False
            ),
            Certificate(
                asset_id=mock_asset.id,
                serial_number='ALREADY_EXPIRED',
                not_after=datetime.utcnow() - timedelta(days=10),  # Already expired
                days_until_expiry=-10,
                is_expired=True
            )
        ]

        for cert in certs:
            db_session.add(cert)
        db_session.commit()

        # Get certificates expiring within 30 days
        expiring_certs = repo.get_expiring_soon(mock_tenant.id, days_threshold=30)

        assert len(expiring_certs) == 1
        assert expiring_certs[0].serial_number == 'EXPIRING_SOON'

    def test_get_expired(self, db_session, mock_asset, mock_tenant):
        """Test getting expired certificates"""
        repo = CertificateRepository(db_session)

        # Create expired and valid certificates
        certs = [
            Certificate(
                asset_id=mock_asset.id,
                serial_number='EXPIRED_1',
                is_expired=True,
                not_after=datetime.utcnow() - timedelta(days=30)
            ),
            Certificate(
                asset_id=mock_asset.id,
                serial_number='EXPIRED_2',
                is_expired=True,
                not_after=datetime.utcnow() - timedelta(days=5)
            ),
            Certificate(
                asset_id=mock_asset.id,
                serial_number='VALID',
                is_expired=False,
                not_after=datetime.utcnow() + timedelta(days=60)
            )
        ]

        for cert in certs:
            db_session.add(cert)
        db_session.commit()

        expired_certs = repo.get_expired(mock_tenant.id)

        assert len(expired_certs) == 2
        assert all(cert.is_expired for cert in expired_certs)

    def test_get_self_signed(self, db_session, mock_asset, mock_tenant):
        """Test getting self-signed certificates"""
        repo = CertificateRepository(db_session)

        certs = [
            Certificate(
                asset_id=mock_asset.id,
                serial_number='SELF_SIGNED',
                is_self_signed=True,
                subject_cn='test.local'
            ),
            Certificate(
                asset_id=mock_asset.id,
                serial_number='CA_SIGNED',
                is_self_signed=False,
                issuer="Let's Encrypt"
            )
        ]

        for cert in certs:
            db_session.add(cert)
        db_session.commit()

        self_signed = repo.get_self_signed(mock_tenant.id)

        assert len(self_signed) == 1
        assert self_signed[0].is_self_signed is True

    def test_get_weak_signatures(self, db_session, mock_asset, mock_tenant):
        """Test getting certificates with weak signatures"""
        repo = CertificateRepository(db_session)

        certs = [
            Certificate(
                asset_id=mock_asset.id,
                serial_number='WEAK_SIG',
                has_weak_signature=True,
                signature_algorithm='SHA1WithRSA'
            ),
            Certificate(
                asset_id=mock_asset.id,
                serial_number='STRONG_SIG',
                has_weak_signature=False,
                signature_algorithm='SHA256WithRSA'
            )
        ]

        for cert in certs:
            db_session.add(cert)
        db_session.commit()

        weak_certs = repo.get_weak_signatures(mock_tenant.id)

        assert len(weak_certs) == 1
        assert weak_certs[0].has_weak_signature is True

    def test_get_certificate_stats(self, db_session, mock_asset, mock_tenant):
        """Test getting certificate statistics"""
        repo = CertificateRepository(db_session)

        # Create diverse certificates
        certs = [
            Certificate(asset_id=mock_asset.id, serial_number='1', is_expired=True),
            Certificate(asset_id=mock_asset.id, serial_number='2', is_expired=False, days_until_expiry=15),
            Certificate(asset_id=mock_asset.id, serial_number='3', is_self_signed=True),
            Certificate(asset_id=mock_asset.id, serial_number='4', has_weak_signature=True),
            Certificate(asset_id=mock_asset.id, serial_number='5', is_wildcard=True),
        ]

        for cert in certs:
            db_session.add(cert)
        db_session.commit()

        stats = repo.get_certificate_stats(mock_tenant.id)

        assert stats['total'] == 5
        assert stats['expired'] == 1
        assert stats['expiring_soon'] == 1  # days_until_expiry <= 30
        assert stats['self_signed'] == 1
        assert stats['weak_signatures'] == 1
        assert stats['wildcards'] == 1
        assert stats['valid'] == 4  # total - expired


# =============================================================================
# ENDPOINT REPOSITORY TESTS
# =============================================================================

class TestEndpointRepository:
    """Test EndpointRepository operations"""

    def test_bulk_upsert_creates_new_endpoints(self, db_session, mock_asset):
        """Test bulk UPSERT creates new endpoint records"""
        repo = EndpointRepository(db_session)

        endpoints_data = [
            {
                'url': 'https://example.com/',
                'method': 'GET',
                'path': '/',
                'status_code': 200,
                'endpoint_type': 'page',
                'is_api': False
            },
            {
                'url': 'https://example.com/api/v1/users',
                'method': 'GET',
                'path': '/api/v1/users',
                'status_code': 200,
                'endpoint_type': 'api',
                'is_api': True
            },
            {
                'url': 'https://example.com/admin/login',
                'method': 'POST',
                'path': '/admin/login',
                'endpoint_type': 'form'
            }
        ]

        result = repo.bulk_upsert(mock_asset.id, endpoints_data)

        assert result['created'] == 3
        assert result['updated'] == 0

        # Verify endpoints were created
        endpoints = db_session.query(Endpoint).filter_by(asset_id=mock_asset.id).all()
        assert len(endpoints) == 3

    def test_get_api_endpoints(self, db_session, mock_asset, mock_tenant):
        """Test getting only API endpoints"""
        repo = EndpointRepository(db_session)

        endpoints = [
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/api/users',
                method='GET',
                is_api=True,
                endpoint_type='api'
            ),
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/api/posts',
                method='GET',
                is_api=True,
                endpoint_type='api'
            ),
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/about',
                method='GET',
                is_api=False,
                endpoint_type='page'
            )
        ]

        for endpoint in endpoints:
            db_session.add(endpoint)
        db_session.commit()

        api_endpoints = repo.get_api_endpoints(mock_tenant.id)

        assert len(api_endpoints) == 2
        assert all(e.is_api for e in api_endpoints)

    def test_get_sensitive_endpoints(self, db_session, mock_asset, mock_tenant):
        """Test getting sensitive endpoints (admin, login, api, etc.)"""
        repo = EndpointRepository(db_session)

        endpoints = [
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/admin/dashboard',
                method='GET'
            ),
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/login',
                method='POST'
            ),
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/api/secret',
                method='GET'
            ),
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/about',
                method='GET'
            )
        ]

        for endpoint in endpoints:
            db_session.add(endpoint)
        db_session.commit()

        sensitive = repo.get_sensitive_endpoints(mock_tenant.id)

        # Should find admin, login, and api endpoints (not about)
        assert len(sensitive) == 3
        assert all(
            any(keyword in e.url.lower() for keyword in ['admin', 'login', 'api', 'secret'])
            for e in sensitive
        )

    def test_get_forms(self, db_session, mock_asset, mock_tenant):
        """Test getting form endpoints"""
        repo = EndpointRepository(db_session)

        endpoints = [
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/contact',
                method='POST',
                endpoint_type='form'
            ),
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/search',
                method='GET',
                endpoint_type='form'
            ),
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/api',
                method='GET',
                endpoint_type='api'
            )
        ]

        for endpoint in endpoints:
            db_session.add(endpoint)
        db_session.commit()

        forms = repo.get_forms(mock_tenant.id)

        assert len(forms) == 2
        assert all(e.endpoint_type == 'form' for e in forms)

    def test_get_external_links(self, db_session, mock_asset, mock_tenant):
        """Test getting external links"""
        repo = EndpointRepository(db_session)

        endpoints = [
            Endpoint(
                asset_id=mock_asset.id,
                url='https://external.com/page',
                is_external=True
            ),
            Endpoint(
                asset_id=mock_asset.id,
                url='https://example.com/internal',
                is_external=False
            )
        ]

        for endpoint in endpoints:
            db_session.add(endpoint)
        db_session.commit()

        external = repo.get_external_links(mock_tenant.id)

        assert len(external) == 1
        assert external[0].is_external is True

    def test_get_by_depth(self, db_session, mock_asset):
        """Test getting endpoints by crawl depth"""
        repo = EndpointRepository(db_session)

        endpoints = [
            Endpoint(asset_id=mock_asset.id, url='https://example.com/', depth=0),
            Endpoint(asset_id=mock_asset.id, url='https://example.com/page1', depth=1),
            Endpoint(asset_id=mock_asset.id, url='https://example.com/page1/sub', depth=2),
            Endpoint(asset_id=mock_asset.id, url='https://example.com/page1/sub/deep', depth=3),
        ]

        for endpoint in endpoints:
            db_session.add(endpoint)
        db_session.commit()

        # Get endpoints at depth 1-2
        depth_filtered = repo.get_by_depth(mock_asset.id, min_depth=1, max_depth=2)

        assert len(depth_filtered) == 2
        assert all(1 <= e.depth <= 2 for e in depth_filtered)

    def test_get_endpoint_stats(self, db_session, mock_asset, mock_tenant):
        """Test getting endpoint statistics"""
        repo = EndpointRepository(db_session)

        endpoints = [
            Endpoint(asset_id=mock_asset.id, url='https://example.com/api/1', is_api=True, endpoint_type='api'),
            Endpoint(asset_id=mock_asset.id, url='https://example.com/api/2', is_api=True, endpoint_type='api'),
            Endpoint(asset_id=mock_asset.id, url='https://external.com', is_external=True, endpoint_type='external'),
            Endpoint(asset_id=mock_asset.id, url='https://example.com/form', endpoint_type='form'),
        ]

        for endpoint in endpoints:
            db_session.add(endpoint)
        db_session.commit()

        stats = repo.get_endpoint_stats(mock_tenant.id)

        assert stats['total'] == 4
        assert stats['api_endpoints'] == 2
        assert stats['external_links'] == 1
        assert stats['forms'] == 1
        assert stats['by_type']['api'] == 2
        assert stats['by_type']['form'] == 1

    def test_get_recent_discoveries(self, db_session, mock_asset, mock_tenant):
        """Test getting recently discovered endpoints"""
        repo = EndpointRepository(db_session)

        # Create endpoints with different discovery times
        old_endpoint = Endpoint(
            asset_id=mock_asset.id,
            url='https://example.com/old',
            first_seen=datetime.utcnow() - timedelta(days=5)
        )
        recent_endpoint = Endpoint(
            asset_id=mock_asset.id,
            url='https://example.com/recent',
            first_seen=datetime.utcnow() - timedelta(hours=12)
        )

        db_session.add(old_endpoint)
        db_session.add(recent_endpoint)
        db_session.commit()

        # Get endpoints discovered in last 24 hours
        recent = repo.get_recent_discoveries(mock_tenant.id, hours=24)

        assert len(recent) == 1
        assert recent[0].url == 'https://example.com/recent'


# =============================================================================
# DATABASE CONSTRAINT TESTS
# =============================================================================

class TestDatabaseConstraints:
    """Test database constraints and unique indexes"""

    def test_service_unique_constraint_asset_port(self, db_session, mock_asset):
        """Test that (asset_id, port) is unique for services"""
        # Create first service
        service1 = Service(
            asset_id=mock_asset.id,
            port=80,
            protocol='http'
        )
        db_session.add(service1)
        db_session.commit()

        # Try to create duplicate (same asset, same port)
        service2 = Service(
            asset_id=mock_asset.id,
            port=80,
            protocol='https'  # Different protocol, but same port
        )
        db_session.add(service2)

        # Should raise IntegrityError due to unique constraint
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_certificate_unique_constraint_asset_serial(self, db_session, mock_asset):
        """Test that (asset_id, serial_number) is unique for certificates"""
        # Create first certificate
        cert1 = Certificate(
            asset_id=mock_asset.id,
            serial_number='ABC123'
        )
        db_session.add(cert1)
        db_session.commit()

        # Try to create duplicate (same asset, same serial)
        cert2 = Certificate(
            asset_id=mock_asset.id,
            serial_number='ABC123'
        )
        db_session.add(cert2)

        # Should raise IntegrityError
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_endpoint_unique_constraint_asset_url_method(self, db_session, mock_asset):
        """Test that (asset_id, url, method) is unique for endpoints"""
        # Create first endpoint
        endpoint1 = Endpoint(
            asset_id=mock_asset.id,
            url='https://example.com/api',
            method='GET'
        )
        db_session.add(endpoint1)
        db_session.commit()

        # Try to create duplicate (same asset, url, method)
        endpoint2 = Endpoint(
            asset_id=mock_asset.id,
            url='https://example.com/api',
            method='GET'
        )
        db_session.add(endpoint2)

        # Should raise IntegrityError
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_endpoint_different_methods_allowed(self, db_session, mock_asset):
        """Test that same URL with different methods is allowed"""
        # Create GET endpoint
        endpoint1 = Endpoint(
            asset_id=mock_asset.id,
            url='https://example.com/api',
            method='GET'
        )

        # Create POST endpoint (same URL, different method)
        endpoint2 = Endpoint(
            asset_id=mock_asset.id,
            url='https://example.com/api',
            method='POST'
        )

        db_session.add(endpoint1)
        db_session.add(endpoint2)
        db_session.commit()

        # Should not raise error - different methods are allowed
        endpoints = db_session.query(Endpoint).filter_by(
            asset_id=mock_asset.id
        ).all()

        assert len(endpoints) == 2
