# Rollback Procedure - Migration 004 (Enrichment Models)

## ⚠️ CRITICAL: Read Before Migration

This document provides step-by-step rollback procedures for migration 004 which adds enrichment models (certificates, endpoints) and priority-based scheduling.

**Migration Overview:**
- **Adds**: 2 new tables (certificates, endpoints)
- **Modifies**: assets table (+6 columns), services table (+10 columns)
- **Adds**: 6 new indexes
- **Risk Level**: MEDIUM (schema changes + data backfill)

---

## 📋 Pre-Migration Checklist

### 1. Verify Current State

```bash
# Check current migration version
cd /Users/cere/Downloads/easm
source venv/bin/activate
alembic current

# Expected output: 003_optimize_indexes
```

### 2. Create Full Database Backup

```bash
# Method 1: Docker-based backup (RECOMMENDED)
docker-compose exec postgres pg_dump -U easm -Fc easm > backups/easm_pre_004_$(date +%Y%m%d_%H%M%S).dump

# Method 2: Direct PostgreSQL backup (if Docker not running)
pg_dump -h localhost -p 15432 -U easm -Fc easm > backups/easm_pre_004_$(date +%Y%m%d_%H%M%S).dump

# Verify backup was created
ls -lh backups/
```

### 3. Document Current Table Counts

```bash
# Connect to database
docker-compose exec postgres psql -U easm -d easm

# Run these queries and save output
SELECT
    'assets' as table_name,
    COUNT(*) as row_count,
    pg_size_pretty(pg_total_relation_size('assets')) as total_size
FROM assets
UNION ALL
SELECT
    'services',
    COUNT(*),
    pg_size_pretty(pg_total_relation_size('services'))
FROM services;

# Save column list for verification
\d assets
\d services

# Exit psql
\q
```

**Save this output for verification after rollback!**

### 4. Check for Active Connections

```bash
# Check for long-running queries or locks
docker-compose exec postgres psql -U easm -d easm -c "
SELECT
    pid,
    usename,
    application_name,
    state,
    query_start,
    NOW() - query_start as duration,
    LEFT(query, 50) as query
FROM pg_stat_activity
WHERE datname = 'easm'
  AND state != 'idle'
  AND pid != pg_backend_pid()
ORDER BY query_start;
"

# If active queries found, consider stopping Celery workers temporarily
docker-compose stop worker beat
```

### 5. Create Migration Log

```bash
# Create log directory
mkdir -p logs

# Start logging
script logs/migration_004_$(date +%Y%m%d_%H%M%S).log
```

---

## ⬆️ Migration Execution

### Step 1: Apply Migration

```bash
# Ensure you're in the project directory with venv activated
cd /Users/cere/Downloads/easm
source venv/bin/activate

# Run migration with verbose output
alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# INFO  [alembic.runtime.migration] Running upgrade 003 -> 004, Add enrichment models and priority system
# ✅ Migration 004 complete: Enrichment models and priority system added
```

### Step 2: Verify Migration

```bash
# Check migration version
alembic current
# Expected: 004

# Verify tables exist
docker-compose exec postgres psql -U easm -d easm -c "\dt"
# Should show: certificates, endpoints

# Verify new columns in assets
docker-compose exec postgres psql -U easm -d easm -c "\d assets"
# Should show: last_enriched_at, enrichment_status, priority, priority_updated_at, priority_auto_calculated

# Verify new columns in services
docker-compose exec postgres psql -U easm -d easm -c "\d services"
# Should show: web_server, http_technologies, http_headers, etc.

# Verify indexes
docker-compose exec postgres psql -U easm -d easm -c "\di" | grep -E "(idx_asset_priority|idx_enrichment|idx_cert|idx_endpoint)"

# Verify priority backfill worked
docker-compose exec postgres psql -U easm -d easm -c "
SELECT
    priority,
    COUNT(*) as asset_count,
    AVG(risk_score) as avg_risk_score
FROM assets
WHERE priority IS NOT NULL
GROUP BY priority
ORDER BY
    CASE priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'normal' THEN 3
        WHEN 'low' THEN 4
    END;
"
```

### Step 3: Verify Application Works

```bash
# Restart services with new schema
docker-compose restart api worker beat

# Check logs for errors
docker-compose logs api | tail -50
docker-compose logs worker | tail -50

# Test API health endpoint
curl http://localhost:8000/health

# Check that old functionality still works
# (Run your smoke tests here)
```

---

## ⬇️ ROLLBACK PROCEDURES

### 🔴 Emergency Rollback (If Migration Fails)

If the migration fails mid-execution:

```bash
# Alembic should automatically rollback the transaction
# Check current state
alembic current

# If stuck between versions, force downgrade
alembic downgrade 003

# If that fails, restore from backup (see Full Database Restore below)
```

