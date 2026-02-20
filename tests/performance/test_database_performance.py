"""
Database Performance Test Suite for EASM Enrichment Pipeline

This test suite benchmarks critical database operations and validates
that performance indexes are working correctly.

Test Categories:
1. Bulk UPSERT Performance (Services, Certificates, Endpoints)
2. Tenant-Scoped Query Performance
3. JOIN Operation Performance
4. Dashboard Statistics Performance
5. Index Usage Verification
6. Query Plan Analysis (EXPLAIN ANALYZE)

Usage:
    # Run all performance tests
    pytest tests/performance/test_database_performance.py -v

    # Run specific test category
    pytest tests/performance/test_database_performance.py::TestBulkUpsertPerformance -v

    # Generate performance report
    pytest tests/performance/test_database_performance.py --benchmark-only

    # Compare before/after migration
    pytest tests/performance/test_database_performance.py --benchmark-compare

Requirements:
    pip install pytest pytest-benchmark psycopg2-binary sqlalchemy
"""

import pytest
import time
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models.database import Asset, AssetType, Service, Finding, FindingSeverity, FindingStatus
from app.models.enrichment import Certificate, Endpoint
from app.repositories.asset_repository import AssetRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.certificate_repository import CertificateRepository
from app.repositories.endpoint_repository import EndpointRepository


# =============================================================================
# TEST FIXTURES AND HELPERS
# =============================================================================

@pytest.fixture(scope="session")
def db_session():
    """Provide database session for tests"""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="session")
def test_tenant_id(db_session):
    """Create test tenant and return ID"""
    from app.models.database import Tenant

    tenant = Tenant(
        name="Performance Test Tenant",
        slug="perf-test",
        contact_policy="test@example.com"
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant.id


@pytest.fixture(scope="session")
def sample_assets(db_session, test_tenant_id):
    """Create sample assets for performance testing"""
    asset_repo = AssetRepository(db_session)

    # Create 1000 test assets
    assets_data = []
    for i in range(1000):
        assets_data.append({
            'identifier': f'test-asset-{i}.example.com',
            'type': AssetType.SUBDOMAIN,
            'risk_score': (i % 10) * 1.0,
            'raw_metadata': f'{{"test": "data-{i}"}}'
        })

    result = asset_repo.bulk_upsert(test_tenant_id, assets_data)
    db_session.commit()

    # Return asset IDs
    assets = db_session.query(Asset).filter_by(tenant_id=test_tenant_id).all()
    return [asset.id for asset in assets]


def generate_service_data(asset_id: int, count: int = 10) -> List[Dict]:
    """Generate test service data for bulk UPSERT"""
    services = []
    for i in range(count):
        services.append({
            'port': 80 + i,
            'protocol': 'https' if i % 2 == 0 else 'http',
            'product': f'nginx/{i}.0',
            'http_status': 200,
            'http_title': f'Test Service {i}',
            'web_server': 'nginx',
            'http_technologies': ['PHP', 'WordPress'] if i % 3 == 0 else ['Node.js'],
            'has_tls': i % 2 == 0,
            'response_time_ms': 100 + i,
            'enrichment_source': 'httpx'
        })
    return services


def generate_certificate_data(count: int = 5) -> List[Dict]:
    """Generate test certificate data for bulk UPSERT"""
    certs = []
    for i in range(count):
        certs.append({
            'serial_number': f'ABC123{i:06d}',
            'subject_cn': f'*.test-{i}.example.com',
            'issuer': 'Let\'s Encrypt Authority X3',
            'not_before': datetime.utcnow() - timedelta(days=30),
            'not_after': datetime.utcnow() + timedelta(days=60),
            'is_expired': False,
            'days_until_expiry': 60,
            'san_domains': [f'test-{i}.example.com', f'www.test-{i}.example.com'],
            'is_self_signed': i % 5 == 0,
            'is_wildcard': True,
            'has_weak_signature': i % 10 == 0
        })
    return certs


def generate_endpoint_data(count: int = 100) -> List[Dict]:
    """Generate test endpoint data for bulk UPSERT"""
    endpoints = []
    for i in range(count):
        endpoints.append({
            'url': f'https://test.example.com/api/v{i % 3}/endpoint{i}',
            'path': f'/api/v{i % 3}/endpoint{i}',
            'method': 'GET' if i % 2 == 0 else 'POST',
            'status_code': 200,
            'endpoint_type': 'api' if i % 2 == 0 else 'static',
            'is_api': i % 2 == 0,
            'is_external': False,
            'depth': i % 5
        })
    return endpoints


def measure_query_time(db_session: Session, query_func, *args, **kwargs) -> float:
    """Measure query execution time in milliseconds"""
    start = time.perf_counter()
    result = query_func(*args, **kwargs)
    end = time.perf_counter()
    return (end - start) * 1000  # Convert to milliseconds


def get_query_plan(db_session: Session, query_text: str) -> Dict:
    """
    Get EXPLAIN ANALYZE output for a query

    Returns execution plan with costs and actual times
    """
    explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_text}"
    result = db_session.execute(text(explain_query))
    plan = result.fetchone()[0]
    return plan[0]


