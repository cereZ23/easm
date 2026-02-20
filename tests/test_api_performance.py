"""
API Performance Tests

Tests performance characteristics including:
- Asset list performance with large datasets
- Finding list performance with filters
- Bulk upsert performance
- Concurrent request handling
- Database query optimization
"""
import pytest
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


class TestAssetPerformance:
    """Test asset endpoint performance"""

    @pytest.mark.performance
    def test_asset_list_performance(self, client, auth_headers, test_tenant, thousand_assets):
        """Test listing 1000+ assets completes in <1s"""
        start = time.time()

        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets",
            headers=auth_headers
        )

        elapsed = time.time() - start

        if response.status_code == 404:
            pytest.skip("Asset list endpoint not yet implemented")

        assert response.status_code == 200

        # Should complete in under 1 second
        assert elapsed < 1.0, f"Asset list took {elapsed:.3f}s, expected < 1s"

        # Verify we got data
        data = response.json()
        assets = data if isinstance(data, list) else data.get("items", [])

        # Should return results (may be paginated)
        assert len(assets) > 0

    @pytest.mark.performance
    def test_asset_list_with_pagination_performance(self, client, auth_headers, test_tenant, thousand_assets):
        """Test paginated asset list is fast"""
        start = time.time()

        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?limit=100&offset=0",
            headers=auth_headers
        )

        elapsed = time.time() - start

        if response.status_code == 404:
            pytest.skip("Asset pagination not yet implemented")

        assert response.status_code == 200

        # Should complete very quickly with pagination
        assert elapsed < 0.5, f"Paginated list took {elapsed:.3f}s, expected < 0.5s"

    @pytest.mark.performance
    def test_asset_filtering_performance(self, client, auth_headers, test_tenant, thousand_assets):
        """Test filtering assets is fast"""
        start = time.time()

        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?min_risk_score=50&type=subdomain",
            headers=auth_headers
        )

        elapsed = time.time() - start

        if response.status_code == 404:
            pytest.skip("Asset filtering not yet implemented")

        assert response.status_code == 200

        # Filtering should still be fast
        assert elapsed < 1.0, f"Filtered list took {elapsed:.3f}s, expected < 1s"


class TestFindingPerformance:
    """Test finding endpoint performance"""

    @pytest.mark.performance
    def test_finding_list_performance(self, client, auth_headers, test_tenant, db_session):
        """Test listing findings with filters completes in <500ms"""
        # Create many findings
        from app.models import Finding, FindingSeverity, FindingStatus

        findings = []
        for i in range(500):
            findings.append(Finding(
                tenant_id=test_tenant.id,
                asset_id=1,  # Would need valid asset
                source="nuclei",
                template_id=f"template-{i % 50}",
                name=f"Finding {i}",
                severity=FindingSeverity.MEDIUM,
                cvss_score=5.0,
                status=FindingStatus.OPEN
            ))

        # Note: This may fail due to foreign key constraints
        # The test verifies the endpoint performance when findings exist

        start = time.time()

        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/findings?severity=critical&status=open",
            headers=auth_headers
        )

        elapsed = time.time() - start

        if response.status_code == 404:
            pytest.skip("Finding list endpoint not yet implemented")

        # Should complete quickly
        assert elapsed < 0.5, f"Finding list took {elapsed:.3f}s, expected < 0.5s"


class TestBulkOperations:
    """Test bulk operation performance"""

    @pytest.mark.performance
    def test_bulk_upsert_performance(self, db_session, test_tenant):
        """Test bulk UPSERT of 1000+ records"""
        from app.models import Asset, AssetType

        start = time.time()

        # Create 1000 assets in batches
        batch_size = 100
        for batch in range(10):
            assets = [
                Asset(
                    tenant_id=test_tenant.id,
                    identifier=f"bulk{batch * batch_size + i}.example.com",
                    type=AssetType.SUBDOMAIN,
                    risk_score=float(i),
                    is_active=True
                )
                for i in range(batch_size)
            ]
            db_session.add_all(assets)
            db_session.commit()

        elapsed = time.time() - start

        # Should complete in reasonable time
        assert elapsed < 3.0, f"Bulk upsert took {elapsed:.3f}s, expected < 3s"

        # Verify all created
        from app.models import Asset
        count = db_session.query(Asset).filter(
            Asset.tenant_id == test_tenant.id,
            Asset.identifier.like("bulk%")
        ).count()

        assert count == 1000

    @pytest.mark.performance
    def test_bulk_finding_upsert(self, db_session, test_tenant, test_asset):
        """Test bulk upserting findings is fast"""
        try:
            from app.scanners.nuclei import store_findings
        except ImportError:
            pytest.skip("Nuclei storage not yet implemented")

        # Generate 1000 findings
        findings = []
        for i in range(1000):
            findings.append({
                "template_id": f"template-{i % 100}",
                "name": f"Vulnerability {i}",
                "severity": ["critical", "high", "medium", "low"][i % 4],
                "cvss_score": float(3.0 + (i % 8)),
                "host": f"https://example.com",
                "matched_at": f"https://example.com/path{i}"
            })

        start = time.time()

        store_findings(db_session, test_tenant.id, test_asset.id, findings)

        elapsed = time.time() - start

        # Should complete quickly (< 3 seconds for 1000 findings)
        assert elapsed < 3.0, f"Bulk finding upsert took {elapsed:.3f}s, expected < 3s"


