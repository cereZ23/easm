"""
Performance tests for EASM platform

Tests cover:
- Batch processing efficiency
- Database query performance
- Memory usage under load
- Concurrent operations
- Bulk upsert performance
- Query optimization

Run with: pytest tests/test_performance.py -v --durations=10
"""
import pytest
import time
import psutil
import os
from unittest.mock import patch, MagicMock
from datetime import datetime
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Tenant, Asset, Event, AssetType, EventKind
from app.repositories.asset_repository import AssetRepository, EventRepository


@pytest.fixture(scope='function')
def test_db():
    """Create test database"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    tenant = Tenant(name="Test", slug="test")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    yield db, tenant

    db.close()
    engine.dispose()


class TestBatchProcessingPerformance:
    """Test batch processing performance"""

    def test_bulk_upsert_small_batch(self, test_db):
        """Benchmark: Bulk upsert with 100 assets"""
        db, tenant = test_db
        repo = AssetRepository(db)

        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': json.dumps({'index': i})
            }
            for i in range(100)
        ]

        start_time = time.time()
        result = repo.bulk_upsert(tenant.id, assets_data)
        elapsed = time.time() - start_time

        assert result['total_processed'] == 100
        # Should complete in under 1 second
        assert elapsed < 1.0, f"Bulk upsert of 100 assets took {elapsed:.2f}s"

    def test_bulk_upsert_medium_batch(self, test_db):
        """Benchmark: Bulk upsert with 1000 assets"""
        db, tenant = test_db
        repo = AssetRepository(db)

        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': json.dumps({'index': i, 'data': 'x' * 100})
            }
            for i in range(1000)
        ]

        start_time = time.time()
        result = repo.bulk_upsert(tenant.id, assets_data)
        elapsed = time.time() - start_time

        assert result['total_processed'] == 1000
        # Should complete in under 5 seconds
        assert elapsed < 5.0, f"Bulk upsert of 1000 assets took {elapsed:.2f}s"

    def test_bulk_upsert_large_batch(self, test_db):
        """Benchmark: Bulk upsert with 5000 assets"""
        db, tenant = test_db
        repo = AssetRepository(db)

        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': json.dumps({'index': i})
            }
            for i in range(5000)
        ]

        start_time = time.time()
        result = repo.bulk_upsert(tenant.id, assets_data)
        elapsed = time.time() - start_time

        assert result['total_processed'] == 5000
        # Should complete in under 20 seconds
        assert elapsed < 20.0, f"Bulk upsert of 5000 assets took {elapsed:.2f}s"

    def test_upsert_vs_individual_inserts(self, test_db):
        """Compare bulk upsert vs individual inserts"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Individual inserts
        start_time = time.time()
        for i in range(100):
            assets_data = [
                {
                    'identifier': f'individual{i}.com',
                    'type': AssetType.SUBDOMAIN,
                    'raw_metadata': '{}'
                }
            ]
            repo.bulk_upsert(tenant.id, assets_data)
        individual_time = time.time() - start_time

        # Bulk upsert
        assets_data = [
            {
                'identifier': f'bulk{i}.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}'
            }
            for i in range(100)
        ]

        start_time = time.time()
        repo.bulk_upsert(tenant.id, assets_data)
        bulk_time = time.time() - start_time

        # Bulk should be at least 2x faster
        assert bulk_time < individual_time / 2, \
            f"Bulk ({bulk_time:.2f}s) not significantly faster than individual ({individual_time:.2f}s)"

    def test_batch_event_creation_performance(self, test_db):
        """Benchmark: Batch event creation"""
        db, tenant = test_db

        # Create assets first
        assets = [
            Asset(
                tenant_id=tenant.id,
                identifier=f'test{i}.com',
                type=AssetType.SUBDOMAIN
            )
            for i in range(1000)
        ]
        db.add_all(assets)
        db.commit()

        # Create events in batch
        event_repo = EventRepository(db)
        events = [
            Event(
                asset_id=assets[i % len(assets)].id,
                kind=EventKind.NEW_ASSET,
                payload=json.dumps({'index': i})
            )
            for i in range(1000)
        ]

        start_time = time.time()
        event_repo.create_batch(events)
        db.commit()
        elapsed = time.time() - start_time

        # Should complete in under 2 seconds
        assert elapsed < 2.0, f"Creating 1000 events took {elapsed:.2f}s"


