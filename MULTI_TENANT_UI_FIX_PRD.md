# Product Requirements Document: Multi-Tenancy UI Fixes

**Document Version:** 1.0
**Date:** 2025-10-26
**Author:** Business Analyst (Claude Code)
**Status:** Ready for Implementation

---

## Executive Summary

The EASM platform has a **critical multi-tenancy issue** in the UI that creates data leakage risks and a poor user experience. While the backend has proper tenant isolation through JWT authentication and database-level access control, the frontend lacks essential tenant management components. Users can onboard new customers (via `/admin/onboard`), but **cannot switch between tenants** and may see **mixed results from different tenants**.

This PRD addresses these issues with a prioritized roadmap focused on security, usability, and scalability.

---

## Current State Analysis

### Backend Implementation (Strong)
- **Authentication:** JWT-based with refresh token support
- **Multi-tenant isolation:** All API endpoints require `tenant_id` in path (`/api/v1/tenants/{tenant_id}/assets`)
- **Access control:** `TenantMembership` model with roles (owner, admin, member, viewer)
- **Permission system:** Role-based permissions (read, write, admin)
- **Onboarding API:** `/api/v1/onboarding/register` creates tenant + user + seeds (admin only)
- **Tenant listing API:** `/api/v1/tenants` returns only tenants user has access to

### Frontend Implementation (Gaps Identified)

#### What Works
1. **Authentication flow:** Login/logout with token management
2. **Tenant store:** Basic Pinia store with `currentTenant` and `fetchTenants()`
3. **Auto-selection:** First tenant auto-selected on login from `localStorage`
4. **API calls:** All data fetching correctly uses `tenantStore.currentTenantId`
5. **Onboarding page:** `/admin/onboard` exists for admins to create new customers

#### Critical Gaps
1. **No tenant switcher UI component** - Users cannot manually switch between tenants they have access to
2. **No visual indication of current tenant** - Users don't know which tenant's data they're viewing
3. **No tenant management page** - Cannot view list of tenants, create tenants (non-admin), or manage memberships
4. **Tenant selection after login is hidden** - Auto-selects first tenant, no choice presented
5. **No role indicator** - Users don't know their role/permissions for current tenant
6. **Navigation doesn't link to onboarding** - Admin onboarding page exists but isn't accessible from navigation

---

## Problem Statement

**As a user with access to multiple tenants**, I need to:
- See which tenant I'm currently viewing
- Switch between my tenants easily
- Know my role/permissions for each tenant
- Be confident I'm not seeing mixed data from other tenants

**As a platform administrator**, I need to:
- Quickly access the customer onboarding workflow
- View all tenants I manage
- Understand which customers are active

**As a customer administrator**, I should:
- Manage my organization's settings
- Invite team members (future feature)
- NOT see other customers' data under any circumstances

---

## User Stories & Requirements

### P0 - Critical (Data Isolation & Security)

#### US-P0-1: Tenant Switcher Component
**Story:** As a user with multiple tenant memberships, I want to see and switch between my tenants so that I can access data for each organization separately.

**Acceptance Criteria:**
- [ ] Dropdown/selector component visible in top navigation bar
- [ ] Shows current tenant name prominently
- [ ] Displays list of all accessible tenants when clicked
- [ ] Switching tenant updates `currentTenant` in store
- [ ] Switching tenant refreshes all data on current page
- [ ] Selection persists to `localStorage` across sessions
- [ ] Shows tenant count badge (e.g., "2 orgs")

**Technical Implementation:**
- Location: `DashboardLayout.vue` navbar (between logo and user menu)
- Component: New `TenantSwitcher.vue` in `/components/layout/`
- State: Uses `useTenantStore()` from Pinia
- API: Calls `tenantApi.list()` on mount
- Triggers: Watch `currentTenant` and emit `tenant-changed` event

**Design Notes:**
```
[EASM Platform] [🔄 Acme Corp ▾] ... Dashboard | Assets | Findings ...  [🌙] [user@email.com ▾]
                 ─────────────
                 │ Acme Corp    ✓│
                 │ TechStart Inc │
                 │ SecureBank    │
                 └──────────────┘
```

---

