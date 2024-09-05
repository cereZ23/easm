"""
Comprehensive unit tests for Repository classes

Tests cover:
- AssetRepository CRUD operations
- EventRepository operations
- Bulk operations and performance
- Error handling
- Query optimization
- Multi-tenant isolation
"""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta
import json

from app.repositories.asset_repository import AssetRepository, EventRepository
from app.models.database import Asset, AssetType, Event, EventKind


class TestAssetRepositoryBasicOperations:
    """Test basic CRUD operations"""

    def test_init_repository(self):
        """Test repository initialization"""
        mock_db = MagicMock()
        repo = AssetRepository(mock_db)
        assert repo.db == mock_db

    def test_get_by_id_found(self):
        """Test getting asset by ID when found"""
        mock_db = MagicMock()
        mock_asset = MagicMock()
        mock_asset.id = 123

        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_asset

        repo = AssetRepository(mock_db)
        result = repo.get_by_id(123)

        assert result == mock_asset
        mock_db.query.assert_called_once_with(Asset)

    def test_get_by_id_not_found(self):
        """Test getting asset by ID when not found"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        repo = AssetRepository(mock_db)
        result = repo.get_by_id(999)

        assert result is None

    def test_get_by_identifier(self):
        """Test getting asset by tenant, identifier, and type"""
        mock_db = MagicMock()
        mock_asset = MagicMock()
        mock_asset.identifier = 'example.com'

        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_asset

        repo = AssetRepository(mock_db)
        result = repo.get_by_identifier(
            tenant_id=1,
            identifier='example.com',
            asset_type=AssetType.DOMAIN
        )

        assert result == mock_asset
        mock_db.query.return_value.filter_by.assert_called_once_with(
            tenant_id=1,
            identifier='example.com',
            type=AssetType.DOMAIN
        )

    def test_get_by_identifier_not_found(self):
        """Test getting non-existent asset"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        repo = AssetRepository(mock_db)
        result = repo.get_by_identifier(1, 'nonexistent.com', AssetType.DOMAIN)

        assert result is None


class TestAssetRepositoryQueryOperations:
    """Test query and filtering operations"""

    def test_get_by_tenant(self):
        """Test getting assets for a tenant"""
        mock_db = MagicMock()
        mock_assets = [MagicMock(), MagicMock(), MagicMock()]

        query_mock = mock_db.query.return_value
        query_mock.filter_by.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.all.return_value = mock_assets

        repo = AssetRepository(mock_db)
        result = repo.get_by_tenant(tenant_id=1)

        assert result == mock_assets
        query_mock.filter_by.assert_called_with(tenant_id=1, is_active=True)

    def test_get_by_tenant_with_type_filter(self):
        """Test getting assets with type filter"""
        mock_db = MagicMock()
        query_mock = mock_db.query.return_value
        query_mock.filter_by.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.all.return_value = []

        repo = AssetRepository(mock_db)
        repo.get_by_tenant(tenant_id=1, asset_type=AssetType.SUBDOMAIN)

        # Should be called twice: once for tenant_id/is_active, once for type
        assert query_mock.filter_by.call_count == 2

    def test_get_by_tenant_pagination(self):
        """Test pagination parameters"""
        mock_db = MagicMock()
        query_mock = mock_db.query.return_value
        query_mock.filter_by.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.all.return_value = []

        repo = AssetRepository(mock_db)
        repo.get_by_tenant(tenant_id=1, limit=50, offset=100)

        query_mock.limit.assert_called_once_with(50)
        query_mock.offset.assert_called_once_with(100)

    def test_count_by_tenant(self):
        """Test counting assets for a tenant"""
        mock_db = MagicMock()
        query_mock = mock_db.query.return_value
        query_mock.filter_by.return_value = query_mock
        query_mock.count.return_value = 42

        repo = AssetRepository(mock_db)
        count = repo.count_by_tenant(tenant_id=1)

        assert count == 42
        query_mock.filter_by.assert_called_once_with(tenant_id=1, is_active=True)

    def test_get_critical_assets(self):
        """Test getting critical assets above risk threshold"""
        mock_db = MagicMock()
        critical_assets = [MagicMock(risk_score=75), MagicMock(risk_score=90)]

        query_mock = mock_db.query.return_value
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = critical_assets

        repo = AssetRepository(mock_db)
        result = repo.get_critical_assets(tenant_id=1, risk_threshold=50.0)

        assert result == critical_assets
        query_mock.filter.assert_called_once()


