# EASM Multi-Tenancy Architecture

## High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION                         │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  VUE.JS FRONTEND (Browser)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           DashboardLayout (Header)                      │   │
│  │  ┌───────────────────────────────────────────────┐     │   │
│  │  │ 🏢 [Tenant A ▼]  Dashboard  Assets  Findings │     │   │
│  │  │    Tenant A                                    │     │   │
│  │  │    Tenant B ✓  ← Currently Selected          │     │   │
│  │  │    Tenant C                                    │     │   │
│  │  └───────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                       │
│                          │ (User clicks Tenant C)                │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         Pinia Tenant Store                              │   │
│  │  currentTenantId: 3 → Updates to Tenant C (id=5)       │   │
│  │  tenants: [A, B, C]                                     │   │
│  │  localStorage.setItem('currentTenantId', '5')           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                       │
│                          │ (Watchers trigger in all views)       │
│                          ▼                                       │
│  ┌──────────────┬──────────────┬──────────────┬─────────────┐  │
│  │ DashboardView│  AssetsView  │ FindingsView │ServicesView │  │
│  │              │              │              │             │  │
│  │ watch(() =>  │ watch(() =>  │ watch(() =>  │ watch(() => │  │
│  │   tenantId)  │   tenantId)  │   tenantId)  │   tenantId) │  │
│  │     ↓        │     ↓        │     ↓        │     ↓       │  │
│  │ loadData()   │ loadAssets() │ loadFindings │loadServices │  │
│  └──────────────┴──────────────┴──────────────┴─────────────┘  │
│                          │                                       │
│                          │ All make API calls with new tenant_id │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │             API Client (axios)                           │   │
│  │  GET /api/v1/tenants/5/assets                           │   │
│  │  GET /api/v1/tenants/5/findings                         │   │
│  │  GET /api/v1/tenants/5/services                         │   │
│  │  GET /api/v1/tenants/5/dashboard                        │   │
│  │                                                           │   │
│  │  Headers: { Authorization: "Bearer <JWT>" }             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ HTTPS
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND (Python)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           JWT Middleware (auth.py)                      │   │
│  │  1. Extract Bearer token from Authorization header      │   │
│  │  2. Decode JWT → user_id, email, is_superuser          │   │
│  │  3. Attach user to request context                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                       │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │        Tenant Access Control (routers/*.py)             │   │
│  │  1. Extract tenant_id from URL path                     │   │
│  │  2. Query DB: Does user have access to tenant_id?       │   │
│  │  3. If NO → Return 403 Forbidden                        │   │
│  │  4. If YES → Continue to resource handler               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                       │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         Resource Handlers (services/*.py)               │   │
│  │  asset_service.get_assets(tenant_id=5, filters={...})   │   │
│  │  finding_service.get_findings(tenant_id=5, ...)         │   │
│  │  service_service.get_services(tenant_id=5, ...)         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                       │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           Database Queries (PostgreSQL)                 │   │
│  │  SELECT * FROM assets WHERE tenant_id = 5 AND ...       │   │
│  │  SELECT * FROM findings WHERE tenant_id = 5 AND ...     │   │
│  │  SELECT * FROM services WHERE tenant_id = 5 AND ...     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    POSTGRESQL DATABASE                           │
├─────────────────────────────────────────────────────────────────┤
│  Table: tenants                                                  │
│  ┌────┬─────────────┬────────┬────────────┐                    │
│  │ id │    name     │  slug  │ is_active  │                    │
│  ├────┼─────────────┼────────┼────────────┤                    │
│  │  3 │  Tenant A   │ ten-a  │    true    │                    │
│  │  4 │  Tenant B   │ ten-b  │    true    │                    │
│  │  5 │  Tenant C   │ ten-c  │    true    │ ← Currently Active │
│  └────┴─────────────┴────────┴────────────┘                    │
│                                                                   │
│  Table: assets (Row-Level Security)                              │
│  ┌────┬───────────┬──────────┬──────────────┐                  │
│  │ id │ tenant_id │   type   │  identifier  │                  │
│  ├────┼───────────┼──────────┼──────────────┤                  │
│  │ 10 │     3     │  domain  │ example-a.com│ ← NOT returned   │
│  │ 11 │     4     │  domain  │ example-b.com│ ← NOT returned   │
│  │ 12 │     5     │  domain  │ example-c.com│ ← RETURNED       │
│  │ 13 │     5     │subdomain │ sub.example-c│ ← RETURNED       │
│  └────┴───────────┴──────────┴──────────────┘                  │
│         ▲                                                         │
│         └─ WHERE tenant_id = 5 (enforced in ALL queries)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security Layers (Defense in Depth)

```
┌────────────────────────────────────────────────────────────────┐
│ Layer 1: Frontend (UX Layer)                                    │
│ ✓ Visual tenant indicator prevents user confusion              │
│ ✓ Confirmation dialog on tenant switch                         │
│ ✓ All API calls include tenant_id in URL                       │
│ ⚠️ NOT TRUSTED - Can be bypassed by malicious client           │
└────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────┐
│ Layer 2: API Gateway (Authentication)                           │
│ ✓ JWT signature validation                                     │
│ ✓ Token expiration check                                       │
│ ✓ User extraction from token claims                            │
│ ⚠️ Does NOT validate tenant access (next layer)                │
└────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────┐
│ Layer 3: Tenant Authorization (CRITICAL)                        │
│ ✓ Verify user has access to requested tenant_id                │
│ ✓ Query user_tenants table for relationship                    │
│ ✓ Return 403 if no access                                      │
│ ✅ PRIMARY SECURITY LAYER                                       │
└────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────┐
│ Layer 4: Database Filtering (Defense in Depth)                  │
│ ✓ ALL queries include WHERE tenant_id = ?                      │
│ ✓ PostgreSQL Row-Level Security policies (optional)            │
│ ✓ Database-level isolation as final safeguard                  │
│ ✅ BACKUP SECURITY LAYER                                        │
└────────────────────────────────────────────────────────────────┘
```

---

## Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       Frontend Components                        │
└─────────────────────────────────────────────────────────────────┘

       ┌──────────────────┐
       │ DashboardLayout  │
       │   (Header/Nav)   │
       └────────┬─────────┘
                │
                │ Contains
                ▼
       ┌──────────────────┐
       │ Tenant Selector  │◄──────┐
       │   Dropdown       │       │
       └────────┬─────────┘       │
                │                 │
                │ Emits change    │ Reads current
                ▼                 │
       ┌──────────────────┐       │
       │  Tenant Store    │       │
       │   (Pinia)        │       │
       │                  │       │
       │ - currentTenant  ├───────┘
       │ - tenants[]      │
       │ - selectTenant() │
       └────────┬─────────┘
                │
                │ Watched by all views
                ▼
    ┌───────────┴────────────────┬────────────────┬────────────┐
    ▼                            ▼                ▼            ▼
┌────────┐                  ┌─────────┐      ┌──────────┐  ┌──────────┐
│Dashboard│                 │Assets   │      │Findings  │  │Services  │
│View    │                  │View     │      │View      │  │View      │
└────────┘                  └─────────┘      └──────────┘  └──────────┘
    │                            │                │            │
    │ All call API with          │                │            │
    │ tenantStore.currentTenantId│                │            │
    └────────────┬───────────────┴────────────────┴────────────┘
                 ▼
        ┌──────────────────┐
        │   API Client     │
        │   (axios)        │
        └────────┬─────────┘
                 │
                 │ HTTP Requests
                 ▼
        ┌──────────────────┐
        │  FastAPI Backend │
        └──────────────────┘
```

---

## Tenant Onboarding Flow

```
┌──────────────┐
│ Admin User   │
│ (superuser)  │
└──────┬───────┘
       │
       │ 1. Clicks "Onboard Client"
       ▼
┌──────────────────────────────────┐
│ OnboardCustomerView.vue          │
│                                  │
│ Form:                            │
│  - Company Name                  │
│  - Admin Email                   │
│  - Password                      │
│  - Domains: [example.com, ...]  │
│                                  │
│ [Submit Button]                  │
└──────┬───────────────────────────┘
       │
       │ 2. POST /api/v1/onboarding/register
       │    { company_name, email, password, domains }
       ▼
┌──────────────────────────────────┐
│ Backend: onboarding.py           │
│                                  │
│ 1. Validate inputs               │
│ 2. Create tenant record          │
│ 3. Create admin user             │
│ 4. Link user to tenant           │
│ 5. Create seed records (domains) │
│ 6. Trigger initial scan (async)  │
│                                  │
│ Return: { tenant_id, user_id }   │
└──────┬───────────────────────────┘
       │
       │ 3. Success response
       ▼
┌──────────────────────────────────┐
│ Frontend shows success message   │
│                                  │
│ "Customer onboarded! Initial     │
│  scan started. Send login        │
│  credentials to admin@..."       │
└──────┬───────────────────────────┘
       │
       │ 4. New tenant user logs in
       ▼
┌──────────────────────────────────┐
│ New User Dashboard               │
│                                  │
│ 🏢 [New Company ▼]               │
│                                  │
│ Total Assets: 0 (scanning...)    │
│ Services: 0                      │
│ Findings: 0                      │
└──────────────────────────────────┘
```

---

## Database Schema (Simplified)

```sql
-- Core tenant table
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User to tenant mapping (many-to-many)
CREATE TABLE user_tenants (
    user_id INTEGER REFERENCES users(id),
    tenant_id INTEGER REFERENCES tenants(id),
    role VARCHAR(50) DEFAULT 'member',  -- owner, admin, member, viewer
    PRIMARY KEY (user_id, tenant_id)
);

-- All resource tables include tenant_id
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    type VARCHAR(50),
    identifier VARCHAR(500),
    -- ... other fields
    CONSTRAINT assets_tenant_fk FOREIGN KEY (tenant_id)
        REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_assets_tenant ON assets(tenant_id);

-- Row-Level Security (PostgreSQL - Optional but Recommended)
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;

CREATE POLICY assets_tenant_isolation ON assets
    USING (tenant_id = current_setting('app.current_tenant_id')::INTEGER);
```

---

## API Request Flow Example

### Frontend Request:
```javascript
// User switches to Tenant C (id=5)
tenantStore.selectTenant(5)

// Assets view watcher triggers
watch(() => tenantStore.currentTenantId, (newId) => {
  assetApi.list(newId, { page: 1, page_size: 25 })
})

// Axios makes HTTP request
GET /api/v1/tenants/5/assets?page=1&page_size=25
Headers: {
  Authorization: "Bearer eyJhbGciOiJIUzI1NiIs..."
}
```

### Backend Processing:
```python
# 1. JWT Middleware
decoded = jwt.decode(token, SECRET_KEY)
current_user = User(id=decoded['user_id'])

# 2. Route Handler
@router.get("/tenants/{tenant_id}/assets")
async def list_assets(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 3. Tenant Access Check
    access = db.query(UserTenant).filter(
        UserTenant.user_id == current_user.id,
        UserTenant.tenant_id == tenant_id
    ).first()

    if not access:
        raise HTTPException(403, "Access denied to this tenant")

    # 4. Query with tenant filter
    assets = db.query(Asset).filter(
        Asset.tenant_id == tenant_id
    ).limit(25).all()

    return assets
```

### Database Query:
```sql
SELECT * FROM assets
WHERE tenant_id = 5
  AND is_active = true
LIMIT 25 OFFSET 0;
```

---

## Testing Checklist

### Unit Tests (Backend):
- [ ] JWT extraction and validation
- [ ] Tenant access control logic
- [ ] Database queries include tenant_id filter
- [ ] 403 response on unauthorized tenant access

### Integration Tests:
- [ ] User A cannot access User B's tenant data
- [ ] Tenant switch triggers data reload
- [ ] All API endpoints require tenant_id
- [ ] Onboarding creates all required records

### E2E Tests:
- [ ] Login → Switch tenants → Verify UI updates
- [ ] Admin onboards client → New user can login
- [ ] Non-admin cannot access onboarding page
- [ ] Tenant deletion cascades to all resources

---

## Monitoring & Alerts

### Metrics to Track:
- Tenant switches per user per day
- API calls by tenant_id (for billing)
- Failed 403 responses (potential security issues)
- Onboarding completion rate

### Security Alerts:
- Multiple 403 errors from same IP (brute force)
- User accessing >10 different tenants rapidly (suspicious)
- Large data exports from single tenant (data exfiltration)
- Failed JWT validations (token manipulation attempts)

---

## Disaster Recovery

### Tenant Data Backup:
```bash
# Per-tenant backup
pg_dump -h localhost -U easm_user easm_db \
  -t assets -t findings -t services \
  --where="tenant_id=5" > tenant_5_backup.sql

# Restore to new tenant
psql -h localhost -U easm_user easm_db < tenant_5_backup.sql
```

### Tenant Isolation Verification:
```sql
-- Audit query: Find any cross-tenant references
SELECT 'assets' AS table_name, a.id, a.tenant_id
FROM assets a
LEFT JOIN tenants t ON a.tenant_id = t.id
WHERE t.id IS NULL;  -- Orphaned records

UNION ALL

SELECT 'findings', f.id, f.tenant_id
FROM findings f
LEFT JOIN tenants t ON f.tenant_id = t.id
WHERE t.id IS NULL;
```

---

## Performance Optimization

### Caching Strategy:
```javascript
// Frontend: Cache tenant list for 5 minutes
const cachedTenants = localStorage.getItem('tenants_cache')
const cacheAge = Date.now() - localStorage.getItem('tenants_cache_time')

if (cachedTenants && cacheAge < 300000) {
  return JSON.parse(cachedTenants)
}
```

### Database Indexes:
```sql
-- Critical indexes for tenant queries
CREATE INDEX idx_assets_tenant_id ON assets(tenant_id);
CREATE INDEX idx_findings_tenant_id ON findings(tenant_id);
CREATE INDEX idx_services_tenant_id ON services(tenant_id);

-- Composite indexes for common queries
CREATE INDEX idx_assets_tenant_type ON assets(tenant_id, type);
CREATE INDEX idx_findings_tenant_severity ON findings(tenant_id, severity);
```

---

## Conclusion

This architecture ensures:
✅ Complete tenant data isolation
✅ Multiple layers of security
✅ Clear visual indication of tenant context
✅ Automatic data refresh on tenant switch
✅ Scalable to thousands of tenants
✅ Compliant with multi-tenancy best practices

**No single point of failure - multiple security layers protect against data leakage.**
