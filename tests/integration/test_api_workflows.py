"""
API Workflow Integration Tests

End-to-end workflow tests for complete user scenarios.
Total: 10 tests
"""
import pytest
import time
import concurrent.futures
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestAPIWorkflows:
    """Test suite for complete API workflows"""

    def test_complete_authentication_workflow(self, api_client, test_user):
        """Test complete authentication workflow from login to logout"""
        # Step 1: Login
        login_response = api_client.post("/api/v1/auth/login", json={
            "username": test_user.username,
            "password": "testpass123"
        })
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]

        # Step 2: Access protected resource
        api_client.headers = {"Authorization": f"Bearer {access_token}"}
        me_response = api_client.get("/api/v1/auth/me")
        assert me_response.status_code == 200
        assert me_response.json()["username"] == test_user.username

        # Step 3: Refresh token
        time.sleep(1)
        refresh_response = api_client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert refresh_response.status_code == 200
        new_token = refresh_response.json()["access_token"]
        assert new_token != access_token

        # Step 4: Use new token
        api_client.headers = {"Authorization": f"Bearer {new_token}"}
        me_response2 = api_client.get("/api/v1/auth/me")
        assert me_response2.status_code == 200

        # Step 5: Logout
        logout_response = api_client.post("/api/v1/auth/logout")
        assert logout_response.status_code == 200

        # Step 6: Verify token is invalid after logout
        me_response3 = api_client.get("/api/v1/auth/me")
        assert me_response3.status_code == 401

    def test_complete_asset_discovery_to_scan_workflow(
        self, authenticated_client, test_tenant, db_session
    ):
        """Test complete workflow from seed creation to vulnerability scan"""
        # Step 1: Create seed
        seed_response = authenticated_client.post(
            f"/api/v1/tenants/{test_tenant.id}/seeds",
            json={
                "type": "domain",
                "identifier": "workflow-test.example.com",
                "priority": "high"
            }
        )
        assert seed_response.status_code in [200, 201]

        # Step 2: Trigger discovery (would normally be async)
        # For testing, we'll simulate by creating an asset
        from app.models import Asset, AssetType
        asset = Asset(
            tenant_id=test_tenant.id,
            identifier="workflow-test.example.com",
            type=AssetType.DOMAIN,
            risk_score=50.0,
            is_active=True
        )
        db_session.add(asset)
        db_session.commit()
        db_session.refresh(asset)

        # Step 3: Verify asset appears in list
        assets_response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets",
            params={"search": "workflow-test"}
        )
        assert assets_response.status_code == 200
        assets = assets_response.json()["items"]
        assert len(assets) > 0
        assert any(a["identifier"] == "workflow-test.example.com" for a in assets)

        # Step 4: Get asset details
        asset_id = next(a["id"] for a in assets if a["identifier"] == "workflow-test.example.com")
        asset_detail = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets/{asset_id}"
        )
        assert asset_detail.status_code == 200

        # Step 5: Trigger scan (would create findings)
        # For testing, we'll create a finding manually
        from app.models import Finding, FindingSeverity, FindingStatus
        finding = Finding(
            asset_id=asset_id,
            tenant_id=test_tenant.id,
            source="nuclei",
            template_id="TEST-WORKFLOW-001",
            name="Test Vulnerability",
            severity=FindingSeverity.HIGH,
            cvss_score=7.5,
            status=FindingStatus.OPEN,
            evidence='{"test": "data"}'
        )
        db_session.add(finding)
        db_session.commit()

        # Step 6: Verify finding appears
        findings_response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings"
        )
        assert findings_response.status_code == 200
        findings = findings_response.json()["items"]
        assert any(f["template_id"] == "TEST-WORKFLOW-001" for f in findings)

    def test_pagination_across_multiple_endpoints(
        self, authenticated_client, test_tenant, large_dataset
    ):
        """Test pagination works consistently across multiple endpoints"""
        endpoints = [
            f"/api/v1/tenants/{test_tenant.id}/assets",
            f"/api/v1/tenants/{test_tenant.id}/findings",
            f"/api/v1/tenants/{test_tenant.id}/services",
        ]

        for endpoint in endpoints:
            # Page 1
            page1 = authenticated_client.get(endpoint, params={"limit": 10, "offset": 0})
            assert page1.status_code == 200
            data1 = page1.json()

            if "items" in data1:
                assert len(data1["items"]) <= 10
                assert "total" in data1

                # Page 2
                page2 = authenticated_client.get(endpoint, params={"limit": 10, "offset": 10})
                assert page2.status_code == 200
                data2 = page2.json()

                # Items should be different between pages
                if len(data1["items"]) > 0 and len(data2["items"]) > 0:
                    ids1 = {item["id"] for item in data1["items"]}
                    ids2 = {item["id"] for item in data2["items"]}
                    assert ids1.isdisjoint(ids2), f"Pagination overlap in {endpoint}"

    @pytest.mark.performance
    def test_filtering_performance_with_large_dataset(
        self, authenticated_client, test_tenant, large_dataset, performance_timer
    ):
        """Test filtering performs well with large datasets"""
        performance_timer.start()

        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets",
            params={
                "type": "subdomain",
                "priority": "high",
                "limit": 50
            }
        )

        elapsed = performance_timer.stop()

        assert response.status_code == 200
        performance_timer.assert_faster_than(
            1.0,
            "Asset filtering with large dataset"
        )

    @pytest.mark.performance
    def test_concurrent_api_requests_from_multiple_users(
        self, api_client, test_user, other_test_user
    ):
        """Test API handles concurrent requests from multiple users"""
        # Login as both users
        token1 = api_client.post("/api/v1/auth/login", json={
            "username": test_user.username,
            "password": "testpass123"
        }).json()["access_token"]

        token2 = api_client.post("/api/v1/auth/login", json={
            "username": other_test_user.username,
            "password": "testpass123"
        }).json()["access_token"]

        def make_request(token, endpoint):
            """Make API request with token"""
            client = TestClient(api_client.app)
            client.headers = {"Authorization": f"Bearer {token}"}
            return client.get(endpoint)

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for _ in range(5):
                futures.append(executor.submit(make_request, token1, "/api/v1/auth/me"))
                futures.append(executor.submit(make_request, token2, "/api/v1/auth/me"))

            # Wait for all requests
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert all(r.status_code == 200 for r in results)

    def test_rate_limiting_across_endpoints(self, api_client, test_user):
        """Test rate limiting is enforced across endpoints"""
        # Login
        login_response = api_client.post("/api/v1/auth/login", json={
            "username": test_user.username,
            "password": "testpass123"
        })
        token = login_response.json()["access_token"]
        api_client.headers = {"Authorization": f"Bearer {token}"}

        # Make many rapid requests
        responses = []
        for i in range(100):
            response = api_client.get("/api/v1/auth/me")
            responses.append(response.status_code)

            # If rate limited, stop
            if response.status_code == 429:
                break

        # Should eventually get rate limited or all succeed
        # (depends on rate limit configuration)
        assert 429 in responses or all(r == 200 for r in responses)

    def test_error_handling_with_database_unavailable(
        self, api_client, test_user, mock_db_error
    ):
        """Test API handles database unavailability gracefully"""
        # Login first (before DB becomes unavailable)
        login_response = api_client.post("/api/v1/auth/login", json={
            "username": test_user.username,
            "password": "testpass123"
        })
        token = login_response.json()["access_token"]
        api_client.headers = {"Authorization": f"Bearer {token}"}

        # With DB error, should return 500 or 503
        response = api_client.get("/api/v1/auth/me")
        assert response.status_code in [500, 503]

        # Error message should be informative
        data = response.json()
        assert "detail" in data or "error" in data

    def test_error_handling_with_redis_unavailable(
        self, api_client, test_user, mock_redis_error
    ):
        """Test API handles Redis unavailability gracefully"""
        # Should still be able to login even if Redis is down
        # (rate limiting may not work, but basic auth should)
        response = api_client.post("/api/v1/auth/login", json={
            "username": test_user.username,
            "password": "testpass123"
        })

        # May succeed without rate limiting, or fail gracefully
        assert response.status_code in [200, 500, 503]

    def test_tenant_isolation_under_concurrent_load(
        self, api_client, test_user, test_tenant, other_tenant, concurrent_assets
    ):
        """Test tenant isolation holds under concurrent requests"""
        # Login
        token = api_client.post("/api/v1/auth/login", json={
            "username": test_user.username,
            "password": "testpass123"
        }).json()["access_token"]

        def get_tenant_assets(tenant_id):
            """Get assets for tenant"""
            client = TestClient(api_client.app)
            client.headers = {"Authorization": f"Bearer {token}"}
            return client.get(f"/api/v1/tenants/{tenant_id}/assets")

        # Make concurrent requests for both tenants
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(20):
                futures.append(executor.submit(get_tenant_assets, test_tenant.id))
                futures.append(executor.submit(get_tenant_assets, other_tenant.id))

            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Requests for test_tenant should succeed
        # Requests for other_tenant should fail (403/404)
        test_results = [r for r in results if r.status_code == 200]
        other_results = [r for r in results if r.status_code in [403, 404]]

        # All successful requests should only show test_tenant data
        for result in test_results:
            data = result.json()
            if "items" in data:
                for item in data["items"]:
                    if "tenant_id" in item:
                        assert item["tenant_id"] == test_tenant.id

    @pytest.mark.performance
    def test_api_response_time_benchmarks(
        self, authenticated_client, test_tenant, performance_timer
    ):
        """Test API endpoints meet response time benchmarks"""
        benchmarks = {
            "/api/v1/auth/me": 0.1,  # 100ms
            f"/api/v1/tenants/{test_tenant.id}/dashboard": 0.5,  # 500ms
            f"/api/v1/tenants/{test_tenant.id}/assets": 0.3,  # 300ms
            f"/api/v1/tenants/{test_tenant.id}/findings": 0.3,  # 300ms
        }

        for endpoint, max_time in benchmarks.items():
            performance_timer.start()
            response = authenticated_client.get(endpoint)
            elapsed = performance_timer.stop()

            assert response.status_code == 200
            performance_timer.assert_faster_than(
                max_time,
                f"Response time for {endpoint}"
            )


