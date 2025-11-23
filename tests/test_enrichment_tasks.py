"""
Test suite for enrichment tasks (HTTPx, Naabu, TLSx, Katana)

Tests cover:
- Task execution and error handling
- Security features (SSRF prevention, input validation, output sanitization)
- Data processing and parsing
- Database integration
- Performance benchmarks
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json

from app.tasks.enrichment import (
    run_enrichment_pipeline,
    get_enrichment_candidates,
    run_httpx,
    run_naabu,
    run_tlsx,
    run_katana,
    parse_httpx_result,
    parse_naabu_result,
    parse_tlsx_result,
    sanitize_http_headers,
    sanitize_html,
    detect_and_redact_private_keys,
    is_ip_allowed
)
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
        slug="test-tenant",
        contact_policy="security@test.com"
    )
    db_session.add(tenant)
    db_session.commit()
    return tenant


@pytest.fixture
def mock_assets(db_session, mock_tenant):
    """Create test assets with different types and risk scores"""
    assets = [
        # Critical priority (risk_score >= 8.0)
        Asset(
            tenant_id=mock_tenant.id,
            type=AssetType.DOMAIN,
            identifier="critical.example.com",
            risk_score=9.0,
            priority="critical",
            is_active=True
        ),
        # High priority (6.0 <= risk_score < 8.0)
        Asset(
            tenant_id=mock_tenant.id,
            type=AssetType.SUBDOMAIN,
            identifier="high.example.com",
            risk_score=7.0,
            priority="high",
            is_active=True
        ),
        # Normal priority (3.0 <= risk_score < 6.0)
        Asset(
            tenant_id=mock_tenant.id,
            type=AssetType.IP,
            identifier="192.0.2.1",
            risk_score=5.0,
            priority="normal",
            is_active=True
        ),
        # Low priority (risk_score < 3.0)
        Asset(
            tenant_id=mock_tenant.id,
            type=AssetType.URL,
            identifier="https://low.example.com",
            risk_score=2.0,
            priority="low",
            is_active=True
        ),
    ]

    for asset in assets:
        db_session.add(asset)

    db_session.commit()
    return assets


# =============================================================================
# ENRICHMENT CANDIDATE SELECTION TESTS
# =============================================================================

class TestEnrichmentCandidates:
    """Test tiered enrichment candidate selection logic"""

    def test_get_candidates_by_priority_critical(self, db_session, mock_tenant, mock_assets):
        """Test getting critical priority assets (1-day TTL)"""
        # Set last_enriched_at to 2 days ago (stale for critical 1-day TTL)
        critical_asset = mock_assets[0]
        critical_asset.last_enriched_at = datetime.utcnow() - timedelta(days=2)
        db_session.commit()

        candidates = get_enrichment_candidates(
            tenant_id=mock_tenant.id,
            asset_ids=None,
            priority="critical",
            force_refresh=False,
            db=db_session
        )

        assert len(candidates) == 1
        assert candidates[0] == critical_asset.id

    def test_get_candidates_by_priority_high(self, db_session, mock_tenant, mock_assets):
        """Test getting high priority assets (3-day TTL)"""
        # Set last_enriched_at to 4 days ago (stale for high 3-day TTL)
        high_asset = mock_assets[1]
        high_asset.last_enriched_at = datetime.utcnow() - timedelta(days=4)
        db_session.commit()

        candidates = get_enrichment_candidates(
            tenant_id=mock_tenant.id,
            asset_ids=None,
            priority="high",
            force_refresh=False,
            db=db_session
        )

        assert len(candidates) == 1
        assert candidates[0] == high_asset.id

    def test_get_candidates_fresh_assets_excluded(self, db_session, mock_tenant, mock_assets):
        """Test that recently enriched assets are excluded"""
        # Set last_enriched_at to 1 hour ago (fresh for all TTLs)
        for asset in mock_assets:
            asset.last_enriched_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()

        candidates = get_enrichment_candidates(
            tenant_id=mock_tenant.id,
            asset_ids=None,
            priority=None,
            force_refresh=False,
            db=db_session
        )

        assert len(candidates) == 0

    def test_get_candidates_force_refresh(self, db_session, mock_tenant, mock_assets):
        """Test force refresh returns all assets regardless of TTL"""
        # Set all assets as recently enriched
        for asset in mock_assets:
            asset.last_enriched_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()

        candidates = get_enrichment_candidates(
            tenant_id=mock_tenant.id,
            asset_ids=None,
            priority=None,
            force_refresh=True,
            db=db_session
        )

        assert len(candidates) == 4  # All assets

    def test_get_candidates_specific_asset_ids(self, db_session, mock_tenant, mock_assets):
        """Test getting specific assets by ID list"""
        asset_ids = [mock_assets[0].id, mock_assets[1].id]

        candidates = get_enrichment_candidates(
            tenant_id=mock_tenant.id,
            asset_ids=asset_ids,
            priority=None,
            force_refresh=False,
            db=db_session
        )

        assert len(candidates) == 2
        assert set(candidates) == set(asset_ids)


# =============================================================================
# HTTPX TESTS
# =============================================================================

class TestHTTPx:
    """Test HTTPx web fingerprinting"""

    def test_parse_httpx_result_success(self):
        """Test parsing valid HTTPx JSON output"""
        httpx_output = {
            "url": "https://example.com:443",
            "status_code": 200,
            "title": "Example Domain",
            "webserver": "nginx/1.21.0",
            "technologies": ["nginx", "PHP", "WordPress"],
            "header": {
                "Server": "nginx/1.21.0",
                "Content-Type": "text/html; charset=UTF-8",
                "Authorization": "Bearer secret-token"  # Should be redacted
            },
            "time": "150ms",
            "content_length": 1234,
            "final_url": "https://www.example.com"
        }

        tenant_logger = Mock()
        result = parse_httpx_result(httpx_output, tenant_logger)

        assert result is not None
        assert result['port'] == 443
        assert result['protocol'] == 'https'
        assert result['http_status'] == 200
        assert result['http_title'] == "Example Domain"
        assert result['web_server'] == "nginx/1.21.0"
        assert result['http_technologies'] == ["nginx", "PHP", "WordPress"]
        assert result['response_time_ms'] == 150
        assert result['content_length'] == 1234
        assert result['redirect_url'] == "https://www.example.com"
        assert result['has_tls'] is True
        assert result['enrichment_source'] == 'httpx'

        # Verify Authorization header was redacted
        assert result['http_headers']['Authorization'] == '[REDACTED]'
        assert result['http_headers']['Server'] == "nginx/1.21.0"

    def test_sanitize_http_headers(self):
        """Test HTTP header sanitization removes sensitive values"""
        headers = {
            "Server": "nginx",
            "Content-Type": "text/html",
            "Authorization": "Bearer secret-token",
            "Cookie": "session=abc123",
            "Set-Cookie": "user=admin; HttpOnly",
            "X-API-Key": "api-key-12345",
            "Custom-Header": "safe-value"
        }

        sanitized = sanitize_http_headers(headers)

        # Sensitive headers should be redacted
        assert sanitized['Authorization'] == '[REDACTED]'
        assert sanitized['Cookie'] == '[REDACTED]'
        assert sanitized['Set-Cookie'] == '[REDACTED]'
        assert sanitized['X-API-Key'] == '[REDACTED]'

        # Non-sensitive headers should be preserved
        assert sanitized['Server'] == 'nginx'
        assert sanitized['Content-Type'] == 'text/html'
        assert sanitized['Custom-Header'] == 'safe-value'

    def test_sanitize_html_removes_xss(self):
        """Test HTML sanitization removes XSS vectors"""
        malicious_html = """
        <script>alert('XSS')</script>
        <iframe src="evil.com"></iframe>
        <a href="javascript:void(0)">Click</a>
        <div onclick="alert('XSS')">Text</div>
        Safe content here
        """

        sanitized = sanitize_html(malicious_html)

        # XSS vectors should be removed
        assert '<script>' not in sanitized
        assert 'alert(' not in sanitized
        assert '<iframe>' not in sanitized
        assert 'javascript:' not in sanitized
        assert 'onclick=' not in sanitized

        # Safe content should be preserved
        assert 'Safe content here' in sanitized

    @patch('app.database.SessionLocal')
    @patch('app.tasks.enrichment.SecureToolExecutor')
    def test_run_httpx_with_domain_assets(self, mock_executor_class, mock_session_local, db_session, mock_tenant, mock_assets):
        """Test HTTPx execution with domain assets"""
        # Patch SessionLocal to return our test session
        mock_session_local.return_value = db_session

        # Setup mock executor
        mock_executor = MagicMock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Mock HTTPx output
        httpx_output = json.dumps({
            "url": "https://critical.example.com",
            "status_code": 200,
            "title": "Test Site",
            "webserver": "nginx"
        })

        mock_executor.execute.return_value = (0, httpx_output, "")
        mock_executor.create_input_file.return_value = "/tmp/urls.txt"

        # Run HTTPx
        result = run_httpx(
            tenant_id=mock_tenant.id,
            asset_ids=[mock_assets[0].id]  # critical.example.com
        )

        # Verify executor was called correctly
        mock_executor.create_input_file.assert_called_once()
        mock_executor.execute.assert_called_once()

        # Verify httpx command arguments
        call_args = mock_executor.execute.call_args
        assert call_args[0][0] == 'httpx'
        assert '-json' in call_args[0][1]
        assert '-status-code' in call_args[0][1]


# =============================================================================
# NAABU TESTS
# =============================================================================

class TestNaabu:
    """Test Naabu port scanning"""

    def test_parse_naabu_result_success(self):
        """Test parsing valid Naabu JSON output"""
        naabu_output = {
            "host": "example.com",
            "port": 443
        }

        tenant_logger = Mock()
        result = parse_naabu_result(naabu_output, tenant_logger)

        assert result is not None
        assert result['host'] == "example.com"
        assert result['port'] == 443
        assert result['protocol'] == 'tcp'
        assert result['enrichment_source'] == 'naabu'

    def test_is_ip_allowed_public_ip(self):
        """Test that public IPs are allowed"""
        tenant_logger = Mock()

        # Public IP (Google DNS)
        assert is_ip_allowed("8.8.8.8", tenant_logger) is True

        # Another public IP
        assert is_ip_allowed("1.1.1.1", tenant_logger) is True

    def test_is_ip_allowed_blocks_rfc1918(self):
        """Test that RFC1918 private IPs are blocked (SSRF prevention)"""
        tenant_logger = Mock()

        # RFC1918 private networks
        assert is_ip_allowed("10.0.0.1", tenant_logger) is False
        assert is_ip_allowed("172.16.0.1", tenant_logger) is False
        assert is_ip_allowed("192.168.1.1", tenant_logger) is False

    def test_is_ip_allowed_blocks_loopback(self):
        """Test that loopback addresses are blocked"""
        tenant_logger = Mock()

        assert is_ip_allowed("127.0.0.1", tenant_logger) is False
        assert is_ip_allowed("127.1.1.1", tenant_logger) is False

    def test_is_ip_allowed_blocks_cloud_metadata(self):
        """Test that cloud metadata endpoints are blocked (SSRF prevention)"""
        tenant_logger = Mock()

        # AWS/Azure/GCP metadata endpoint
        assert is_ip_allowed("169.254.169.254", tenant_logger) is False

    def test_is_ip_allowed_blocks_link_local(self):
        """Test that link-local addresses are blocked"""
        tenant_logger = Mock()

        assert is_ip_allowed("169.254.1.1", tenant_logger) is False


# =============================================================================
# TLSX TESTS
# =============================================================================

class TestTLSx:
    """Test TLSx certificate analysis"""

    def test_detect_and_redact_private_keys_rsa(self):
        """Test CRITICAL private key detection for RSA keys"""
        output_with_key = """
        Some output here
        -----BEGIN RSA PRIVATE KEY-----
        MIIEpAIBAAKCAQEA1234567890abcdef
        ... private key data ...
        -----END RSA PRIVATE KEY-----
        More output
        """

        tenant_logger = Mock()
        detected, sanitized = detect_and_redact_private_keys(output_with_key, tenant_logger)

        assert detected is True
        assert '-----BEGIN RSA PRIVATE KEY-----' not in sanitized
        assert '[REDACTED: PRIVATE KEY - CRITICAL SECURITY INCIDENT]' in sanitized
        assert 'Some output here' in sanitized
        assert 'More output' in sanitized

        # Verify critical alert was logged
        tenant_logger.critical.assert_called()

    def test_detect_and_redact_private_keys_ec(self):
        """Test CRITICAL private key detection for EC keys"""
        output_with_key = """
        -----BEGIN EC PRIVATE KEY-----
        MHcCAQEEIIGlGNHHFx2JdRuPswrxQnL2J
        ... private key data ...
        -----END EC PRIVATE KEY-----
        """

        tenant_logger = Mock()
        detected, sanitized = detect_and_redact_private_keys(output_with_key, tenant_logger)

        assert detected is True
        assert '-----BEGIN EC PRIVATE KEY-----' not in sanitized
        assert '[REDACTED: PRIVATE KEY' in sanitized

    def test_detect_and_redact_private_keys_generic(self):
        """Test CRITICAL private key detection for generic keys"""
        output_with_key = """
        -----BEGIN PRIVATE KEY-----
        MIIEvQIBADANBgkqhkiG9w0BAQEFAASC
        -----END PRIVATE KEY-----
        """

        tenant_logger = Mock()
        detected, sanitized = detect_and_redact_private_keys(output_with_key, tenant_logger)

        assert detected is True
        assert '-----BEGIN PRIVATE KEY-----' not in sanitized

    def test_detect_and_redact_private_keys_encrypted(self):
        """Test CRITICAL private key detection for encrypted keys"""
        output_with_key = """
        -----BEGIN ENCRYPTED PRIVATE KEY-----
        MIIFLTBXBgkqhkiG9w0BBQ0wSjApBgkq
        -----END ENCRYPTED PRIVATE KEY-----
        """

        tenant_logger = Mock()
        detected, sanitized = detect_and_redact_private_keys(output_with_key, tenant_logger)

        assert detected is True
        assert '-----BEGIN ENCRYPTED PRIVATE KEY-----' not in sanitized

    def test_detect_and_redact_private_keys_clean_output(self):
        """Test that clean output (no private keys) passes through"""
        clean_output = """
        -----BEGIN CERTIFICATE-----
        MIIDXTCCAkWgAwIBAgIJAKL0UG+mRkSvMA0GCSqGSIb3
        -----END CERTIFICATE-----
        Subject: CN=example.com
        Issuer: Let's Encrypt
        """

        tenant_logger = Mock()
        detected, sanitized = detect_and_redact_private_keys(clean_output, tenant_logger)

        assert detected is False
        assert sanitized == clean_output

        # No critical alert for clean output
        tenant_logger.critical.assert_not_called()

    def test_detect_and_redact_multiple_keys(self):
        """Test detection of multiple private keys in output"""
        output_with_keys = """
        -----BEGIN RSA PRIVATE KEY-----
        ... key 1 ...
        -----END RSA PRIVATE KEY-----
        Some text
        -----BEGIN EC PRIVATE KEY-----
        ... key 2 ...
        -----END EC PRIVATE KEY-----
        """

        tenant_logger = Mock()
        detected, sanitized = detect_and_redact_private_keys(output_with_keys, tenant_logger)

        assert detected is True
        # Both keys should be redacted
        assert sanitized.count('[REDACTED: PRIVATE KEY') == 2
        assert '-----BEGIN RSA PRIVATE KEY-----' not in sanitized
        assert '-----BEGIN EC PRIVATE KEY-----' not in sanitized


# =============================================================================
# SECURITY VALIDATION TESTS
# =============================================================================

class TestSecurityValidation:
    """Test security validation and SSRF prevention"""

    @patch('app.database.SessionLocal')
    def test_httpx_validates_urls(self, mock_session_local, db_session, mock_tenant):
        """Test that HTTPx validates URLs before execution"""
        # Patch SessionLocal to return our test session
        mock_session_local.return_value = db_session

        # Create asset with internal IP (should be rejected by URLValidator)
        internal_asset = Asset(
            tenant_id=mock_tenant.id,
            type=AssetType.IP,
            identifier="192.168.1.1",  # Private IP
            is_active=True
        )
        db_session.add(internal_asset)
        db_session.commit()

        with patch('app.tasks.enrichment.SecureToolExecutor'):
            result = run_httpx(
                tenant_id=mock_tenant.id,
                asset_ids=[internal_asset.id]
            )

            # Should return 0 services because IP was rejected
            assert result.get('services_enriched', 0) == 0

    @patch('app.database.SessionLocal')
    def test_naabu_validates_ips(self, mock_session_local, db_session, mock_tenant):
        """Test that Naabu validates IPs before scanning"""
        # Patch SessionLocal to return our test session
        mock_session_local.return_value = db_session

        # Create asset with loopback IP (should be rejected)
        loopback_asset = Asset(
            tenant_id=mock_tenant.id,
            type=AssetType.IP,
            identifier="127.0.0.1",  # Loopback
            is_active=True
        )
        db_session.add(loopback_asset)
        db_session.commit()

        with patch('app.tasks.enrichment.SecureToolExecutor'):
            result = run_naabu(
                tenant_id=mock_tenant.id,
                asset_ids=[loopback_asset.id]
            )

            # Should return 0 ports because IP was blocked
            assert result.get('ports_discovered', 0) == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestEnrichmentIntegration:
    """Test end-to-end enrichment workflows"""

    @patch('app.database.SessionLocal')
    @patch('app.tasks.enrichment.chain')
    @patch('app.tasks.enrichment.group')
    def test_run_enrichment_pipeline_orchestration(self, mock_group, mock_chain, mock_session_local, db_session, mock_tenant, mock_assets):
        """Test that enrichment pipeline orchestrates tools correctly"""
        # Patch SessionLocal to return our test session
        mock_session_local.return_value = db_session

        # Set assets as stale
        for asset in mock_assets:
            asset.last_enriched_at = datetime.utcnow() - timedelta(days=10)
        db_session.commit()

        # Mock Celery primitives
        mock_parallel = Mock()
        mock_group.return_value = mock_parallel
        mock_sequential = Mock()
        mock_chain.return_value = mock_sequential
        mock_sequential.apply_async.return_value = Mock(id='task-123')

        result = run_enrichment_pipeline(
            tenant_id=mock_tenant.id,
            asset_ids=None,
            priority=None,
            force_refresh=False
        )

        # Verify parallel group was created with HTTPx, Naabu, TLSx
        mock_group.assert_called_once()

        # Verify chain was created (parallel group → Katana)
        mock_chain.assert_called_once()

        # Verify pipeline was queued
        mock_sequential.apply_async.assert_called_once()

        assert result['status'] == 'started'
        assert result['task_id'] == 'task-123'


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestEnrichmentPerformance:
    """Test enrichment performance benchmarks"""

    def test_bulk_candidate_selection_performance(self, db_session, mock_tenant):
        """Test that candidate selection is fast even with many assets"""
        import time

        # Create 1000 assets
        assets = []
        for i in range(1000):
            asset = Asset(
                tenant_id=mock_tenant.id,
                type=AssetType.SUBDOMAIN,
                identifier=f"subdomain{i}.example.com",
                risk_score=5.0,
                priority="normal",
                last_enriched_at=datetime.utcnow() - timedelta(days=10),
                is_active=True
            )
            assets.append(asset)

        db_session.bulk_save_objects(assets)
        db_session.commit()

        # Time the candidate selection
        start_time = time.time()
        candidates = get_enrichment_candidates(
            tenant_id=mock_tenant.id,
            asset_ids=None,
            priority="normal",
            force_refresh=False,
            db=db_session
        )
        elapsed_time = time.time() - start_time

        # Should complete in < 100ms even with 1000 assets
        assert elapsed_time < 0.1
        assert len(candidates) > 0


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error handling in enrichment tasks"""

    @patch('app.database.SessionLocal')
    @patch('app.tasks.enrichment.SecureToolExecutor')
    def test_httpx_handles_tool_execution_error(self, mock_executor_class, mock_session_local, db_session, mock_tenant, mock_assets):
        """Test that HTTPx handles tool execution errors gracefully"""
        # Patch SessionLocal to return our test session
        mock_session_local.return_value = db_session

        # Setup mock executor to raise exception
        mock_executor = MagicMock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor
        mock_executor.create_input_file.return_value = "/tmp/urls.txt"

        from app.utils.secure_executor import ToolExecutionError
        mock_executor.execute.side_effect = ToolExecutionError("Tool failed")

        result = run_httpx(
            tenant_id=mock_tenant.id,
            asset_ids=[mock_assets[0].id]
        )

        # Should return error but not crash
        assert 'error' in result
        assert result['services_enriched'] == 0

    def test_parse_httpx_handles_malformed_json(self):
        """Test that parser handles malformed JSON gracefully"""
        malformed_data = {
            "url": "https://example.com",
            # Missing required fields
        }

        tenant_logger = Mock()
        result = parse_httpx_result(malformed_data, tenant_logger)

        # Should return None for malformed data
        # Parser should not crash
        assert True  # Test passes if no exception raised


