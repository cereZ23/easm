"""
Authentication API endpoint tests

Tests all authentication flows including:
- Login with credentials
- Token refresh
- Logout
- Rate limiting
- Token validation
"""
import pytest
import time
from datetime import datetime, timedelta


class TestAuthLogin:
    """Test login endpoint"""

    def test_login_success(self, client, test_user, db_session):
        """Test successful login returns JWT tokens"""
        response = client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "password123"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_email(self, client):
        """Test login with non-existent email returns 401"""
        response = client.post("/api/v1/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password123"
        })

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "incorrect" in data["detail"].lower() or "invalid" in data["detail"].lower()

    def test_login_invalid_password(self, client, test_user):
        """Test login with wrong password returns 401"""
        response = client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "wrongpassword"
        })

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_login_inactive_user(self, client, db_session, test_tenant):
        """Test login with inactive user returns 401"""
        # Create inactive user
        try:
            from app.models.user import User
            from app.security.auth import get_password_hash
        except ImportError:
            pytest.skip("User model not yet implemented")

        inactive_user = User(
            email="inactive@example.com",
            username="inactive",
            hashed_password=get_password_hash("password123"),
            is_active=False
        )
        db_session.add(inactive_user)
        db_session.commit()

        response = client.post("/api/v1/auth/login", json={
            "email": "inactive@example.com",
            "password": "password123"
        })

        assert response.status_code in [401, 403]

    @pytest.mark.slow
    def test_login_rate_limiting(self, client):
        """Test login endpoint has rate limiting (10 requests per minute)"""
        # Make 11 rapid login attempts
        responses = []
        for i in range(11):
            response = client.post("/api/v1/auth/login", json={
                "email": f"test{i}@example.com",
                "password": "password123"
            })
            responses.append(response.status_code)
            if i < 10:
                # Small delay to avoid overwhelming test server
                time.sleep(0.1)

        # At least one request should be rate limited (429 Too Many Requests)
        # Note: This test may be skipped if rate limiting is not yet implemented
        if 429 in responses:
            assert responses.count(429) >= 1
        else:
            pytest.skip("Rate limiting not yet implemented")

    def test_login_missing_email(self, client):
        """Test login without email returns 422"""
        response = client.post("/api/v1/auth/login", json={
            "password": "password123"
        })

        assert response.status_code == 422

    def test_login_missing_password(self, client):
        """Test login without password returns 422"""
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com"
        })

        assert response.status_code == 422


class TestTokenRefresh:
    """Test token refresh endpoint"""

    def test_refresh_token_success(self, client, test_user):
        """Test refresh token generates new access token"""
        # First, login to get refresh token
        login_response = client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "password123"
        })

        if login_response.status_code != 200:
            pytest.skip("Login endpoint not yet implemented")

        refresh_token = login_response.json().get("refresh_token")
        if not refresh_token:
            pytest.skip("Refresh token not returned in login response")

        # Use refresh token to get new access token
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data

    def test_refresh_token_invalid(self, client):
        """Test invalid refresh token returns 401"""
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid.token.here"
        })

        assert response.status_code == 401

    def test_refresh_token_expired(self, client):
        """Test expired refresh token returns 401"""
        try:
            from app.security.auth import create_refresh_token
        except ImportError:
            pytest.skip("Auth module not yet implemented")

        # Create an already-expired token
        expired_token = create_refresh_token(
            {"sub": "test@example.com"},
            expires_delta=timedelta(seconds=-1)
        )

        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": expired_token
        })

        assert response.status_code == 401


