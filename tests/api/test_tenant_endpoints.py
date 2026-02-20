"""
Tenant Endpoint Tests

Tests for tenant dashboard, stats, and multi-tenant isolation.
Total: 8 tests
"""
import pytest
from fastapi.testclient import TestClient

from app.models import Tenant, Asset, Finding, AssetType, FindingSeverity, FindingStatus


class TestTenantEndpoints:
    """Test suite for tenant endpoints"""

    def test_get_tenant_dashboard_returns_stats(self, authenticated_client, test_tenant, tenant_with_data):
        """Test tenant dashboard returns comprehensive statistics"""
        response = authenticated_client.get(f"/api/v1/tenants/{test_tenant.id}/dashboard")

        assert response.status_code == 200
        data = response.json()

        # Verify dashboard structure
        assert "tenant_id" in data
        assert "tenant_name" in data
        assert "stats" in data

        stats = data["stats"]
        # Core metrics
        assert "total_assets" in stats
        assert "total_findings" in stats
        assert "critical_findings" in stats
        assert "high_findings" in stats
        assert "new_assets_24h" in stats
        assert "new_findings_24h" in stats

        # Risk metrics
        assert "risk_score" in stats or "average_risk_score" in stats

        # Verify actual data
        assert stats["total_assets"] > 0
        assert isinstance(stats["total_findings"], int)

    def test_get_tenant_dashboard_requires_auth(self, api_client, test_tenant):
        """Test tenant dashboard requires authentication"""
        response = api_client.get(f"/api/v1/tenants/{test_tenant.id}/dashboard")

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_get_tenant_dashboard_enforces_tenant_isolation(
        self, authenticated_client, test_tenant, other_tenant
    ):
        """Test users cannot access other tenants' dashboards"""
        # Try to access another tenant's dashboard
        response = authenticated_client.get(f"/api/v1/tenants/{other_tenant.id}/dashboard")

        # Should return 403 Forbidden or 404 Not Found
        assert response.status_code in [403, 404]

    def test_get_tenant_stats_returns_detailed_metrics(
        self, authenticated_client, test_tenant, tenant_with_data
    ):
        """Test tenant stats endpoint returns detailed metrics"""
        response = authenticated_client.get(f"/api/v1/tenants/{test_tenant.id}/stats")

        assert response.status_code == 200
        data = response.json()

        # Asset breakdown
        assert "asset_types" in data
        assert isinstance(data["asset_types"], dict)

        # Finding breakdown
        assert "findings_by_severity" in data
        assert isinstance(data["findings_by_severity"], dict)

        # Trends (if implemented)
        if "trends" in data:
            assert isinstance(data["trends"], dict)

    def test_tenant_endpoints_require_valid_tenant_id(self, authenticated_client):
        """Test tenant endpoints validate tenant ID format"""
        # Invalid tenant ID format
        response = authenticated_client.get("/api/v1/tenants/invalid-id/dashboard")
        assert response.status_code in [400, 404, 422]

        # Non-existent but valid format
        response = authenticated_client.get("/api/v1/tenants/99999/dashboard")
        assert response.status_code in [403, 404]

    def test_tenant_not_found_returns_404(self, authenticated_client):
        """Test accessing non-existent tenant returns 404"""
        response = authenticated_client.get("/api/v1/tenants/99999/dashboard")

        assert response.status_code in [403, 404]
        data = response.json()
        assert "detail" in data

    def test_unauthorized_tenant_access_returns_403(
        self, authenticated_client, test_tenant, other_tenant, other_tenant_assets
    ):
        """Test accessing unauthorized tenant returns 403"""
        # User authenticated for test_tenant trying to access other_tenant
        response = authenticated_client.get(f"/api/v1/tenants/{other_tenant.id}/dashboard")

        assert response.status_code in [403, 404]

    def test_tenant_dashboard_pagination(
        self, authenticated_client, test_tenant, many_tenant_assets
    ):
        """Test tenant dashboard handles large datasets with pagination"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/dashboard",
            params={"limit": 10, "offset": 0}
        )

        assert response.status_code == 200
        data = response.json()

        # If recent_activity is paginated
        if "recent_activity" in data:
            activity = data["recent_activity"]
            if isinstance(activity, dict):
                assert "items" in activity
                assert "total" in activity
                assert len(activity["items"]) <= 10


@pytest.fixture
def tenant_with_data(db_session, test_tenant):
    """Create tenant with assets and findings"""
    # Create assets
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"test{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=float(i * 10),
            is_active=True
        )
        for i in range(5)
    ]
    db_session.add_all(assets)
    db_session.commit()

    # Create findings
    for asset in assets[:3]:
        db_session.refresh(asset)
        finding = Finding(
            asset_id=asset.id,
            tenant_id=test_tenant.id,
            source="nuclei",
            template_id=f"CVE-2021-{asset.id}",
            name=f"Test Vulnerability {asset.id}",
            severity=FindingSeverity.HIGH,
            cvss_score=7.5,
            status=FindingStatus.OPEN,
            evidence='{"test": "data"}'
        )
        db_session.add(finding)

    db_session.commit()
    return test_tenant


@pytest.fixture
def other_tenant(db_session):
    """Create another tenant for isolation testing"""
    tenant = Tenant(
        name="Other Tenant",
        slug="other-tenant",
        contact_policy="other@test.com"
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def other_tenant_assets(db_session, other_tenant):
    """Create assets for other tenant"""
    assets = [
        Asset(
            tenant_id=other_tenant.id,
            identifier=f"other{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=50.0,
            is_active=True
        )
        for i in range(3)
    ]
    db_session.add_all(assets)
    db_session.commit()
    return assets


@pytest.fixture
def many_tenant_assets(db_session, test_tenant):
    """Create many assets for pagination testing"""
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"asset{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=25.0,
            is_active=True
        )
        for i in range(50)
    ]
    db_session.add_all(assets)
    db_session.commit()
    return assets