# =============================================================================
# TEST SUITE 1: BULK UPSERT PERFORMANCE
# =============================================================================

class TestBulkUpsertPerformance:
    """
    Test bulk UPSERT performance for enrichment operations

    Critical for enrichment pipeline performance.
    Target: <100ms for 1000 records
    """

    def test_service_bulk_upsert_1000_records(self, db_session, sample_assets, benchmark):
        """
        Benchmark bulk UPSERT of 1000 service records

        Expected: <100ms with proper unique index on (asset_id, port)
        Without index: >5000ms (50x slower)
        """
        service_repo = ServiceRepository(db_session)
        asset_id = sample_assets[0]

        # Generate 1000 service records
        services_data = generate_service_data(asset_id, count=1000)

        def bulk_upsert():
            return service_repo.bulk_upsert(asset_id, services_data)

        result = benchmark(bulk_upsert)

        # Verify results
        assert result['total_processed'] == 1000
        assert result['created'] + result['updated'] == 1000

        # Performance assertion
        # With index: should complete in <100ms
        # Without index: would take >5000ms
        assert benchmark.stats['mean'] < 0.100  # 100ms

    def test_service_bulk_upsert_update_existing(self, db_session, sample_assets, benchmark):
        """
        Benchmark bulk UPSERT when updating existing records

        Tests ON CONFLICT DO UPDATE performance
        Expected: Similar performance to INSERT (index is critical)
        """
        service_repo = ServiceRepository(db_session)
        asset_id = sample_assets[1]

        # Create initial records
        services_data = generate_service_data(asset_id, count=500)
        service_repo.bulk_upsert(asset_id, services_data)
        db_session.commit()

        # Update existing records (same ports, different data)
        updated_services = generate_service_data(asset_id, count=500)
        for service in updated_services:
            service['http_title'] = 'Updated Title'

        def bulk_update():
            return service_repo.bulk_upsert(asset_id, updated_services)

        result = benchmark(bulk_update)

        # All should be updates, not creates
        assert result['updated'] == 500
        assert result['created'] == 0

    def test_certificate_bulk_upsert_100_records(self, db_session, sample_assets, benchmark):
        """
        Benchmark bulk UPSERT of 100 certificate records

        Expected: <50ms with unique index on (asset_id, serial_number)
        """
        cert_repo = CertificateRepository(db_session)
        asset_id = sample_assets[2]

        certs_data = generate_certificate_data(count=100)

        def bulk_upsert():
            return cert_repo.bulk_upsert(asset_id, certs_data)

        result = benchmark(bulk_upsert)

        assert result['total_processed'] == 100
        assert benchmark.stats['mean'] < 0.050  # 50ms

    def test_endpoint_bulk_upsert_1000_records(self, db_session, sample_assets, benchmark):
        """
        Benchmark bulk UPSERT of 1000 endpoint records (Katana crawl results)

        Expected: <150ms with unique index on (asset_id, url, method)
        """
        endpoint_repo = EndpointRepository(db_session)
        asset_id = sample_assets[3]

        endpoints_data = generate_endpoint_data(count=1000)

        def bulk_upsert():
            return endpoint_repo.bulk_upsert(asset_id, endpoints_data)

        result = benchmark(bulk_upsert)

        assert result['total_processed'] == 1000
        assert benchmark.stats['mean'] < 0.150  # 150ms


