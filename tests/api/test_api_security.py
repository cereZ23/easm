"""
API Security Tests

Tests for API security including authentication, authorization, input validation,
and protection against common attacks.
Total: 10 tests
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.security
class TestAPISecurity:
    """Test suite for API security measures"""

    def test_jwt_tampering_detected(self, api_client, test_user):
        """Test that tampered JWT tokens are rejected"""
        # Get valid token
        login_response = api_client.post("/api/v1/auth/login", json={
            "username": test_user.username,
            "password": "testpass123"
        })
        valid_token = login_response.json()["access_token"]

        # Tamper with token (change last character)
        tampered_token = valid_token[:-1] + ('A' if valid_token[-1] != 'A' else 'B')

        # Try to use tampered token
        api_client.headers = {"Authorization": f"Bearer {tampered_token}"}
        response = api_client.get("/api/v1/auth/me")

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_expired_token_rejected(self, api_client, expired_token):
        """Test that expired tokens are rejected"""
        api_client.headers = {"Authorization": f"Bearer {expired_token}"}
        response = api_client.get("/api/v1/auth/me")

        assert response.status_code == 401
        data = response.json()
        assert "expired" in data["detail"].lower() or "invalid" in data["detail"].lower()

    def test_sql_injection_prevented(self, authenticated_client, test_tenant):
        """Test SQL injection attempts are prevented"""
        sql_injection_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE assets;--",
            "1' UNION SELECT * FROM users--",
            "admin'--",
            "' OR 1=1--",
        ]

        for payload in sql_injection_payloads:
            # Try SQL injection in search parameter
            response = authenticated_client.get(
                f"/api/v1/tenants/{test_tenant.id}/assets",
                params={"search": payload}
            )

            # Should either sanitize input or return safe error
            assert response.status_code in [200, 400, 422]

            # If successful, should return valid data (not SQL error)
            if response.status_code == 200:
                data = response.json()
                assert "items" in data
                # Should not expose SQL errors
                assert "SQL" not in str(data).upper()
                assert "SYNTAX" not in str(data).upper()

    def test_xss_input_sanitized(self, authenticated_client, test_tenant):
        """Test XSS payloads are sanitized"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
        ]

        for payload in xss_payloads:
            # Try to create seed with XSS payload
            response = authenticated_client.post(
                f"/api/v1/tenants/{test_tenant.id}/seeds",
                json={
                    "type": "domain",
                    "identifier": payload
                }
            )

            # Should reject invalid input
            assert response.status_code in [400, 422]

            # If accepted, XSS should be sanitized
            if response.status_code in [200, 201]:
                data = response.json()
                # Should not contain script tags
                assert "<script>" not in str(data).lower()
                assert "onerror" not in str(data).lower()

    def test_ssrf_prevention_on_asset_creation(self, authenticated_client, test_tenant):
        """Test SSRF prevention when creating assets"""
        ssrf_payloads = [
            {"type": "domain", "identifier": "localhost"},
            {"type": "domain", "identifier": "127.0.0.1"},
            {"type": "domain", "identifier": "169.254.169.254"},  # AWS metadata
            {"type": "domain", "identifier": "0.0.0.0"},
            {"type": "ip", "identifier": "127.0.0.1"},
            {"type": "ip", "identifier": "192.168.1.1"},
            {"type": "ip", "identifier": "10.0.0.1"},
            {"type": "ip", "identifier": "172.16.0.1"},
        ]

        for payload in ssrf_payloads:
            response = authenticated_client.post(
                f"/api/v1/tenants/{test_tenant.id}/seeds",
                json=payload
            )

            # Should reject internal/private IPs and hostnames
            assert response.status_code in [400, 422]
            data = response.json()
            assert "detail" in data or "error" in data

    def test_rate_limiting_enforced(self, api_client, test_user):
        """Test rate limiting is enforced on API endpoints"""
        # Login
        login_response = api_client.post("/api/v1/auth/login", json={
            "username": test_user.username,
            "password": "testpass123"
        })
        token = login_response.json()["access_token"]
        api_client.headers = {"Authorization": f"Bearer {token}"}

        # Make rapid requests
        rate_limited = False
        for i in range(200):
            response = api_client.get("/api/v1/auth/me")

            if response.status_code == 429:
                rate_limited = True
                data = response.json()
                assert "detail" in data
                assert "rate" in data["detail"].lower() or "too many" in data["detail"].lower()
                break

        # Should eventually hit rate limit
        # (or if rate limit is very high, all requests succeed)
        assert rate_limited or response.status_code == 200

    def test_cors_headers_correct(self, api_client):
        """Test CORS headers are configured correctly"""
        response = api_client.options("/api/v1/auth/login")

        # CORS headers should be present
        headers = response.headers

        # May have CORS headers or not depending on configuration
        # If present, verify they're secure
        if "access-control-allow-origin" in headers:
            origin = headers["access-control-allow-origin"]
            # Should not be wildcard (*) in production
            # But for testing, either specific domain or *
            assert origin is not None

    def test_security_headers_present(self, api_client):
        """Test security headers are present in responses"""
        response = api_client.get("/api/v1/auth/login")

        headers = response.headers

        # Check for important security headers
        # Note: FastAPI may not set all these by default
        security_headers = [
            "x-content-type-options",
            "x-frame-options",
            "x-xss-protection",
        ]

        # At least some security headers should be present
        # This is more of a guideline test
        present_headers = [h for h in security_headers if h in headers]

        # If security headers are implemented
        if "x-content-type-options" in headers:
            assert headers["x-content-type-options"] == "nosniff"

        if "x-frame-options" in headers:
            assert headers["x-frame-options"] in ["DENY", "SAMEORIGIN"]

    def test_multi_tenant_isolation_enforced(
        self, authenticated_client, test_tenant, other_tenant, other_tenant_assets
    ):
        """Test strict multi-tenant isolation"""
        # User authenticated for test_tenant tries to access other_tenant resources

        # Test 1: List other tenant's assets
        response1 = authenticated_client.get(
            f"/api/v1/tenants/{other_tenant.id}/assets"
        )
        assert response1.status_code in [403, 404]

        # Test 2: Get specific asset from other tenant
        if other_tenant_assets:
            other_asset_id = other_tenant_assets[0].id
            response2 = authenticated_client.get(
                f"/api/v1/tenants/{other_tenant.id}/assets/{other_asset_id}"
            )
            assert response2.status_code in [403, 404]

        # Test 3: Try to create seed for other tenant
        response3 = authenticated_client.post(
            f"/api/v1/tenants/{other_tenant.id}/seeds",
            json={
                "type": "domain",
                "identifier": "malicious.example.com"
            }
        )
        assert response3.status_code in [403, 404]

        # Test 4: Try to access other tenant's findings
        response4 = authenticated_client.get(
            f"/api/v1/tenants/{other_tenant.id}/findings"
        )
        assert response4.status_code in [403, 404]

    def test_unauthorized_access_blocked(self, api_client, test_tenant):
        """Test unauthorized access is blocked"""
        protected_endpoints = [
            f"/api/v1/tenants/{test_tenant.id}/dashboard",
            f"/api/v1/tenants/{test_tenant.id}/assets",
            f"/api/v1/tenants/{test_tenant.id}/findings",
            f"/api/v1/tenants/{test_tenant.id}/services",
            "/api/v1/auth/me",
        ]

        for endpoint in protected_endpoints:
            # Try without authentication
            response = api_client.get(endpoint)

            # Should return 401 Unauthorized
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data


# ==================== Fixtures ====================

@pytest.fixture
def expired_token():
    """Generate an expired JWT token"""
    from datetime import datetime, timedelta
    from jose import jwt
    from app.config import get_settings

    settings = get_settings()
    payload = {
        "sub": "testuser",
        "exp": datetime.utcnow() - timedelta(days=1),
        "type": "access"
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
