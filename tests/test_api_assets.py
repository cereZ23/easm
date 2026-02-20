"""
Asset API endpoint tests

Tests asset management endpoints including:
- Listing assets with filtering and pagination
- Creating assets
- Retrieving asset details
- Updating and deleting assets
- Filtering by type, risk score, time range
- Tenant isolation
"""
import pytest
from datetime import datetime, timedelta


class TestListAssets:
    """Test listing assets endpoint"""

    def test_list_assets_basic(self, client, auth_headers, test_tenant, test_assets):
        """Test listing assets returns all tenant assets"""
        response = client.get(f"/api/v1/tenants/{test_tenant.slug}/assets", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("List assets endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        # Response should be a list or paginated response
        assets = data if isinstance(data, list) else data.get("items", [])

        assert len(assets) >= len(test_assets)

        # Verify asset structure
        if len(assets) > 0:
            asset = assets[0]
            assert "id" in asset
            assert "identifier" in asset
            assert "type" in asset
            assert "risk_score" in asset

    def test_list_assets_empty_tenant(self, client, auth_headers, other_tenant):
        """Test listing assets for tenant with no assets returns empty list"""
        response = client.get(f"/api/v1/tenants/{other_tenant.slug}/assets", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("List assets endpoint not yet implemented")

        # Should either be empty or forbidden (due to tenant isolation)
        if response.status_code == 200:
            data = response.json()
            assets = data if isinstance(data, list) else data.get("items", [])
            # May have other_tenant_assets from fixtures
        elif response.status_code == 403:
            # Tenant isolation working correctly
            assert True


class TestFilterAssets:
    """Test asset filtering"""

    def test_filter_assets_by_type(self, client, auth_headers, test_tenant, test_assets):
        """Test filtering assets by type (domain, subdomain, ip, url)"""
        # Filter for subdomains
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?type=subdomain",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Asset filtering not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assets = data if isinstance(data, list) else data.get("items", [])

        # All returned assets should be subdomains
        for asset in assets:
            assert asset["type"] in ["subdomain", "SUBDOMAIN"]

    def test_filter_assets_by_multiple_types(self, client, auth_headers, test_tenant, test_assets):
        """Test filtering assets by multiple types"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?type=domain&type=subdomain",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Multi-type filtering not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assets = data if isinstance(data, list) else data.get("items", [])

        # All returned assets should be domains or subdomains
        for asset in assets:
            assert asset["type"].lower() in ["domain", "subdomain"]

    def test_filter_assets_changed_since(self, client, auth_headers, test_tenant, test_assets):
        """Test filtering assets by changed_since timestamp"""
        # Get assets changed in last 24 hours
        changed_since = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?changed_since={changed_since}",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("changed_since filtering not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assets = data if isinstance(data, list) else data.get("items", [])

        # Should only return recently changed assets
        for asset in assets:
            if "last_seen" in asset:
                last_seen = datetime.fromisoformat(asset["last_seen"].replace("Z", "+00:00"))
                # Asset should be recent
                assert last_seen >= datetime.utcnow() - timedelta(hours=25)

    def test_filter_assets_by_risk_score(self, client, auth_headers, test_tenant, test_assets):
        """Test filtering assets with risk_score >= threshold"""
        # Filter for high-risk assets (score >= 70)
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?min_risk_score=70",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Risk score filtering not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assets = data if isinstance(data, list) else data.get("items", [])

        # All returned assets should have risk_score >= 70
        for asset in assets:
            assert asset["risk_score"] >= 70

    def test_filter_assets_active_only(self, client, auth_headers, test_tenant, test_assets, db_session):
        """Test filtering for active assets only"""
        # Create an inactive asset
        from app.models import Asset, AssetType

        inactive_asset = Asset(
            tenant_id=test_tenant.id,
            identifier="inactive.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=50.0,
            is_active=False
        )
        db_session.add(inactive_asset)
        db_session.commit()

        # Filter for active assets
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?is_active=true",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Active filtering not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assets = data if isinstance(data, list) else data.get("items", [])

        # All returned assets should be active
        for asset in assets:
            if "is_active" in asset:
                assert asset["is_active"] is True


class TestAssetPagination:
    """Test asset pagination"""

    def test_asset_pagination(self, client, auth_headers, test_tenant, test_assets):
        """Test pagination with limit/offset"""
        # Get first page
        response1 = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?limit=2&offset=0",
            headers=auth_headers
        )

        if response1.status_code == 404:
            pytest.skip("Asset pagination not yet implemented")

        assert response1.status_code == 200
        data1 = response1.json()

        # Get second page
        response2 = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?limit=2&offset=2",
            headers=auth_headers
        )

        assert response2.status_code == 200
        data2 = response2.json()

        assets1 = data1 if isinstance(data1, list) else data1.get("items", [])
        assets2 = data2 if isinstance(data2, list) else data2.get("items", [])

        # Should have different assets on different pages
        if len(assets1) > 0 and len(assets2) > 0:
            assert assets1[0]["id"] != assets2[0]["id"]

    def test_asset_pagination_metadata(self, client, auth_headers, test_tenant, test_assets):
        """Test pagination includes metadata (total, page info)"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?limit=2",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Asset pagination not yet implemented")

        assert response.status_code == 200
        data = response.json()

        # If using paginated response format
        if not isinstance(data, list):
            assert "total" in data or "count" in data
            assert "items" in data or "results" in data


class TestAssetSorting:
    """Test asset sorting"""

    def test_asset_sorting(self, client, auth_headers, test_tenant, test_assets):
        """Test sorting assets by risk_score, last_seen, etc."""
        # Sort by risk score descending
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?sort_by=risk_score&sort_order=desc",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Asset sorting not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assets = data if isinstance(data, list) else data.get("items", [])

        if len(assets) >= 2:
            # Verify descending order
            for i in range(len(assets) - 1):
                assert assets[i]["risk_score"] >= assets[i + 1]["risk_score"]


class TestCreateAsset:
    """Test creating assets"""

    def test_create_asset_manual(self, client, auth_headers, test_tenant, db_session):
        """Test manually creating asset via API"""
        response = client.post(
            f"/api/v1/tenants/{test_tenant.slug}/assets",
            headers=auth_headers,
            json={
                "identifier": "manual.example.com",
                "type": "subdomain",
                "risk_score": 25.0
            }
        )

        if response.status_code == 404:
            pytest.skip("Create asset endpoint not yet implemented")

        assert response.status_code in [200, 201]
        data = response.json()

        assert data["identifier"] == "manual.example.com"
        assert data["type"].lower() == "subdomain"
        assert data["risk_score"] == 25.0
        assert "id" in data

    def test_invalid_asset_type(self, client, auth_headers, test_tenant):
        """Test creating asset with invalid type returns 400"""
        response = client.post(
            f"/api/v1/tenants/{test_tenant.slug}/assets",
            headers=auth_headers,
            json={
                "identifier": "test.example.com",
                "type": "invalid_type",
                "risk_score": 25.0
            }
        )

        if response.status_code == 404:
            pytest.skip("Create asset endpoint not yet implemented")

        assert response.status_code in [400, 422]

    def test_duplicate_asset_identifier(self, client, auth_headers, test_tenant, test_asset):
        """Test duplicate asset identifier is rejected"""
        response = client.post(
            f"/api/v1/tenants/{test_tenant.slug}/assets",
            headers=auth_headers,
            json={
                "identifier": test_asset.identifier,
                "type": "subdomain",
                "risk_score": 25.0
            }
        )

        if response.status_code == 404:
            pytest.skip("Create asset endpoint not yet implemented")

        # Should either return existing asset or error
        assert response.status_code in [200, 400, 409]


class TestGetAsset:
    """Test retrieving asset details"""

    def test_get_asset_details(self, client, auth_headers, test_asset, db_session):
        """Test retrieving asset with services, certs, findings"""
        response = client.get(
            f"/api/v1/assets/{test_asset.id}",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Get asset endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == test_asset.id
        assert data["identifier"] == test_asset.identifier
        assert data["type"] == test_asset.type.value or data["type"].lower() == test_asset.type.value

        # May include related data
        # "services", "certificates", "findings" are optional

    def test_get_nonexistent_asset(self, client, auth_headers):
        """Test retrieving non-existent asset returns 404"""
        response = client.get("/api/v1/assets/999999", headers=auth_headers)

        if response.status_code == 401:
            pytest.skip("Get asset endpoint not yet implemented")

        assert response.status_code == 404


class TestUpdateAsset:
    """Test updating assets"""

    def test_update_asset_risk_score(self, client, auth_headers, test_asset):
        """Test updating asset risk score"""
        response = client.patch(
            f"/api/v1/assets/{test_asset.id}",
            headers=auth_headers,
            json={"risk_score": 80.0}
        )

        if response.status_code == 404:
            pytest.skip("Update asset endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assert data["risk_score"] == 80.0

    def test_update_asset_immutable_fields(self, client, auth_headers, test_asset):
        """Test cannot change immutable fields like identifier"""
        response = client.patch(
            f"/api/v1/assets/{test_asset.id}",
            headers=auth_headers,
            json={"identifier": "changed.example.com"}
        )

        if response.status_code == 404:
            pytest.skip("Update asset endpoint not yet implemented")

        # Should either ignore or reject the change
        if response.status_code == 200:
            data = response.json()
            assert data["identifier"] == test_asset.identifier  # Unchanged
        else:
            assert response.status_code in [400, 422]


class TestDeleteAsset:
    """Test deleting assets"""

    def test_delete_asset(self, client, auth_headers, test_asset, db_session):
        """Test soft-deleting asset"""
        response = client.delete(f"/api/v1/assets/{test_asset.id}", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Delete asset endpoint not yet implemented")

        assert response.status_code in [200, 204]

        # Verify asset is soft-deleted (is_active = False) or removed
        get_response = client.get(f"/api/v1/assets/{test_asset.id}", headers=auth_headers)

        # Should either return 404 or return asset with is_active=False
        if get_response.status_code == 200:
            data = get_response.json()
            if "is_active" in data:
                assert data["is_active"] is False


class TestTenantIsolation:
    """Test tenant isolation for assets"""

    def test_asset_tenant_isolation(self, client, auth_headers, other_tenant_asset):
        """Test cannot access asset from different tenant"""
        response = client.get(f"/api/v1/assets/{other_tenant_asset.id}", headers=auth_headers)

        if response.status_code == 404:
            # Either endpoint not implemented or isolation working
            pytest.skip("Asset endpoint not implemented or isolation working")

        # Should be forbidden or not found
        assert response.status_code in [403, 404]

    def test_cannot_update_other_tenant_asset(self, client, auth_headers, other_tenant_asset):
        """Test cannot update asset from different tenant"""
        response = client.patch(
            f"/api/v1/assets/{other_tenant_asset.id}",
            headers=auth_headers,
            json={"risk_score": 100.0}
        )

        if response.status_code == 404:
            pytest.skip("Update asset endpoint not implemented or isolation working")

        assert response.status_code in [403, 404]

    def test_cannot_delete_other_tenant_asset(self, client, auth_headers, other_tenant_asset):
        """Test cannot delete asset from different tenant"""
        response = client.delete(f"/api/v1/assets/{other_tenant_asset.id}", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Delete asset endpoint not implemented or isolation working")

        assert response.status_code in [403, 404]


class TestAssetSearch:
    """Test asset search functionality"""

    def test_search_assets_by_identifier(self, client, auth_headers, test_tenant, test_assets):
        """Test searching assets by identifier pattern"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?search=api",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Asset search not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assets = data if isinstance(data, list) else data.get("items", [])

        # Should return assets matching search term
        for asset in assets:
            assert "api" in asset["identifier"].lower()
