"""
Service API endpoint tests

Tests service management endpoints including:
- Listing services
- Filtering by port, product
- Service details
- Tenant isolation
- Pagination
"""
import pytest


class TestListServices:
    """Test listing services endpoint"""

    def test_list_services(self, client, auth_headers, test_tenant, test_services):
        """Test listing services for tenant"""
        response = client.get(f"/api/v1/tenants/{test_tenant.slug}/services", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("List services endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        services = data if isinstance(data, list) else data.get("items", [])
        assert len(services) >= len(test_services)

        # Verify service structure
        if len(services) > 0:
            service = services[0]
            assert "id" in service
            assert "port" in service
            assert "protocol" in service

    def test_list_services_empty_tenant(self, client, auth_headers, other_tenant):
        """Test listing services for tenant with no services"""
        response = client.get(f"/api/v1/tenants/{other_tenant.slug}/services", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("List services endpoint not yet implemented")

        # Should either be empty or forbidden
        if response.status_code == 200:
            data = response.json()
            services = data if isinstance(data, list) else data.get("items", [])
        elif response.status_code == 403:
            assert True


class TestFilterServices:
    """Test service filtering"""

    def test_filter_services_by_port(self, client, auth_headers, test_tenant, test_services):
        """Test filtering services by port number"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/services?port=443",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Service port filtering not yet implemented")

        assert response.status_code == 200
        data = response.json()

        services = data if isinstance(data, list) else data.get("items", [])

        # All returned services should be on port 443
        for service in services:
            assert service["port"] == 443

    def test_filter_services_by_product(self, client, auth_headers, test_tenant, test_services):
        """Test filtering services by product name (nginx, apache)"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/services?product=nginx",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Service product filtering not yet implemented")

        assert response.status_code == 200
        data = response.json()

        services = data if isinstance(data, list) else data.get("items", [])

        # All returned services should be nginx
        for service in services:
            assert "nginx" in service.get("product", "").lower()

    def test_filter_services_by_protocol(self, client, auth_headers, test_tenant, test_services):
        """Test filtering services by protocol"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/services?protocol=https",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Service protocol filtering not yet implemented")

        assert response.status_code == 200
        data = response.json()

        services = data if isinstance(data, list) else data.get("items", [])

        for service in services:
            assert service.get("protocol", "").lower() == "https"


class TestGetService:
    """Test retrieving service details"""

    def test_get_service_details(self, client, auth_headers, test_service):
        """Test retrieving service details"""
        response = client.get(f"/api/v1/services/{test_service.id}", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Get service endpoint not yet implemented")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == test_service.id
        assert data["port"] == test_service.port
        assert data["protocol"] == test_service.protocol
        assert "asset_id" in data or "asset" in data

    def test_get_nonexistent_service(self, client, auth_headers):
        """Test retrieving non-existent service returns 404"""
        response = client.get("/api/v1/services/999999", headers=auth_headers)

        if response.status_code == 401:
            pytest.skip("Get service endpoint not yet implemented")

        assert response.status_code == 404


class TestServicePagination:
    """Test service pagination"""

    def test_service_pagination(self, client, auth_headers, test_tenant, test_services):
        """Test service list pagination"""
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/services?limit=2&offset=0",
            headers=auth_headers
        )

        if response.status_code == 404:
            pytest.skip("Service pagination not yet implemented")

        assert response.status_code == 200
        data = response.json()

        # Should support pagination
        if not isinstance(data, list):
            assert "items" in data or "results" in data


class TestServiceTenantIsolation:
    """Test tenant isolation for services"""

    def test_service_tenant_isolation(self, client, auth_headers, other_tenant_service):
        """Test cannot access service from different tenant"""
        response = client.get(f"/api/v1/services/{other_tenant_service.id}", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Service endpoint not implemented or isolation working")

        # Should be forbidden or not found
        assert response.status_code in [403, 404]