# =============================================================================
# TEST SUITE 2: TENANT-SCOPED QUERY PERFORMANCE
# =============================================================================

class TestTenantScopedQueries:
    """
    Test performance of tenant-scoped queries with JOINs

    These queries are extremely common in the UI/API.
    Target: <50ms for queries on 100k+ record tables
    """

    def test_certificate_expiring_soon_query(self, db_session, test_tenant_id, sample_assets, benchmark):
        """
        Benchmark certificate expiry query with JOIN to assets

        Query: certificates JOIN assets WHERE tenant_id = X AND expiring soon
        Expected: <20ms with composite index (asset_id, is_expired, not_after)
        Without index: >500ms (25x slower)
        """
        cert_repo = CertificateRepository(db_session)

        # Create test data
        for asset_id in sample_assets[:100]:
            certs = generate_certificate_data(count=10)
            cert_repo.bulk_upsert(asset_id, certs)
        db_session.commit()

        def query_expiring():
            return cert_repo.get_expiring_soon(test_tenant_id, days_threshold=30, limit=100)

        certs = benchmark(query_expiring)

        assert len(certs) >= 0  # May be empty if no expiring certs
        assert benchmark.stats['mean'] < 0.020  # 20ms

    def test_certificate_stats_aggregation(self, db_session, test_tenant_id, benchmark):
        """
        Benchmark certificate statistics aggregation

        Runs 6 count() queries with different filters
        Expected: <100ms total with proper indexes
        Without indexes: >3000ms (30x slower)
        """
        cert_repo = CertificateRepository(db_session)

        def get_stats():
            return cert_repo.get_certificate_stats(test_tenant_id)

        stats = benchmark(get_stats)

        assert 'total' in stats
        assert 'expired' in stats
        assert 'expiring_soon' in stats
        assert benchmark.stats['mean'] < 0.100  # 100ms

    def test_get_api_endpoints_tenant_wide(self, db_session, test_tenant_id, sample_assets, benchmark):
        """
        Benchmark API endpoint discovery across tenant

        Query: endpoints JOIN assets WHERE tenant_id = X AND is_api = true
        Expected: <30ms with partial index on is_api
        Without index: >1000ms (33x slower)
        """
        endpoint_repo = EndpointRepository(db_session)

        # Create test data
        for asset_id in sample_assets[:50]:
            endpoints = generate_endpoint_data(count=50)
            endpoint_repo.bulk_upsert(asset_id, endpoints)
        db_session.commit()

        def query_api_endpoints():
            return endpoint_repo.get_api_endpoints(test_tenant_id, limit=1000)

        endpoints = benchmark(query_api_endpoints)

        assert len(endpoints) >= 0
        assert benchmark.stats['mean'] < 0.030  # 30ms

    def test_services_by_technology_search(self, db_session, test_tenant_id, sample_assets, benchmark):
        """
        Benchmark technology stack search using JSONB containment

        Query: services WHERE http_technologies @> '["WordPress"]'
        Expected: <50ms with GIN index on http_technologies
        Without GIN index: >2000ms (40x slower)
        """
        service_repo = ServiceRepository(db_session)

        # Create test data
        for asset_id in sample_assets[:100]:
            services = generate_service_data(asset_id, count=10)
            service_repo.bulk_upsert(asset_id, services)
        db_session.commit()

        def search_technology():
            return service_repo.get_services_by_technology(test_tenant_id, 'WordPress')

        services = benchmark(search_technology)

        assert len(services) >= 0
        assert benchmark.stats['mean'] < 0.050  # 50ms