### 🟡 Standard Rollback (Migration Succeeded but Issues Found)

#### Option 1: Alembic Downgrade (RECOMMENDED)

```bash
# Stop all services first
docker-compose stop worker beat api

# Downgrade to previous version
alembic downgrade 003

# Expected output:
# INFO  [alembic.runtime.migration] Running downgrade 004 -> 003, Add enrichment models and priority system
# ✅ Migration 004 rolled back: Enrichment models removed

# Verify rollback
alembic current
# Expected: 003

# Verify tables removed
docker-compose exec postgres psql -U easm -d easm -c "\dt" | grep -E "(certificates|endpoints)"
# Should return nothing

# Verify columns removed from assets
docker-compose exec postgres psql -U easm -d easm -c "\d assets" | grep -E "(last_enriched_at|priority)"
# Should return nothing

# Verify columns removed from services
docker-compose exec postgres psql -U easm -d easm -c "\d services" | grep -E "(web_server|http_technologies)"
# Should return nothing

# Restart services
docker-compose start api worker beat
```

#### Option 2: Full Database Restore (If Alembic Rollback Fails)

```bash
# Stop all services
docker-compose down

# Identify your backup file
ls -lh backups/easm_pre_004_*

# Restore database
# Method 1: Docker-based restore
docker-compose up -d postgres
sleep 5  # Wait for postgres to be ready

# Drop and recreate database
docker-compose exec postgres psql -U easm -c "DROP DATABASE IF EXISTS easm;"
docker-compose exec postgres psql -U easm -c "CREATE DATABASE easm;"

# Restore from backup
docker-compose exec -T postgres pg_restore -U easm -d easm < backups/easm_pre_004_YYYYMMDD_HHMMSS.dump

# Method 2: Direct restore (if Docker not working)
dropdb -h localhost -p 15432 -U easm easm
createdb -h localhost -p 15432 -U easm easm
pg_restore -h localhost -p 15432 -U easm -d easm backups/easm_pre_004_YYYYMMDD_HHMMSS.dump

# Verify restoration
docker-compose exec postgres psql -U easm -d easm -c "SELECT COUNT(*) FROM assets;"
# Compare with pre-migration count

# Verify migration version
alembic current
# Should show: 003

# Start all services
docker-compose up -d
```

---

## ✅ Post-Rollback Verification

### 1. Data Integrity Check

```bash
# Verify row counts match pre-migration counts
docker-compose exec postgres psql -U easm -d easm -c "
SELECT
    'assets' as table_name,
    COUNT(*) as row_count
FROM assets
UNION ALL
SELECT 'services', COUNT(*) FROM services;
"

# Compare with saved pre-migration counts
# They should match EXACTLY
```

### 2. Application Health Check

```bash
# Check all services are running
docker-compose ps

# Check API health
curl http://localhost:8000/health

# Check Celery worker
docker-compose exec worker celery -A app.celery_app inspect active

# Check Beat scheduler
docker-compose logs beat | tail -20
```

### 3. Functional Testing

```bash
# Test discovery pipeline (should work as before migration)
# Test asset creation
# Test service listing
# Verify no enrichment-related errors in logs
```

---

## 🔍 Troubleshooting Common Rollback Issues

### Issue 1: Alembic Downgrade Fails with Foreign Key Violation

```bash
# This means there's data in the new tables
# Check for data
docker-compose exec postgres psql -U easm -d easm -c "
SELECT 'certificates' as table_name, COUNT(*) FROM certificates
UNION ALL
SELECT 'endpoints', COUNT(*) FROM endpoints;
"

# If data exists, you have two options:

# Option A: Delete data and retry downgrade
docker-compose exec postgres psql -U easm -d easm -c "
TRUNCATE TABLE endpoints CASCADE;
TRUNCATE TABLE certificates CASCADE;
"
alembic downgrade 003

# Option B: Full database restore (safer)
# Follow "Full Database Restore" procedure above
```

### Issue 2: Migration Version Mismatch

```bash
# Check alembic_version table
docker-compose exec postgres psql -U easm -d easm -c "SELECT * FROM alembic_version;"

# If version doesn't match reality, manually fix
docker-compose exec postgres psql -U easm -d easm -c "UPDATE alembic_version SET version_num = '003';"

# Then verify schema manually matches migration 003
```

### Issue 3: Indexes Not Dropped During Rollback

