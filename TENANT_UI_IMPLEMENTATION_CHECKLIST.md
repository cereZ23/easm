# Multi-Tenant UI Fix - Implementation Checklist

**For:** Frontend Developer
**Sprint:** Sprint 6
**Estimated:** 10-12 days
**PRD:** See `MULTI_TENANT_UI_FIX_PRD.md` for full requirements

---

## Phase 1: Critical Fixes (Days 1-5)

### Day 1-2: Tenant Switcher Component

- [ ] **Create `frontend/src/components/layout/TenantSwitcher.vue`**
  - Dropdown component showing current tenant name
  - Lists all accessible tenants (from `useTenantStore().tenants`)
  - Click handler calls `tenantStore.selectTenant(id)`
  - Shows role badge per tenant (Owner, Admin, Member, Viewer)
  - Emits `tenant-changed` event on switch

- [ ] **Add visual design:**
  - Dropdown trigger: `[🔄 Acme Corp ▾]`
  - Dropdown menu with tenant list
  - Checkmark on current tenant
  - Responsive (mobile: full-width modal, desktop: dropdown)

- [ ] **State management:**
  - Use `useTenantStore()` from Pinia
  - Watch `currentTenant` changes
  - Persist selection to `localStorage` (already implemented in store)

**Files:**
- `frontend/src/components/layout/TenantSwitcher.vue` (NEW)

**Testing:**
- [ ] Renders with correct tenant name
- [ ] Shows list of tenants on click
- [ ] Switches tenant and updates store
- [ ] Persists to localStorage

---

### Day 2-3: Integrate Tenant Switcher into Layout

- [ ] **Update `frontend/src/layouts/DashboardLayout.vue`**
  - Import `TenantSwitcher.vue`
  - Add between logo and main navigation
  - Listen for `tenant-changed` event
  - Trigger data refresh on current page (emit global event or use router refresh)

- [ ] **Navigation structure:**
  ```
  [EASM Platform] [TenantSwitcher] Dashboard | Assets | Findings | ... [Theme] [User Menu]
  ```

- [ ] **Responsive layout:**
  - Desktop: Inline in navbar
  - Mobile: Move to hamburger menu or sticky header

**Files:**
- `frontend/src/layouts/DashboardLayout.vue` (UPDATE)

**Testing:**
- [ ] Switcher visible on all pages
- [ ] Switching tenant refreshes dashboard data
- [ ] Switching tenant from Assets page shows new tenant's assets

---

### Day 3-4: Tenant Context Indicators

- [ ] **Create `frontend/src/components/layout/TenantBadge.vue`**
  - Small badge/chip showing current tenant name
  - Optional: Color-coded per tenant
  - Props: `size` (small, medium), `showIcon` (boolean)

- [ ] **Add TenantBadge to page headers:**
  - `DashboardView.vue`: Subtitle or breadcrumb
  - `AssetsView.vue`: Header subtitle
  - `FindingsView.vue`: Header subtitle
  - `CertificatesView.vue`: Header subtitle
  - `ServicesView.vue`: Header subtitle

- [ ] **Update page titles:**
  - Format: "Assets - Acme Corp"
  - Or breadcrumb: `Home > Acme Corp > Assets`

**Files:**
- `frontend/src/components/layout/TenantBadge.vue` (NEW)
- `frontend/src/views/dashboard/DashboardView.vue` (UPDATE)
- `frontend/src/views/assets/AssetsView.vue` (UPDATE)
- `frontend/src/views/findings/FindingsView.vue` (UPDATE)
- `frontend/src/views/certificates/CertificatesView.vue` (UPDATE)
- `frontend/src/views/services/ServicesView.vue` (UPDATE)

**Testing:**
- [ ] Badge shows current tenant on all pages
- [ ] Badge updates when switching tenant
- [ ] Visual styling is consistent

---

### Day 4-5: Post-Login Tenant Selection

- [ ] **Create `frontend/src/components/modals/TenantSelectionModal.vue`**
  - Modal dialog shown after login
  - Condition: User has multiple tenants AND no current tenant selected
  - Lists tenants with cards (name, role, asset count, finding count)
  - Click card to select tenant and proceed to dashboard
  - "Remember my choice" checkbox (already implemented via localStorage)

- [ ] **Integrate into login flow:**
  - Option A: Add to `DashboardLayout.vue` `onMounted`
  - Option B: Add to router navigation guard
  - Trigger logic:
    ```typescript
    if (tenants.length > 1 && !currentTenant) {
      showTenantSelectionModal = true
    }
    ```

- [ ] **Fetch tenant stats for modal:**
  - Consider calling `GET /api/v1/tenants/{id}/dashboard` for each tenant
  - Or add summary stats to `GET /api/v1/tenants` response

