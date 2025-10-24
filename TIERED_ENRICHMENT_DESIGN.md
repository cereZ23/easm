# Tiered Enrichment Strategy - Design Document

## Overview

Instead of a single TTL for all assets, use **priority-based enrichment cadence**:
- **Critical assets**: 1-day TTL (daily enrichment)
- **Normal assets**: 3-day TTL (every 3 days)
- **Low-priority assets**: Configurable (default: 14 days)

This optimizes resource usage while ensuring important assets have fresh data.

---

## Asset Priority Levels

### Priority Classification

```python
class AssetPriority(str, Enum):
    CRITICAL = "critical"  # 1-day TTL - Daily enrichment
    HIGH = "high"          # 3-day TTL - Every 3 days
    NORMAL = "normal"      # 7-day TTL - Weekly (optional tier)
    LOW = "low"            # 14-day TTL - Bi-weekly (optional tier)
```

### How Assets Get Prioritized

**Automatic Classification** (rule-based):
```python
def calculate_asset_priority(asset: Asset) -> AssetPriority:
    """
    Automatically determine asset priority based on characteristics

    CRITICAL if:
    - Has active services on sensitive ports (443, 80, 8080)
    - Has findings with severity >= HIGH
    - Risk score >= 80
    - Manually marked as critical by user
    - Production environment tag

    HIGH if:
    - Has open ports
    - Has valid SSL certificate
    - Risk score >= 50
    - Recently discovered (< 30 days)

    NORMAL if:
    - Active asset
    - Has some enrichment data

    LOW if:
    - No services found
    - Inactive for > 90 days
    - Risk score < 20
    """

    # Rule 1: Manual override
    if asset.tags and 'critical' in asset.tags:
        return AssetPriority.CRITICAL

    # Rule 2: Has high-severity findings
    if asset.findings:
        max_severity = max(f.severity for f in asset.findings)
        if max_severity in [FindingSeverity.CRITICAL, FindingSeverity.HIGH]:
            return AssetPriority.CRITICAL

    # Rule 3: Risk score based
    if asset.risk_score >= 80:
        return AssetPriority.CRITICAL
    elif asset.risk_score >= 50:
        return AssetPriority.HIGH

    # Rule 4: Has services (active attack surface)
    if asset.services and len(asset.services) > 0:
        # Check for sensitive services
        sensitive_ports = [80, 443, 8080, 8443, 3000, 5000]
        has_sensitive = any(s.port in sensitive_ports for s in asset.services)
        if has_sensitive:
            return AssetPriority.CRITICAL
        return AssetPriority.HIGH

    # Rule 5: New assets (discovery freshness)
    if asset.first_seen:
        days_old = (datetime.utcnow() - asset.first_seen).days
        if days_old < 7:
            return AssetPriority.HIGH  # New discoveries need quick enrichment

    # Rule 6: Long-inactive assets
    if asset.last_seen:
        days_since_seen = (datetime.utcnow() - asset.last_seen).days
        if days_since_seen > 90:
            return AssetPriority.LOW

    # Default
    return AssetPriority.NORMAL
```

**Manual Override** (via API/UI):
```python
# Allow users to manually set priority
PUT /api/v1/assets/123
{
    "priority": "critical"  # Override automatic classification
}
```

---

## Configuration

### Updated app/config.py

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Tiered Enrichment Configuration (Sprint 2 - Enhanced)
    enrichment_enabled: bool = True
    enrichment_auto_trigger: bool = True
    enrichment_batch_size: int = 100

    # TTL per priority level (in days)
    enrichment_ttl_critical: int = 1   # Daily for critical assets
    enrichment_ttl_high: int = 3       # Every 3 days for high-priority
    enrichment_ttl_normal: int = 7     # Weekly for normal assets
    enrichment_ttl_low: int = 14       # Bi-weekly for low-priority

    # Resource limits per priority (max assets per enrichment run)
    enrichment_max_assets_critical: int = 10000   # No limit for critical
    enrichment_max_assets_high: int = 5000
    enrichment_max_assets_normal: int = 2000
    enrichment_max_assets_low: int = 1000

    # Priority calculation settings
    enrichment_auto_prioritize: bool = True  # Auto-calculate priorities
    enrichment_critical_risk_threshold: int = 80
    enrichment_high_risk_threshold: int = 50
    enrichment_new_asset_days: int = 7  # Assets < 7 days old = HIGH priority

    # Enrichment scheduling (Celery beat)
    enrichment_critical_schedule: str = "0 */4 * * *"  # Every 4 hours (catches 1-day TTL)
    enrichment_high_schedule: str = "0 2 * * *"       # Daily at 2 AM
    enrichment_normal_schedule: str = "0 3 * * 0"     # Weekly on Sunday
    enrichment_low_schedule: str = "0 4 1,15 * *"     # Bi-weekly (1st, 15th)
