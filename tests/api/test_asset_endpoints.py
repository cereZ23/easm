"""
Asset Endpoint Tests

Tests for asset listing, filtering, search, creation, and tree hierarchy.
Total: 12 tests
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.models import Asset, AssetType


class TestAssetEndpoints:
    """Test suite for asset endpoints"""

    def test_list_assets_returns_paginated_results(
        self, authenticated_client, test_tenant, many_assets
    ):
        """Test listing assets returns paginated results"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets",
            params={"limit": 10, "offset": 0}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify pagination structure
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

        # Verify data
        assert len(data["items"]) <= 10
        assert data["total"] >= 10
        assert isinstance(data["items"], list)

        # Verify asset structure
        if len(data["items"]) > 0:
            asset = data["items"][0]
            assert "id" in asset
            assert "identifier" in asset
            assert "type" in asset
            assert "risk_score" in asset

    def test_list_assets_with_type_filter(
        self, authenticated_client, test_tenant, mixed_type_assets
    ):
        """Test filtering assets by type"""
        # Filter for subdomains only
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets",
            params={"type": "subdomain"}
        )

        assert response.status_code == 200
        data = response.json()

        # All returned assets should be subdomains
        for asset in data["items"]:
            assert asset["type"] == "subdomain"

        # Filter for IPs
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets",
            params={"type": "ip"}
        )

        assert response.status_code == 200
        data = response.json()

        for asset in data["items"]:
            assert asset["type"] == "ip"

    def test_list_assets_with_priority_filter(
        self, authenticated_client, test_tenant, priority_assets
    ):
        """Test filtering assets by priority level"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets",
            params={"priority": "critical"}
        )

        assert response.status_code == 200
        data = response.json()

        # All returned assets should be critical priority
        for asset in data["items"]:
            assert asset.get("priority") == "critical" or asset.get("risk_score", 0) >= 75

    def test_list_assets_with_search_query(
        self, authenticated_client, test_tenant, searchable_assets
    ):
        """Test searching assets by identifier"""
        search_term = "production"

        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets",
            params={"search": search_term}
        )

        assert response.status_code == 200
        data = response.json()

        # All returned assets should contain search term
        for asset in data["items"]:
            assert search_term.lower() in asset["identifier"].lower()

    def test_list_assets_enforces_tenant_isolation(
        self, authenticated_client, test_tenant, other_tenant, other_tenant_assets
    ):
        """Test tenant isolation - users only see their tenant's assets"""
        response = authenticated_client.get(f"/api/v1/tenants/{test_tenant.id}/assets")

        assert response.status_code == 200
        data = response.json()

        # Should only see test_tenant assets, not other_tenant assets
        for asset in data["items"]:
            # If tenant_id is exposed, verify it
            if "tenant_id" in asset:
                assert asset["tenant_id"] == test_tenant.id

            # Should not see other tenant's identifiers
            assert not asset["identifier"].startswith("other")

    def test_get_asset_by_id_returns_details(
        self, authenticated_client, test_tenant, sample_asset
    ):
        """Test getting single asset by ID returns full details"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets/{sample_asset.id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify full asset details
        assert data["id"] == sample_asset.id
        assert data["identifier"] == sample_asset.identifier
        assert data["type"] == sample_asset.type.value
        assert "risk_score" in data
        assert "first_seen" in data
        assert "last_seen" in data

        # May include related data
        if "services" in data:
            assert isinstance(data["services"], list)
        if "findings" in data:
            assert isinstance(data["findings"], list)

    def test_get_asset_not_found_returns_404(self, authenticated_client, test_tenant):
        """Test getting non-existent asset returns 404"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets/99999"
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_get_asset_tree_returns_hierarchy(
        self, authenticated_client, test_tenant, hierarchical_assets
    ):
        """Test asset tree endpoint returns hierarchical structure"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets/tree"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify hierarchical structure
        assert isinstance(data, list) or isinstance(data, dict)

        # Should have root domains
        if isinstance(data, list):
            assert len(data) > 0
            # Each item should have children or subdomains
            for item in data:
                assert "identifier" in item
                if "children" in item:
                    assert isinstance(item["children"], list)

    def test_create_asset_seed_success(self, authenticated_client, test_tenant):
        """Test creating a new asset seed successfully"""
        seed_data = {
            "type": "domain",
            "identifier": "newseed.example.com",
            "priority": "high"
        }

        response = authenticated_client.post(
            f"/api/v1/tenants/{test_tenant.id}/seeds",
            json=seed_data
        )

        assert response.status_code in [200, 201]
        data = response.json()

        assert data["identifier"] == seed_data["identifier"]
        assert data["type"] == seed_data["type"]
        if "priority" in data:
            assert data["priority"] == seed_data["priority"]

    def test_create_asset_seed_invalid_domain_rejected(
        self, authenticated_client, test_tenant
    ):
        """Test creating asset seed with invalid domain is rejected"""
        invalid_seeds = [
            {"type": "domain", "identifier": "not a valid domain!"},
            {"type": "domain", "identifier": ""},
            {"type": "domain", "identifier": "../../../etc/passwd"},
            {"type": "ip", "identifier": "999.999.999.999"},
        ]

        for seed_data in invalid_seeds:
            response = authenticated_client.post(
                f"/api/v1/tenants/{test_tenant.id}/seeds",
                json=seed_data
            )

            assert response.status_code in [400, 422]

    @pytest.mark.security
    def test_create_asset_seed_internal_ip_blocked(
        self, authenticated_client, test_tenant
    ):
        """Test creating asset seed with internal/private IP is blocked"""
        internal_ips = [
            {"type": "ip", "identifier": "127.0.0.1"},
            {"type": "ip", "identifier": "192.168.1.1"},
            {"type": "ip", "identifier": "10.0.0.1"},
            {"type": "ip", "identifier": "172.16.0.1"},
            {"type": "domain", "identifier": "localhost"},
        ]

        for seed_data in internal_ips:
            response = authenticated_client.post(
                f"/api/v1/tenants/{test_tenant.id}/seeds",
                json=seed_data
            )

            # Should reject internal IPs for security
            assert response.status_code in [400, 422]

    @pytest.mark.performance
    def test_list_assets_performance_with_1000_assets(
        self, authenticated_client, test_tenant, thousand_assets, performance_timer
    ):
        """Test listing assets performs well with large dataset"""
        performance_timer.start()

        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets",
            params={"limit": 100, "offset": 0}
        )

        elapsed = performance_timer.stop()

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 100

        # Should respond in under 500ms
        performance_timer.assert_faster_than(
            0.5,
            f"Asset listing with 1000 records"
        )


@pytest.fixture
def many_assets(db_session, test_tenant):
    """Create many assets for pagination testing"""
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"sub{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=float(i % 100),
            is_active=True
        )
        for i in range(25)
    ]
    db_session.add_all(assets)
    db_session.commit()
    return assets


@pytest.fixture
def mixed_type_assets(db_session, test_tenant):
    """Create assets of different types"""
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"sub{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=30.0,
            is_active=True
        )
        for i in range(5)
    ] + [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"1.2.3.{i}",
            type=AssetType.IP,
            risk_score=40.0,
            is_active=True
        )
        for i in range(5)
    ] + [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"https://sub{i}.example.com/path",
            type=AssetType.URL,
            risk_score=20.0,
            is_active=True
        )
        for i in range(3)
    ]
    db_session.add_all(assets)
    db_session.commit()
    return assets


@pytest.fixture
def priority_assets(db_session, test_tenant):
    """Create assets with different priority levels"""
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"critical{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=85.0,
            is_active=True,
            priority='critical'
        )
        for i in range(3)
    ] + [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"normal{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=30.0,
            is_active=True,
            priority='normal'
        )
        for i in range(5)
    ]
    db_session.add_all(assets)
    db_session.commit()
    return assets


@pytest.fixture
def searchable_assets(db_session, test_tenant):
    """Create assets with searchable identifiers"""
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier="production-api.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=50.0,
            is_active=True
        ),
        Asset(
            tenant_id=test_tenant.id,
            identifier="production-web.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=45.0,
            is_active=True
        ),
        Asset(
            tenant_id=test_tenant.id,
            identifier="staging-api.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=20.0,
            is_active=True
        ),
    ]
    db_session.add_all(assets)
    db_session.commit()
    return assets


@pytest.fixture
def hierarchical_assets(db_session, test_tenant):
    """Create assets with parent-child relationships"""
    # Root domain
    root = Asset(
        tenant_id=test_tenant.id,
        identifier="example.com",
        type=AssetType.DOMAIN,
        risk_score=60.0,
        is_active=True
    )
    db_session.add(root)
    db_session.commit()
    db_session.refresh(root)

    # Subdomains
    subdomains = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"sub{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=40.0,
            is_active=True,
            parent_id=root.id
        )
        for i in range(5)
    ]
    db_session.add_all(subdomains)
    db_session.commit()
    return [root] + subdomains


@pytest.fixture
def thousand_assets(db_session, test_tenant):
    """Create 1000 assets for performance testing"""
    # Create in batches for efficiency
    batch_size = 100
    for batch in range(10):
        assets = [
            Asset(
                tenant_id=test_tenant.id,
                identifier=f"perf{batch * batch_size + i}.example.com",
                type=AssetType.SUBDOMAIN,
                risk_score=float((batch * batch_size + i) % 100),
                is_active=True
            )
            for i in range(batch_size)
        ]
        db_session.add_all(assets)
        db_session.commit()

    return 1000  # Return count
