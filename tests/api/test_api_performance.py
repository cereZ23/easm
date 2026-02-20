"""
API Performance Tests

Tests for API endpoint performance and response times.
Total: 5 tests
"""
import pytest
import time
from statistics import mean, median


@pytest.mark.performance
class TestAPIPerformance:
    """Test suite for API performance benchmarks"""

    def test_list_assets_response_time_under_200ms(
        self, authenticated_client, test_tenant, thousand_assets, performance_timer
    ):
        """Test listing assets responds in under 200ms"""
        performance_timer.start()

        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets",
            params={"limit": 50, "offset": 0}
        )

        elapsed = performance_timer.stop()

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 50

        # Should respond in under 200ms
        performance_timer.assert_faster_than(
            0.2,
            "Asset listing with 1000 records"
        )

    def test_dashboard_endpoint_response_time_under_500ms(
        self, authenticated_client, test_tenant, full_tenant_data, performance_timer
    ):
        """Test dashboard endpoint responds in under 500ms"""
        performance_timer.start()

        response = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/dashboard"
        )

        elapsed = performance_timer.stop()

        assert response.status_code == 200
        data = response.json()
        assert "stats" in data

        # Dashboard should respond in under 500ms even with aggregations
        performance_timer.assert_faster_than(
            0.5,
            "Dashboard with full tenant data"
        )

    def test_concurrent_requests_throughput(
        self, authenticated_client, test_tenant, performance_assets
    ):
        """Test API handles concurrent requests with good throughput"""
        import concurrent.futures

        endpoint = f"/api/v1/tenants/{test_tenant.id}/assets"
        num_requests = 50
        start_time = time.time()

        def make_request():
            """Make single API request"""
            response = authenticated_client.get(endpoint, params={"limit": 10})
            return response.status_code == 200

        # Execute concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        elapsed = time.time() - start_time

        # All requests should succeed
        assert all(results)

        # Calculate throughput
        throughput = num_requests / elapsed
        print(f"\nThroughput: {throughput:.2f} requests/second")

        # Should handle at least 20 requests/second
        assert throughput >= 20, f"Throughput too low: {throughput:.2f} req/s"

    def test_database_query_performance(
        self, authenticated_client, test_tenant, large_finding_dataset, performance_timer
    ):
        """Test database queries perform efficiently with large datasets"""
        # Test 1: Filtered query
        performance_timer.start()
        response1 = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/findings",
            params={"severity": "critical", "status": "open"}
        )
        elapsed1 = performance_timer.stop()

        assert response1.status_code == 200
        performance_timer.assert_faster_than(0.3, "Filtered findings query")

        # Test 2: Complex aggregation
        performance_timer.start()
        response2 = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/stats"
        )
        elapsed2 = performance_timer.stop()

        assert response2.status_code == 200
        performance_timer.assert_faster_than(0.5, "Stats aggregation query")

        # Test 3: Search query
        performance_timer.start()
        response3 = authenticated_client.get(
            f"/api/v1/tenants/{test_tenant.id}/assets",
            params={"search": "prod"}
        )
        elapsed3 = performance_timer.stop()

        assert response3.status_code == 200
        performance_timer.assert_faster_than(0.3, "Asset search query")

    def test_pagination_performance_with_10k_records(
        self, authenticated_client, test_tenant, ten_k_assets
    ):
        """Test pagination performance with 10k records"""
        response_times = []

        # Test multiple pages
        for offset in [0, 100, 1000, 5000, 9000]:
            start = time.time()

            response = authenticated_client.get(
                f"/api/v1/tenants/{test_tenant.id}/assets",
                params={"limit": 100, "offset": offset}
            )

            elapsed = time.time() - start
            response_times.append(elapsed)

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) <= 100

        # Calculate statistics
        avg_time = mean(response_times)
        median_time = median(response_times)
        max_time = max(response_times)

        print(f"\nPagination performance:")
        print(f"  Average: {avg_time*1000:.0f}ms")
        print(f"  Median: {median_time*1000:.0f}ms")
        print(f"  Max: {max_time*1000:.0f}ms")

        # All pages should respond in reasonable time
        assert avg_time < 0.3, f"Average pagination time too high: {avg_time:.3f}s"
        assert max_time < 0.5, f"Max pagination time too high: {max_time:.3f}s"

        # Pagination performance should be consistent (last page not much slower)
        time_variance = max_time / min(response_times)
        assert time_variance < 3.0, f"Pagination performance variance too high: {time_variance:.2f}x"