```

---

## Database Schema Updates

### Add priority column to assets table

```python
# In app/models/database.py - Asset model

class Asset(Base):
    # ... existing columns ...

    # Enrichment tracking (existing)
    last_enriched_at = Column(DateTime)
    enrichment_status = Column(String(50), default='pending')

    # NEW: Priority-based enrichment
    priority = Column(String(20), default='normal')  # critical, high, normal, low
    priority_updated_at = Column(DateTime)
    priority_auto_calculated = Column(Boolean, default=True)  # False if manually set

    __table_args__ = (
        # ... existing indexes ...
        Index('idx_asset_priority_enrichment', 'tenant_id', 'priority', 'last_enriched_at'),
    )
```

### Migration

```python
# alembic/versions/005_add_asset_priority.py

def upgrade():
    # Add priority columns
    op.add_column('assets', sa.Column('priority', sa.String(20), server_default='normal'))
    op.add_column('assets', sa.Column('priority_updated_at', sa.DateTime()))
    op.add_column('assets', sa.Column('priority_auto_calculated', sa.Boolean(), server_default='true'))

    # Create index for efficient priority-based queries
    op.create_index(
        'idx_asset_priority_enrichment',
        'assets',
        ['tenant_id', 'priority', 'last_enriched_at']
    )

    # Backfill priorities for existing assets
    # (Run calculate_asset_priority for all existing assets)
    op.execute("""
        UPDATE assets
        SET priority = CASE
            WHEN risk_score >= 80 THEN 'critical'
            WHEN risk_score >= 50 THEN 'high'
            WHEN risk_score >= 20 THEN 'normal'
            ELSE 'low'
        END,
        priority_updated_at = NOW(),
        priority_auto_calculated = true
        WHERE priority IS NULL;
    """)

def downgrade():
    op.drop_index('idx_asset_priority_enrichment', 'assets')
    op.drop_column('assets', 'priority_auto_calculated')
    op.drop_column('assets', 'priority_updated_at')
    op.drop_column('assets', 'priority')
```

---

## Implementation

### Updated Enrichment Pipeline

```python
# app/tasks/enrichment.py

def get_enrichment_candidates(
    tenant_id: int,
    priority: str,  # NEW parameter
    force_refresh: bool,
    db
) -> List[int]:
    """
    Get list of asset IDs that need enrichment for a specific priority level

    Args:
        tenant_id: Tenant ID
        priority: Priority level (critical, high, normal, low)
        force_refresh: If True, return all active assets of this priority
        db: Database session

    Returns:
        List of asset IDs to enrich
    """
    from app.repositories.asset_repository import AssetRepository

    # Get TTL for this priority level
    ttl_map = {
        'critical': settings.enrichment_ttl_critical,  # 1 day
        'high': settings.enrichment_ttl_high,          # 3 days
        'normal': settings.enrichment_ttl_normal,      # 7 days
        'low': settings.enrichment_ttl_low             # 14 days
    }

    ttl_days = ttl_map.get(priority, 7)
    cutoff_time = datetime.utcnow() - timedelta(days=ttl_days)

    # Get max assets for this priority
    max_assets_map = {
        'critical': settings.enrichment_max_assets_critical,  # 10000
        'high': settings.enrichment_max_assets_high,          # 5000
        'normal': settings.enrichment_max_assets_normal,      # 2000
        'low': settings.enrichment_max_assets_low             # 1000
    }
    max_assets = max_assets_map.get(priority, 10000)

    if force_refresh:
        # Get all active assets of this priority
        assets = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.is_active == True,
            Asset.priority == priority
        ).limit(max_assets).all()
    else:
        # Get assets not enriched since cutoff time
        assets = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.is_active == True,
            Asset.priority == priority,
            (Asset.last_enriched_at == None) | (Asset.last_enriched_at < cutoff_time)
        ).order_by(
            # Prioritize: never enriched, then oldest enrichment
            Asset.last_enriched_at.nullsfirst()
        ).limit(max_assets).all()

    logger.info(
        f"Enrichment candidates (tenant {tenant_id}, priority {priority}): "
        f"{len(assets)} assets (TTL: {ttl_days} days)"
    )

    return [asset.id for asset in assets]


