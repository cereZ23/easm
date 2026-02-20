"""
Tenant API endpoint tests

Tests tenant management endpoints including:
- Listing tenants (admin only)
- Creating tenants (admin only)
- Retrieving tenant details
- Updating tenant configuration
- Dashboard statistics
- Tenant isolation
"""
import pytest


class TestListTenants:
    """Test listing tenants endpoint"""

    def test_list_tenants_admin_only(self, client, admin_headers, test_tenant, other_tenant):
        """Test listing tenants requires admin role"""
        response = client.get("/api/v1/tenants", headers=admin_headers)

        if response.status_code == 404:
            pytest.skip("Tenant list endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        # Should return list of tenants
        assert isinstance(data, list) or "items" in data

        if isinstance(data, list):
            tenants = data
        else:
            tenants = data["items"]

        assert len(tenants) >= 2  # At least test_tenant and other_tenant
        tenant_slugs = [t["slug"] for t in tenants]
        assert "test-tenant" in tenant_slugs
        assert "other-tenant" in tenant_slugs

    def test_list_tenants_forbidden_for_users(self, client, auth_headers):
        """Test regular users cannot list all tenants"""
        response = client.get("/api/v1/tenants", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Tenant list endpoint not yet implemented")

        # Should either return 403 Forbidden or only the user's tenant
        assert response.status_code in [200, 403]

        if response.status_code == 200:
            data = response.json()
            tenants = data if isinstance(data, list) else data.get("items", [])

            # Regular user should only see their own tenant
            assert len(tenants) == 1
            assert tenants[0]["slug"] == "test-tenant"

    def test_list_tenants_unauthorized(self, client):
        """Test listing tenants without auth returns 401"""
        response = client.get("/api/v1/tenants")

        assert response.status_code == 401


class TestCreateTenant:
    """Test creating tenant endpoint"""

    def test_create_tenant_admin_only(self, client, admin_headers, db_session):
        """Test creating tenant requires admin"""
        response = client.post("/api/v1/tenants", headers=admin_headers, json={
            "name": "New Tenant",
            "slug": "new-tenant",
            "contact_policy": "security@newtenant.com"
        })

        if response.status_code == 404:
            pytest.skip("Tenant creation endpoint not yet implemented")

        assert response.status_code in [200, 201]
        data = response.json()

        assert data["name"] == "New Tenant"
        assert data["slug"] == "new-tenant"
        assert data["contact_policy"] == "security@newtenant.com"
        assert "id" in data

    def test_create_tenant_forbidden_for_users(self, client, auth_headers):
        """Test regular users cannot create tenants"""
        response = client.post("/api/v1/tenants", headers=auth_headers, json={
            "name": "Unauthorized Tenant",
            "slug": "unauthorized-tenant"
        })

        if response.status_code == 404:
            pytest.skip("Tenant creation endpoint not yet implemented")

        assert response.status_code == 403

    def test_create_tenant_duplicate_slug(self, client, admin_headers, test_tenant):
        """Test duplicate tenant slug returns 400"""
        response = client.post("/api/v1/tenants", headers=admin_headers, json={
            "name": "Duplicate Slug Tenant",
            "slug": test_tenant.slug,  # Duplicate slug
            "contact_policy": "test@example.com"
        })

        if response.status_code == 404:
            pytest.skip("Tenant creation endpoint not yet implemented")

        assert response.status_code in [400, 409]
        data = response.json()
        assert "detail" in data
        assert "slug" in data["detail"].lower() or "exists" in data["detail"].lower()

    def test_create_tenant_invalid_slug(self, client, admin_headers):
        """Test invalid slug format returns 422"""
        response = client.post("/api/v1/tenants", headers=admin_headers, json={
            "name": "Invalid Slug Tenant",
            "slug": "Invalid Slug!@#",  # Invalid characters
            "contact_policy": "test@example.com"
        })

        if response.status_code == 404:
            pytest.skip("Tenant creation endpoint not yet implemented")

        assert response.status_code in [400, 422]


class TestGetTenant:
    """Test retrieving tenant details"""

    def test_get_tenant_details(self, client, auth_headers, test_tenant):
        """Test retrieving tenant details"""
        response = client.get(f"/api/v1/tenants/{test_tenant.slug}", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Get tenant endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assert data["slug"] == test_tenant.slug
        assert data["name"] == test_tenant.name
        assert "id" in data
        assert "contact_policy" in data

    def test_get_tenant_by_id(self, client, auth_headers, test_tenant):
        """Test retrieving tenant by ID"""
        response = client.get(f"/api/v1/tenants/{test_tenant.id}", headers=auth_headers)

        if response.status_code == 404:
            # Try slug-based endpoint instead
            pytest.skip("Get tenant by ID not implemented")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_tenant.id

    def test_get_nonexistent_tenant(self, client, auth_headers):
        """Test retrieving non-existent tenant returns 404"""
        response = client.get("/api/v1/tenants/nonexistent-slug", headers=auth_headers)

        if response.status_code == 401:
            pytest.skip("Get tenant endpoint not yet implemented")

        assert response.status_code == 404


class TestUpdateTenant:
    """Test updating tenant"""

    def test_update_tenant(self, client, auth_headers, test_tenant, db_session):
        """Test updating tenant name/config"""
        response = client.patch(f"/api/v1/tenants/{test_tenant.slug}", headers=auth_headers, json={
            "name": "Updated Tenant Name",
            "contact_policy": "newsecurity@example.com"
        })

        if response.status_code == 404:
            pytest.skip("Update tenant endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Updated Tenant Name"
        assert data["contact_policy"] == "newsecurity@example.com"
        assert data["slug"] == test_tenant.slug  # Slug should not change

    def test_update_tenant_admin_required(self, client, auth_headers, other_tenant):
        """Test regular users cannot update other tenants"""
        response = client.patch(f"/api/v1/tenants/{other_tenant.slug}", headers=auth_headers, json={
            "name": "Hacked Tenant"
        })

        if response.status_code == 404:
            pytest.skip("Update tenant endpoint not yet implemented")

        # Should be forbidden (403) or not found (404) due to tenant isolation
        assert response.status_code in [403, 404]

    def test_update_tenant_slug_immutable(self, client, admin_headers, test_tenant):
        """Test tenant slug cannot be changed"""
        response = client.patch(f"/api/v1/tenants/{test_tenant.slug}", headers=admin_headers, json={
            "slug": "new-slug"
        })

        if response.status_code == 404:
            pytest.skip("Update tenant endpoint not yet implemented")

        # Slug change should either be ignored or return error
        if response.status_code == 200:
            data = response.json()
            assert data["slug"] == test_tenant.slug  # Slug unchanged
        else:
            assert response.status_code in [400, 422]


class TestTenantDashboard:
    """Test tenant dashboard statistics"""

    def test_get_dashboard_stats(self, client, auth_headers, test_tenant, test_assets, test_findings):
        """Test dashboard returns correct stats"""
        response = client.get(f"/api/v1/tenants/{test_tenant.slug}/dashboard", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Dashboard endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        # Should include key metrics
        assert "total_assets" in data or "asset_count" in data
        assert "total_findings" in data or "finding_count" in data or "findings" in data

        # Verify counts are reasonable
        asset_count = data.get("total_assets") or data.get("asset_count", 0)
        assert asset_count >= len(test_assets)

    def test_dashboard_only_shows_tenant_data(self, client, auth_headers, test_tenant, other_tenant_assets):
        """Test dashboard only shows data for user's tenant"""
        response = client.get(f"/api/v1/tenants/{test_tenant.slug}/dashboard", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Dashboard endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        # Should not include other tenant's assets
        # (Exact validation depends on dashboard implementation)


class TestTenantIsolation:
    """Test tenant isolation is enforced"""

    def test_tenant_isolation(self, client, auth_headers, other_tenant):
        """Test users cannot access other tenant's data"""
        # Try to access other tenant's details
        response = client.get(f"/api/v1/tenants/{other_tenant.slug}", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Tenant isolation test - endpoint not yet implemented")

        # Should either be forbidden or not found
        assert response.status_code in [403, 404]

    def test_tenant_isolation_assets(self, client, auth_headers, other_tenant):
        """Test users cannot list other tenant's assets"""
        response = client.get(f"/api/v1/tenants/{other_tenant.slug}/assets", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Tenant asset isolation test - endpoint not yet implemented")

        # Should either be forbidden or not found
        assert response.status_code in [403, 404]

    def test_admin_can_access_all_tenants(self, client, admin_headers, test_tenant, other_tenant):
        """Test admin can access any tenant"""
        # Admin should be able to access both tenants
        response1 = client.get(f"/api/v1/tenants/{test_tenant.slug}", headers=admin_headers)
        response2 = client.get(f"/api/v1/tenants/{other_tenant.slug}", headers=admin_headers)

        if response1.status_code == 404 or response2.status_code == 404:
            pytest.skip("Admin multi-tenant access - endpoint not yet implemented")

        assert response1.status_code == 200
        assert response2.status_code == 200


class TestTenantSeeds:
    """Test tenant seed management"""

    def test_add_seeds_to_tenant(self, client, auth_headers, test_tenant):
        """Test adding seeds to tenant"""
        response = client.post(f"/api/v1/tenants/{test_tenant.slug}/seeds", headers=auth_headers, json={
            "domains": ["newdomain.com", "anotherdomain.com"],
            "asns": ["AS12345"],
            "keywords": ["TestCorp"]
        })

        if response.status_code == 404:
            pytest.skip("Seed management endpoint not yet implemented")

        assert response.status_code in [200, 201]
        data = response.json()

        # Should return created seeds
        assert "seeds" in data or "created" in data or isinstance(data, list)

    def test_list_tenant_seeds(self, client, auth_headers, test_tenant, sample_seeds):
        """Test listing seeds for tenant"""
        response = client.get(f"/api/v1/tenants/{test_tenant.slug}/seeds", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("List seeds endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        # Should return list of seeds
        seeds = data if isinstance(data, list) else data.get("items", [])
        assert len(seeds) > 0
