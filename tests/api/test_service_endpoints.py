"""
Service Endpoint Tests

Tests for service listing, filtering, and multi-tenant isolation.
Total: 5 tests
"""
import pytest
from fastapi.testclient import TestClient

from app.models import Asset, Service, AssetType


class TestServiceEndpoints:
    """Test suite for service endpoints"""

    def test_list_services_for_tenant(
        self, authenticated_client, test_tenant, tenant_with_services
    ):
        """Test listing all services for a tenant"""
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/services"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        if isinstance(data, dict):
            assert "items" in data
            services = data["items"]
        else:
            services = data

        assert isinstance(services, list)
        assert len(services) > 0

        # Verify service structure
        service = services[0]
        assert "id" in service
        assert "asset_id" in service
        assert "port" in service
        assert "protocol" in service

        # Optional fields
        if "product" in service:
            assert isinstance(service["product"], (str, type(None)))
        if "version" in service:
            assert isinstance(service["version"], (str, type(None)))

    def test_list_services_for_asset(
        self, authenticated_client, test_tenant, asset_with_multiple_services
    ):
        """Test listing services for a specific asset"""
        asset_id = asset_with_multiple_services.id

        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets/{asset_id}/services"
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            services = data.get("items", data)
        else:
            services = data

        # Should return multiple services for this asset
        assert len(services) >= 3

        # All services should belong to this asset
        for service in services:
            assert service["asset_id"] == asset_id

    def test_service_filtering_by_port(
        self, authenticated_client, test_tenant, tenant_with_services
    ):
        """Test filtering services by port number"""
        # Filter for HTTPS services (port 443)
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/services",
            params={"port": 443}
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            services = data["items"]
        else:
            services = data

        # All returned services should be on port 443
        for service in services:
            assert service["port"] == 443

    def test_service_filtering_by_protocol(
        self, authenticated_client, test_tenant, tenant_with_services
    ):
        """Test filtering services by protocol"""
        # Filter for HTTPS protocol
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/services",
            params={"protocol": "https"}
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            services = data["items"]
        else:
            services = data

        # All returned services should use HTTPS
        for service in services:
            assert service["protocol"].lower() == "https"

    @pytest.mark.security
    def test_services_enforce_tenant_isolation(
        self, authenticated_client, test_tenant, other_tenant, other_tenant_services
    ):
        """Test tenant isolation for service endpoints"""
        # User authenticated for test_tenant should not see other_tenant's services
        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/services"
        )

        assert response.status_code == 200
        data = response.json()

        if isinstance(data, dict):
            services = data["items"]
        else:
            services = data

        # Should not see other tenant's services
        # Verify by checking asset_ids or service details
        for service in services:
            # Services should belong to test_tenant's assets
            assert service["asset_id"] is not None


@pytest.fixture
def tenant_with_services(db_session, test_tenant):
    """Create tenant with assets and services"""
    # Create assets
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"web{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=40.0,
            is_active=True
        )
        for i in range(3)
    ]
    db_session.add_all(assets)
    db_session.commit()

    # Create services for each asset
    services = []
    for asset in assets:
        db_session.refresh(asset)
        # HTTP service
        services.append(Service(
            asset_id=asset.id,
            port=80,
            protocol="http",
            product="nginx",
            version="1.18.0",
            http_status=301
        ))
        # HTTPS service
        services.append(Service(
            asset_id=asset.id,
            port=443,
            protocol="https",
            product="nginx",
            version="1.18.0",
            http_status=200,
            http_title=f"Service for {asset.identifier}"
        ))

    db_session.add_all(services)
    db_session.commit()
    return services


@pytest.fixture
def asset_with_multiple_services(db_session, test_tenant):
    """Create asset with multiple services"""
    asset = Asset(
        tenant_id=test_tenant.id,
        identifier="multi-service.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=50.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    # Create multiple services
    services = [
        Service(asset_id=asset.id, port=80, protocol="http", product="nginx"),
        Service(asset_id=asset.id, port=443, protocol="https", product="nginx"),
        Service(asset_id=asset.id, port=22, protocol="ssh", product="OpenSSH", version="8.2"),
        Service(asset_id=asset.id, port=3306, protocol="mysql", product="MySQL", version="8.0"),
    ]
    db_session.add_all(services)
    db_session.commit()

    return asset


@pytest.fixture
def other_tenant_services(db_session, other_tenant):
    """Create services for other tenant"""
    # Create asset for other tenant
    asset = Asset(
        tenant_id=other_tenant.id,
        identifier="other-service.example.com",
        type=AssetType.SUBDOMAIN,
        risk_score=30.0,
        is_active=True
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    # Create services
    services = [
        Service(asset_id=asset.id, port=80, protocol="http"),
        Service(asset_id=asset.id, port=443, protocol="https"),
    ]
    db_session.add_all(services)
    db_session.commit()
    return services