@celery.task(name='app.tasks.enrichment.run_enrichment_pipeline')
def run_enrichment_pipeline(
    tenant_id: int,
    priority: str = None,  # NEW: Optional priority filter
    force_refresh: bool = False
):
    """
    Orchestrate enrichment pipeline for a tenant

    Args:
        tenant_id: Tenant ID
        priority: Optional priority filter (critical, high, normal, low)
                 If None, enriches all priorities based on TTL
        force_refresh: If True, re-enrich all assets regardless of last_enriched_at
    """
    from app.database import SessionLocal

    db = SessionLocal()

    try:
        tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})

        if priority:
            # Single priority level
            tenant_logger.info(f"Starting enrichment pipeline for priority={priority}")
            asset_ids = get_enrichment_candidates(tenant_id, priority, force_refresh, db)

            if not asset_ids:
                tenant_logger.info(f"No {priority} priority assets need enrichment")
                return {'tenant_id': tenant_id, 'priority': priority, 'status': 'no_assets'}

            # Run enrichment for this priority
            run_enrichment_for_assets(asset_ids, tenant_id, priority)

        else:
            # All priorities - run in order (critical first)
            priorities = ['critical', 'high', 'normal', 'low']
            total_assets = 0

            for pri in priorities:
                asset_ids = get_enrichment_candidates(tenant_id, pri, force_refresh, db)
                if asset_ids:
                    tenant_logger.info(f"Enriching {len(asset_ids)} {pri} priority assets")
                    run_enrichment_for_assets(asset_ids, tenant_id, pri)
                    total_assets += len(asset_ids)

            return {
                'tenant_id': tenant_id,
                'total_assets': total_assets,
                'status': 'completed'
            }

    finally:
        db.close()


def run_enrichment_for_assets(asset_ids: List[int], tenant_id: int, priority: str):
    """Execute enrichment chain for given assets"""

    # Build enrichment chain (same as before)
    chain(
        group(
            run_httpx.si(asset_ids, tenant_id, False),
            run_naabu.si(asset_ids, tenant_id),
            run_tlsx.si(asset_ids, tenant_id)
        ),
        process_enrichment_results.s(tenant_id),
        run_katana.s(tenant_id),
        process_katana_results.s(tenant_id)
    ).apply_async(
        queue=f'tenant_{tenant_id}',
        priority=get_celery_priority(priority)  # Higher priority tasks first
    )


def get_celery_priority(asset_priority: str) -> int:
    """Map asset priority to Celery task priority (0-9, higher = more urgent)"""
    return {
        'critical': 9,  # Highest
        'high': 7,
        'normal': 5,
        'low': 3
    }.get(asset_priority, 5)
