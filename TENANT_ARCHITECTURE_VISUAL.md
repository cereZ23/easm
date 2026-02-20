# Multi-Tenant Architecture - Current vs. Proposed

**Visual Reference for Implementation**

---

## Current Architecture (Before Fix)

### User Login Flow
```
┌──────────┐
│  Login   │
│  Page    │
└─────┬────┘
      │
      ▼
┌─────────────────────────────────┐
│  POST /api/v1/auth/login        │
│  Returns: JWT + User Info       │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  GET /api/v1/tenants            │
│  Returns: [Tenant A, Tenant B]  │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Auto-select First Tenant       │
│  (Tenant A)                     │
│  ❌ No user choice              │
│  ❌ No visual feedback          │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Dashboard View                 │
│  ❌ No tenant indicator         │
│  ❌ No way to switch            │
└─────────────────────────────────┘
```

**Problem:** User doesn't know they're in "Tenant A" context, thinks data might be mixed.

---

## Proposed Architecture (After Fix)

### Enhanced Login Flow
```
┌──────────┐
│  Login   │
│  Page    │
└─────┬────┘
      │
      ▼
┌─────────────────────────────────┐
│  POST /api/v1/auth/login        │
│  Returns: JWT + User Info       │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  GET /api/v1/tenants            │
│  Returns:                       │
│  [                              │
│    {id: 1, name: "Acme Corp",   │
│     user_role: "owner"},        │  ← ✅ NEW: Includes role
│    {id: 2, name: "TechStart",   │
│     user_role: "admin"}         │
│  ]                              │
└────────────┬────────────────────┘
             │
             ▼
    ┌────────┴────────┐
    │  Has Multiple   │
    │  Tenants?       │
    └────┬───────┬────┘
         │ YES   │ NO
         │       └──────────┐
         ▼                  │
┌────────────────────────┐  │
│ Tenant Selection Modal │  │
│                        │  │
│ ┌────────────────────┐ │  │
│ │ Acme Corp (Owner)  │ │  │  ← ✅ NEW: User chooses
│ │ 245 assets         │ │  │
│ └────────────────────┘ │  │
│                        │  │
│ ┌────────────────────┐ │  │
│ │ TechStart (Admin)  │ │  │
│ │ 89 assets          │ │  │
│ └────────────────────┘ │  │
└────────┬───────────────┘  │
         │                  │
         └──────────┬───────┘
                    │
                    ▼
         ┌────────────────────┐
         │  Tenant Selected   │
         │  (e.g., Acme Corp) │
         │  ✅ Stored in      │
         │     localStorage   │
         └──────────┬─────────┘
                    │
                    ▼
┌────────────────────────────────────────────┐
│  Dashboard Layout with Tenant Context      │
│                                            │
│  [EASM] [🔄 Acme Corp ▾] Dashboard ...    │  ← ✅ NEW: Visible switcher
│                                            │
│  Dashboard - Acme Corp                     │  ← ✅ NEW: Context indicator
│  ─────────────────────────                 │
│  Overview of your attack surface           │
│                                            │
└────────────────────────────────────────────┘
```

---

## Component Architecture

### Current (Before Fix)

```
frontend/src/
├── stores/
│   └── tenant.ts                   ✅ Store exists (logic is good)
├── api/
│   └── tenants.ts                  ✅ API client exists
├── layouts/
│   └── DashboardLayout.vue         ❌ No tenant UI
├── views/
│   ├── dashboard/DashboardView.vue ❌ No tenant indicator
│   ├── assets/AssetsView.vue       ❌ No tenant indicator
│   └── admin/OnboardCustomerView.vue ✅ Exists, not linked
└── components/
    └── (no tenant components)       ❌ Missing UI layer
```

**Gap:** Store has all the logic, but no UI components use it visibly.

---

### Proposed (After Fix)

```
frontend/src/
├── stores/
│   └── tenant.ts                   ✅ Enhanced with role tracking
├── api/
│   └── tenants.ts                  ✅ Updated types (add user_role)
├── layouts/
│   └── DashboardLayout.vue         ✅ Integrates TenantSwitcher
│                                      + Admin dropdown menu
├── components/
│   ├── layout/
│   │   ├── TenantSwitcher.vue      ✅ NEW: Dropdown switcher
│   │   └── TenantBadge.vue         ✅ NEW: Visual indicator
│   └── modals/
│       └── TenantSelectionModal.vue ✅ NEW: Post-login choice
├── views/
│   ├── dashboard/DashboardView.vue ✅ Adds TenantBadge
│   ├── assets/AssetsView.vue       ✅ Adds TenantBadge
│   ├── findings/FindingsView.vue   ✅ Adds TenantBadge
│   └── admin/
│       ├── OnboardCustomerView.vue ✅ Linked in nav
│       └── TenantsManagementView.vue ✅ NEW: Tenant list page
└── utils/
    └── permissions.ts               ✅ NEW: Role helper functions
```