#### US-P0-2: Tenant Context Indicator
**Story:** As a user, I want to always see which tenant's data I'm viewing so that I never accidentally confuse data from different organizations.

**Acceptance Criteria:**
- [ ] Current tenant name shown in page headers or breadcrumbs
- [ ] Tenant badge/chip visible on all data pages (Assets, Findings, etc.)
- [ ] Dashboard subtitle includes tenant name (already implemented partially)
- [ ] Distinct visual styling per tenant (optional: color-coding)

**Technical Implementation:**
- Add `<TenantBadge />` component showing current tenant
- Display in page titles: "Assets - Acme Corp"
- Add to breadcrumbs: `Home > Acme Corp > Assets`

---

#### US-P0-3: Force Tenant Selection on Login
**Story:** As a user logging in, I want to explicitly select which tenant I'll access (if I have multiple) so that I'm aware of the context I'm entering.

**Acceptance Criteria:**
- [ ] After successful login, if user has multiple tenants, show tenant selection modal
- [ ] User must choose a tenant before proceeding to dashboard
- [ ] If user has only one tenant, auto-select and proceed (current behavior)
- [ ] Remember last selection for next login (current behavior via localStorage)

**Technical Implementation:**
- Create `TenantSelectionModal.vue` component
- Trigger in router guard or `DashboardLayout.vue` `onMounted`
- Condition: `tenants.length > 1 && !currentTenant`

---

### P1 - High Priority (Management & Usability)

#### US-P1-1: Tenant List Management Page
**Story:** As an administrator, I want to see all tenants I have access to and their basic details so that I can manage my portfolio of customers.

**Acceptance Criteria:**
- [ ] New route: `/tenants` or `/admin/tenants`
- [ ] Table showing: Tenant name, slug, # of assets, # of findings, created date
- [ ] Click row to switch to that tenant and navigate to dashboard
- [ ] Search/filter by tenant name
- [ ] For superusers: shows ALL tenants; regular users: only their tenants

**Technical Implementation:**
- New view: `TenantsManagementView.vue`
- API: Uses existing `tenantApi.list()`
- Router entry: Under admin section, requires auth
- Table columns: Name, Slug, Status, Asset Count, Finding Count, Actions

---

#### US-P1-2: Admin Navigation Access
**Story:** As a platform admin, I want quick access to the onboarding workflow so that I can add new customers efficiently.

**Acceptance Criteria:**
- [ ] "Admin" dropdown in navbar (only for admins/superusers)
- [ ] Dropdown items: "Onboard Customer", "Manage Tenants"
- [ ] Conditional rendering based on `user.is_superuser`
- [ ] Visual indicator showing admin mode

**Technical Implementation:**
- Update `DashboardLayout.vue` navbar
- Add conditional admin menu section
- Links: `/admin/onboard`, `/admin/tenants`

---

#### US-P1-3: Tenant Creation API Integration (Non-Admin)
**Story:** As an owner-role user, I want to create sub-tenants or projects under my organization (future multi-level tenancy).

**Status:** Deferred to Sprint 6 (backend supports via `POST /api/v1/tenants`, requires permission updates)

---

#### US-P1-4: Role & Permission Display
**Story:** As a user, I want to see my role for the current tenant so that I know what actions I can perform.

**Acceptance Criteria:**
- [ ] Display role badge in tenant switcher or user menu
- [ ] Shows: "Owner", "Admin", "Member", "Viewer"
- [ ] Tooltip explaining permissions for each role
- [ ] Visible on tenant selection modal

**Technical Implementation:**
- Extend `TenantResponse` type to include user's role
- Backend: Update `/api/v1/tenants` to include membership role in response
- Display in `TenantSwitcher` as secondary text

---

### P2 - Medium Priority (Enhancements)

#### US-P2-1: Tenant Settings Page
**Story:** As a tenant owner/admin, I want to manage my organization's settings so that I can configure policies and preferences.

**Acceptance Criteria:**
- [ ] Route: `/settings/tenant` (tenant-scoped)
- [ ] Edit tenant name, contact policy
- [ ] View/manage seeds (domains being monitored)
- [ ] Only accessible to owner/admin roles

**Technical Implementation:**
- New view: `TenantSettingsView.vue`
- API: `PATCH /api/v1/tenants/{tenant_id}` (already exists)
- Form validation, permission checks