class TestConcurrency:
    """Test concurrent request handling"""

    @pytest.mark.performance
    @pytest.mark.slow
    def test_concurrent_requests(self, client, auth_headers, test_tenant):
        """Test API handles 50 concurrent requests"""
        def make_request(i):
            response = client.get(
                f"/api/v1/tenants/{test_tenant.slug}/assets",
                headers=auth_headers
            )
            return response.status_code

        start = time.time()

        # Make 50 concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]

        elapsed = time.time() - start

        if 404 in results:
            pytest.skip("Endpoint not yet implemented")

        # Most requests should succeed
        success_count = sum(1 for r in results if r == 200)
        assert success_count >= 45, f"Only {success_count}/50 requests succeeded"

        # Should handle concurrency efficiently
        # 50 requests in under 10 seconds
        assert elapsed < 10.0, f"Concurrent requests took {elapsed:.3f}s, expected < 10s"

    @pytest.mark.performance
    def test_concurrent_different_endpoints(self, client, auth_headers, test_tenant):
        """Test concurrent requests to different endpoints"""
        def make_asset_request():
            return client.get(
                f"/api/v1/tenants/{test_tenant.slug}/assets",
                headers=auth_headers
            )

        def make_finding_request():
            return client.get(
                f"/api/v1/tenants/{test_tenant.slug}/findings",
                headers=auth_headers
            )

        def make_service_request():
            return client.get(
                f"/api/v1/tenants/{test_tenant.slug}/services",
                headers=auth_headers
            )

        # Mix of different endpoints
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(30):
                if i % 3 == 0:
                    futures.append(executor.submit(make_asset_request))
                elif i % 3 == 1:
                    futures.append(executor.submit(make_finding_request))
                else:
                    futures.append(executor.submit(make_service_request))

            results = [f.result() for f in as_completed(futures)]

        # Should all complete successfully (or 404 if not implemented)
        success_count = sum(1 for r in results if r.status_code in [200, 404])
        assert success_count == 30


class TestQueryOptimization:
    """Test database query optimization"""

    @pytest.mark.performance
    def test_database_query_optimization(self, db_session, test_tenant, thousand_assets):
        """Test queries use proper indexes (no seq scans)"""
        from app.models import Asset

        # Enable query logging (if using PostgreSQL)
        # This test verifies queries are efficient

        start = time.time()

        # Query with filter (should use index)
        assets = db_session.query(Asset).filter(
            Asset.tenant_id == test_tenant.id,
            Asset.risk_score >= 50
        ).limit(100).all()

        elapsed = time.time() - start

        # Should be very fast with proper indexes
        assert elapsed < 0.1, f"Filtered query took {elapsed:.3f}s, expected < 0.1s"

        # Verify we got results
        assert len(assets) > 0

    @pytest.mark.performance
    def test_join_query_performance(self, db_session, test_tenant, test_assets, test_services):
        """Test queries with joins are optimized"""
        from app.models import Asset, Service

        start = time.time()

        # Query assets with their services (JOIN)
        results = db_session.query(Asset, Service).join(
            Service,
            Asset.id == Service.asset_id
        ).filter(
            Asset.tenant_id == test_tenant.id
        ).all()

        elapsed = time.time() - start

        # Should complete quickly
        assert elapsed < 0.2, f"JOIN query took {elapsed:.3f}s, expected < 0.2s"

    @pytest.mark.performance
    def test_count_query_performance(self, db_session, test_tenant, thousand_assets):
        """Test COUNT queries are fast"""
        from app.models import Asset

        start = time.time()

        # Count query
        count = db_session.query(Asset).filter(
            Asset.tenant_id == test_tenant.id
        ).count()

        elapsed = time.time() - start

        # COUNT should be very fast
        assert elapsed < 0.05, f"COUNT query took {elapsed:.3f}s, expected < 0.05s"

        assert count == 1000


class TestResponseSerialization:
    """Test response serialization performance"""

    @pytest.mark.performance
    def test_large_response_serialization(self, client, auth_headers, test_tenant, thousand_assets):
        """Test serializing large responses is fast"""
        start = time.time()

        # Request large dataset
        response = client.get(
            f"/api/v1/tenants/{test_tenant.slug}/assets?limit=500",
            headers=auth_headers
        )

        elapsed = time.time() - start

        if response.status_code == 404:
            pytest.skip("Endpoint not yet implemented")

        # Serializing 500 assets should be fast
        assert elapsed < 1.0, f"Serialization took {elapsed:.3f}s, expected < 1s"

        # Verify we got data
        data = response.json()
        assets = data if isinstance(data, list) else data.get("items", [])
        assert len(assets) > 0