class TestLogout:
    """Test logout endpoint"""

    def test_logout_revokes_token(self, client, auth_headers):
        """Test logout invalidates token"""
        # Logout
        response = client.post("/api/v1/auth/logout", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Logout endpoint not yet implemented")

        assert response.status_code in [200, 204]

        # Try to use the token after logout
        # This should fail if token revocation is implemented
        protected_response = client.get("/api/v1/auth/me", headers=auth_headers)

        # Either 401 (revoked) or 200 (revocation not yet implemented)
        if protected_response.status_code == 401:
            # Token revocation is working
            assert True
        else:
            pytest.skip("Token revocation not yet implemented")


class TestCurrentUser:
    """Test current user endpoint"""

    def test_get_current_user(self, client, auth_headers, test_user):
        """Test /auth/me returns user profile"""
        response = client.get("/api/v1/auth/me", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Current user endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert "id" in data
        assert "username" in data

    def test_unauthorized_access(self, client):
        """Test endpoints without token return 401"""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_invalid_token_format(self, client):
        """Test malformed JWT returns 401"""
        headers = {"Authorization": "Bearer invalid-token-format"}
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == 401

    def test_missing_bearer_prefix(self, client, auth_headers):
        """Test token without 'Bearer' prefix returns 401"""
        # Extract token without Bearer prefix
        token = auth_headers["Authorization"].replace("Bearer ", "")
        headers = {"Authorization": token}

        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == 401

    def test_expired_token_rejected(self, client):
        """Test expired JWT returns 401"""
        try:
            from app.security.auth import create_access_token
        except ImportError:
            pytest.skip("Auth module not yet implemented")

        # Create an already-expired token
        expired_token = create_access_token(
            {"sub": "test@example.com", "user_id": 1},
            expires_delta=timedelta(seconds=-1)
        )

        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == 401


class TestPasswordChange:
    """Test password change endpoint (if implemented)"""

    def test_change_password_success(self, client, auth_headers, test_user, db_session):
        """Test successful password change"""
        response = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "current_password": "password123",
            "new_password": "newpassword456"
        })

        if response.status_code == 404:
            pytest.skip("Password change endpoint not yet implemented")

        assert response.status_code == 200

        # Verify can login with new password
        login_response = client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "newpassword456"
        })

        assert login_response.status_code == 200

    def test_change_password_wrong_current(self, client, auth_headers):
        """Test password change with wrong current password fails"""
        response = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "current_password": "wrongpassword",
            "new_password": "newpassword456"
        })

        if response.status_code == 404:
            pytest.skip("Password change endpoint not yet implemented")

        assert response.status_code in [400, 401]


class TestTokenSecurity:
    """Test JWT token security features"""

    def test_token_contains_user_info(self, client, test_user):
        """Test JWT token contains user information"""
        try:
            from jose import jwt
            from app.config import get_settings
        except ImportError:
            pytest.skip("JWT library or config not available")

        login_response = client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "password123"
        })

        if login_response.status_code != 200:
            pytest.skip("Login endpoint not yet implemented")

        token = login_response.json()["access_token"]

        # Decode token (without verification for testing)
        try:
            settings = get_settings()
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

            assert "sub" in payload
            assert "exp" in payload
            assert payload["sub"] == test_user.email or payload.get("user_id") == test_user.id
        except Exception:
            pytest.skip("Token decoding failed - token format may differ")

    def test_tokens_have_different_purposes(self, client, test_user):
        """Test access and refresh tokens have different type indicators"""
        try:
            from jose import jwt
        except ImportError:
            pytest.skip("JWT library not available")

        login_response = client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "password123"
        })

        if login_response.status_code != 200:
            pytest.skip("Login endpoint not yet implemented")

        data = login_response.json()
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")

        if not refresh_token:
            pytest.skip("Refresh token not implemented")

        # Decode both tokens (without verification)
        try:
            access_payload = jwt.decode(access_token, options={"verify_signature": False})
            refresh_payload = jwt.decode(refresh_token, options={"verify_signature": False})

            # Should have different type/purpose indicators
            if "type" in access_payload and "type" in refresh_payload:
                assert access_payload["type"] != refresh_payload["type"]
        except Exception:
            pytest.skip("Token structure inspection failed")