---

#### US-P2-2: Tenant Activity Dashboard
**Story:** As a tenant admin, I want to see recent activity and changes across my organization so that I can monitor team actions.

**Status:** Partially implemented in main dashboard (recent activity widget)

---

#### US-P2-3: Tenant Branding
**Story:** As a tenant owner, I want to customize the appearance of the platform for my team (logo, colors) so that it feels like our tool.

**Status:** Deferred to future sprint (requires backend tenant customization fields)

---

#### US-P2-4: Tenant Invitation System
**Story:** As a tenant admin, I want to invite team members to my tenant with specific roles so that my team can collaborate.

**Status:** Deferred (requires invitation token system, email integration)

---

## Technical Architecture

### New Components

```
frontend/src/components/
├── layout/
│   ├── TenantSwitcher.vue          # Dropdown for switching tenants
│   └── TenantBadge.vue             # Visual tenant indicator
└── modals/
    └── TenantSelectionModal.vue    # Post-login tenant selection
```

### New Views

```
frontend/src/views/
├── admin/
│   ├── OnboardCustomerView.vue     # ✅ Already exists
│   └── TenantsManagementView.vue   # NEW: List all tenants
└── settings/
    └── TenantSettingsView.vue      # NEW: Tenant settings page
```

### State Management (Pinia Store Updates)

**Current `tenant.ts` store:**
```typescript
// Existing
const currentTenant = ref<Tenant | null>(null)
const tenants = ref<Tenant[]>([])

// Needs enhancement:
interface TenantWithRole extends Tenant {
  user_role: string           // Add role for current user
  user_permissions: string[]  // Add permissions array
}
```

### Router Updates

```typescript
// New routes to add
{
  path: '/admin/tenants',
  name: 'TenantManagement',
  component: () => import('@/views/admin/TenantsManagementView.vue'),
  meta: { requiresAuth: true, requiresAdmin: true }
},
{
  path: '/settings/tenant',
  name: 'TenantSettings',
  component: () => import('@/views/settings/TenantSettingsView.vue'),
  meta: { requiresAuth: true, requiresTenantAdmin: true }
}
```

### Backend API Updates (Minimal)

**Required:**
1. Update `GET /api/v1/tenants` response to include user's role per tenant
2. Add `GET /api/v1/tenants/{tenant_id}/members` (future: member management)

**Schema Update:**
```python
class TenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    user_role: Optional[str] = None  # NEW: Add user's role for this tenant
```

**Implementation in `/api/v1/tenants` list endpoint:**
```python
@router.get("", response_model=list[TenantResponse])
def list_tenants(db: Session, current_user: User):
    if current_user.is_superuser:
        tenants = db.query(Tenant).all()
        return [
            TenantResponse(
                **tenant.__dict__,
                user_role="superuser"
            ) for tenant in tenants
        ]
    else:
        return [
            TenantResponse(
                **membership.tenant.__dict__,
                user_role=membership.role  # Include role
            )
            for membership in current_user.tenant_memberships
            if membership.is_active
        ]
```

---

## Data Flow & Isolation Verification

### Current Data Flow
```
1. User logs in → JWT token issued
2. Frontend calls GET /api/v1/tenants → returns accessible tenants
3. Frontend auto-selects first tenant → stores in localStorage
4. All API calls use tenantStore.currentTenantId in URL path
5. Backend verifies user has access to tenant via verify_tenant_access()
```

### Risk Assessment: Mixed Results Issue

**Root Cause Analysis:**
- Backend isolation is **STRONG** (all endpoints require tenant_id, verified per request)
- Frontend isolation **appears weak** due to missing UI controls

**Actual Risk:**
- **Low risk of data leakage** - Backend prevents cross-tenant access
- **High risk of user confusion** - Users may think data is mixed due to:
  1. No visible tenant indicator
  2. Auto-selection of first tenant without user awareness
  3. No way to switch tenants

**Verification Test Cases:**
1. ✅ User A (Tenant 1) cannot access `/api/v1/tenants/2/assets` → 403 Forbidden
2. ✅ API calls without tenant_id in path fail → caught by dependency injection
3. ⚠️ User B (Tenant 1 + Tenant 2) sees Tenant 1 data but thinks they're viewing Tenant 2 → **UI confusion, not data leak**