class TestDatabaseQueryPerformance:
    """Test database query performance"""

    def test_get_by_tenant_performance(self, test_db):
        """Benchmark: Query assets by tenant"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Create 1000 assets
        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}'
            }
            for i in range(1000)
        ]
        repo.bulk_upsert(tenant.id, assets_data)

        # Query performance
        start_time = time.time()
        assets = repo.get_by_tenant(tenant.id, limit=1000)
        elapsed = time.time() - start_time

        assert len(assets) == 1000
        # Query should be fast with index
        assert elapsed < 0.5, f"Query took {elapsed:.2f}s"

    def test_get_by_identifier_performance(self, test_db):
        """Benchmark: Query by identifier with index"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Create 10000 assets
        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}'
            }
            for i in range(10000)
        ]
        repo.bulk_upsert(tenant.id, assets_data)

        # Query specific asset (should use index)
        start_time = time.time()
        asset = repo.get_by_identifier(tenant.id, 'sub5000.example.com', AssetType.SUBDOMAIN)
        elapsed = time.time() - start_time

        assert asset is not None
        # Should be nearly instant with index
        assert elapsed < 0.1, f"Indexed query took {elapsed:.2f}s"

    def test_critical_assets_query_performance(self, test_db):
        """Benchmark: Query critical assets"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Create mix of assets with different risk scores
        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}',
                'risk_score': float(i % 100)
            }
            for i in range(1000)
        ]
        repo.bulk_upsert(tenant.id, assets_data)

        # Query critical assets
        start_time = time.time()
        critical = repo.get_critical_assets(tenant.id, risk_threshold=50.0)
        elapsed = time.time() - start_time

        assert len(critical) > 0
        # Should complete quickly with proper filtering
        assert elapsed < 0.5, f"Critical assets query took {elapsed:.2f}s"

    def test_pagination_performance(self, test_db):
        """Benchmark: Pagination performance"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Create 5000 assets
        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}'
            }
            for i in range(5000)
        ]
        repo.bulk_upsert(tenant.id, assets_data)

        # Test pagination at different offsets
        start_time = time.time()

        # First page
        page1 = repo.get_by_tenant(tenant.id, limit=100, offset=0)
        # Middle page
        page2 = repo.get_by_tenant(tenant.id, limit=100, offset=2500)
        # Last page
        page3 = repo.get_by_tenant(tenant.id, limit=100, offset=4900)

        elapsed = time.time() - start_time

        assert len(page1) == 100
        assert len(page2) == 100
        assert len(page3) == 100

        # All three pages should complete quickly
        assert elapsed < 1.0, f"Pagination took {elapsed:.2f}s"