# ==================== Fixtures ====================

@pytest.fixture
def performance_assets(db_session, test_tenant):
    """Create assets for performance testing"""
    from app.models import Asset, AssetType

    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"perf{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=float(i % 100),
            is_active=True,
            priority=['low', 'normal', 'high', 'critical'][i % 4]
        )
        for i in range(100)
    ]
    db_session.add_all(assets)
    db_session.commit()
    return assets


@pytest.fixture
def full_tenant_data(db_session, test_tenant):
    """Create full dataset for dashboard testing"""
    from app.models import Asset, Finding, Service, AssetType, FindingSeverity, FindingStatus

    # Create 200 assets
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"dashboard{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=float(i % 100),
            is_active=True
        )
        for i in range(200)
    ]
    db_session.add_all(assets)
    db_session.commit()

    # Create services
    services = []
    for i, asset in enumerate(assets[:100]):
        db_session.refresh(asset)
        services.append(Service(
            asset_id=asset.id,
            port=443,
            protocol="https"
        ))
    db_session.add_all(services)

    # Create findings with various severities
    findings = []
    for i, asset in enumerate(assets[:50]):
        severity = [FindingSeverity.CRITICAL, FindingSeverity.HIGH,
                   FindingSeverity.MEDIUM, FindingSeverity.LOW][i % 4]
        finding = Finding(
            asset_id=asset.id,
            tenant_id=test_tenant.id,
            source="nuclei",
            template_id=f"DASH-{i}",
            name=f"Finding {i}",
            severity=severity,
            cvss_score=8.0 if severity == FindingSeverity.CRITICAL else 5.0,
            status=FindingStatus.OPEN,
            evidence='{}'
        )
        findings.append(finding)
    db_session.add_all(findings)

    db_session.commit()
    return {"assets": 200, "services": 100, "findings": 50}


@pytest.fixture
def large_finding_dataset(db_session, test_tenant):
    """Create large finding dataset"""
    from app.models import Asset, Finding, AssetType, FindingSeverity, FindingStatus

    # Create assets
    assets = [
        Asset(
            tenant_id=test_tenant.id,
            identifier=f"finding-perf{i}.example.com",
            type=AssetType.SUBDOMAIN,
            risk_score=50.0,
            is_active=True
        )
        for i in range(100)
    ]
    db_session.add_all(assets)
    db_session.commit()

    # Create many findings
    findings = []
    severities = [FindingSeverity.CRITICAL, FindingSeverity.HIGH,
                 FindingSeverity.MEDIUM, FindingSeverity.LOW]
    statuses = [FindingStatus.OPEN, FindingStatus.OPEN,
               FindingStatus.FIXED, FindingStatus.FALSE_POSITIVE]

    for i, asset in enumerate(assets):
        db_session.refresh(asset)
        # 5 findings per asset = 500 total
        for j in range(5):
            finding = Finding(
                asset_id=asset.id,
                tenant_id=test_tenant.id,
                source="nuclei",
                template_id=f"PERF-{i}-{j}",
                name=f"Performance Test Finding {i}-{j}",
                severity=severities[(i + j) % 4],
                cvss_score=7.5,
                status=statuses[(i + j) % 4],
                evidence='{}'
            )
            findings.append(finding)

    db_session.add_all(findings)
    db_session.commit()
    return 500


@pytest.fixture
def ten_k_assets(db_session, test_tenant):
    """Create 10,000 assets for pagination testing"""
    from app.models import Asset, AssetType

    # Create in batches for efficiency
    batch_size = 1000
    for batch in range(10):
        assets = [
            Asset(
                tenant_id=test_tenant.id,
                identifier=f"paginate{batch * batch_size + i}.example.com",
                type=AssetType.SUBDOMAIN,
                risk_score=float((batch * batch_size + i) % 100),
                is_active=True
            )
            for i in range(batch_size)
        ]
        db_session.add_all(assets)
        db_session.commit()

    return 10000