```bash
# List all indexes
docker-compose exec postgres psql -U easm -d easm -c "\di"

# Manually drop enrichment-related indexes if they still exist
docker-compose exec postgres psql -U easm -d easm -c "
DROP INDEX IF EXISTS idx_asset_priority_enrichment;
DROP INDEX IF EXISTS idx_enrichment_status;
DROP INDEX IF EXISTS idx_enrichment_source;
DROP INDEX IF EXISTS idx_has_tls;
DROP INDEX IF EXISTS idx_asset_cert;
DROP INDEX IF EXISTS idx_expiry;
DROP INDEX IF EXISTS idx_expired;
DROP INDEX IF EXISTS idx_asset_serial;
DROP INDEX IF EXISTS idx_asset_endpoint;
DROP INDEX IF EXISTS idx_endpoint_type;
DROP INDEX IF EXISTS idx_is_api;
DROP INDEX IF EXISTS idx_asset_url;
"
```

### Issue 4: Columns Still Exist After Rollback

```bash
# Manually drop columns if downgrade failed to remove them
docker-compose exec postgres psql -U easm -d easm -c "
-- Drop assets columns
ALTER TABLE assets DROP COLUMN IF EXISTS last_enriched_at;
ALTER TABLE assets DROP COLUMN IF EXISTS enrichment_status;
ALTER TABLE assets DROP COLUMN IF EXISTS priority;
ALTER TABLE assets DROP COLUMN IF EXISTS priority_updated_at;
ALTER TABLE assets DROP COLUMN IF EXISTS priority_auto_calculated;

-- Drop services columns
ALTER TABLE services DROP COLUMN IF EXISTS web_server;
ALTER TABLE services DROP COLUMN IF EXISTS http_technologies;
ALTER TABLE services DROP COLUMN IF EXISTS http_headers;
ALTER TABLE services DROP COLUMN IF EXISTS response_time_ms;
ALTER TABLE services DROP COLUMN IF EXISTS content_length;
ALTER TABLE services DROP COLUMN IF EXISTS redirect_url;
ALTER TABLE services DROP COLUMN IF EXISTS screenshot_url;
ALTER TABLE services DROP COLUMN IF EXISTS has_tls;
ALTER TABLE services DROP COLUMN IF EXISTS tls_version;
ALTER TABLE services DROP COLUMN IF EXISTS enriched_at;
ALTER TABLE services DROP COLUMN IF EXISTS enrichment_source;
"
```

---

## 📊 Rollback Decision Matrix

| Scenario | Time Since Migration | Recommended Action | Downtime |
|----------|---------------------|-------------------|----------|
| Migration failed during execution | N/A | Automatic rollback (already happened) | None |
| Critical bug found immediately | < 1 hour | Alembic downgrade | ~2 minutes |
| Data corruption detected | < 24 hours | Full database restore | ~5-10 minutes |
| Minor issues, fixable | Any | Fix forward, don't rollback | None |
| Production running for days | > 24 hours | **DO NOT ROLLBACK** - Fix forward or new migration | N/A |

---

## 🚨 When NOT to Rollback

**DO NOT rollback if:**
1. ✅ Migration completed successfully
2. ✅ New enrichment data has been collected
3. ✅ More than 24 hours have passed
4. ✅ Other dependent migrations have run (005+)
5. ✅ Issues are fixable with code changes

**Instead:**
- Fix bugs in application code
- Create a new migration (005) to fix schema issues
- Update data with SQL scripts

---

## 📝 Rollback Checklist

Before declaring rollback complete, verify:

- [ ] Migration version is 003: `alembic current`
- [ ] certificates table does NOT exist: `\dt`
- [ ] endpoints table does NOT exist: `\dt`
- [ ] assets table has NO new columns: `\d assets`
- [ ] services table has NO new columns: `\d services`
- [ ] All enrichment indexes removed: `\di`
- [ ] Row counts match pre-migration: Compare with saved counts
- [ ] All services running: `docker-compose ps`
- [ ] API health check passes: `curl http://localhost:8000/health`
- [ ] No errors in logs: `docker-compose logs --tail=100`
- [ ] Discovery pipeline works: Run test discovery
- [ ] Backup still exists: `ls -lh backups/`

---

## 📞 Emergency Contacts

If rollback fails and you need help:

1. **Check logs**: `logs/migration_004_*.log`
2. **Review backup**: Ensure backup file exists and is not corrupted
3. **Database state**: Document current state with screenshots/output
4. **Attempt full restore**: Follow "Full Database Restore" procedure
5. **Worst case**: Restore from nightly backup (if available)

---

## 📚 Related Documentation

- Migration file: `alembic/versions/004_add_enrichment_models.py`
- Architecture review: `ARCHITECTURE_REVIEW.md`
- Tiered enrichment design: `TIERED_ENRICHMENT_DESIGN.md`
- Sprint 2 architecture: `SPRINT_2_ENRICHMENT_ARCHITECTURE.md`

---

**Created**: 2025-10-24
**Migration**: 004 - Add enrichment models and priority system
**Author**: Claude Code (Sprint 2 Day 2)
**Status**: Ready for execution