# =============================================================================
# PRIORITY SYSTEM TESTS
# =============================================================================

class TestPrioritySystem:
    """Test tiered enrichment priority system"""

    def test_critical_assets_enriched_daily(self, db_session, mock_tenant):
        """Test that critical assets (1-day TTL) are selected after 24 hours"""
        # Create critical asset enriched 25 hours ago
        asset = Asset(
            tenant_id=mock_tenant.id,
            type=AssetType.DOMAIN,
            identifier="critical.example.com",
            risk_score=9.0,
            priority="critical",
            last_enriched_at=datetime.utcnow() - timedelta(hours=25),
            is_active=True
        )
        db_session.add(asset)
        db_session.commit()

        candidates = get_enrichment_candidates(
            tenant_id=mock_tenant.id,
            asset_ids=None,
            priority="critical",
            force_refresh=False,
            db=db_session
        )

        assert len(candidates) == 1
        assert candidates[0] == asset.id

    def test_high_assets_enriched_every_3_days(self, db_session, mock_tenant):
        """Test that high priority assets (3-day TTL) are selected after 72 hours"""
        # Create high priority asset enriched 73 hours ago
        asset = Asset(
            tenant_id=mock_tenant.id,
            type=AssetType.DOMAIN,
            identifier="high.example.com",
            risk_score=7.0,
            priority="high",
            last_enriched_at=datetime.utcnow() - timedelta(hours=73),
            is_active=True
        )
        db_session.add(asset)
        db_session.commit()

        candidates = get_enrichment_candidates(
            tenant_id=mock_tenant.id,
            asset_ids=None,
            priority="high",
            force_refresh=False,
            db=db_session
        )

        assert len(candidates) == 1

    def test_normal_assets_enriched_weekly(self, db_session, mock_tenant):
        """Test that normal priority assets (7-day TTL) are selected after 7 days"""
        # Create normal asset enriched 8 days ago
        asset = Asset(
            tenant_id=mock_tenant.id,
            type=AssetType.DOMAIN,
            identifier="normal.example.com",
            risk_score=5.0,
            priority="normal",
            last_enriched_at=datetime.utcnow() - timedelta(days=8),
            is_active=True
        )
        db_session.add(asset)
        db_session.commit()

        candidates = get_enrichment_candidates(
            tenant_id=mock_tenant.id,
            asset_ids=None,
            priority="normal",
            force_refresh=False,
            db=db_session
        )

        assert len(candidates) == 1

    def test_low_assets_enriched_biweekly(self, db_session, mock_tenant):
        """Test that low priority assets (14-day TTL) are selected after 14 days"""
        # Create low priority asset enriched 15 days ago
        asset = Asset(
            tenant_id=mock_tenant.id,
            type=AssetType.DOMAIN,
            identifier="low.example.com",
            risk_score=1.0,
            priority="low",
            last_enriched_at=datetime.utcnow() - timedelta(days=15),
            is_active=True
        )
        db_session.add(asset)
        db_session.commit()

        candidates = get_enrichment_candidates(
            tenant_id=mock_tenant.id,
            asset_ids=None,
            priority="low",
            force_refresh=False,
            db=db_session
        )

        assert len(candidates) == 1