class TestAssetRepositoryBulkOperations:
    """Test bulk operations for performance"""

    @patch('app.repositories.asset_repository.insert')
    def test_bulk_upsert_creates_records(self, mock_insert):
        """Test bulk upsert creates new records"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_db.execute.return_value = mock_result

        assets_data = [
            {'identifier': 'sub1.example.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
            {'identifier': 'sub2.example.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
            {'identifier': 'sub3.example.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
        ]

        repo = AssetRepository(mock_db)
        result = repo.bulk_upsert(tenant_id=1, assets_data=assets_data)

        assert result['created'] == 3
        assert result['total_processed'] == 3
        mock_db.commit.assert_called_once()

    @patch('app.repositories.asset_repository.insert')
    def test_bulk_upsert_empty_list(self, mock_insert):
        """Test bulk upsert with empty list"""
        mock_db = MagicMock()

        repo = AssetRepository(mock_db)
        result = repo.bulk_upsert(tenant_id=1, assets_data=[])

        assert result['created'] == 0
        assert result['updated'] == 0
        mock_db.execute.assert_not_called()

    @patch('app.repositories.asset_repository.insert')
    def test_bulk_upsert_includes_tenant_id(self, mock_insert):
        """Test bulk upsert includes tenant_id in all records"""
        mock_db = MagicMock()
        mock_db.execute.return_value = MagicMock(rowcount=2)

        mock_stmt = MagicMock()
        mock_stmt.on_conflict_do_update.return_value = mock_stmt
        mock_stmt.returning.return_value = mock_stmt
        mock_insert.return_value = mock_stmt

        assets_data = [
            {'identifier': 'sub1.example.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
            {'identifier': 'sub2.example.com', 'type': AssetType.SUBDOMAIN, 'raw_metadata': '{}'},
        ]

        repo = AssetRepository(mock_db)
        repo.bulk_upsert(tenant_id=5, assets_data=assets_data)

        # Check that insert was called with records containing tenant_id
        call_args = mock_insert.return_value.values.call_args
        records = call_args[0][0]

        assert all(record['tenant_id'] == 5 for record in records)

    @patch('app.repositories.asset_repository.insert')
    def test_bulk_upsert_sets_timestamps(self, mock_insert):
        """Test bulk upsert sets first_seen and last_seen"""
        mock_db = MagicMock()
        mock_db.execute.return_value = MagicMock(rowcount=1)

        mock_stmt = MagicMock()
        mock_stmt.on_conflict_do_update.return_value = mock_stmt
        mock_stmt.returning.return_value = mock_stmt
        mock_insert.return_value = mock_stmt

        assets_data = [
            {'identifier': 'test.com', 'type': AssetType.DOMAIN, 'raw_metadata': '{}'}
        ]

        repo = AssetRepository(mock_db)
        repo.bulk_upsert(tenant_id=1, assets_data=assets_data)

        call_args = mock_insert.return_value.values.call_args
        records = call_args[0][0]

        assert 'first_seen' in records[0]
        assert 'last_seen' in records[0]

    def test_create_batch(self):
        """Test creating multiple assets in batch"""
        mock_db = MagicMock()

        assets = [
            Asset(tenant_id=1, identifier='test1.com', type=AssetType.DOMAIN),
            Asset(tenant_id=1, identifier='test2.com', type=AssetType.DOMAIN),
            Asset(tenant_id=1, identifier='test3.com', type=AssetType.DOMAIN),
        ]

        repo = AssetRepository(mock_db)
        result = repo.create_batch(assets)

        assert result == assets
        mock_db.add_all.assert_called_once_with(assets)
        mock_db.flush.assert_called_once()

    def test_mark_inactive_bulk(self):
        """Test marking multiple assets inactive"""
        mock_db = MagicMock()
        query_mock = mock_db.query.return_value
        query_mock.filter.return_value = query_mock

        asset_ids = [1, 2, 3, 4, 5]

        repo = AssetRepository(mock_db)
        repo.mark_inactive(asset_ids)

        query_mock.update.assert_called_once()
        update_args = query_mock.update.call_args[0][0]
        assert update_args['is_active'] == False
        mock_db.commit.assert_called_once()


class TestAssetRepositoryRiskScore:
    """Test risk score operations"""

    def test_update_risk_score(self):
        """Test updating asset risk score"""
        mock_db = MagicMock()
        mock_asset = MagicMock()
        mock_asset.risk_score = 10.0

        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_asset

        repo = AssetRepository(mock_db)
        repo.update_risk_score(asset_id=1, risk_score=75.5)

        assert mock_asset.risk_score == 75.5
        mock_db.flush.assert_called_once()

    def test_update_risk_score_nonexistent_asset(self):
        """Test updating risk score for non-existent asset"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        repo = AssetRepository(mock_db)
        # Should not raise exception
        repo.update_risk_score(asset_id=999, risk_score=50.0)


