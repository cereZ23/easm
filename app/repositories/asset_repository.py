"""
Repository pattern for Asset data access

Provides clean abstraction over database operations with:
- Bulk operations for performance
- Proper error handling
- Transaction management
- Query optimization
"""

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import and_, or_
from typing import List, Dict, Optional
from datetime import datetime
import json

from app.models.database import Asset, AssetType, Event, EventKind


class AssetRepository:
    """Repository for Asset entity operations"""

    def __init__(self, db: Session):
        """
        Initialize repository with database session

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_by_id(self, asset_id: int) -> Optional[Asset]:
        """Get asset by ID"""
        return self.db.query(Asset).filter_by(id=asset_id).first()

    def get_by_identifier(self, tenant_id: int, identifier: str, asset_type: AssetType) -> Optional[Asset]:
        """
        Get asset by tenant, identifier, and type

        Args:
            tenant_id: Tenant ID
            identifier: Asset identifier (domain, IP, URL)
            asset_type: Type of asset

        Returns:
            Asset if found, None otherwise
        """
        return self.db.query(Asset).filter_by(
            tenant_id=tenant_id,
            identifier=identifier,
            type=asset_type
        ).first()

    def get_by_tenant(
        self,
        tenant_id: int,
        asset_type: Optional[AssetType] = None,
        is_active: bool = True,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Asset]:
        """
        Get assets for a tenant with pagination

        Args:
            tenant_id: Tenant ID
            asset_type: Optional filter by asset type
            is_active: Filter by active status
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of assets
        """
        query = self.db.query(Asset).filter_by(tenant_id=tenant_id, is_active=is_active)

        if asset_type:
            query = query.filter_by(type=asset_type)

        return query.order_by(Asset.risk_score.desc()).limit(limit).offset(offset).all()

    def count_by_tenant(self, tenant_id: int, is_active: bool = True) -> int:
        """Count assets for a tenant"""
        return self.db.query(Asset).filter_by(tenant_id=tenant_id, is_active=is_active).count()

    def bulk_upsert(self, tenant_id: int, assets_data: List[Dict]) -> Dict[str, int]:
        """
        Bulk insert or update assets using PostgreSQL UPSERT

        This is much more efficient than individual inserts/updates.
        Uses PostgreSQL's ON CONFLICT DO UPDATE for atomic upserts.

        Args:
            tenant_id: Tenant ID
            assets_data: List of dicts with asset data
                Each dict should have: identifier, type, raw_metadata

        Returns:
            Dict with counts of created/updated assets
        """
        if not assets_data:
            return {'created': 0, 'updated': 0}

        # Prepare records for upsert
        records = []
        for data in assets_data:
            records.append({
                'tenant_id': tenant_id,
                'identifier': data['identifier'],
                'type': data['type'],
                'raw_metadata': data.get('raw_metadata'),
                'first_seen': datetime.utcnow(),
                'last_seen': datetime.utcnow(),
                'risk_score': data.get('risk_score', 0.0),
                'is_active': True
            })

        # Build UPSERT statement
        stmt = insert(Asset).values(records)

        # On conflict, update last_seen and metadata
        stmt = stmt.on_conflict_do_update(
            index_elements=['tenant_id', 'identifier', 'type'],
            set_={
                'last_seen': stmt.excluded.last_seen,
                'raw_metadata': stmt.excluded.raw_metadata,
                'is_active': stmt.excluded.is_active
            }
        ).returning(Asset.id)

        # Execute and get affected rows
        result = self.db.execute(stmt)
        affected = result.rowcount

        self.db.commit()

        # For simplicity, we return total affected
        # In production, you might want to track created vs updated separately
        return {
            'created': affected,  # Approximation
            'updated': 0,
            'total_processed': len(records)
        }

    def create_batch(self, assets: List[Asset]) -> List[Asset]:
        """
        Create multiple assets in a batch

        Args:
            assets: List of Asset objects to create

        Returns:
            List of created assets with IDs
        """
        self.db.add_all(assets)
        self.db.flush()  # Get IDs without committing
        return assets

    def update_risk_score(self, asset_id: int, risk_score: float):
        """Update asset risk score"""
        asset = self.get_by_id(asset_id)
        if asset:
            asset.risk_score = risk_score
            self.db.flush()

    def mark_inactive(self, asset_ids: List[int]):
        """
        Mark assets as inactive (bulk operation)

        Args:
            asset_ids: List of asset IDs to deactivate
        """
        self.db.query(Asset).filter(Asset.id.in_(asset_ids)).update(
            {'is_active': False},
            synchronize_session=False
        )
        self.db.commit()

    def get_critical_assets(self, tenant_id: int, risk_threshold: float = 50.0) -> List[Asset]:
        """
        Get critical assets above risk threshold

        Args:
            tenant_id: Tenant ID
            risk_threshold: Minimum risk score

        Returns:
            List of high-risk assets
        """
        return self.db.query(Asset).filter(
            and_(
                Asset.tenant_id == tenant_id,
                Asset.risk_score >= risk_threshold,
                Asset.is_active == True
            )
        ).order_by(Asset.risk_score.desc()).all()


class EventRepository:
    """Repository for Event entity operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_event(self, asset_id: int, kind: EventKind, payload: Dict) -> Event:
        """
        Create new event

        Args:
            asset_id: Asset ID
            kind: Event kind
            payload: Event payload data

        Returns:
            Created event
        """
        event = Event(
            asset_id=asset_id,
            kind=kind,
            payload=json.dumps(payload)
        )
        self.db.add(event)
        self.db.flush()
        return event

    def create_batch(self, events: List[Event]):
        """Create multiple events in batch"""
        self.db.add_all(events)
        self.db.flush()

    def get_by_asset(
        self,
        asset_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[Event]:
        """Get events for an asset"""
        return self.db.query(Event).filter_by(
            asset_id=asset_id
        ).order_by(Event.created_at.desc()).limit(limit).offset(offset).all()

    def get_recent_by_tenant(
        self,
        tenant_id: int,
        hours: int = 24,
        event_kinds: Optional[List[EventKind]] = None
    ) -> List[Event]:
        """
        Get recent events for a tenant

        Args:
            tenant_id: Tenant ID
            hours: Number of hours to look back
            event_kinds: Optional filter by event kinds

        Returns:
            List of recent events
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = self.db.query(Event).join(Asset).filter(
            and_(
                Asset.tenant_id == tenant_id,
                Event.created_at >= cutoff
            )
        )

        if event_kinds:
            query = query.filter(Event.kind.in_(event_kinds))

        return query.order_by(Event.created_at.desc()).all()