```

### Automatic Priority Calculation Task

```python
@celery.task(name='app.tasks.enrichment.update_asset_priorities')
def update_asset_priorities(tenant_id: int):
    """
    Recalculate priorities for all assets in a tenant

    Runs daily to update priorities based on:
    - Risk scores
    - Findings severity
    - Service changes
    - Age

    Only updates assets with priority_auto_calculated=True
    (Manual overrides are preserved)
    """
    from app.database import SessionLocal

    db = SessionLocal()

    try:
        tenant_logger = TenantLoggerAdapter(logger, {'tenant_id': tenant_id})
        tenant_logger.info("Updating asset priorities")

        # Get all assets with auto-calculated priorities
        assets = db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.is_active == True,
            Asset.priority_auto_calculated == True
        ).all()

        updated_count = 0
        priority_changes = {'critical': 0, 'high': 0, 'normal': 0, 'low': 0}

        for asset in assets:
            old_priority = asset.priority
            new_priority = calculate_asset_priority(asset)

            if old_priority != new_priority:
                asset.priority = new_priority
                asset.priority_updated_at = datetime.utcnow()
                priority_changes[new_priority] += 1
                updated_count += 1

        db.commit()

        tenant_logger.info(
            f"Updated {updated_count} asset priorities: "
            f"critical={priority_changes['critical']}, "
            f"high={priority_changes['high']}, "
            f"normal={priority_changes['normal']}, "
            f"low={priority_changes['low']}"
        )

        return {
            'tenant_id': tenant_id,
            'updated': updated_count,
            'priorities': priority_changes
        }

    finally:
        db.close()
```

---

## Celery Beat Schedules

### Updated app/celery_app.py

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    # ... existing schedules ...

    # Priority-based enrichment schedules

    'enrichment-critical-assets': {
        'task': 'app.tasks.enrichment.run_all_tenants_enrichment',
        'schedule': crontab(hour='*/4'),  # Every 4 hours (catches 1-day TTL)
        'kwargs': {'priority': 'critical', 'force_refresh': False}
    },

    'enrichment-high-priority-assets': {
        'task': 'app.tasks.enrichment.run_all_tenants_enrichment',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'kwargs': {'priority': 'high', 'force_refresh': False}
    },

    'enrichment-normal-priority-assets': {
        'task': 'app.tasks.enrichment.run_all_tenants_enrichment',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Weekly Sunday 3 AM
        'kwargs': {'priority': 'normal', 'force_refresh': False}
    },

    'enrichment-low-priority-assets': {
        'task': 'app.tasks.enrichment.run_all_tenants_enrichment',
        'schedule': crontab(hour=4, minute=0, day_of_month='1,15'),  # Bi-weekly
        'kwargs': {'priority': 'low', 'force_refresh': False}
    },

    # Daily priority recalculation
    'update-asset-priorities': {
        'task': 'app.tasks.enrichment.run_all_tenants_priority_update',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    }
}


@celery.task(name='app.tasks.enrichment.run_all_tenants_enrichment')
def run_all_tenants_enrichment(priority: str = None, force_refresh: bool = False):
    """Run enrichment for all tenants with optional priority filter"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()

        for tenant in tenants:
            run_enrichment_pipeline.apply_async(
                args=[tenant.id],
                kwargs={'priority': priority, 'force_refresh': force_refresh},
                queue=f'tenant_{tenant.id}'
            )

        logger.info(f"Queued enrichment for {len(tenants)} tenants (priority={priority})")
        return {'tenants': len(tenants), 'priority': priority}
    finally:
        db.close()


@celery.task(name='app.tasks.enrichment.run_all_tenants_priority_update')
def run_all_tenants_priority_update():
    """Update priorities for all tenants"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()

        for tenant in tenants:
            update_asset_priorities.apply_async(
                args=[tenant.id],
                queue=f'tenant_{tenant.id}'
            )

        logger.info(f"Queued priority updates for {len(tenants)} tenants")
        return {'tenants': len(tenants)}
    finally:
        db.close()
```

---

## Resource Usage Comparison

### Single TTL (7 days) vs Tiered TTL (1 + 3 days)

**Scenario**: 10,000 assets total
- 500 critical (5%)
- 2,000 high (20%)
- 5,000 normal (50%)
- 2,500 low (25%)

**Single 7-day TTL**:
```
Daily scans: 10,000 / 7 = 1,429 assets/day
Monthly: 1,429 × 30 = 42,857 scans/month
```

