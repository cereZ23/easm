# Database Query Optimization - Quick Reference Guide

**For EASM Development Team**

This is a quick reference for writing optimized database queries in the EASM platform.

---

## 1. Always Use Eager Loading for Relationships

### ❌ Bad (N+1 Queries)
```python
# This triggers 1 + N queries
assets = asset_repo.get_by_tenant(tenant_id=1)

for asset in assets:
    # Each iteration = new query!
    for service in asset.services:
        print(service.port)
# Total: 1 + 100 = 101 queries for 100 assets
```

### ✅ Good (2 Queries)
```python
# Use eager loading
assets = asset_repo.get_by_tenant(
    tenant_id=1,
    eager_load_relations=True  # Prevents N+1
)

for asset in assets:
    # No additional queries
    for service in asset.services:
        print(service.port)
# Total: 2 queries (1 assets + 1 all services)
```

---

## 2. Use Bulk Operations

### ❌ Bad (1000 Round-trips)
```python
for service_data in services:
    service = Service(**service_data)
    db.add(service)
    db.commit()  # 1000 commits!
# Time: ~5000ms
```

### ✅ Good (1 Round-trip)
```python
service_repo.bulk_upsert(asset_id, services)
# Time: ~50ms (100x faster)
```

---

## 3. Always Use LIMIT for Paginated Queries

### ❌ Bad (Loads Everything)
```python
# Loads all 1 million endpoints into memory
endpoints = db.query(Endpoint).filter_by(asset_id=1).all()
```

### ✅ Good (Loads Only What's Needed)
```python
# Loads only 100 records
endpoints = db.query(Endpoint).filter_by(asset_id=1)\
    .order_by(Endpoint.url)\
    .limit(100)\
    .offset(page * 100)\
    .all()
```

---

## 4. Avoid SELECT * - Only Query Needed Columns

### ❌ Bad (Loads Large JSON Fields)
```python
services = db.query(Service).filter_by(asset_id=1).all()
# Loads: http_headers (large), http_technologies, raw_metadata, etc.
```

### ✅ Good (Only Needed Columns)
```python
services = db.query(
    Service.id,
    Service.port,
    Service.protocol,
    Service.has_tls
).filter_by(asset_id=1).all()
# 5-10x faster
```

---

## 5. Use EXISTS for Existence Checks

### ❌ Bad (Loads Entire Result)
```python
# Loads all services just to check if any exist
has_services = len(db.query(Service).filter_by(asset_id=1).all()) > 0
```

### ✅ Good (Stops at First Match)
```python
from sqlalchemy import exists

has_services = db.query(
    exists().where(Service.asset_id == 1)
).scalar()
# 100x faster for large result sets
```

---

## 6. Filter Early in JOINs

### ❌ Bad (Joins Everything, Then Filters)
```python
# Joins all certificates, then filters
certs = db.query(Certificate)\
    .join(Asset)\
    .filter(
        Asset.tenant_id == 1,
        Certificate.is_expired == False
    ).all()
```

### ✅ Good (Filter Assets First)
```python
# Filters assets first (smaller JOIN)
certs = db.query(Certificate)\
    .join(Asset, Asset.id == Certificate.asset_id)\
    .filter(Asset.tenant_id == 1)\
    .filter(Certificate.is_expired == False)\
    .all()

# Even better: use subquery
asset_ids = db.query(Asset.id).filter(Asset.tenant_id == 1).subquery()
certs = db.query(Certificate)\
    .filter(Certificate.asset_id.in_(asset_ids))\
    .filter(Certificate.is_expired == False)\
    .all()
```

---

## 7. Use COUNT() Efficiently

### ❌ Bad (Loads All Records)
```python
count = len(db.query(Service).filter_by(asset_id=1).all())
# Loads all services into memory, then counts
```

### ✅ Good (Database COUNT)
```python
count = db.query(Service).filter_by(asset_id=1).count()
# Database counts, doesn't load records
```

---

## 8. Batch Database Operations

### ❌ Bad (N Database Calls)
```python
for asset_id in asset_ids:
    asset = db.query(Asset).filter_by(id=asset_id).first()
    # Do something
# N queries
```

### ✅ Good (1 Database Call)
```python
assets = db.query(Asset).filter(Asset.id.in_(asset_ids)).all()
asset_map = {a.id: a for a in assets}
for asset_id in asset_ids:
    asset = asset_map.get(asset_id)
    # Do something
# 1 query
```