**Files:**
- `frontend/src/components/modals/TenantSelectionModal.vue` (NEW)
- `frontend/src/layouts/DashboardLayout.vue` (UPDATE: add modal trigger)

**Testing:**
- [ ] Modal shows for multi-tenant users on first login
- [ ] Modal doesn't show if user has only one tenant
- [ ] Selecting tenant dismisses modal and loads dashboard
- [ ] Modal doesn't show again if tenant already selected

---

### Day 5: Phase 1 Testing & QA

- [ ] **End-to-end testing:**
  - Login as multi-tenant user
  - Select tenant from modal
  - Switch tenant using navbar dropdown
  - Verify data changes on all pages
  - Test localStorage persistence

- [ ] **Cross-browser testing:**
  - Chrome, Firefox, Safari
  - Mobile responsive

- [ ] **Bug fixes and polish:**
  - Address any UX issues
  - Refine styling
  - Add loading states

---

## Phase 2: Management Features (Days 6-10)

### Day 6-7: Tenant Management Page

- [ ] **Create `frontend/src/views/admin/TenantsManagementView.vue`**
  - Table showing all accessible tenants
  - Columns: Name, Slug, Status (Active/Inactive), # Assets, # Findings, Created Date
  - Search/filter by name
  - Click row to switch to tenant and navigate to dashboard
  - For superusers: Show ALL tenants
  - For regular users: Show only tenants with membership

- [ ] **Add route:**
  ```typescript
  {
    path: '/admin/tenants',
    name: 'TenantManagement',
    component: () => import('@/views/admin/TenantsManagementView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  }
  ```

- [ ] **Fetch data:**
  - Use existing `tenantApi.list()`
  - For stats, call `tenantApi.getDashboard(id)` per tenant (async)
  - Consider adding bulk stats endpoint if performance is slow

**Files:**
- `frontend/src/views/admin/TenantsManagementView.vue` (NEW)
- `frontend/src/router/index.ts` (UPDATE: add route)

**Testing:**
- [ ] Admin can see all tenants they manage
- [ ] Superuser sees ALL tenants
- [ ] Regular user sees only their tenants
- [ ] Clicking tenant switches context and navigates

---

### Day 7-8: Admin Navigation

- [ ] **Update `frontend/src/layouts/DashboardLayout.vue`**
  - Add "Admin" dropdown in navbar (conditional on `user.is_superuser`)
  - Dropdown items:
    - "Onboard Customer" → `/admin/onboard`
    - "Manage Tenants" → `/admin/tenants`
  - Place between main navigation and user menu

- [ ] **Visual design:**
  - Icon: Shield or settings icon
  - Label: "Admin" or "Administration"
  - Distinct styling (e.g., different color) to indicate admin mode

**Files:**
- `frontend/src/layouts/DashboardLayout.vue` (UPDATE)

**Testing:**
- [ ] Admin dropdown visible only for superusers
- [ ] Regular users don't see admin menu
- [ ] Links navigate correctly

---

### Day 8-9: Role & Permission Display

- [ ] **Backend: Update `GET /api/v1/tenants` to include role**
  - Modify `app/api/routers/tenants.py`
  - Update `TenantResponse` schema to include `user_role: Optional[str]`
  - For each tenant, include user's role (owner, admin, member, viewer)

- [ ] **Frontend: Update types**
  - `frontend/src/api/types.ts`: Add `user_role?: string` to `Tenant` interface

- [ ] **Display role in UI:**
  - TenantSwitcher dropdown: Show role as secondary text
  - TenantSelectionModal: Show role per tenant card
  - Optional: Tooltip explaining permissions

- [ ] **Add permissions helper:**
  - Create utility function `hasPermission(role, permission)`
  - Use for conditional rendering (e.g., hide "Delete" button for viewers)

**Files:**
- `app/api/routers/tenants.py` (UPDATE)
- `app/api/schemas/tenant.py` (UPDATE)
- `frontend/src/api/types.ts` (UPDATE)
- `frontend/src/components/layout/TenantSwitcher.vue` (UPDATE)
- `frontend/src/components/modals/TenantSelectionModal.vue` (UPDATE)
- `frontend/src/utils/permissions.ts` (NEW: helper functions)

**Testing:**
- [ ] Role displays correctly in tenant switcher
- [ ] Role displays in tenant selection modal
- [ ] Backend includes role in API response

---

### Day 9-10: Phase 2 Testing & Integration

- [ ] **End-to-end admin workflow:**
  - Login as admin
  - Navigate to "Admin" → "Onboard Customer"
  - Create new customer
  - Verify new tenant appears in "Manage Tenants"
  - Switch to new tenant, verify data isolation

