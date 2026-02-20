"""
Nuclei Integration Tests

Tests Nuclei vulnerability scanner integration including:
- Running Nuclei scans
- Parsing JSON output
- Storing findings in database
- Template selection and filtering
- Rate limiting and timeout handling
- Deduplication
- Smart template filtering based on technologies
- Error handling
"""
import pytest
import json
import subprocess
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestNucleiExecution:
    """Test Nuclei scan execution"""

    @pytest.mark.integration
    def test_run_nuclei_scan_basic(self, test_tenant, test_assets):
        """Test basic Nuclei scan execution"""
        try:
            from app.scanners.nuclei import NucleiScanner
        except ImportError:
            pytest.skip("Nuclei scanner module not yet implemented")

        scanner = NucleiScanner()

        # Mock execution
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='[{"template":"test","host":"https://example.com","severity":"high"}]',
                stderr=""
            )

            targets = [asset.identifier for asset in test_assets if asset.type.value == "subdomain"]
            result = scanner.run_scan(targets, severity=["critical", "high"])

            assert mock_run.called
            call_args = mock_run.call_args[0][0]

            # Verify nuclei command structure
            assert "nuclei" in call_args
            assert "-json" in call_args or "-jsonl" in call_args

    def test_nuclei_severity_filtering(self):
        """Test Nuclei respects severity filter"""
        try:
            from app.scanners.nuclei import NucleiScanner
        except ImportError:
            pytest.skip("Nuclei scanner module not yet implemented")

        scanner = NucleiScanner()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            scanner.run_scan(["example.com"], severity=["critical", "high"])

            call_args = mock_run.call_args[0][0]

            # Should include severity flags
            assert "-severity" in call_args or "-s" in call_args

    def test_nuclei_template_selection(self):
        """Test correct template paths used"""
        try:
            from app.scanners.nuclei import NucleiScanner
        except ImportError:
            pytest.skip("Nuclei scanner module not yet implemented")

        scanner = NucleiScanner()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            scanner.run_scan(
                ["example.com"],
                templates=["cves/", "exposed-panels/", "misconfiguration/"]
            )

            call_args = mock_run.call_args[0][0]

            # Should include template flags
            assert "-t" in call_args or "-templates" in call_args

    def test_nuclei_rate_limiting(self):
        """Test Nuclei rate limiting flag applied"""
        try:
            from app.scanners.nuclei import NucleiScanner
        except ImportError:
            pytest.skip("Nuclei scanner module not yet implemented")

        scanner = NucleiScanner()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            scanner.run_scan(["example.com"], rate_limit=300)

            call_args = mock_run.call_args[0][0]

            # Should include rate limiting
            assert "-rl" in call_args or "-rate-limit" in call_args

    @pytest.mark.slow
    def test_nuclei_timeout_handling(self):
        """Test Nuclei scan timeout after 30 minutes"""
        try:
            from app.scanners.nuclei import NucleiScanner
        except ImportError:
            pytest.skip("Nuclei scanner module not yet implemented")

        scanner = NucleiScanner()

        with patch('subprocess.run') as mock_run:
            # Simulate timeout
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["nuclei"],
                timeout=1800
            )

            with pytest.raises(subprocess.TimeoutExpired):
                scanner.run_scan(["example.com"], timeout=1)


class TestNucleiParsing:
    """Test Nuclei JSON output parsing"""

    def test_nuclei_json_parsing(self, sample_nuclei_output):
        """Test parsing Nuclei JSON output"""
        try:
            from app.scanners.nuclei import parse_nuclei_output
        except ImportError:
            pytest.skip("Nuclei parser not yet implemented")

        findings = parse_nuclei_output(sample_nuclei_output)

        assert len(findings) == 1
        finding = findings[0]

        assert finding["template_id"] == "CVE-2021-44228"
        assert finding["severity"] == "critical"
        assert finding["name"] == "Apache Log4j RCE"
        assert finding["host"] == "https://api.example.com"
        assert finding["cvss_score"] == 10.0
        assert finding["cve_id"] == "CVE-2021-44228"

    def test_nuclei_parsing_multiple_findings(self):
        """Test parsing multiple Nuclei findings"""
        try:
            from app.scanners.nuclei import parse_nuclei_output
        except ImportError:
            pytest.skip("Nuclei parser not yet implemented")

        multi_output = '''[
            {"template-id":"CVE-2021-44228","info":{"name":"Log4j","severity":"critical"},"host":"https://api.example.com","cvss-score":10.0,"cve-id":"CVE-2021-44228"},
            {"template-id":"exposed-panel","info":{"name":"Login Panel","severity":"medium"},"host":"https://app.example.com","cvss-score":5.3}
        ]'''

        findings = parse_nuclei_output(multi_output)

        assert len(findings) == 2

    def test_nuclei_parsing_empty_output(self):
        """Test parsing empty Nuclei output"""
        try:
            from app.scanners.nuclei import parse_nuclei_output
        except ImportError:
            pytest.skip("Nuclei parser not yet implemented")

        findings = parse_nuclei_output("[]")
        assert findings == []

    def test_nuclei_parsing_invalid_json(self):
        """Test handling invalid JSON gracefully"""
        try:
            from app.scanners.nuclei import parse_nuclei_output
        except ImportError:
            pytest.skip("Nuclei parser not yet implemented")

        # Should not crash, return empty list or raise specific error
        with pytest.raises((json.JSONDecodeError, ValueError)):
            parse_nuclei_output("invalid json {[")