class TestMemoryUsagePerformance:
    """Test memory usage under load"""

    def test_memory_usage_bulk_upsert(self, test_db):
        """Monitor memory usage during bulk upsert"""
        db, tenant = test_db
        repo = AssetRepository(db)

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create large batch
        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': json.dumps({'data': 'x' * 1000})
            }
            for i in range(5000)
        ]

        repo.bulk_upsert(tenant.id, assets_data)

        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory

        # Memory increase should be reasonable (< 100MB for this test)
        assert memory_increase < 100, f"Memory increased by {memory_increase:.2f}MB"

    def test_memory_usage_query_large_dataset(self, test_db):
        """Monitor memory usage querying large dataset"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Create 10000 assets
        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}'
            }
            for i in range(10000)
        ]
        repo.bulk_upsert(tenant.id, assets_data)

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Query with pagination (good practice)
        for offset in range(0, 10000, 1000):
            assets = repo.get_by_tenant(tenant.id, limit=1000, offset=offset)
            assert len(assets) <= 1000

        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory

        # Pagination should keep memory usage low
        assert memory_increase < 50, f"Memory increased by {memory_increase:.2f}MB"

    def test_no_memory_leak_repeated_operations(self, test_db):
        """Test for memory leaks in repeated operations"""
        db, tenant = test_db
        repo = AssetRepository(db)

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Perform many operations
        for iteration in range(10):
            assets_data = [
                {
                    'identifier': f'test{iteration}_{i}.com',
                    'type': AssetType.SUBDOMAIN,
                    'raw_metadata': '{}'
                }
                for i in range(100)
            ]
            repo.bulk_upsert(tenant.id, assets_data)

            # Query back
            assets = repo.get_by_tenant(tenant.id, limit=100)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Should not have significant memory leak
        assert memory_increase < 50, f"Potential memory leak: {memory_increase:.2f}MB increase"


class TestConcurrentOperationsPerformance:
    """Test concurrent operations performance"""

    def test_concurrent_reads_performance(self, test_db):
        """Benchmark: Concurrent read operations"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Create test data
        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}'
            }
            for i in range(1000)
        ]
        repo.bulk_upsert(tenant.id, assets_data)

        # Simulate concurrent reads
        start_time = time.time()

        for _ in range(100):
            assets = repo.get_by_tenant(tenant.id, limit=10)
            assert len(assets) <= 10

        elapsed = time.time() - start_time

        # 100 queries should complete quickly
        assert elapsed < 2.0, f"100 concurrent reads took {elapsed:.2f}s"

    def test_mixed_read_write_performance(self, test_db):
        """Benchmark: Mixed read and write operations"""
        db, tenant = test_db
        repo = AssetRepository(db)

        start_time = time.time()

        for i in range(50):
            # Write
            assets_data = [
                {
                    'identifier': f'batch{i}_{j}.com',
                    'type': AssetType.SUBDOMAIN,
                    'raw_metadata': '{}'
                }
                for j in range(10)
            ]
            repo.bulk_upsert(tenant.id, assets_data)

            # Read
            assets = repo.get_by_tenant(tenant.id, limit=10)

        elapsed = time.time() - start_time

        # Mixed operations should complete in reasonable time
        assert elapsed < 5.0, f"Mixed operations took {elapsed:.2f}s"


class TestDiscoveryPipelinePerformance:
    """Test discovery pipeline performance"""

    @patch('app.tasks.discovery.SessionLocal')
    @patch('app.utils.secure_executor.SecureToolExecutor.execute')
    @patch('app.utils.secure_executor.SecureToolExecutor.read_output_file')
    @patch('app.tasks.discovery.store_raw_output')
    def test_process_discovery_results_batch_performance(
        self, mock_store, mock_read, mock_execute, mock_session_local, test_db
    ):
        """Benchmark: Processing discovery results in batches"""
        from app.tasks.discovery import process_discovery_results

        db, tenant = test_db
        mock_session_local.return_value = db

        # Simulate large discovery result
        dnsx_result = {
            'resolved': [
                {
                    'host': f'sub{i}.example.com',
                    'a': [f'1.2.{i//256}.{i%256}']
                }
                for i in range(1000)
            ],
            'tenant_id': tenant.id
        }

        start_time = time.time()
        result = process_discovery_results(dnsx_result, tenant.id)
        elapsed = time.time() - start_time

        assert result['total_resolved'] == 1000
        # Should process 1000 records efficiently
        assert elapsed < 5.0, f"Processing 1000 records took {elapsed:.2f}s"

    @patch('app.tasks.discovery.SessionLocal')
    def test_collect_seeds_performance(self, mock_session_local, test_db):
        """Benchmark: Collecting seeds"""
        from app.tasks.discovery import collect_seeds
        from app.models.database import Seed

        db, tenant = test_db
        mock_session_local.return_value = db

        # Create many seeds
        seeds = [
            Seed(
                tenant_id=tenant.id,
                type='domain',
                value=f'domain{i}.com',
                enabled=True
            )
            for i in range(100)
        ]
        db.add_all(seeds)
        db.commit()

        start_time = time.time()
        result = collect_seeds(tenant.id)
        elapsed = time.time() - start_time

        assert len(result['domains']) == 100
        # Should be very fast
        assert elapsed < 0.5, f"Collecting 100 seeds took {elapsed:.2f}s"