**Recommendation:**
- Issue is **UX/perception**, not security breach
- Fix with **P0 UI enhancements** (tenant switcher + context indicators)
- Add **P1 explicit tenant selection** to prevent confusion

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Sprint 6, Week 1)
**Goal:** Eliminate tenant confusion and enable switching

- [ ] **Day 1-2:** Create `TenantSwitcher.vue` component
- [ ] **Day 2-3:** Integrate tenant switcher into `DashboardLayout.vue` navbar
- [ ] **Day 3-4:** Add `TenantBadge.vue` to all data views
- [ ] **Day 4-5:** Create `TenantSelectionModal.vue` for post-login selection
- [ ] **Day 5:** Testing & QA for tenant switching

**Deliverables:**
- Working tenant switcher in navigation
- Visual tenant indicators on all pages
- User can switch between tenants seamlessly

---

### Phase 2: Management Features (Sprint 6, Week 2)
**Goal:** Admin tooling and tenant management

- [ ] **Day 6-7:** Create `TenantsManagementView.vue`
- [ ] **Day 7-8:** Add admin dropdown to navigation
- [ ] **Day 8-9:** Implement role/permission display
- [ ] **Day 9-10:** Backend API enhancement for role inclusion
- [ ] **Day 10:** Integration testing

**Deliverables:**
- Tenant management page for admins
- Admin navigation section
- Role indicators in UI

---

### Phase 3: Settings & Enhancements (Sprint 7)
**Goal:** Tenant configuration and UX polish

- [ ] Create `TenantSettingsView.vue`
- [ ] Implement tenant branding (colors, logo)
- [ ] Add tenant invitation system (member management)
- [ ] Multi-level tenant hierarchy (parent/child tenants)

---

## Success Metrics

### Quantitative KPIs
1. **Tenant switch time:** < 2 seconds to switch and reload data
2. **User confusion rate:** < 5% support tickets about "wrong data" after fix
3. **Admin onboarding time:** Reduce from ~15 min to < 5 min with direct navigation
4. **Multi-tenant user adoption:** Track % of users accessing 2+ tenants per session

### Qualitative Goals
1. Users can confidently identify which tenant they're viewing
2. Admins can efficiently onboard new customers
3. Zero data leakage incidents (maintain current security posture)
4. Improved platform trust and perception

---

## Security Considerations

### Backend Security (Maintained)
- ✅ All API endpoints enforce tenant isolation via `verify_tenant_access()`
- ✅ JWT tokens do NOT contain tenant_id (prevents token reuse across tenants)
- ✅ Database queries filtered by tenant_id at ORM level
- ✅ Superuser bypass is explicit and logged

### Frontend Security (Enhanced)
- ✅ No sensitive tenant data in localStorage (only tenant_id for UX)
- ✅ Tenant switcher validates access before allowing switch (calls backend)
- ✅ API client includes tenant_id in every request path
- ⚠️ **New Risk:** Tenant confusion → Implement P0 visual indicators

### Audit & Compliance
- Log all tenant switches: `User X switched from Tenant A to Tenant B`
- Track cross-tenant access attempts (should be 0 after fix)
- Monitor for anomalous multi-tenant access patterns

---

## Testing Strategy

### Unit Tests
- `TenantSwitcher.vue`: Component renders, switches tenant, persists selection
- `useTenantStore()`: fetchTenants, selectTenant, state persistence

### Integration Tests
1. **Tenant Switching Flow:**
   - Login as multi-tenant user → Select tenant → Verify data loads correctly
   - Switch tenant → Verify data refreshes and shows different tenant's data

2. **Isolation Verification:**
   - User A (Tenant 1) cannot see Tenant 2 data
   - API calls with wrong tenant_id return 403

3. **Admin Onboarding:**
   - Admin creates new tenant → User logs in → Sees new tenant in list