class TestNucleiFindingStorage:
    """Test storing Nuclei findings in database"""

    def test_store_nuclei_findings(self, db_session, test_tenant, test_assets, sample_nuclei_output):
        """Test storing Nuclei findings in database"""
        try:
            from app.scanners.nuclei import parse_nuclei_output, store_findings
        except ImportError:
            pytest.skip("Nuclei storage not yet implemented")

        findings = parse_nuclei_output(sample_nuclei_output)

        # Find matching asset
        asset = next((a for a in test_assets if "api" in a.identifier), test_assets[0])

        stored = store_findings(db_session, test_tenant.id, asset.id, findings)

        assert len(stored) >= 1

        # Verify finding in database
        from app.models import Finding
        db_finding = db_session.query(Finding).filter_by(
            template_id="CVE-2021-44228",
            asset_id=asset.id
        ).first()

        assert db_finding is not None
        assert db_finding.severity.value == "critical"
        assert db_finding.cvss_score == 10.0

    def test_finding_deduplication(self, db_session, test_tenant, test_asset):
        """Test duplicate findings are not created"""
        try:
            from app.scanners.nuclei import store_findings
        except ImportError:
            pytest.skip("Nuclei storage not yet implemented")

        finding_data = [{
            "template_id": "CVE-2023-12345",
            "name": "Test Vuln",
            "severity": "high",
            "cvss_score": 7.5,
            "host": "https://example.com",
            "matched_at": "https://example.com/",
            "cve_id": "CVE-2023-12345"
        }]

        # Store once
        store_findings(db_session, test_tenant.id, test_asset.id, finding_data)

        # Store again
        store_findings(db_session, test_tenant.id, test_asset.id, finding_data)

        # Should only have one finding
        from app.models import Finding
        count = db_session.query(Finding).filter_by(
            template_id="CVE-2023-12345",
            asset_id=test_asset.id
        ).count()

        assert count == 1

    def test_finding_update_last_seen(self, db_session, existing_finding):
        """Test existing findings update last_seen timestamp"""
        try:
            from app.scanners.nuclei import store_findings
        except ImportError:
            pytest.skip("Nuclei storage not yet implemented")

        original_last_seen = existing_finding.last_seen

        # Wait a moment
        import time
        time.sleep(0.1)

        # Re-detect the finding
        finding_data = [{
            "template_id": existing_finding.template_id,
            "name": existing_finding.name,
            "severity": existing_finding.severity.value,
            "cvss_score": existing_finding.cvss_score,
            "host": "https://example.com",
            "matched_at": "https://example.com/"
        }]

        store_findings(db_session, existing_finding.tenant_id, existing_finding.asset_id, finding_data)

        # Refresh from DB
        db_session.refresh(existing_finding)

        # last_seen should be updated
        assert existing_finding.last_seen > original_last_seen


class TestSmartTemplateFiltering:
    """Test smart template selection based on detected technologies"""

    def test_smart_template_filtering(self, test_assets_with_tech):
        """Test templates filtered based on detected technologies"""
        try:
            from app.scanners.nuclei import select_templates_for_asset
        except ImportError:
            pytest.skip("Smart template filtering not yet implemented")

        # WordPress asset should get WordPress templates
        wordpress_asset = next(a for a in test_assets_with_tech if "wordpress" in a.identifier)
        templates = select_templates_for_asset(wordpress_asset)

        assert any("wordpress" in t.lower() for t in templates)

        # Drupal asset should get Drupal templates
        drupal_asset = next(a for a in test_assets_with_tech if "drupal" in a.identifier)
        templates = select_templates_for_asset(drupal_asset)

        assert any("drupal" in t.lower() for t in templates)