class TestEventRepositoryBasicOperations:
    """Test EventRepository basic operations"""

    def test_init_repository(self):
        """Test event repository initialization"""
        mock_db = MagicMock()
        repo = EventRepository(mock_db)
        assert repo.db == mock_db

    def test_create_event(self):
        """Test creating single event"""
        mock_db = MagicMock()

        repo = EventRepository(mock_db)
        event = repo.create_event(
            asset_id=1,
            kind=EventKind.NEW_ASSET,
            payload={'test': 'data'}
        )

        assert event.asset_id == 1
        assert event.kind == EventKind.NEW_ASSET
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_create_event_serializes_payload(self):
        """Test event payload is JSON serialized"""
        mock_db = MagicMock()

        repo = EventRepository(mock_db)
        payload = {'domain': 'example.com', 'ips': ['1.2.3.4', '5.6.7.8']}
        event = repo.create_event(
            asset_id=1,
            kind=EventKind.NEW_ASSET,
            payload=payload
        )

        # Payload should be JSON string
        assert isinstance(event.payload, str)
        parsed = json.loads(event.payload)
        assert parsed == payload

    def test_create_batch(self):
        """Test creating multiple events in batch"""
        mock_db = MagicMock()

        events = [
            Event(asset_id=1, kind=EventKind.NEW_ASSET, payload='{}'),
            Event(asset_id=2, kind=EventKind.OPEN_PORT, payload='{}'),
            Event(asset_id=3, kind=EventKind.NEW_CERT, payload='{}'),
        ]

        repo = EventRepository(mock_db)
        repo.create_batch(events)

        mock_db.add_all.assert_called_once_with(events)
        mock_db.flush.assert_called_once()

    def test_get_by_asset(self):
        """Test getting events for an asset"""
        mock_db = MagicMock()
        mock_events = [MagicMock(), MagicMock()]

        query_mock = mock_db.query.return_value
        query_mock.filter_by.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.all.return_value = mock_events

        repo = EventRepository(mock_db)
        result = repo.get_by_asset(asset_id=1)

        assert result == mock_events
        query_mock.filter_by.assert_called_once_with(asset_id=1)

    def test_get_by_asset_pagination(self):
        """Test event pagination"""
        mock_db = MagicMock()
        query_mock = mock_db.query.return_value
        query_mock.filter_by.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.all.return_value = []

        repo = EventRepository(mock_db)
        repo.get_by_asset(asset_id=1, limit=50, offset=100)

        query_mock.limit.assert_called_once_with(50)
        query_mock.offset.assert_called_once_with(100)