- [ ] **Role-based access testing:**
  - Test viewer role: Can read, cannot edit
  - Test member role: Can read/write, cannot admin
  - Test admin role: Full access to tenant
  - Test owner role: All permissions

- [ ] **Performance testing:**
  - Load 50+ tenants, verify switcher performs well
  - Test data refresh speed when switching tenants

- [ ] **Bug fixes and polish**

---

## Code Quality Checklist

### TypeScript
- [ ] All components use proper TypeScript types
- [ ] No `any` types (use specific interfaces)
- [ ] Pinia store typed correctly

### Accessibility
- [ ] Keyboard navigation works (Tab, Enter, Escape)
- [ ] Screen reader compatible (ARIA labels)
- [ ] Focus management in modals

### Responsive Design
- [ ] Mobile layout tested (iPhone, Android)
- [ ] Tablet layout tested
- [ ] Desktop layout tested (1920x1080, 1366x768)

### Error Handling
- [ ] Loading states for async operations
- [ ] Error messages for failed API calls
- [ ] Graceful degradation if tenant API fails

### Dark Mode
- [ ] All new components support dark mode
- [ ] Theme switcher still works

---

## Backend Changes Required

### Minimal Backend Updates (2-3 hours)

**File:** `app/api/routers/tenants.py`

```python
@router.get("", response_model=list[TenantResponse])
def list_tenants(db: Session, current_user: User):
    if current_user.is_superuser:
        tenants = db.query(Tenant).all()
        return [
            TenantResponse(
                **tenant.__dict__,
                user_role="superuser"  # NEW
            ) for tenant in tenants
        ]
    else:
        return [
            TenantResponse(
                **membership.tenant.__dict__,
                user_role=membership.role  # NEW: Include role
            )
            for membership in current_user.tenant_memberships
            if membership.is_active
        ]
```

**File:** `app/api/schemas/tenant.py`

```python
class TenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    user_role: Optional[str] = None  # NEW
```

**Testing:**
- [ ] API returns role for each tenant
- [ ] Superuser gets "superuser" role
- [ ] Regular users get their membership role

---

## Testing Checklist

### Manual Testing Scenarios

1. **Single-Tenant User:**
   - [ ] Login → Auto-select tenant → Dashboard loads
   - [ ] No tenant selection modal shown
   - [ ] Tenant name shown in UI

2. **Multi-Tenant User:**
   - [ ] Login → Tenant selection modal shown
   - [ ] Select tenant → Dashboard loads
   - [ ] Switch tenant via navbar dropdown
   - [ ] Data refreshes on all pages

3. **Admin User:**
   - [ ] Login → Admin dropdown visible
   - [ ] Navigate to "Onboard Customer"
   - [ ] Create new customer successfully
   - [ ] Navigate to "Manage Tenants"
   - [ ] See all tenants in list

4. **Superuser:**
   - [ ] Login → See ALL tenants (not just memberships)
   - [ ] Can access any tenant
   - [ ] Role shows as "superuser"

5. **Data Isolation:**
   - [ ] Switch from Tenant A to Tenant B
   - [ ] Verify assets, findings, certs all change
   - [ ] No data from Tenant A visible in Tenant B context

### Automated Tests (Optional)

- [ ] Unit tests for `TenantSwitcher.vue`
- [ ] Unit tests for `useTenantStore()` updates
- [ ] Integration test: Tenant switching flow
- [ ] E2E test: Multi-tenant user journey

---

## Definition of Done

### Phase 1 (P0 - Critical)
- [x] Tenant switcher component created and integrated
- [x] All pages show current tenant indicator
- [x] Post-login tenant selection modal works
- [x] Switching tenant refreshes data correctly
- [x] Manual testing complete
- [x] Code reviewed and merged

### Phase 2 (P1 - High)
- [x] Tenant management page functional
- [x] Admin navigation added
- [x] Role display implemented
- [x] Backend API updated with role
- [x] End-to-end admin workflow tested
- [x] Code reviewed and merged

### Final Acceptance
- [x] Product owner approval
- [x] No regression bugs
- [x] Documentation updated
- [x] Deployment to staging successful

---

## Support & Resources

- **Full PRD:** `MULTI_TENANT_UI_FIX_PRD.md`
- **Summary:** `MULTI_TENANT_FIX_SUMMARY.md`
- **Current Tenant Store:** `frontend/src/stores/tenant.ts`
- **Backend Tenant Router:** `app/api/routers/tenants.py`
- **Onboarding Page (Reference):** `frontend/src/views/admin/OnboardCustomerView.vue`

**Questions?** Ask in #frontend-dev Slack channel or tag @product-owner