### E2E Tests (Playwright/Cypress)
```javascript
test('Multi-tenant user can switch between tenants', async () => {
  await login('multitenant@user.com', 'password')
  await expect(page.locator('[data-testid="tenant-switcher"]')).toBeVisible()
  await page.click('[data-testid="tenant-switcher"]')
  await expect(page.locator('[data-testid="tenant-option-2"]')).toBeVisible()
  await page.click('[data-testid="tenant-option-2"]')
  await expect(page.locator('[data-testid="current-tenant-name"]')).toHaveText('TechStart Inc')
})
```

---

## Appendix A: User Roles & Permissions Matrix

| Role      | Read Assets | Create/Edit Assets | Manage Users | Manage Tenant Settings | Delete Tenant |
|-----------|-------------|---------------------|--------------|------------------------|---------------|
| **Viewer**   | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Member**   | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Admin**    | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Owner**    | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Superuser** | ✅ (all) | ✅ (all) | ✅ (all) | ✅ (all) | ✅ (all) |

---

## Appendix B: API Endpoints Reference

### Tenant Management
- `GET /api/v1/tenants` - List accessible tenants (✅ exists, needs role enhancement)
- `POST /api/v1/tenants` - Create tenant (✅ exists, admin only)
- `GET /api/v1/tenants/{id}` - Get tenant details (✅ exists)
- `PATCH /api/v1/tenants/{id}` - Update tenant (✅ exists)
- `GET /api/v1/tenants/{id}/dashboard` - Get dashboard stats (✅ exists)

### Onboarding
- `POST /api/v1/onboarding/register` - Onboard new customer (✅ exists, admin only)

### Future Endpoints (P2)
- `GET /api/v1/tenants/{id}/members` - List tenant members
- `POST /api/v1/tenants/{id}/members` - Invite member
- `DELETE /api/v1/tenants/{id}/members/{user_id}` - Remove member

---

## Appendix C: UI Mockups

### Tenant Switcher (Navbar)
```
┌─────────────────────────────────────────────────────────────┐
│ [EASM Platform]  [🔄 Acme Corp ▾]   Dashboard  Assets ...  │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
         ┌────────────────────────┐
         │ Switch Organization    │
         ├────────────────────────┤
         │ ✓ Acme Corp     (Owner)│
         │   TechStart Inc (Admin)│
         │   SecureBank    (Member)│
         └────────────────────────┘
```

### Tenant Selection Modal (Post-Login)
```
┌────────────────────────────────────────┐
│  Select Organization                   │
│                                        │
│  You have access to 3 organizations:   │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ Acme Corp                        │ │
│  │ Owner • 245 assets • 12 findings │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ TechStart Inc                    │ │
│  │ Admin • 89 assets • 3 findings   │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ SecureBank                       │ │
│  │ Member • 512 assets • 45 findings│ │
│  └──────────────────────────────────┘ │
│                                        │
│              [Continue →]              │
└────────────────────────────────────────┘
```

### Tenant Badge (Page Header)
```
┌────────────────────────────────────────┐
│  Assets                                │
│  [Acme Corp] Manage discovered assets  │
│  ─────────────────────────────────     │
│  ...                                   │
└────────────────────────────────────────┘
```

---

## Approval & Sign-Off

| Stakeholder          | Role                  | Status | Date |
|----------------------|-----------------------|--------|------|
| Product Owner        | Business Owner        | ⏳     |      |
| Engineering Lead     | Technical Architect   | ⏳     |      |
| Frontend Developer   | Implementation Lead   | ⏳     |      |
| Security Team        | Security Review       | ⏳     |      |
| QA Lead              | Testing Approval      | ⏳     |      |

---

## Revision History

| Version | Date       | Author           | Changes                               |
|---------|------------|------------------|---------------------------------------|
| 1.0     | 2025-10-26 | Business Analyst | Initial PRD creation                  |

---

## Next Steps

1. **Review & Approval:** Circulate PRD to stakeholders for feedback
2. **Technical Refinement:** Frontend developer reviews component architecture
3. **Sprint Planning:** Add P0 items to Sprint 6 backlog
4. **Design Review:** Create high-fidelity mockups for tenant switcher
5. **Implementation:** Begin Phase 1 development

**Priority:** HIGH - Addresses critical UX issue affecting multi-tenant users
**Estimated Effort:** 10-12 developer days (P0 + P1)
**Target Completion:** End of Sprint 6 (2 weeks)