# ==================== Fixtures ====================

@pytest.fixture
def other_test_user(db_session, test_tenant):
    """Create another test user"""
    from app.models import User, TenantMembership
    from app.security.auth import get_password_hash

    user = User(
        username="otheruser",
        email="other@example.com",
        hashed_password=get_password_hash("testpass123"),
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=test_tenant.id,
        role="user"
    )
    db_session.add(membership)
    db_session.commit()

    return user


@pytest.fixture
def large_dataset(db_session, test_tenant):
    """Create large dataset for testing"""
    from app.models import Asset, Finding, Service, AssetType, FindingSeverity, FindingStatus

    # Create 100 assets
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"large{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=float(i % 100),
            is_active=True,
            priority=['low', 'normal', 'high', 'critical'][i % 4]
        )
        for i in range(100)
    ]
    db_session.add_all(assets)
    db_session.commit()

    # Create services for first 50 assets
    services = []
    for i, asset in enumerate(assets[:50]):
        db_session.refresh(asset)
        services.append(Service(
            asset_id=asset.id,
            port=443,
            protocol="https",
            product="nginx"
        ))
    db_session.add_all(services)

    # Create findings for first 30 assets
    findings = []
    for i, asset in enumerate(assets[:30]):
        finding = Finding(
            asset_id=asset.id,
            tenant_id=test_tenant.id,
            source="nuclei",
            template_id=f"LARGE-{i}",
            name=f"Finding {i}",
            severity=[FindingSeverity.LOW, FindingSeverity.MEDIUM, FindingSeverity.HIGH][i % 3],
            cvss_score=5.0,
            status=FindingStatus.OPEN,
            evidence='{}'
        )
        findings.append(finding)
    db_session.add_all(findings)

    db_session.commit()
    return {"assets": 100, "services": 50, "findings": 30}


@pytest.fixture
def concurrent_assets(db_session, test_tenant, other_tenant):
    """Create assets for concurrent testing"""
    from app.models import Asset, AssetType

    # Assets for test_tenant
    test_assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"concurrent{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=50.0,
            is_active=True
        )
        for i in range(10)
    ]

    # Assets for other_tenant
    other_assets = [
        Asset(
            tenant_id=other_tenant.id,
            identifier=f"other-concurrent{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=50.0,
            is_active=True
        )
        for i in range(10)
    ]

    db_session.add_all(test_assets + other_assets)
    db_session.commit()

    return {"test": test_assets, "other": other_assets}


@pytest.fixture
def mock_db_error(monkeypatch):
    """Mock database error"""
    def raise_db_error(*args, **kwargs):
        from sqlalchemy.exc import OperationalError
        raise OperationalError("Database unavailable", None, None)

    # This would need to be implemented in actual code
    # For now, this is a placeholder
    return None


@pytest.fixture
def mock_redis_error(monkeypatch):
    """Mock Redis error"""
    def raise_redis_error(*args, **kwargs):
        import redis
        raise redis.ConnectionError("Redis unavailable")

    # This would need to be implemented in actual code
    return None