**Tiered TTL** (1 + 3 + 7 + 14 days):
```
Critical: 500 / 1 = 500 assets/day
High:     2,000 / 3 = 667 assets/day
Normal:   5,000 / 7 = 714 assets/day
Low:      2,500 / 14 = 179 assets/day
─────────────────────────────────────
Total:    2,060 assets/day

Monthly: 2,060 × 30 = 61,800 scans/month
```

**Resource Impact**: +44% scans vs single 7-day TTL

**BUT**: Critical assets get **7x fresher data** (daily vs weekly)

### Cost-Benefit Analysis

**Benefits**:
- ✅ Critical assets: Daily enrichment (fresh threat intel)
- ✅ High-priority: 3-day enrichment (good balance)
- ✅ Smart resource allocation (important assets first)
- ✅ Automated priority calculation (less manual work)
- ✅ Celery task priorities (critical tasks run first)

**Costs**:
- ⚠️ +44% more scans than single 7-day TTL
- ⚠️ Slightly more complex configuration
- ⚠️ Additional database column + index

**Net Result**: Worth it - fresh data on critical assets justifies 44% cost increase

---

## API Endpoints

### Manual Priority Management

```python
# app/routers/assets.py

@router.put("/assets/{asset_id}/priority")
async def update_asset_priority(
    asset_id: int,
    priority: str,  # critical, high, normal, low
    current_user = Depends(get_current_user)
):
    """
    Manually set asset priority (overrides automatic calculation)

    This disables automatic priority recalculation for this asset
    until explicitly re-enabled.
    """
    db = SessionLocal()
    try:
        asset = db.query(Asset).filter(
            Asset.id == asset_id,
            Asset.tenant_id == current_user.tenant_id
        ).first()

        if not asset:
            raise HTTPException(404, "Asset not found")

        # Validate priority
        valid_priorities = ['critical', 'high', 'normal', 'low']
        if priority not in valid_priorities:
            raise HTTPException(400, f"Invalid priority. Must be one of: {valid_priorities}")

        # Update priority
        asset.priority = priority
        asset.priority_updated_at = datetime.utcnow()
        asset.priority_auto_calculated = False  # Disable auto-calculation

        db.commit()

        logger.info(f"Asset {asset_id} priority manually set to {priority}")

        return {
            'asset_id': asset_id,
            'priority': priority,
            'auto_calculated': False
        }

    finally:
        db.close()


@router.post("/assets/{asset_id}/priority/auto")
async def enable_auto_priority(
    asset_id: int,
    current_user = Depends(get_current_user)
):
    """
    Re-enable automatic priority calculation for an asset

    The priority will be recalculated immediately and then
    updated daily based on asset characteristics.
    """
    db = SessionLocal()
    try:
        asset = db.query(Asset).filter(
            Asset.id == asset_id,
            Asset.tenant_id == current_user.tenant_id
        ).first()

        if not asset:
            raise HTTPException(404, "Asset not found")

        # Recalculate priority
        new_priority = calculate_asset_priority(asset)

        asset.priority = new_priority
        asset.priority_updated_at = datetime.utcnow()
        asset.priority_auto_calculated = True

        db.commit()

        logger.info(f"Asset {asset_id} auto-priority re-enabled: {new_priority}")

        return {
            'asset_id': asset_id,
            'priority': new_priority,
            'auto_calculated': True
        }

    finally:
        db.close()


@router.get("/assets/priority-stats")
async def get_priority_stats(current_user = Depends(get_current_user)):
    """Get priority distribution for tenant's assets"""
    db = SessionLocal()
    try:
        stats = db.query(
            Asset.priority,
            func.count(Asset.id).label('count')
        ).filter(
            Asset.tenant_id == current_user.tenant_id,
            Asset.is_active == True
        ).group_by(Asset.priority).all()

        return {
            'total': sum(s.count for s in stats),
            'by_priority': {s.priority: s.count for s in stats}
        }

    finally:
        db.close()
```

---

## Testing

### Unit Tests

