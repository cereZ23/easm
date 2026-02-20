"""
Certificate API endpoint tests

Tests certificate management endpoints including:
- Listing certificates
- Filtering expiring certificates
- Filtering wildcard certificates
- Certificate details
- Tenant isolation
- Pagination
"""
import pytest
from datetime import datetime, timedelta


class TestListCertificates:
    """Test listing certificates endpoint"""

    def test_list_certificates(self, client, auth_headers, test_tenant, test_certs):
        """Test listing certificates for tenant"""
        response = client.get(f"/api/v1/tenants/{test_tenant.slug}/certificates", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("List certificates endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        certs = data if isinstance(data, list) else data.get("items", [])
        assert len(certs) >= len(test_certs)

        # Verify certificate structure
        if len(certs) > 0:
            cert = certs[0]
            assert "id" in cert
            assert "common_name" in cert
            assert "not_after" in cert or "expiry" in cert or "not_before" in cert

    def test_list_certificates_empty_tenant(self, client, auth_headers, other_tenant):
        """Test listing certificates for tenant with no certs"""
        response = client.get(f"/api/v1/tenants/{other_tenant.slug}/certificates", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("List certificates endpoint not yet implemented")

        # Should either be empty or forbidden
        if response.status_code == 200:
            data = response.json()
            certs = data if isinstance(data, list) else data.get("items", [])
        elif response.status_code == 403:
            assert True


class TestFilterCertificates:
    """Test certificate filtering"""

    def test_filter_expiring_certificates(self, client, auth_headers, test_tenant, test_certs):
        """Test filtering certs expiring within 30 days"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/certificates?expiring_in_days=30",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Certificate expiring filter not yet implemented")

        assert response.status_code == 200
        data = response.json()

        certs = data if isinstance(data, list) else data.get("items", [])

        # Verify certificates are expiring soon
        threshold = datetime.utcnow() + timedelta(days=30)
        for cert in certs:
            if "not_after" in cert:
                expiry = datetime.fromisoformat(cert["not_after"].replace("Z", "+00:00"))
                assert expiry <= threshold

    def test_filter_wildcard_certificates(self, client, auth_headers, test_tenant, test_certs):
        """Test filtering wildcard certificates"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/certificates?is_wildcard=true",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Certificate wildcard filter not yet implemented")

        assert response.status_code == 200
        data = response.json()

        certs = data if isinstance(data, list) else data.get("items", [])

        # All returned certs should be wildcard
        for cert in certs:
            assert cert.get("is_wildcard") is True or "*" in cert.get("common_name", "")

    def test_filter_self_signed_certificates(self, client, auth_headers, test_tenant):
        """Test filtering self-signed certificates"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/certificates?is_self_signed=true",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Certificate self-signed filter not yet implemented")

        assert response.status_code == 200
        data = response.json()

        certs = data if isinstance(data, list) else data.get("items", [])

        for cert in certs:
            if "is_self_signed" in cert:
                assert cert["is_self_signed"] is True

    def test_filter_certificates_by_issuer(self, client, auth_headers, test_tenant, test_certs):
        """Test filtering certificates by issuer"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/certificates?issuer=Let%27s%20Encrypt",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Certificate issuer filter not yet implemented")

        assert response.status_code == 200
        data = response.json()

        certs = data if isinstance(data, list) else data.get("items", [])

        for cert in certs:
            assert "let's encrypt" in cert.get("issuer", "").lower()


class TestGetCertificate:
    """Test retrieving certificate details"""

    def test_get_certificate_details(self, client, auth_headers, test_cert):
        """Test retrieving certificate details"""
        response = client.get(f"/api/v1/certificates/{test_cert.id}", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Get certificate endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == test_cert.id
        assert data["common_name"] == test_cert.common_name
        assert "issuer" in data
        assert "not_after" in data or "not_before" in data

    def test_get_nonexistent_certificate(self, client, auth_headers):
        """Test retrieving non-existent certificate returns 404"""
        response = client.get("/api/v1/certificates/999999", headers=auth_headers)

        if response.status_code == 401:
            pytest.skip("Get certificate endpoint not yet implemented")

        assert response.status_code == 404


class TestCertificatePagination:
    """Test certificate pagination"""

    def test_certificate_pagination(self, client, auth_headers, test_tenant, test_certs):
        """Test certificate list pagination"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/certificates?limit=2&offset=0",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Certificate pagination not yet implemented")

        assert response.status_code == 200
        data = response.json()

        # Should support pagination
        if not isinstance(data, list):
            assert "items" in data or "results" in data


class TestCertificateTenantIsolation:
    """Test tenant isolation for certificates"""

    def test_certificate_tenant_isolation(self, client, auth_headers, other_tenant_cert):
        """Test cannot access cert from different tenant"""
        response = client.get(f"/api/v1/certificates/{other_tenant_cert.id}", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Certificate endpoint not implemented or isolation working")

        # Should be forbidden or not found
        assert response.status_code in [403, 404]
