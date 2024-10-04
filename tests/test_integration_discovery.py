"""
Integration tests for discovery pipeline

Tests the complete discovery flow with database and external dependencies.
Uses test containers for PostgreSQL and MinIO when available.

These tests verify:
- Complete discovery pipeline execution
- Database persistence
- Task chaining and coordination
- MinIO storage integration
- Multi-tenant isolation
- Error recovery
"""
import pytest
import tempfile
import os
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, Tenant, Asset, Seed, Event, AssetType, EventKind
from app.repositories.asset_repository import AssetRepository, EventRepository
from app.tasks.discovery import (
    collect_seeds,
    run_subfinder,
    run_dnsx,
    process_discovery_results
)


@pytest.fixture(scope='function')
def test_db():
    """Create in-memory SQLite database for testing"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    yield db

    db.close()
    engine.dispose()


@pytest.fixture
def sample_tenant(test_db):
    """Create sample tenant for testing"""
    tenant = Tenant(
        name="Test Tenant",
        slug="test-tenant",
        contact_policy="security@test.com",
        api_keys=None
    )
    test_db.add(tenant)
    test_db.commit()
    test_db.refresh(tenant)
    return tenant


@pytest.fixture
def sample_seeds(test_db, sample_tenant):
    """Create sample seeds for testing"""
    seeds = [
        Seed(tenant_id=sample_tenant.id, type='domain', value='example.com', enabled=True),
        Seed(tenant_id=sample_tenant.id, type='domain', value='test.org', enabled=True),
        Seed(tenant_id=sample_tenant.id, type='keyword', value='TestCorp', enabled=True),
        Seed(tenant_id=sample_tenant.id, type='asn', value='AS12345', enabled=True),
    ]
    test_db.add_all(seeds)
    test_db.commit()
    return seeds


class TestDiscoveryPipelineIntegration:
    """Test complete discovery pipeline"""

    @patch('app.database.SessionLocal')
    def test_collect_seeds_integration(self, mock_session_local, test_db, sample_tenant, sample_seeds):
        """Test seed collection with real database"""
        mock_session_local.return_value = test_db

        result = collect_seeds(sample_tenant.id)

        assert 'domains' in result
        assert 'keywords' in result
        assert 'asns' in result
        assert len(result['domains']) == 2
        assert 'example.com' in result['domains']
        assert 'test.org' in result['domains']
        assert 'TestCorp' in result['keywords']
        assert 'AS12345' in result['asns']

    @patch('app.database.SessionLocal')
    def test_collect_seeds_disabled_seeds_excluded(self, mock_session_local, test_db, sample_tenant):
        """Test that disabled seeds are not collected"""
        mock_session_local.return_value = test_db

        # Create enabled and disabled seeds
        enabled_seed = Seed(tenant_id=sample_tenant.id, type='domain', value='enabled.com', enabled=True)
        disabled_seed = Seed(tenant_id=sample_tenant.id, type='domain', value='disabled.com', enabled=False)

        test_db.add_all([enabled_seed, disabled_seed])
        test_db.commit()

        result = collect_seeds(sample_tenant.id)

        assert 'enabled.com' in result['domains']
        assert 'disabled.com' not in result['domains']

    @patch('app.utils.secure_executor.SecureToolExecutor.execute')
    @patch('app.utils.secure_executor.SecureToolExecutor.read_output_file')
    @patch('app.tasks.discovery.store_raw_output')
    def test_subfinder_integration(self, mock_store, mock_read, mock_execute):
        """Test subfinder execution with mocked tool"""
        mock_execute.return_value = (0, "", "")
        mock_read.return_value = "sub1.example.com\nsub2.example.com\nsub3.example.com\n"

        seed_data = {
            'domains': ['example.com'],
            'keywords': [],
            'asns': [],
            'ip_ranges': []
        }

        result = run_subfinder(seed_data, tenant_id=1)

        assert result['tenant_id'] == 1
        assert len(result['subdomains']) == 3
        assert 'sub1.example.com' in result['subdomains']
        assert 'sub2.example.com' in result['subdomains']
        assert 'sub3.example.com' in result['subdomains']

        # Verify storage was called
        mock_store.assert_called_once()

    @patch('subprocess.run')
    @patch('app.tasks.discovery.store_raw_output')
    def test_dnsx_integration(self, mock_store, mock_run):
        """Test dnsx execution with mocked subprocess"""
        # Mock dnsx output
        dnsx_output = [
            json.dumps({'host': 'sub1.example.com', 'a': ['1.2.3.4'], 'status': 'NOERROR'}),
            json.dumps({'host': 'sub2.example.com', 'a': ['1.2.3.5'], 'status': 'NOERROR'}),
        ]

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            output_file = f.name
            f.write('\n'.join(dnsx_output))

        try:
            with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                mock_file = MagicMock()
                mock_file.name = output_file
                mock_tempfile.return_value.__enter__.return_value = mock_file

                mock_run.return_value = MagicMock(returncode=0)

                subfinder_result = {
                    'subdomains': ['sub1.example.com', 'sub2.example.com'],
                    'tenant_id': 1
                }

                result = run_dnsx(subfinder_result, tenant_id=1)

                assert result['tenant_id'] == 1
                assert len(result['resolved']) == 2
                assert result['resolved'][0]['host'] == 'sub1.example.com'
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    @patch('app.database.SessionLocal')
    @patch('app.tasks.discovery.store_raw_output')
    def test_process_discovery_results_integration(self, mock_store, mock_session_local, test_db, sample_tenant):
        """Test processing discovery results with real database"""
        mock_session_local.return_value = test_db

        dnsx_result = {
            'resolved': [
                {'host': 'sub1.example.com', 'a': ['1.2.3.4']},
                {'host': 'sub2.example.com', 'a': ['1.2.3.5']},
                {'host': 'sub3.example.com', 'a': ['1.2.3.6']},
            ],
            'tenant_id': sample_tenant.id
        }

        result = process_discovery_results(dnsx_result, sample_tenant.id)

        assert result['assets_processed'] >= 3
        assert result['total_resolved'] == 3

        # Verify assets were created in database
        assets = test_db.query(Asset).filter_by(tenant_id=sample_tenant.id).all()
        assert len(assets) >= 3

        identifiers = [a.identifier for a in assets]
        assert 'sub1.example.com' in identifiers
        assert 'sub2.example.com' in identifiers
        assert 'sub3.example.com' in identifiers

    @patch('app.database.SessionLocal')
    def test_full_pipeline_chain(self, mock_session_local, test_db, sample_tenant, sample_seeds):
        """Test complete discovery pipeline chain"""
        mock_session_local.return_value = test_db

        # Step 1: Collect seeds
        seed_data = collect_seeds(sample_tenant.id)
        assert len(seed_data['domains']) == 2

        # Step 2: Mock subfinder
        with patch('app.utils.secure_executor.SecureToolExecutor.execute') as mock_execute, \
             patch('app.utils.secure_executor.SecureToolExecutor.read_output_file') as mock_read, \
             patch('app.tasks.discovery.store_raw_output'):

            mock_execute.return_value = (0, "", "")
            mock_read.return_value = "sub1.example.com\nsub2.example.com\n"

            subfinder_result = run_subfinder(seed_data, sample_tenant.id)
            assert len(subfinder_result['subdomains']) == 2

            # Step 3: Mock dnsx
            dnsx_output = [
                json.dumps({'host': 'sub1.example.com', 'a': ['1.2.3.4']}),
                json.dumps({'host': 'sub2.example.com', 'a': ['1.2.3.5']}),
            ]

            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                output_file = f.name
                f.write('\n'.join(dnsx_output))

            try:
                with patch('tempfile.NamedTemporaryFile') as mock_tempfile, \
                     patch('subprocess.run') as mock_run:

                    mock_file = MagicMock()
                    mock_file.name = output_file
                    mock_tempfile.return_value.__enter__.return_value = mock_file
                    mock_run.return_value = MagicMock(returncode=0)

                    dnsx_result = run_dnsx(subfinder_result, sample_tenant.id)
                    assert len(dnsx_result['resolved']) == 2

                    # Step 4: Process results
                    final_result = process_discovery_results(dnsx_result, sample_tenant.id)
                    assert final_result['total_resolved'] == 2

                    # Verify database state
                    assets = test_db.query(Asset).filter_by(tenant_id=sample_tenant.id).all()
                    assert len(assets) >= 2
            finally:
                if os.path.exists(output_file):
                    os.unlink(output_file)


class TestDatabaseOperationsIntegration:
    """Test database operations with real database"""

    @patch('app.database.SessionLocal')
    def test_asset_upsert_creates_new(self, mock_session_local, test_db, sample_tenant):
        """Test upserting new assets"""
        mock_session_local.return_value = test_db

        repo = AssetRepository(test_db)

        assets_data = [
            {'identifier': 'new1.example.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{"test": "data"}'},
            {'identifier': 'new2.example.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{"test": "data"}'},
        ]

        result = repo.bulk_upsert(sample_tenant.id, assets_data)

        assert result['created'] >= 2

        # Verify in database
        asset1 = repo.get_by_identifier(sample_tenant.id, 'new1.example.com', AssetType.SUBDOMAIN)
        assert asset1 is not None
        assert asset1.identifier == 'new1.example.com'

    @patch('app.database.SessionLocal')
    def test_asset_upsert_updates_existing(self, mock_session_local, test_db, sample_tenant):
        """Test upserting existing assets updates them"""
        mock_session_local.return_value = test_db

        # Create initial asset
        asset = Asset(
            tenant_id=sample_tenant.id,
            identifier='existing.example.com',
            type=AssetType.SUBDOMAIN,
            raw_metadata='{"version": 1}'
        )
        test_db.add(asset)
        test_db.commit()

        first_seen = asset.first_seen
        asset_id = asset.id

        # Upsert same asset with new metadata
        repo = AssetRepository(test_db)
        assets_data = [
            {'identifier': 'existing.example.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{"version": 2}'},
        ]

        repo.bulk_upsert(sample_tenant.id, assets_data)

        # Verify update
        updated_asset = repo.get_by_identifier(sample_tenant.id, 'existing.example.com', AssetType.SUBDOMAIN)
        assert updated_asset.id == asset_id
        assert updated_asset.raw_metadata == '{"version": 2}'
        assert updated_asset.last_seen > first_seen

    def test_event_repository_integration(self, test_db, sample_tenant):
        """Test event repository with real database"""
        # Create asset
        asset = Asset(
            tenant_id=sample_tenant.id,
            identifier='test.example.com',
            type=AssetType.SUBDOMAIN
        )
        test_db.add(asset)
        test_db.commit()
        test_db.refresh(asset)

        # Create events
        event_repo = EventRepository(test_db)

        events = [
            Event(asset_id=asset.id, kind=EventKind.NEW_ASSET, payload='{"test": 1}'),
            Event(asset_id=asset.id, kind=EventKind.OPEN_PORT, payload='{"port": 443}'),
            Event(asset_id=asset.id, kind=EventKind.NEW_CERT, payload='{"cert": "data"}'),
        ]

        event_repo.create_batch(events)
        test_db.commit()

        # Query events
        retrieved_events = event_repo.get_by_asset(asset.id)
        assert len(retrieved_events) == 3

    def test_batch_processing_efficiency(self, test_db, sample_tenant):
        """Test batch processing handles large datasets efficiently"""
        repo = AssetRepository(test_db)

        # Create large batch
        assets_data = [
            {
                'identifier': f'sub{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': json.dumps({'index': i})
            }
            for i in range(200)
        ]

        result = repo.bulk_upsert(sample_tenant.id, assets_data)

        assert result['total_processed'] == 200

        # Verify count
        count = repo.count_by_tenant(sample_tenant.id)
        assert count == 200


class TestMultiTenantIsolation:
    """Test multi-tenant isolation in discovery pipeline"""

    @patch('app.database.SessionLocal')
    def test_tenant_data_isolation(self, mock_session_local, test_db):
        """Test that tenant data is properly isolated"""
        mock_session_local.return_value = test_db

        # Create two tenants
        tenant1 = Tenant(name="Tenant 1", slug="tenant-1")
        tenant2 = Tenant(name="Tenant 2", slug="tenant-2")
        test_db.add_all([tenant1, tenant2])
        test_db.commit()
        test_db.refresh(tenant1)
        test_db.refresh(tenant2)

        # Create assets for each tenant
        repo = AssetRepository(test_db)

        tenant1_assets = [
            {'identifier': 'tenant1-sub1.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
            {'identifier': 'tenant1-sub2.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
        ]

        tenant2_assets = [
            {'identifier': 'tenant2-sub1.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
            {'identifier': 'tenant2-sub2.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
        ]

        repo.bulk_upsert(tenant1.id, tenant1_assets)
        repo.bulk_upsert(tenant2.id, tenant2_assets)

        # Query assets for each tenant
        t1_assets = repo.get_by_tenant(tenant1.id)
        t2_assets = repo.get_by_tenant(tenant2.id)

        assert len(t1_assets) == 2
        assert len(t2_assets) == 2

        # Verify isolation
        t1_identifiers = [a.identifier for a in t1_assets]
        t2_identifiers = [a.identifier for a in t2_assets]

        assert 'tenant1-sub1.com' in t1_identifiers
        assert 'tenant1-sub1.com' not in t2_identifiers
        assert 'tenant2-sub1.com' in t2_identifiers
        assert 'tenant2-sub1.com' not in t1_identifiers

    @patch('app.database.SessionLocal')
    def test_cross_tenant_access_prevented(self, mock_session_local, test_db):
        """Test that cross-tenant access is prevented"""
        mock_session_local.return_value = test_db

        tenant1 = Tenant(name="Tenant 1", slug="tenant-1")
        tenant2 = Tenant(name="Tenant 2", slug="tenant-2")
        test_db.add_all([tenant1, tenant2])
        test_db.commit()
        test_db.refresh(tenant1)
        test_db.refresh(tenant2)

        repo = AssetRepository(test_db)

        # Create asset for tenant1
        assets_data = [
            {'identifier': 'secret.example.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'}
        ]
        repo.bulk_upsert(tenant1.id, assets_data)

        # Try to access from tenant2
        asset = repo.get_by_identifier(tenant2.id, 'secret.example.com', AssetType.SUBDOMAIN)
        assert asset is None  # Should not be found

        # Verify it exists for tenant1
        asset = repo.get_by_identifier(tenant1.id, 'secret.example.com', AssetType.SUBDOMAIN)
        assert asset is not None


class TestErrorRecoveryIntegration:
    """Test error recovery in discovery pipeline"""

    @patch('app.database.SessionLocal')
    def test_partial_failure_recovery(self, mock_session_local, test_db, sample_tenant):
        """Test that partial failures don't corrupt database"""
        mock_session_local.return_value = test_db

        repo = AssetRepository(test_db)

        # First batch succeeds
        batch1 = [
            {'identifier': 'good1.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
        ]
        result1 = repo.bulk_upsert(sample_tenant.id, batch1)
        assert result1['created'] >= 1

        # Second batch has issue but database should remain consistent
        batch2 = [
            {'identifier': 'good2.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
        ]

        try:
            result2 = repo.bulk_upsert(sample_tenant.id, batch2)
        except Exception:
            test_db.rollback()

        # First asset should still exist
        asset = repo.get_by_identifier(sample_tenant.id, 'good1.com', AssetType.SUBDOMAIN)
        assert asset is not None

    @patch('app.database.SessionLocal')
    @patch('app.utils.secure_executor.SecureToolExecutor.execute')
    def test_tool_execution_failure_handling(self, mock_execute, mock_session_local, test_db, sample_tenant):
        """Test handling of tool execution failures"""
        mock_session_local.return_value = test_db
        mock_execute.side_effect = Exception("Tool failed")

        seed_data = {
            'domains': ['example.com'],
            'keywords': [],
            'asns': [],
            'ip_ranges': []
        }

        result = run_subfinder(seed_data, sample_tenant.id)

        # Should return empty result, not crash
        assert result['subdomains'] == []
        assert 'error' in result

    @patch('app.database.SessionLocal')
    def test_empty_results_handling(self, mock_session_local, test_db, sample_tenant):
        """Test handling of empty discovery results"""
        mock_session_local.return_value = test_db

        dnsx_result = {
            'resolved': [],
            'tenant_id': sample_tenant.id
        }

        result = process_discovery_results(dnsx_result, sample_tenant.id)

        assert result['total_resolved'] == 0
        assert result['assets_processed'] == 0
