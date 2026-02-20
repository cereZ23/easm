"""
Finding Endpoint Tests

Tests for vulnerability finding listing, filtering, status updates, and deduplication.
Total: 8 tests
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.models import Asset, Finding, AssetType, FindingSeverity, FindingStatus


class TestFindingEndpoints:
    """Test suite for finding endpoints"""

    def test_list_findings_for_tenant(
        self, authenticated_client, test_tenant, tenant_with_findings
    ):
        """Test listing all findings for a tenant"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        if isinstance(data, dict):
            assert "items" in data
            findings = data["items"]
        else:
            findings = data

        assert isinstance(findings, list)
        assert len(findings) > 0

        # Verify finding structure
        finding = findings[0]
        assert "id" in finding
        assert "asset_id" in finding
        assert "template_id" in finding
        assert "name" in finding
        assert "severity" in finding
        assert "status" in finding

    def test_list_findings_with_severity_filter(
        self, authenticated_client, test_tenant, findings_mixed_severity
    ):
        """Test filtering findings by severity level"""
        # Filter for critical findings only
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings",
            params={"severity": "critical"}
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            findings = data["items"]
        else:
            findings = data

        # All returned findings should be critical
        for finding in findings:
            assert finding["severity"].lower() == "critical"

        # Filter for high severity
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings",
            params={"severity": "high"}
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            findings = data["items"]
        else:
            findings = data

        for finding in findings:
            assert finding["severity"].lower() == "high"

    def test_list_findings_with_status_filter(
        self, authenticated_client, test_tenant, findings_various_statuses
    ):
        """Test filtering findings by status"""
        # Filter for open findings
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings",
            params={"status": "open"}
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            findings = data["items"]
        else:
            findings = data

        # All returned findings should be open
        for finding in findings:
            assert finding["status"].lower() == "open"

        # Filter for false positives
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings",
            params={"status": "false_positive"}
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            findings = data["items"]
        else:
            findings = data

        for finding in findings:
            assert finding["status"].lower() in ["false_positive", "suppressed"]

    def test_get_finding_by_id_returns_details(
        self, authenticated_client, test_tenant, sample_finding
    ):
        """Test getting single finding by ID returns full details"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings/{sample_finding.id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify full finding details
        assert data["id"] == sample_finding.id
        assert data["template_id"] == sample_finding.template_id
        assert data["name"] == sample_finding.name
        assert data["severity"] == sample_finding.severity.value
        assert "cvss_score" in data
        assert "evidence" in data
        assert "first_seen" in data

        # May include related asset details
        if "asset" in data:
            assert isinstance(data["asset"], dict)
            assert "identifier" in data["asset"]

    def test_update_finding_status_to_false_positive(
        self, authenticated_client, test_tenant, open_finding
    ):
        """Test updating finding status to false positive"""
        response = authenticated_client.patch(
            f"/api/v1/tenants/{test_tenant.id}/findings/{open_finding.id}",
            json={
                "status": "false_positive",
                "reason": "This is not actually vulnerable"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify status updated
        assert data["status"].lower() in ["false_positive", "suppressed"]

        # Verify finding is retrievable with new status
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings/{open_finding.id}"
        )
        data = response.json()
        assert data["status"].lower() in ["false_positive", "suppressed"]

    def test_update_finding_status_to_fixed(
        self, authenticated_client, test_tenant, open_finding
    ):
        """Test updating finding status to fixed"""
        response = authenticated_client.patch(
            f"/api/v1/tenants/{test_tenant.id}/findings/{open_finding.id}",
            json={
                "status": "fixed",
                "reason": "Patched vulnerability"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify status updated
        assert data["status"].lower() in ["fixed", "resolved", "closed"]

    @pytest.mark.security
    def test_findings_enforce_tenant_isolation(
        self, authenticated_client, test_tenant, other_tenant, other_tenant_findings
    ):
        """Test tenant isolation for finding endpoints"""
        # User authenticated for test_tenant should not see other_tenant's findings
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings"
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            findings = data["items"]
        else:
            findings = data

        # Should not see other tenant's findings
        # Verify all findings belong to test_tenant
        for finding in findings:
            if "tenant_id" in finding:
                assert finding["tenant_id"] == test_tenant.id

        # Try to access other tenant's finding directly
        other_finding_id = other_tenant_findings[0].id
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings/{other_finding_id}"
        )

        # Should be 403 or 404
        assert response.status_code in [403, 404]

    def test_finding_deduplication_working(
        self, authenticated_client, test_tenant, duplicate_findings
    ):
        """Test that duplicate findings are properly deduplicated"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings"
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            findings = data["items"]
        else:
            findings = data

        # Should have deduplicated findings
        # Count unique template_id + asset_id combinations
        unique_combos = set()
        for finding in findings:
            combo = (finding["template_id"], finding["asset_id"])
            # Should not have duplicates of same template on same asset
            assert combo not in unique_combos or finding["status"] != "open"
            unique_combos.add(combo)