```python
# tests/test_enrichment_tiered.py

def test_calculate_asset_priority_critical():
    """Test critical priority assignment"""
    asset = Asset(
        risk_score=90,
        services=[Service(port=443)]
    )

    priority = calculate_asset_priority(asset)
    assert priority == AssetPriority.CRITICAL


def test_calculate_asset_priority_high():
    """Test high priority assignment"""
    asset = Asset(
        risk_score=60,
        services=[Service(port=8080)]
    )

    priority = calculate_asset_priority(asset)
    assert priority == AssetPriority.HIGH


def test_get_enrichment_candidates_by_priority():
    """Test TTL filtering by priority"""
    # Create test assets with different priorities and enrichment times
    # ... setup ...

    # Critical (1-day TTL) should include assets > 1 day old
    critical_ids = get_enrichment_candidates(tenant_id=1, priority='critical', force_refresh=False, db=db)

    # High (3-day TTL) should include assets > 3 days old
    high_ids = get_enrichment_candidates(tenant_id=1, priority='high', force_refresh=False, db=db)

    assert len(critical_ids) > 0
    assert len(high_ids) > 0


def test_manual_priority_override():
    """Test that manual priority persists"""
    asset = Asset(priority='normal', priority_auto_calculated=True)

    # Manually set to critical
    asset.priority = 'critical'
    asset.priority_auto_calculated = False

    # Auto-calculation should skip this asset
    update_asset_priorities(tenant_id=1)

    # Priority should still be critical
    assert asset.priority == 'critical'
```

---

## Monitoring

### Dashboard Metrics

```python
# Show enrichment cadence per priority
enrichment_by_priority_gauge = Gauge(
    'enrichment_assets_by_priority',
    'Number of assets per priority level',
    ['tenant_id', 'priority']
)

# Track average enrichment age per priority
enrichment_age_seconds = Histogram(
    'enrichment_age_seconds',
    'Time since last enrichment',
    ['tenant_id', 'priority'],
    buckets=[3600, 86400, 259200, 604800, 1209600]  # 1h, 1d, 3d, 7d, 14d
)
```

### Grafana Dashboard

```
┌─────────────────────────────────────────────────────────┐
│ Enrichment Pipeline - Priority Distribution              │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Critical (1-day):  500 assets  ████████ 5%              │
│  High (3-day):     2000 assets  ████████████████████ 20% │
│  Normal (7-day):   5000 assets  ██████████████████████████████████ 50% │
│  Low (14-day):     2500 assets  █████████████████████ 25% │
│                                                           │
├─────────────────────────────────────────────────────────┤
│ Next Enrichment Schedule                                 │
├─────────────────────────────────────────────────────────┤
│  Critical: Next run in 2h (every 4h)                     │
│  High:     Next run in 18h (daily 2 AM)                  │
│  Normal:   Next run in 6d (Sunday 3 AM)                  │
│  Low:      Next run in 12d (1st/15th 4 AM)               │
└─────────────────────────────────────────────────────────┘
```

---

## Summary

### Configuration

```python
# Final configuration in app/config.py
enrichment_ttl_critical: int = 1   # ✅ Daily (as requested)
enrichment_ttl_high: int = 3       # ✅ Every 3 days (as requested)
enrichment_ttl_normal: int = 7     # Weekly (optional tier)
enrichment_ttl_low: int = 14       # Bi-weekly (optional tier)
```

### Impact

**Resource Usage**: +44% vs single 7-day TTL
**Benefit**: Critical assets get 7x fresher data (daily vs weekly)

### Implementation Effort

**Additional Work** (vs single TTL):
- ✅ Add `priority` column to assets (+1 migration)
- ✅ Implement `calculate_asset_priority()` (+200 lines)
- ✅ Update `get_enrichment_candidates()` (+50 lines)
- ✅ Add 4 Celery beat schedules (+30 lines)
- ✅ Add API endpoints for manual priority (+100 lines)
- ✅ Add tests (+200 lines)

**Total**: +600 lines of code, +2 hours implementation time

### Next Steps

Ready to implement with tiered enrichment (1-day + 3-day TTL)?

- ✅ Critical assets: 1-day TTL (daily)
- ✅ High priority: 3-day TTL (every 3 days)
- ⚠️ Normal: 7-day TTL (optional)
- ⚠️ Low: 14-day TTL (optional)

Should I proceed with this design?