**Result:** UI layer now matches backend capabilities.

---

## Data Flow Diagrams

### Current: Asset Loading (Hidden Tenant Context)

```
User clicks "Assets"
        │
        ▼
┌────────────────────────────────────┐
│  AssetsView.vue                    │
│                                    │
│  const tenantId =                  │
│    tenantStore.currentTenantId     │  ← User doesn't see this
│                                    │
│  assets = await assetApi.list(     │
│    tenantId,  ← Backend enforces   │
│    params     ← isolation here     │
│  )                                 │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  GET /api/v1/tenants/1/assets      │  ← Backend verifies access
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  Backend: verify_tenant_access()   │
│  - Check user has membership       │
│  - Check tenant_id matches         │
│  - Return 403 if invalid           │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  SQL Query:                        │
│  SELECT * FROM assets              │
│  WHERE tenant_id = 1               │  ← Isolated by tenant_id
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  Return Assets for Tenant 1        │
│  ✅ Secure                         │
│  ❌ User confused (no indicator)   │
└────────────────────────────────────┘
```

**Security:** Strong (backend prevents cross-tenant access)
**UX:** Weak (user doesn't know context)

---

### Proposed: Asset Loading (Visible Tenant Context)

```
User sees: [🔄 Acme Corp ▾]  ← ✅ Always visible
           │
           │ User clicks "Assets"
           │
           ▼
┌────────────────────────────────────┐
│  AssetsView.vue                    │
│                                    │
│  Header: "Assets - Acme Corp"      │  ← ✅ Tenant name visible
│          [Acme Corp Badge]         │  ← ✅ Visual indicator
│                                    │
│  const tenantId =                  │
│    tenantStore.currentTenantId     │  ← User sees this now
│                                    │
│  assets = await assetApi.list(     │
│    tenantId,                       │
│    params                          │
│  )                                 │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  GET /api/v1/tenants/1/assets      │  ← Same as before
└──────────┬─────────────────────────┘
           │
           ▼
   (Same backend flow)
           │
           ▼
┌────────────────────────────────────┐
│  Return Assets for Tenant 1        │
│  ✅ Secure                         │
│  ✅ User confident (knows context) │
└────────────────────────────────────┘
```

**Security:** Same (no changes)
**UX:** Strong (user always aware of context)

---

## Tenant Switching Flow (Proposed)

```
User in Tenant A viewing Assets
           │
           ▼
┌────────────────────────────────────┐
│  Navbar: [🔄 Acme Corp ▾]         │
│          User clicks dropdown      │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  Dropdown opens:                   │
│  ┌──────────────────────────────┐ │
│  │ ✓ Acme Corp     (Owner)      │ │
│  │   TechStart Inc (Admin)      │ │  ← User clicks TechStart
│  │   SecureBank    (Member)     │ │
│  └──────────────────────────────┘ │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  tenantStore.selectTenant(2)       │
│  - Updates currentTenant           │
│  - Saves to localStorage           │
│  - Emits 'tenant-changed' event    │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  AssetsView watches tenant change  │
│  - Detects currentTenantId change  │
│  - Calls loadAssets() again        │
│  - Fetches data for Tenant 2       │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  UI Updates:                       │
│  - Navbar: [🔄 TechStart Inc ▾]   │
│  - Header: "Assets - TechStart Inc"│
│  - Badge: [TechStart Inc]          │
│  - Table: TechStart's assets       │
└────────────────────────────────────┘
           │
           ▼
    User is now in Tenant B
    ✅ Clear visual feedback
    ✅ Data refreshed
    ✅ Context obvious
```

---

## Backend Security Enforcement (Unchanged)

### Request Flow with Tenant Verification

```
Frontend Request:
GET /api/v1/tenants/2/assets
Authorization: Bearer <JWT>
           │
           ▼
┌────────────────────────────────────┐
│  FastAPI Middleware                │
│  - Extracts JWT                    │
│  - Calls jwt_manager.verify_token()│
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  get_current_user() Dependency     │
│  - Looks up user by ID from JWT    │
│  - Returns User object             │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  verify_tenant_access(tenant_id=2) │
│  - Checks if user is superuser     │
│  - OR queries TenantMembership     │
│    WHERE user_id = X AND           │
│          tenant_id = 2             │
│  - Checks role has 'read' perm     │
│  - Returns membership or 403       │
└──────────┬─────────────────────────┘
           │
           ▼
    ┌──────────┴──────────┐
    │  Has Access?        │
    └──────┬───────┬──────┘
     YES   │       │  NO
           │       └─────────────┐
           ▼                     ▼
┌─────────────────────┐  ┌──────────────┐
│  Execute Query      │  │  Return 403  │
│  with tenant_id = 2 │  │  Forbidden   │
└─────────────────────┘  └──────────────┘
```

**Key Point:** Backend isolation is already bulletproof. UI just needs to make it visible.

---

## Role-Based Permissions Matrix (Enforced Backend, Displayed Frontend)

```
┌──────────────┬──────────┬──────────┬──────────┬──────────┬────────────┐
│ Permission   │  Viewer  │  Member  │  Admin   │  Owner   │ Superuser  │
├──────────────┼──────────┼──────────┼──────────┼──────────┼────────────┤
│ View Assets  │    ✅    │    ✅    │    ✅    │    ✅    │     ✅     │
│ Edit Assets  │    ❌    │    ✅    │    ✅    │    ✅    │     ✅     │
│ Scan Assets  │    ❌    │    ✅    │    ✅    │    ✅    │     ✅     │
│ Invite Users │    ❌    │    ❌    │    ✅    │    ✅    │     ✅     │
│ Edit Tenant  │    ❌    │    ❌    │    ✅    │    ✅    │     ✅     │
│ Delete Tenant│    ❌    │    ❌    │    ❌    │    ✅    │     ✅     │
│ All Tenants  │    ❌    │    ❌    │    ❌    │    ❌    │     ✅     │
└──────────────┴──────────┴──────────┴──────────┴──────────┴────────────┘
```

**Frontend Display:**
- Show role badge in tenant switcher
- Disable/hide actions based on role
- Use `hasPermission(role, action)` helper

**Backend Enforcement:**
- Already implemented via `TenantMembership.has_permission()`
- API endpoints check permissions via `verify_tenant_access(required_permission='write')`

---

## Comparison: Before vs. After

### Before (Current State)
```
User Experience:
❌ "Which company's data am I looking at?"
❌ "Can I switch to my other client?"
❌ "Is this showing mixed results?"
❌ "How do I add a new customer?" (admin)

Backend Reality:
✅ Data is properly isolated
✅ All APIs verify tenant access
✅ No data leakage possible

Gap: Perception vs. Reality
```

### After (Proposed State)
```
User Experience:
✅ "I'm viewing Acme Corp's data" (visible indicator)
✅ "I can switch to TechStart Inc" (dropdown)
✅ "Data is clearly separated" (confidence)
✅ "I can onboard customers here" (admin nav)

Backend Reality:
✅ Data is properly isolated (unchanged)
✅ All APIs verify tenant access (unchanged)
✅ No data leakage possible (unchanged)

Result: Perception matches Reality
```

---

## Visual Mockup: Complete UI (After Implementation)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  [EASM Platform]  [🔄 Acme Corp ▾]   Dashboard | Assets | Findings ... │
│                                                                         │
│  ┌─────────────────────┐                      [Admin ▾]  [🌙]  [User▾]│
│  │ ✓ Acme Corp (Owner) │                                               │
│  │   TechStart (Admin) │                                               │
│  │   SecureBank (Member)│ ← Tenant Switcher                            │
│  └─────────────────────┘                                               │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Dashboard - Acme Corp  [Acme Corp Badge]  ← Context Indicators        │
│  ─────────────────────────────────────────                             │
│  Overview of your attack surface                                       │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │ Total Assets │  │   Services   │  │  Certificates│                │
│  │     245      │  │     89       │  │      34      │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
│                                                                         │
│  ┌─────────────────────────────────────────────────┐                  │
│  │  Recent Activity                                │                  │
│  │  • New subdomain discovered: api.acme.com       │                  │
│  │  • Critical finding: SQL Injection on login page│                  │
│  └─────────────────────────────────────────────────┘                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Admin Dropdown (Superusers only):**
```
[Admin ▾]
  │
  ├─ Onboard Customer
  └─ Manage Tenants
```

---

## Key Takeaways

1. **Backend is Already Secure** - No security changes needed, just UI enhancements
2. **Store Logic is Good** - Pinia tenant store already has all needed functions
3. **Gap is UI Layer** - Need components to make tenant context visible
4. **Low Implementation Risk** - Small, isolated changes to frontend
5. **High User Value** - Eliminates confusion, builds confidence, enables scale

**Implementation Priority:**
- P0: Tenant switcher + visual indicators (security perception)
- P1: Admin navigation + tenant management (operational efficiency)
- P2: Settings + branding (customization)

---

**Ready for Development!** See `TENANT_UI_IMPLEMENTATION_CHECKLIST.md` for step-by-step tasks.