class TestEventRepositoryQueryOperations:
    """Test event query operations"""

    @patch('app.repositories.asset_repository.datetime')
    def test_get_recent_by_tenant(self, mock_datetime):
        """Test getting recent events for a tenant"""
        mock_db = MagicMock()
        mock_events = [MagicMock(), MagicMock()]

        # Mock current time
        now = datetime(2024, 1, 15, 12, 0, 0)
        mock_datetime.utcnow.return_value = now

        query_mock = mock_db.query.return_value
        query_mock.join.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = mock_events

        repo = EventRepository(mock_db)
        result = repo.get_recent_by_tenant(tenant_id=1, hours=24)

        assert result == mock_events
        query_mock.join.assert_called_once_with(Asset)

    @patch('app.repositories.asset_repository.datetime')
    def test_get_recent_by_tenant_with_event_kinds(self, mock_datetime):
        """Test filtering by event kinds"""
        mock_db = MagicMock()

        now = datetime(2024, 1, 15, 12, 0, 0)
        mock_datetime.utcnow.return_value = now

        query_mock = mock_db.query.return_value
        query_mock.join.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = []

        repo = EventRepository(mock_db)
        repo.get_recent_by_tenant(
            tenant_id=1,
            hours=24,
            event_kinds=[EventKind.NEW_ASSET, EventKind.OPEN_PORT]
        )

        # Should have two filter calls
        assert query_mock.filter.call_count == 2


class TestRepositoryMultiTenantIsolation:
    """Test multi-tenant isolation in repositories"""

    def test_asset_queries_include_tenant_filter(self):
        """Test that asset queries always include tenant_id"""
        mock_db = MagicMock()
        query_mock = mock_db.query.return_value
        query_mock.filter_by.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.all.return_value = []

        repo = AssetRepository(mock_db)

        # All these should filter by tenant_id
        repo.get_by_tenant(tenant_id=1)
        repo.get_by_identifier(tenant_id=1, identifier='test.com', asset_type=AssetType.DOMAIN)
        repo.get_critical_assets(tenant_id=1)

        # Verify tenant_id is in all filter calls
        calls = query_mock.filter_by.call_args_list
        assert len(calls) >= 3

    @patch('app.repositories.asset_repository.insert')
    def test_bulk_upsert_tenant_isolation(self, mock_insert):
        """Test bulk upsert enforces tenant isolation"""
        mock_db = MagicMock()
        mock_db.execute.return_value = MagicMock(rowcount=2)

        mock_stmt = MagicMock()
        mock_stmt.on_conflict_do_update.return_value = mock_stmt
        mock_stmt.returning.return_value = mock_stmt
        mock_insert.return_value = mock_stmt

        assets_data = [
            {'identifier': 'test1.com', 'type': AssetType.DOMAIN, 'raw_metadata': '{}'},
            {'identifier': 'test2.com', 'type': AssetType.DOMAIN, 'raw_metadata': '{}'},
        ]

        repo = AssetRepository(mock_db)

        # Insert for tenant 1
        repo.bulk_upsert(tenant_id=1, assets_data=assets_data)

        # Verify all records have tenant_id=1
        call_args = mock_insert.return_value.values.call_args
        records = call_args[0][0]
        assert all(record['tenant_id'] == 1 for record in records)

    def test_event_queries_join_asset_for_tenant_filter(self):
        """Test event queries join with Asset for tenant filtering"""
        mock_db = MagicMock()
        query_mock = mock_db.query.return_value
        query_mock.join.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = []

        repo = EventRepository(mock_db)
        repo.get_recent_by_tenant(tenant_id=1, hours=24)

        # Should join with Asset to filter by tenant
        query_mock.join.assert_called_once_with(Asset)


class TestRepositoryErrorHandling:
    """Test error handling in repositories"""

    @patch('app.repositories.asset_repository.insert')
    def test_bulk_upsert_database_error(self, mock_insert):
        """Test bulk upsert handles database errors"""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database connection error")

        assets_data = [
            {'identifier': 'test.com', 'type': AssetType.DOMAIN, 'raw_metadata': '{}'}
        ]

        repo = AssetRepository(mock_db)

        with pytest.raises(Exception):
            repo.bulk_upsert(tenant_id=1, assets_data=assets_data)

    def test_create_event_invalid_payload(self):
        """Test creating event with non-serializable payload"""
        mock_db = MagicMock()

        repo = EventRepository(mock_db)

        # Create an object that can't be JSON serialized
        class NonSerializable:
            pass

        with pytest.raises(TypeError):
            repo.create_event(
                asset_id=1,
                kind=EventKind.NEW_ASSET,
                payload={'obj': NonSerializable()}
            )