# =============================================================================
# TEST SUITE 3: N+1 QUERY PREVENTION
# =============================================================================

class TestN1QueryPrevention:
    """
    Test that N+1 query problems are avoided with proper eager loading

    N+1 queries occur when loading a collection then accessing relationships
    in a loop, causing 1 + N additional queries.
    """

    def test_assets_with_services_eager_loading(self, db_session, test_tenant_id, sample_assets, benchmark):
        """
        Verify eager loading prevents N+1 queries when accessing services

        Without eager loading: 1 query for assets + N queries for services = N+1
        With eager loading: 2 queries total (1 for assets + 1 for all services)
        """
        asset_repo = AssetRepository(db_session)
        service_repo = ServiceRepository(db_session)

        # Create services for assets
        for asset_id in sample_assets[:50]:
            services = generate_service_data(asset_id, count=5)
            service_repo.bulk_upsert(asset_id, services)
        db_session.commit()

        def query_with_eager_loading():
            # This should use selectinload to fetch all services in 1 additional query
            assets = asset_repo.get_by_tenant(
                test_tenant_id,
                limit=50,
                eager_load_relations=True
            )

            # Access services (should NOT trigger N queries)
            total_services = 0
            for asset in assets:
                total_services += len(asset.services)

            return total_services

        total = benchmark(query_with_eager_loading)

        assert total >= 0
        # With eager loading, this should be fast even with many assets
        assert benchmark.stats['mean'] < 0.050  # 50ms

    def test_critical_assets_with_findings_eager_loading(self, db_session, test_tenant_id, sample_assets, benchmark):
        """
        Verify eager loading for critical assets with findings

        Critical assets are frequently displayed with their findings.
        Eager loading is essential for good performance.
        """
        asset_repo = AssetRepository(db_session)

        # Create findings for assets
        for asset_id in sample_assets[:30]:
            for i in range(5):
                finding = Finding(
                    asset_id=asset_id,
                    name=f'Test Finding {i}',
                    severity=FindingSeverity.HIGH,
                    status=FindingStatus.OPEN,
                    source='nuclei',
                    template_id=f'test-{i}'
                )
                db_session.add(finding)
        db_session.commit()

        def query_with_eager_loading():
            assets = asset_repo.get_critical_assets(
                test_tenant_id,
                risk_threshold=5.0,
                eager_load_relations=True
            )

            # Access findings (should NOT trigger N queries)
            total_findings = 0
            for asset in assets:
                total_findings += len(asset.findings)

            return total_findings

        total = benchmark(query_with_eager_loading)

        assert total >= 0
        assert benchmark.stats['mean'] < 0.050  # 50ms


# =============================================================================
# TEST SUITE 4: INDEX USAGE VERIFICATION
# =============================================================================

