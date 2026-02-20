"""
Unit tests for NucleiService

Tests cover:
- Nuclei execution with various templates
- JSON output parsing
- Finding normalization
- Severity filtering
- Rate limiting
- Error handling
- Security controls (URL validation, output sanitization)
- Risk score calculation
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.services.scanning.nuclei_service import (
    NucleiService,
    calculate_risk_score_from_findings
)
from app.utils.secure_executor import ToolExecutionError


class TestNucleiService:
    """Test suite for NucleiService"""

    @pytest.fixture
    def nuclei_service(self):
        """Create NucleiService instance"""
        return NucleiService(tenant_id=1)

    @pytest.fixture
    def sample_nuclei_output(self):
        """Sample Nuclei JSON output"""
        return json.dumps({
            "template-id": "CVE-2021-12345",
            "info": {
                "name": "Test Vulnerability",
                "severity": "critical",
                "description": "A test vulnerability",
                "tags": ["cve", "test"],
                "reference": ["https://example.com"],
                "classification": {
                    "cvss-metrics": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                    "cvss-score": 9.8,
                    "cve-id": ["CVE-2021-12345"]
                }
            },
            "matcher-name": "version-check",
            "type": "http",
            "host": "https://example.com",
            "matched-at": "https://example.com/vulnerable",
            "timestamp": "2024-01-01T12:00:00Z",
            "curl-command": "curl -X GET https://example.com/vulnerable"
        })

    def test_init(self, nuclei_service):
        """Test NucleiService initialization"""
        assert nuclei_service.tenant_id == 1
        assert nuclei_service.url_validator is not None

    def test_validate_urls_valid(self, nuclei_service):
        """Test URL validation with valid URLs"""
        urls = [
            "https://example.com",
            "http://test.example.com:8080",
            "https://192.0.2.1"
        ]

        valid_urls, errors = nuclei_service._validate_urls(urls)

        assert len(valid_urls) == 3
        assert len(errors) == 0

    def test_validate_urls_invalid(self, nuclei_service):
        """Test URL validation with invalid URLs"""
        urls = [
            "https://localhost",  # Blocked
            "http://127.0.0.1",   # Loopback
            "https://169.254.169.254",  # Metadata endpoint
            "ftp://example.com",  # Invalid scheme
            "not-a-url"
        ]

        valid_urls, errors = nuclei_service._validate_urls(urls)

        assert len(valid_urls) == 0
        assert len(errors) == 5

    def test_validate_urls_mixed(self, nuclei_service):
        """Test URL validation with mixed valid/invalid"""
        urls = [
            "https://example.com",  # Valid
            "https://localhost",     # Invalid
            "http://test.com",      # Valid
        ]

        valid_urls, errors = nuclei_service._validate_urls(urls)

        assert len(valid_urls) == 2
        assert len(errors) == 1
        assert "https://example.com" in valid_urls
        assert "http://test.com" in valid_urls

    def test_build_nuclei_args_default(self, nuclei_service):
        """Test building Nuclei arguments with defaults"""
        args = nuclei_service._build_nuclei_args(
            urls_file="/tmp/urls.txt",
            templates=None,
            severity=['critical', 'high'],
            rate_limit=300,
            concurrency=50
        )

        assert '-l' in args
        assert '/tmp/urls.txt' in args
        assert '-json' in args
        assert '-silent' in args
        assert '-severity' in args
        assert 'critical,high' in args
        assert '-rl' in args
        assert '300' in args
        assert '-c' in args
        assert '50' in args

        # Default templates
        assert 'cves/' in args
        assert 'exposed-panels/' in args

    def test_build_nuclei_args_custom_templates(self, nuclei_service):
        """Test building Nuclei arguments with custom templates"""
        args = nuclei_service._build_nuclei_args(
            urls_file="/tmp/urls.txt",
            templates=['custom-template.yaml', 'takeovers/'],
            severity=['critical'],
            rate_limit=100,
            concurrency=25
        )

        assert 'custom-template.yaml' in args
        assert 'takeovers/' in args
        assert '-severity' in args
        assert 'critical' in args

    def test_parse_nuclei_result_valid(self, nuclei_service, sample_nuclei_output):
        """Test parsing valid Nuclei result"""
        result = json.loads(sample_nuclei_output)
        finding = nuclei_service.parse_nuclei_result(result)

        assert finding is not None
        assert finding['template_id'] == 'CVE-2021-12345'
        assert finding['name'] == 'Test Vulnerability'
        assert finding['severity'] == 'critical'
        assert finding['cvss_score'] == 9.8
        assert finding['cve_id'] == 'CVE-2021-12345'
        assert finding['matched_at'] == 'https://example.com/vulnerable'
        assert finding['host'] == 'example.com'
        assert finding['source'] == 'nuclei'

    def test_parse_nuclei_result_missing_fields(self, nuclei_service):
        """Test parsing Nuclei result with missing fields"""
        result = {
            "template-id": "test-template",
            "info": {
                "name": "Test",
                "severity": "high"
            },
            "host": "https://example.com"
        }

        finding = nuclei_service.parse_nuclei_result(result)

        assert finding is not None
        assert finding['template_id'] == 'test-template'
        assert finding['severity'] == 'high'
        assert finding['cvss_score'] is None
        assert finding['cve_id'] is None

    def test_parse_nuclei_result_invalid_severity(self, nuclei_service):
        """Test parsing Nuclei result with invalid severity"""
        result = {
            "template-id": "test",
            "info": {
                "name": "Test",
                "severity": "unknown-severity"  # Invalid
            },
            "host": "https://example.com"
        }

        finding = nuclei_service.parse_nuclei_result(result)

        assert finding is not None
        assert finding['severity'] == 'info'  # Defaults to info

    def test_parse_nuclei_output_multiple(self, nuclei_service, sample_nuclei_output):
        """Test parsing multiple Nuclei results"""
        stdout = sample_nuclei_output + '\n' + sample_nuclei_output

        findings = nuclei_service._parse_nuclei_output(stdout)

        assert len(findings) == 2
        assert all(f['template_id'] == 'CVE-2021-12345' for f in findings)

    def test_parse_nuclei_output_invalid_json(self, nuclei_service):
        """Test parsing Nuclei output with invalid JSON lines"""
        stdout = '''
{"valid": "json"}
invalid json line
{"another": "valid"}
'''

        with patch.object(nuclei_service, 'parse_nuclei_result') as mock_parse:
            mock_parse.side_effect = [
                {'finding': 1},
                None,  # Invalid line returns None
                {'finding': 2}
            ]

            findings = nuclei_service._parse_nuclei_output(stdout)

            # Should skip invalid lines
            assert mock_parse.call_count >= 2

    def test_calculate_stats(self, nuclei_service):
        """Test statistics calculation"""
        urls = ['https://example.com', 'https://test.com']
        findings = [
            {'severity': 'critical'},
            {'severity': 'critical'},
            {'severity': 'high'},
            {'severity': 'medium'},
            {'severity': 'low'},
            {'severity': 'info'}
        ]

        stats = nuclei_service._calculate_stats(urls, findings)

        assert stats['urls_scanned'] == 2
        assert stats['findings_count'] == 6
        assert stats['by_severity']['critical'] == 2
        assert stats['by_severity']['high'] == 1
        assert stats['by_severity']['medium'] == 1
        assert stats['by_severity']['low'] == 1
        assert stats['by_severity']['info'] == 1

    @pytest.mark.asyncio
    async def test_scan_urls_success(self, nuclei_service, sample_nuclei_output):
        """Test successful URL scanning"""
        urls = ['https://example.com']

        with patch('app.services.scanning.nuclei_service.SecureToolExecutor') as mock_executor:
            # Mock executor context manager
            mock_ctx = MagicMock()
            mock_executor.return_value.__enter__.return_value = mock_ctx
            mock_executor.return_value.__exit__.return_value = None

            # Mock file creation
            mock_ctx.create_input_file.return_value = '/tmp/urls.txt'

            # Mock Nuclei execution
            mock_ctx.execute.return_value = (0, sample_nuclei_output, '')

            # Mock storage
            with patch('app.services.scanning.nuclei_service.store_raw_output'):
                result = await nuclei_service.scan_urls(urls)

                assert result['stats']['urls_scanned'] == 1
                assert result['stats']['findings_count'] == 1
                assert len(result['findings']) == 1
                assert result['findings'][0]['template_id'] == 'CVE-2021-12345'

    @pytest.mark.asyncio
    async def test_scan_urls_no_valid_urls(self, nuclei_service):
        """Test scanning with no valid URLs"""
        urls = ['https://localhost', 'http://127.0.0.1']

        result = await nuclei_service.scan_urls(urls)

        assert result['stats']['urls_scanned'] == 0
        assert result['stats']['findings_count'] == 0
        assert len(result['errors']) > 0

    @pytest.mark.asyncio
    async def test_scan_urls_tool_execution_error(self, nuclei_service):
        """Test handling of tool execution errors"""
        urls = ['https://example.com']

        with patch('app.services.scanning.nuclei_service.SecureToolExecutor') as mock_executor:
            mock_ctx = MagicMock()
            mock_executor.return_value.__enter__.return_value = mock_ctx
            mock_executor.return_value.__exit__.return_value = None

            mock_ctx.create_input_file.return_value = '/tmp/urls.txt'
            mock_ctx.execute.side_effect = ToolExecutionError("Tool failed")

            with patch('app.services.scanning.nuclei_service.store_raw_output'):
                result = await nuclei_service.scan_urls(urls)

                assert result['stats']['findings_count'] == 0
                assert len(result['errors']) > 0

    @pytest.mark.asyncio
    async def test_scan_asset(self, nuclei_service, sample_nuclei_output):
        """Test scanning single asset"""
        with patch('app.services.scanning.nuclei_service.SecureToolExecutor') as mock_executor:
            mock_ctx = MagicMock()
            mock_executor.return_value.__enter__.return_value = mock_ctx
            mock_executor.return_value.__exit__.return_value = None

            mock_ctx.create_input_file.return_value = '/tmp/urls.txt'
            mock_ctx.execute.return_value = (0, sample_nuclei_output, '')

            with patch('app.services.scanning.nuclei_service.store_raw_output'):
                findings = await nuclei_service.scan_asset(
                    asset_id=123,
                    asset_url='https://example.com'
                )

                assert len(findings) == 1
                assert findings[0]['asset_id'] == 123


class TestRiskScoreCalculation:
    """Test risk score calculation"""

    def test_calculate_risk_score_empty(self):
        """Test risk score with no findings"""
        score = calculate_risk_score_from_findings([])
        assert score == 0.0

    def test_calculate_risk_score_critical(self):
        """Test risk score with critical findings"""
        findings = [
            {'severity': 'critical'},
            {'severity': 'critical'}
        ]
        score = calculate_risk_score_from_findings(findings)
        assert score == 6.0  # 2 * 3.0

    def test_calculate_risk_score_mixed(self):
        """Test risk score with mixed severity"""
        findings = [
            {'severity': 'critical'},  # 3.0
            {'severity': 'high'},      # 2.0
            {'severity': 'medium'},    # 1.0
            {'severity': 'low'},       # 0.5
            {'severity': 'info'}       # 0.1
        ]
        score = calculate_risk_score_from_findings(findings)
        assert score == 6.6  # 3.0 + 2.0 + 1.0 + 0.5 + 0.1

    def test_calculate_risk_score_capped(self):
        """Test risk score is capped at 10.0"""
        findings = [{'severity': 'critical'}] * 10  # 10 * 3.0 = 30.0
        score = calculate_risk_score_from_findings(findings)
        assert score == 10.0  # Capped

    def test_calculate_risk_score_unknown_severity(self):
        """Test risk score with unknown severity"""
        findings = [
            {'severity': 'critical'},
            {'severity': 'unknown'},  # Unknown, treated as 0.0
            {'severity': 'high'}
        ]
        score = calculate_risk_score_from_findings(findings)
        assert score == 5.0  # 3.0 + 0.0 + 2.0


# Pytest configuration
@pytest.fixture(scope='session')
def event_loop():
    """Create event loop for async tests"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
