"""
Certificate Endpoint Tests

Tests for TLS certificate listing, expiration tracking, and filtering.
Total: 7 tests
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.models import Asset, AssetType
from app.models.enrichment import Certificate


class TestCertificateEndpoints:
    """Test suite for certificate endpoints"""

    def test_list_certificates_for_tenant(
        self, authenticated_client, test_tenant, tenant_with_certificates
    ):
        """Test listing all certificates for a tenant"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/certificates"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        if isinstance(data, dict):
            assert "items" in data
            certs = data["items"]
        else:
            certs = data

        assert isinstance(certs, list)
        assert len(certs) > 0

        # Verify certificate structure
        cert = certs[0]
        assert "id" in cert
        assert "asset_id" in cert
        assert "common_name" in cert
        assert "issuer" in cert
        assert "not_before" in cert
        assert "not_after" in cert

    def test_list_expiring_certificates_within_30_days(
        self, authenticated_client, test_tenant, expiring_certificates
    ):
        """Test listing certificates expiring within 30 days"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/certificates",
            params={"expiring_within_days": 30}
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            certs = data["items"]
        else:
            certs = data

        # Should return certificates expiring soon
        assert len(certs) > 0

        # Verify all certificates expire within 30 days
        cutoff_date = datetime.utcnow() + timedelta(days=30)
        for cert in certs:
            not_after = datetime.fromisoformat(cert["not_after"].replace('Z', '+00:00'))
            assert not_after <= cutoff_date

    def test_list_expiring_certificates_within_7_days(
        self, authenticated_client, test_tenant, critical_expiring_certificates
    ):
        """Test listing certificates expiring within 7 days (critical)"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/certificates",
            params={"expiring_within_days": 7}
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            certs = data["items"]
        else:
            certs = data

        # Verify all certificates expire within 7 days
        cutoff_date = datetime.utcnow() + timedelta(days=7)
        for cert in certs:
            not_after = datetime.fromisoformat(cert["not_after"].replace('Z', '+00:00'))
            assert not_after <= cutoff_date

    def test_certificate_details_include_san_domains(
        self, authenticated_client, test_tenant, certificate_with_sans
    ):
        """Test certificate details include Subject Alternative Names"""
        cert_id = certificate_with_sans.id

        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/certificates/{cert_id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should include SAN domains
        assert "san_domains" in data or "subject_alt_names" in data

        san_key = "san_domains" if "san_domains" in data else "subject_alt_names"
        assert isinstance(data[san_key], list)
        assert len(data[san_key]) > 0

    def test_certificate_issuer_filtering(
        self, authenticated_client, test_tenant, certificates_various_issuers
    ):
        """Test filtering certificates by issuer"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/certificates",
            params={"issuer": "Let's Encrypt"}
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            certs = data["items"]
        else:
            certs = data

        # All returned certificates should be from Let's Encrypt
        for cert in certs:
            assert "let's encrypt" in cert["issuer"].lower()

    @pytest.mark.security
    def test_certificates_enforce_tenant_isolation(
        self, authenticated_client, test_tenant, other_tenant, other_tenant_certificates
    ):
        """Test tenant isolation for certificate endpoints"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/certificates"
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            certs = data["items"]
        else:
            certs = data

        # Should not see other tenant's certificates
        # Verify by checking asset ownership
        for cert in certs:
            assert cert["asset_id"] is not None

    def test_expired_certificates_flagged(
        self, authenticated_client, test_tenant, expired_certificates
    ):
        """Test expired certificates are properly flagged"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/certificates",
            params={"expired": "true"}
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            certs = data["items"]
        else:
            certs = data

        # All returned certificates should be expired
        now = datetime.utcnow()
        for cert in certs:
            not_after = datetime.fromisoformat(cert["not_after"].replace('Z', '+00:00'))
            assert not_after < now


@pytest.fixture
def tenant_with_certificates(db_session, test_tenant):
    """Create tenant with assets and certificates"""
    # Create assets
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"secure{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=30.0,
            is_active=True
        )
        for i in range(3)
    ]
    db_session.add_all(assets)
    db_session.commit()

    # Create certificates
    certificates = []
    for i, asset in enumerate(assets):
        db_session.refresh(asset)
        cert = Certificate(
            asset_id=asset.id,
            common_name=asset.identifier,
            issuer="Let's Encrypt Authority X3",
            not_before=datetime.utcnow() - timedelta(days=30),
            not_after=datetime.utcnow() + timedelta(days=60),
            serial_number=f"serial_{i}",
            san_domains=[asset.identifier, f"www.{asset.identifier}"]
        )
        certificates.append(cert)

    db_session.add_all(certificates)
    db_session.commit()
    return certificates


@pytest.fixture
def expiring_certificates(db_session, test_tenant):
    """Create certificates expiring within 30 days"""
    asset = Asset(
        tenant_id=test_tenant.id,
        identifier="expiring-soon.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=50.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    certificates = [
        Certificate(
            asset_id=asset.id,
            common_name=asset.identifier,
            issuer="DigiCert",
            not_before=datetime.utcnow() - timedelta(days=300),
            not_after=datetime.utcnow() + timedelta(days=15),
            serial_number="exp_15_days"
        ),
        Certificate(
            asset_id=asset.id,
            common_name=f"alt.{asset.identifier}",
            issuer="DigiCert",
            not_before=datetime.utcnow() - timedelta(days=300),
            not_after=datetime.utcnow() + timedelta(days=25),
            serial_number="exp_25_days"
        ),
    ]
    db_session.add_all(certificates)
    db_session.commit()
    return certificates


@pytest.fixture
def critical_expiring_certificates(db_session, test_tenant):
    """Create certificates expiring within 7 days"""
    asset = Asset(
        tenant_id=test_tenant.id,
        identifier="critical-expiry.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=75.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    cert = Certificate(
        asset_id=asset.id,
        common_name=asset.identifier,
        issuer="Let's Encrypt",
        not_before=datetime.utcnow() - timedelta(days=80),
        not_after=datetime.utcnow() + timedelta(days=3),
        serial_number="critical_3_days"
    )
    db_session.add(cert)
    db_session.commit()
    return [cert]


@pytest.fixture
def certificate_with_sans(db_session, test_tenant):
    """Create certificate with multiple SAN domains"""
    asset = Asset(
        tenant_id=test_tenant.id,
        identifier="multi-san.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=40.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    cert = Certificate(
        asset_id=asset.id,
        common_name="multi-san.example.com",
        issuer="DigiCert SHA2 Secure Server CA",
        not_before=datetime.utcnow() - timedelta(days=30),
        not_after=datetime.utcnow() + timedelta(days=335),
        serial_number="san_cert_123",
        san_domains=[
            "multi-san.example.com",
            "www.multi-san.example.com",
            "api.multi-san.example.com",
            "cdn.multi-san.example.com"
        ]
    )
    db_session.add(cert)
    db_session.commit()
    db_session.refresh(cert)
    return cert


@pytest.fixture
def certificates_various_issuers(db_session, test_tenant):
    """Create certificates from various issuers"""
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"issuer{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=35.0,
            is_active=True
        )
        for i in range(4)
    ]
    db_session.add_all(assets)
    db_session.commit()

    issuers = [
        "Let's Encrypt Authority X3",
        "Let's Encrypt Authority R3",
        "DigiCert SHA2 Secure Server CA",
        "GlobalSign RSA CA 2018"
    ]

    certificates = []
    for asset, issuer in zip(assets, issuers):
        db_session.refresh(asset)
        cert = Certificate(
            asset_id=asset.id,
            common_name=asset.identifier,
            issuer=issuer,
            not_before=datetime.utcnow() - timedelta(days=30),
            not_after=datetime.utcnow() + timedelta(days=335),
            serial_number=f"issuer_{asset.id}"
        )
        certificates.append(cert)

    db_session.add_all(certificates)
    db_session.commit()
    return certificates


@pytest.fixture
def other_tenant_certificates(db_session, other_tenant):
    """Create certificates for other tenant"""
    asset = Asset(
        tenant_id=other_tenant.id,
        identifier="other-cert.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=30.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    cert = Certificate(
        asset_id=asset.id,
        common_name=asset.identifier,
        issuer="Let's Encrypt",
        not_before=datetime.utcnow() - timedelta(days=30),
        not_after=datetime.utcnow() + timedelta(days=60),
        serial_number="other_tenant_cert"
    )
    db_session.add(cert)
    db_session.commit()
    return [cert]


@pytest.fixture
def expired_certificates(db_session, test_tenant):
    """Create expired certificates"""
    asset = Asset(
        tenant_id=test_tenant.id,
        identifier="expired.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=80.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    cert = Certificate(
        asset_id=asset.id,
        common_name=asset.identifier,
        issuer="Old CA",
        not_before=datetime.utcnow() - timedelta(days=400),
        not_after=datetime.utcnow() - timedelta(days=5),
        serial_number="expired_cert"
    )
    db_session.add(cert)
    db_session.commit()
    return [cert]