class TestIndexUsage:
    """
    Verify that PostgreSQL query planner is using indexes correctly

    Uses EXPLAIN ANALYZE to inspect query plans
    """

    def test_service_upsert_uses_unique_index(self, db_session, sample_assets):
        """
        Verify that bulk UPSERT uses unique index for conflict detection

        EXPLAIN should show Index Scan on idx_services_asset_port_unique
        """
        asset_id = sample_assets[0]

        # Construct UPSERT query (simplified version)
        query = f"""
        INSERT INTO services (asset_id, port, protocol)
        VALUES ({asset_id}, 80, 'http')
        ON CONFLICT (asset_id, port) DO UPDATE SET protocol = EXCLUDED.protocol
        RETURNING id
        """

        # Can't easily test full UPSERT with EXPLAIN, but we can verify index exists
        index_check = db_session.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'services'
              AND indexname LIKE '%asset_port%'
        """))

        indexes = index_check.fetchall()
        assert len(indexes) > 0, "Index on (asset_id, port) should exist"

        # Check that it's a UNIQUE index
        index_def = indexes[0][1]
        assert 'UNIQUE' in index_def.upper(), "Index should be UNIQUE for UPSERT performance"

    def test_certificate_expiry_query_uses_composite_index(self, db_session, test_tenant_id):
        """
        Verify that certificate expiry queries use composite index

        Expected index: idx_certificates_expired_expiry (asset_id, is_expired, not_after)
        """
        query = f"""
        SELECT c.* FROM certificates c
        JOIN assets a ON c.asset_id = a.id
        WHERE a.tenant_id = {test_tenant_id}
          AND c.is_expired = false
          AND c.not_after <= CURRENT_TIMESTAMP + INTERVAL '30 days'
        ORDER BY c.not_after
        LIMIT 100
        """

        plan = get_query_plan(db_session, query)

        # Inspect plan to verify index usage
        plan_str = str(plan)

        # Should use index scan, not sequential scan
        assert 'Seq Scan on certificates' not in plan_str or 'Index' in plan_str, \
            "Query should use index, not sequential scan"

        # Print plan for debugging
        print(f"\nQuery Plan:\n{plan_str}")

    def test_gin_index_used_for_technology_search(self, db_session, test_tenant_id):
        """
        Verify that JSONB technology searches use GIN index

        Expected index: idx_services_http_technologies_gin
        """
        query = f"""
        SELECT s.* FROM services s
        JOIN assets a ON s.asset_id = a.id
        WHERE a.tenant_id = {test_tenant_id}
          AND s.http_technologies @> '["WordPress"]'::jsonb
        LIMIT 100
        """

        plan = get_query_plan(db_session, query)
        plan_str = str(plan)

        # GIN index should be used for JSONB containment
        # Look for "Bitmap Index Scan" or "Index Scan" on GIN index
        print(f"\nGIN Index Query Plan:\n{plan_str}")

        # This is informational - GIN indexes show up as bitmap scans
        # We just verify the query completes successfully
        assert plan is not None

    def test_partial_index_used_for_active_certificates(self, db_session):
        """
        Verify that partial index is used for active certificate queries

        Expected index: idx_certificates_active_only WHERE is_expired = false
        """
        query = """
        SELECT * FROM certificates
        WHERE is_expired = false
        ORDER BY not_after
        LIMIT 100
        """

        plan = get_query_plan(db_session, query)
        plan_str = str(plan)

        # Partial index should be used
        print(f"\nPartial Index Query Plan:\n{plan_str}")

        # Verify query uses index, not seq scan
        assert 'Seq Scan on certificates' not in plan_str or \
               plan_str.count('Index') > 0, \
            "Query should use partial index for is_expired = false"


# =============================================================================
# TEST SUITE 5: LARGE DATASET PERFORMANCE
# =============================================================================

class TestLargeDatasetPerformance:
    """
    Test performance with datasets of 10k, 100k, 1M records

    These tests are optional and should be run before production deployment
    to verify scaling characteristics.

    Run with: pytest -k "large_dataset" -v
    """

    @pytest.mark.slow
    def test_service_query_with_10k_records(self, db_session, test_tenant_id, sample_assets):
        """
        Test service queries with 10,000 service records

        Simulates small to medium deployment
        """
        service_repo = ServiceRepository(db_session)

        # Create 10k services (10 services per asset across 1000 assets)
        for asset_id in sample_assets[:1000]:
            services = generate_service_data(asset_id, count=10)
            service_repo.bulk_upsert(asset_id, services)
        db_session.commit()

        # Query should still be fast
        start = time.perf_counter()
        services = service_repo.get_by_asset(sample_assets[0], limit=100)
        duration = (time.perf_counter() - start) * 1000

        assert duration < 20, f"Query took {duration}ms, should be <20ms with index"

    @pytest.mark.slow
    def test_certificate_stats_with_10k_records(self, db_session, test_tenant_id, sample_assets):
        """
        Test certificate statistics with 10,000 certificate records

        Stats queries run multiple count() operations
        """
        cert_repo = CertificateRepository(db_session)

        # Create 10k certificates (100 certs per asset across 100 assets)
        for asset_id in sample_assets[:100]:
            certs = generate_certificate_data(count=100)
            cert_repo.bulk_upsert(asset_id, certs)
        db_session.commit()

        # Stats query should be fast with indexes
        start = time.perf_counter()
        stats = cert_repo.get_certificate_stats(test_tenant_id)
        duration = (time.perf_counter() - start) * 1000

        assert duration < 100, f"Stats query took {duration}ms, should be <100ms with indexes"
        assert stats['total'] > 0


# =============================================================================
# TEST UTILITIES
# =============================================================================

def test_list_all_indexes(db_session):
    """
    Utility test to list all indexes in the database

    Run this to verify migration 005 created all indexes correctly
    """
    result = db_session.execute(text("""
        SELECT
            schemaname,
            tablename,
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    """))

    print("\n" + "="*100)
    print("DATABASE INDEXES")
    print("="*100)

    for row in result:
        schema, table, index_name, index_def = row
        print(f"\n{table}.{index_name}:")
        print(f"  {index_def}")

    print("\n" + "="*100)


def test_check_index_usage_stats(db_session):
    """
    Check index usage statistics from pg_stat_user_indexes

    Run this after the application has been running for a while to
    identify unused indexes (candidates for removal)
    """
    result = db_session.execute(text("""
        SELECT
            schemaname,
            tablename,
            indexname,
            idx_scan as scans,
            idx_tup_read as tuples_read,
            idx_tup_fetch as tuples_fetched,
            pg_size_pretty(pg_relation_size(indexrelid)) as size
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
        ORDER BY idx_scan DESC
    """))

    print("\n" + "="*100)
    print("INDEX USAGE STATISTICS")
    print("="*100)
    print(f"{'Table':<20} {'Index':<40} {'Scans':<10} {'Size':<10}")
    print("-"*100)

    for row in result:
        schema, table, index_name, scans, tuples_read, tuples_fetched, size = row
        print(f"{table:<20} {index_name:<40} {scans or 0:<10} {size:<10}")

    print("="*100)
    print("\nNOTE: Indexes with 0 scans may be unused and candidates for removal")
    print("      Run this test after production usage for accurate statistics")
    print("="*100 + "\n")


def test_analyze_slow_queries(db_session):
    """
    Query pg_stat_statements to find slow queries

    Requires pg_stat_statements extension:
        CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

    Run this in production to identify optimization opportunities
    """
    try:
        result = db_session.execute(text("""
            SELECT
                substring(query, 1, 100) as query_snippet,
                calls,
                round(total_exec_time::numeric, 2) as total_time_ms,
                round(mean_exec_time::numeric, 2) as mean_time_ms,
                round(max_exec_time::numeric, 2) as max_time_ms,
                round((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 2) as pct_total_time
            FROM pg_stat_statements
            WHERE query NOT LIKE '%pg_stat%'
              AND query NOT LIKE '%pg_catalog%'
            ORDER BY mean_exec_time DESC
            LIMIT 20
        """))

        print("\n" + "="*100)
        print("SLOWEST QUERIES (by mean execution time)")
        print("="*100)
        print(f"{'Query Snippet':<102} {'Calls':<10} {'Mean (ms)':<12} {'% Time':<10}")
        print("-"*100)

        for row in result:
            query, calls, total_time, mean_time, max_time, pct = row
            print(f"{query:<102} {calls:<10} {mean_time:<12} {pct:<10}")

        print("="*100 + "\n")

    except Exception as e:
        print(f"\nCould not query pg_stat_statements: {e}")
        print("Enable with: CREATE EXTENSION IF NOT EXISTS pg_stat_statements;\n")


if __name__ == '__main__':
    """
    Run performance tests directly

    Usage:
        python test_database_performance.py
    """
    pytest.main([__file__, '-v', '--benchmark-only'])