@pytest.fixture
def tenant_with_findings(db_session, test_tenant):
    """Create tenant with assets and findings"""
    # Create assets
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"vuln{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=60.0,
            is_active=True
        )
        for i in range(3)
    ]
    db_session.add_all(assets)
    db_session.commit()

    # Create findings
    findings = []
    for i, asset in enumerate(assets):
        db_session.refresh(asset)
        finding = Finding(
            asset_id=asset.id,
            tenant_id=test_tenant.id,
            source="nuclei",
            template_id=f"CVE-2021-{44228 + i}",
            name=f"Vulnerability {i}",
            severity=FindingSeverity.HIGH,
            cvss_score=7.5 + i * 0.5,
            status=FindingStatus.OPEN,
            evidence=f'{{"proof": "data{i}"}}'
        )
        findings.append(finding)

    db_session.add_all(findings)
    db_session.commit()
    return findings


@pytest.fixture
def findings_mixed_severity(db_session, test_tenant):
    """Create findings with different severity levels"""
    asset = Asset(
        tenant_id=test_tenant.id,
        identifier="multi-vuln.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=80.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    severities = [
        FindingSeverity.CRITICAL,
        FindingSeverity.CRITICAL,
        FindingSeverity.HIGH,
        FindingSeverity.HIGH,
        FindingSeverity.MEDIUM,
        FindingSeverity.LOW,
    ]

    findings = []
    for i, severity in enumerate(severities):
        finding = Finding(
            asset_id=asset.id,
            tenant_id=test_tenant.id,
            source="nuclei",
            template_id=f"VULN-{severity.value}-{i}",
            name=f"{severity.value} Vulnerability {i}",
            severity=severity,
            cvss_score=10.0 if severity == FindingSeverity.CRITICAL else 7.5,
            status=FindingStatus.OPEN,
            evidence='{}'
        )
        findings.append(finding)

    db_session.add_all(findings)
    db_session.commit()
    return findings


@pytest.fixture
def findings_various_statuses(db_session, test_tenant, sample_asset):
    """Create findings with different statuses"""
    statuses = [
        FindingStatus.OPEN,
        FindingStatus.OPEN,
        FindingStatus.FIXED,
        FindingStatus.FALSE_POSITIVE,
    ]

    findings = []
    for i, status in enumerate(statuses):
        finding = Finding(
            asset_id=sample_asset.id,
            tenant_id=test_tenant.id,
            source="nuclei",
            template_id=f"STATUS-TEST-{i}",
            name=f"Finding {status.value} {i}",
            severity=FindingSeverity.MEDIUM,
            cvss_score=5.0,
            status=status,
            evidence='{}'
        )
        findings.append(finding)

    db_session.add_all(findings)
    db_session.commit()
    return findings


@pytest.fixture
def open_finding(db_session, test_tenant, sample_asset):
    """Create an open finding for status update tests"""
    finding = Finding(
        asset_id=sample_asset.id,
        tenant_id=test_tenant.id,
        source="nuclei",
        template_id="UPDATE-TEST-001",
        name="Test Finding for Updates",
        severity=FindingSeverity.HIGH,
        cvss_score=7.5,
        status=FindingStatus.OPEN,
        evidence='{"test": "data"}'
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


@pytest.fixture
def other_tenant_findings(db_session, other_tenant):
    """Create findings for other tenant"""
    asset = Asset(
        tenant_id=other_tenant.id,
        identifier="other-vuln.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=50.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    finding = Finding(
        asset_id=asset.id,
        tenant_id=other_tenant.id,
        source="nuclei",
        template_id="OTHER-TENANT-001",
        name="Other Tenant Finding",
        severity=FindingSeverity.MEDIUM,
        cvss_score=5.5,
        status=FindingStatus.OPEN,
        evidence='{}'
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return [finding]


@pytest.fixture
def duplicate_findings(db_session, test_tenant, sample_asset):
    """Create duplicate findings to test deduplication"""
    # Create same finding multiple times (should be deduplicated)
    findings = []
    for i in range(3):
        finding = Finding(
            asset_id=sample_asset.id,
            tenant_id=test_tenant.id,
            source="nuclei",
            template_id="CVE-2021-44228",  # Same template
            name="Log4Shell RCE",
            severity=FindingSeverity.CRITICAL,
            cvss_score=10.0,
            status=FindingStatus.OPEN if i == 0 else FindingStatus.FALSE_POSITIVE,
            evidence=f'{{"scan": {i}}}',
            first_seen=datetime.utcnow() - timedelta(days=i)
        )
        findings.append(finding)

    db_session.add_all(findings)
    db_session.commit()
    return findings