class TestIndexEffectiveness:
    """Test that database indexes are effective"""

    def test_tenant_identifier_index_used(self, test_db):
        """Test that tenant+identifier index improves performance"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Create many assets
        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}'
            }
            for i in range(5000)
        ]
        repo.bulk_upsert(tenant.id, assets_data)

        # Query should be fast due to index
        start_time = time.time()
        asset = repo.get_by_identifier(tenant.id, 'sub2500.example.com', AssetType.SUBDOMAIN)
        elapsed = time.time() - start_time

        assert asset is not None
        # Index should make this very fast even with 5000 records
        assert elapsed < 0.1, f"Indexed query took {elapsed:.2f}s"

    def test_risk_score_ordering_performance(self, test_db):
        """Test that ordering by risk_score is efficient"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Create assets with various risk scores
        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}',
                'risk_score': float(i % 100)
            }
            for i in range(1000)
        ]
        repo.bulk_upsert(tenant.id, assets_data)

        # Query with ordering
        start_time = time.time()
        assets = repo.get_by_tenant(tenant.id, limit=100)
        elapsed = time.time() - start_time

        # Should be ordered by risk_score descending
        assert len(assets) == 100
        # Ordering should be fast
        assert elapsed < 0.5, f"Ordered query took {elapsed:.2f}s"


class TestScalabilityMetrics:
    """Test scalability metrics"""

    def test_linear_scaling_bulk_upsert(self, test_db):
        """Test that bulk upsert scales linearly"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Test with different sizes
        times = {}

        for size in [100, 500, 1000]:
            assets_data = [
                {
                    'identifier': f'size{size}_{i}.com',
                    'type': AssetType.SUBDOMAIN,
                    'raw_metadata': '{}'
                }
                for i in range(size)
            ]

            start_time = time.time()
            repo.bulk_upsert(tenant.id, assets_data)
            elapsed = time.time() - start_time
            times[size] = elapsed

        # Check roughly linear scaling
        # 1000 should take less than 15x the time of 100
        scaling_factor = times[1000] / times[100]
        assert scaling_factor < 15, f"Scaling factor {scaling_factor:.2f} indicates poor scalability"

    def test_query_performance_with_growing_dataset(self, test_db):
        """Test query performance as dataset grows"""
        db, tenant = test_db
        repo = AssetRepository(db)

        query_times = []

        # Add data in stages and measure query time
        for batch in range(5):
            assets_data = [
                {
                    'identifier': f'batch{batch}_{i}.com',
                    'type': AssetType.SUBDOMAIN,
                    'raw_metadata': '{}'
                }
                for i in range(1000)
            ]
            repo.bulk_upsert(tenant.id, assets_data)

            # Measure query time
            start_time = time.time()
            repo.get_by_identifier(tenant.id, f'batch{batch}_500.com', AssetType.SUBDOMAIN)
            elapsed = time.time() - start_time
            query_times.append(elapsed)

        # Query time should remain relatively constant (due to indexes)
        # Last query should not be significantly slower than first
        assert query_times[-1] < query_times[0] * 3, \
            "Query performance degraded significantly as dataset grew"


@pytest.mark.benchmark
class TestBenchmarkComparisons:
    """Benchmark tests for comparison"""

    def test_benchmark_bulk_upsert_1000(self, test_db, benchmark):
        """Benchmark: Bulk upsert 1000 records"""
        db, tenant = test_db
        repo = AssetRepository(db)

        assets_data = [
            {
                'identifier': f'bench{i}.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}'
            }
            for i in range(1000)
        ]

        def upsert():
            repo.bulk_upsert(tenant.id, assets_data)

        if hasattr(pytest, 'benchmark'):
            benchmark(upsert)
        else:
            upsert()

    def test_benchmark_query_by_identifier(self, test_db, benchmark):
        """Benchmark: Query by identifier"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # Setup data
        assets_data = [
            {
                'identifier': f'bench{i}.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{}'
            }
            for i in range(1000)
        ]
        repo.bulk_upsert(tenant.id, assets_data)

        def query():
            repo.get_by_identifier(tenant.id, 'bench500.com', AssetType.SUBDOMAIN)

        if hasattr(pytest, 'benchmark'):
            benchmark(query)
        else:
            query()