class TestNucleiSecurity:
    """Test Nuclei security features"""

    def test_nuclei_private_ip_blocking(self):
        """Test Nuclei scan blocks private IPs"""
        try:
            from app.scanners.nuclei import NucleiScanner, is_private_ip
        except ImportError:
            pytest.skip("Nuclei security not yet implemented")

        # Private IPs should be blocked
        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("127.0.0.1") is True

        # Public IPs should be allowed
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False

    def test_nuclei_scan_blocks_private_targets(self):
        """Test scanning private IPs is prevented"""
        try:
            from app.scanners.nuclei import NucleiScanner
        except ImportError:
            pytest.skip("Nuclei scanner not yet implemented")

        scanner = NucleiScanner()

        # Should raise error or filter out private IPs
        with pytest.raises((ValueError, PermissionError)):
            scanner.run_scan(["192.168.1.1", "10.0.0.1"])


class TestNucleiCooldown:
    """Test scan cooldown mechanism"""

    def test_nuclei_scan_cooldown(self, db_session, test_asset):
        """Test asset not scanned within 24h cooldown"""
        try:
            from app.scanners.nuclei import should_scan_asset
        except ImportError:
            pytest.skip("Nuclei cooldown not yet implemented")

        # Set last_scanned_at to 1 hour ago
        test_asset.last_enriched_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()

        # Should not scan (within cooldown)
        should_scan = should_scan_asset(test_asset, cooldown_hours=24)
        assert should_scan is False

        # Set last_scanned_at to 25 hours ago
        test_asset.last_enriched_at = datetime.utcnow() - timedelta(hours=25)
        db_session.commit()

        # Should scan (outside cooldown)
        should_scan = should_scan_asset(test_asset, cooldown_hours=24)
        assert should_scan is True


class TestNucleiPerformance:
    """Test Nuclei performance features"""

    @pytest.mark.performance
    def test_nuclei_bulk_upsert_performance(self, db_session, large_finding_set, test_asset):
        """Test bulk UPSERT handles 1000+ findings efficiently"""
        try:
            from app.scanners.nuclei import store_findings
        except ImportError:
            pytest.skip("Nuclei bulk storage not yet implemented")

        import time
        start = time.time()

        # Store 1500 findings
        store_findings(db_session, test_asset.tenant_id, test_asset.id, large_finding_set)

        elapsed = time.time() - start

        # Should complete in reasonable time (< 5 seconds)
        assert elapsed < 5.0, f"Bulk upsert took {elapsed:.2f}s, expected < 5s"

        # Verify findings stored
        from app.models import Finding
        count = db_session.query(Finding).filter_by(asset_id=test_asset.id).count()
        assert count >= 1000


class TestNucleiErrorHandling:
    """Test Nuclei error handling"""

    def test_nuclei_error_handling(self):
        """Test graceful handling of Nuclei errors"""
        try:
            from app.scanners.nuclei import NucleiScanner
        except ImportError:
            pytest.skip("Nuclei scanner not yet implemented")

        scanner = NucleiScanner()

        with patch('subprocess.run') as mock_run:
            # Simulate Nuclei error
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: template not found"
            )

            # Should handle error gracefully
            with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
                scanner.run_scan(["example.com"])

    def test_nuclei_command_not_found(self):
        """Test handling when Nuclei is not installed"""
        try:
            from app.scanners.nuclei import NucleiScanner
        except ImportError:
            pytest.skip("Nuclei scanner not yet implemented")

        scanner = NucleiScanner()

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("nuclei: command not found")

            with pytest.raises(FileNotFoundError):
                scanner.run_scan(["example.com"])


class TestNucleiPipelineIntegration:
    """Test Nuclei integrated into enrichment pipeline"""

    @pytest.mark.integration
    def test_nuclei_pipeline_integration(self, db_session, test_tenant, test_assets):
        """Test Nuclei integrated into enrichment pipeline"""
        try:
            from app.pipelines.enrichment import EnrichmentPipeline
        except ImportError:
            pytest.skip("Enrichment pipeline not yet implemented")

        pipeline = EnrichmentPipeline(db_session, test_tenant.id)

        with patch('app.scanners.nuclei.NucleiScanner.run_scan') as mock_scan:
            mock_scan.return_value = []

            # Run pipeline
            pipeline.run(test_assets[:1])

            # Nuclei should have been called
            assert mock_scan.called