---

## 9. Use Proper Indexes

### Check if Query Uses Index

```sql
EXPLAIN ANALYZE
SELECT * FROM services
WHERE asset_id = 1 AND has_tls = true;

-- Look for "Index Scan" in output
-- If you see "Seq Scan", add index
```

### Verify Index Exists

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'services'
  AND indexname LIKE '%tls%';
```

---

## 10. Common Anti-Patterns

### ❌ Loading Full Objects for ID-Only Operations
```python
# Bad: Loads entire Asset object
asset = db.query(Asset).filter_by(identifier='example.com').first()
service = Service(asset_id=asset.id, ...)
```

```python
# Good: Only query ID
asset_id = db.query(Asset.id).filter_by(identifier='example.com').scalar()
service = Service(asset_id=asset_id, ...)
```

### ❌ Multiple Queries in a Loop
```python
# Bad: 100 queries
for hostname in hostnames:
    asset = db.query(Asset).filter_by(identifier=hostname).first()
```

```python
# Good: 1 query
assets = db.query(Asset).filter(Asset.identifier.in_(hostnames)).all()
asset_map = {a.identifier: a for a in assets}
for hostname in hostnames:
    asset = asset_map.get(hostname)
```

### ❌ ORDER BY on Large Result Sets Without Limit
```python
# Bad: Sorts 1 million records, returns 100
endpoints = db.query(Endpoint)\
    .order_by(Endpoint.url.desc())\
    .all()[:100]
```

```python
# Good: Database limits before sorting optimization
endpoints = db.query(Endpoint)\
    .order_by(Endpoint.url.desc())\
    .limit(100)\
    .all()
```

---

## Performance Checklist

Before committing code with database queries, check:

- [ ] Are you loading relationships? Use `eager_load_relations=True`
- [ ] Are you inserting/updating multiple records? Use `bulk_upsert()`
- [ ] Are you loading large result sets? Add `LIMIT`
- [ ] Are you using `SELECT *`? Query only needed columns
- [ ] Are you checking existence? Use `exists()` instead of loading
- [ ] Are you counting records? Use `count()` instead of `len(all())`
- [ ] Are you querying in a loop? Batch the query
- [ ] Are you filtering after JOIN? Filter before JOIN
- [ ] Does your query need an index? Run `EXPLAIN ANALYZE`
- [ ] Are you caching repeated queries? Use Redis for expensive queries

---

## Testing Query Performance

```python
import time

def measure_query(query_func):
    start = time.perf_counter()
    result = query_func()
    duration = (time.perf_counter() - start) * 1000
    print(f"Query took {duration:.2f}ms")
    return result

# Usage
result = measure_query(lambda: asset_repo.get_by_tenant(1))
```

---

## When to Ask for Help

If your query:
- Takes > 100ms for < 10k records
- Triggers > 10 database queries for one operation
- Shows "Seq Scan" in EXPLAIN for tables > 1000 rows
- Causes timeout errors
- Loads > 1MB of data when you only need IDs

→ Ask the database team for optimization help!

---

## Useful Repository Methods

All repositories have optimized methods - use them!

### AssetRepository
```python
# ✅ Optimized bulk operations
asset_repo.bulk_upsert(tenant_id, assets_data)

# ✅ Eager loading support
asset_repo.get_by_tenant(tenant_id, eager_load_relations=True)

# ✅ Bulk identifier lookup (prevents N+1)
asset_repo.get_by_identifiers_bulk(tenant_id, identifiers_by_type)
```

### ServiceRepository
```python
# ✅ Bulk UPSERT (100x faster than individual)
service_repo.bulk_upsert(asset_id, services_data)

# ✅ Technology search with GIN index
service_repo.get_services_by_technology(tenant_id, 'WordPress')
```

### CertificateRepository
```python
# ✅ Efficient expiry queries with composite index
cert_repo.get_expiring_soon(tenant_id, days_threshold=30)

# ✅ Bulk UPSERT
cert_repo.bulk_upsert(asset_id, certificates_data)
```

---

## Resources

- **Full Optimization Report:** `/docs/DATABASE_OPTIMIZATION_REPORT.md`
- **Performance Tests:** `/tests/performance/test_database_performance.py`
- **Migration 005:** `/alembic/versions/005_enrichment_performance_indexes.py`

---

**Remember:** Premature optimization is the root of all evil, but N+1 queries are always evil. 😄
