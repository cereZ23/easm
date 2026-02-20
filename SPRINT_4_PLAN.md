# Sprint 4: Vue.js Frontend + Dashboard

**Goal:** Build a world-class Vue.js frontend with real-time dashboard, asset visualization, and finding triage interface

**Duration:** Estimated 3-4 days
**Status:** 🚀 Starting
**Prerequisites:** ✅ Sprint 3 Complete (API with 35 endpoints ready)

---

## Objectives

### Core Features
1. **Authentication Flow** - Login, logout, token refresh
2. **Main Dashboard** - Real-time statistics and KPIs
3. **Asset Management** - Tree view, search, filtering
4. **Finding Triage** - Kanban board for vulnerability management
5. **Certificate Monitor** - Expiry alerts and health
6. **Dark Mode** - Professional dark/light theme toggle
7. **Data Visualization** - Charts, graphs, trends
8. **Responsive Design** - Mobile-first, works on all devices

---

## Technology Stack

### Core Framework
- **Vue 3** - Composition API with `<script setup>`
- **TypeScript** - Full type safety
- **Vite** - Lightning-fast build tool
- **Pinia** - State management
- **Vue Router** - Client-side routing

### UI Components
- **Tailwind CSS** - Utility-first styling
- **Headless UI** - Accessible components (Vue version)
- **Heroicons** - Beautiful icon set
- **Vue Transitions** - Smooth animations

### Data Visualization
- **Chart.js** + **vue-chartjs** - Charts and graphs
- **D3.js** - Advanced visualizations
- **Vue Flow** - Asset tree/network diagrams

### API Integration
- **Axios** - HTTP client with interceptors
- **Tanstack Query (Vue Query)** - Data fetching, caching, sync

### Additional Libraries
- **VueUse** - Composition utilities
- **date-fns** - Date formatting
- **Zod** - Schema validation
- **clsx** - Conditional classes

---

## Architecture

### Project Structure
```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── api/               # API client and services
│   │   ├── client.ts      # Axios instance with auth
│   │   ├── auth.ts        # Auth endpoints
│   │   ├── tenants.ts     # Tenant endpoints
│   │   ├── assets.ts      # Asset endpoints
│   │   ├── findings.ts    # Finding endpoints
│   │   └── types.ts       # API type definitions
│   ├── assets/            # Static assets
│   │   ├── images/
│   │   └── icons/
│   ├── components/        # Reusable components
│   │   ├── common/        # Buttons, Inputs, Cards
│   │   ├── layout/        # Navbar, Sidebar, Footer
│   │   ├── charts/        # Chart components
│   │   └── tables/        # Data tables
│   ├── composables/       # Vue composables
│   │   ├── useAuth.ts
│   │   ├── useTenant.ts
│   │   └── useTheme.ts
│   ├── layouts/           # Page layouts
│   │   ├── AuthLayout.vue
│   │   └── DashboardLayout.vue
│   ├── router/            # Vue Router config
│   │   └── index.ts
│   ├── stores/            # Pinia stores
│   │   ├── auth.ts
│   │   ├── tenant.ts
│   │   └── theme.ts
│   ├── views/             # Page components
│   │   ├── auth/
│   │   │   ├── LoginView.vue
│   │   │   └── LogoutView.vue
│   │   ├── dashboard/
│   │   │   └── DashboardView.vue
│   │   ├── assets/
│   │   │   ├── AssetListView.vue
│   │   │   ├── AssetDetailView.vue
│   │   │   └── AssetTreeView.vue
│   │   ├── findings/
│   │   │   ├── FindingListView.vue
│   │   │   ├── FindingBoardView.vue
│   │   │   └── FindingDetailView.vue
│   │   ├── certificates/
│   │   │   └── CertificateListView.vue
│   │   └── settings/
│   │       └── SettingsView.vue
│   ├── utils/             # Utility functions
│   │   ├── format.ts      # Formatters
│   │   └── validators.ts  # Validation
│   ├── App.vue            # Root component
│   ├── main.ts            # App entry point
│   └── style.css          # Global styles
├── .env.example
├── .env.local
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

---

## Key Features Design

### 1. Authentication Flow

**Login Page** (`views/auth/LoginView.vue`)
- Clean, centered login form
- Email + password fields
- "Remember me" checkbox
- Error handling with toast notifications
- Automatic redirect after login

**Auth Store** (`stores/auth.ts`)
```typescript
interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
}

// Actions
- login(email, password)
- logout()
- refreshAccessToken()
- fetchCurrentUser()
```

**Auth Guard** (`router/index.ts`)
- Protect routes requiring authentication
- Redirect to login if not authenticated
- Check token expiry and auto-refresh

### 2. Main Dashboard

**Dashboard View** (`views/dashboard/DashboardView.vue`)

**Layout:**
```
┌─────────────────────────────────────────────┐
│  [Logo]  Dashboard    [Tenant ▼]  [🌙] [👤] │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐      │
│  │ 1,234│ │  456 │ │  89  │ │  12  │      │
│  │Assets│ │Svcs  │ │Certs │ │Finds │      │
│  └──────┘ └──────┘ └──────┘ └──────┘      │
│                                             │
│  ┌─────────────────┐ ┌──────────────────┐ │
│  │ Asset Growth    │ │ Severity Dist.   │ │
│  │ (Line Chart)    │ │ (Doughnut)       │ │
│  └─────────────────┘ └──────────────────┘ │
│                                             │
│  ┌─────────────────────────────────────┐  │
│  │ Recent Findings                      │  │
│  │ ┌───────────────────────────────┐   │  │
│  │ │ CVE-2024-1234  Critical  🔴   │   │  │
│  │ │ Exposed Admin Panel  High 🟠  │   │  │
│  │ └───────────────────────────────┘   │  │
│  └─────────────────────────────────────┘  │
│                                             │
└─────────────────────────────────────────────┘
```

**Components:**
- `StatCard.vue` - KPI cards with icons
- `AssetGrowthChart.vue` - Line chart (Chart.js)
- `SeverityDistributionChart.vue` - Doughnut chart
- `RecentFindingsTable.vue` - Latest findings
- `TenantSelector.vue` - Dropdown for multi-tenant

**Real-time Updates:**
- Use Vue Query with `refetchInterval: 30000` (30s)
- WebSocket connection for instant updates (future)
- Loading skeletons during fetch

### 3. Asset Management

**Asset List View** (`views/assets/AssetListView.vue`)
- Searchable, filterable table
- Columns: Type, Identifier, Risk Score, Last Seen, Actions
- Pagination with page size selector
- Export to CSV/JSON
- Bulk actions (scan, delete)

**Asset Tree View** (`views/assets/AssetTreeView.vue`)
- Hierarchical visualization using Vue Flow
- Root domains → Subdomains → IPs → Services
- Click to expand/collapse
- Color-coded by risk level
- Zoom/pan controls

**Asset Detail View** (`views/assets/AssetDetailView.vue`)
- Full asset details
- Associated services, certificates, endpoints
- Finding timeline
- Scan history
- Quick actions (re-scan, delete)

### 4. Finding Triage Interface

**Finding Board View** (`views/findings/FindingBoardView.vue`)

**Kanban Layout:**
```
┌──────────┐ ┌──────────┐ ┌──────────┐
│  OPEN    │ │SUPPRESSED│ │  FIXED   │
│  (45)    │ │   (12)   │ │   (23)   │
├──────────┤ ├──────────┤ ├──────────┤
│ ┌──────┐ │ │ ┌──────┐ │ │ ┌──────┐ │
│ │ CVE  │ │ │ │False │ │ │ │Patched│ │
│ │-2024 │ │ │ │Pos.  │ │ │ │Last  │ │
│ │-1234 │ │ │ │      │ │ │ │Week  │ │
│ └──────┘ │ │ └──────┘ │ │ └──────┘ │
│          │ │          │ │          │
└──────────┘ └──────────┘ └──────────┘
```

**Features:**
- Drag-and-drop between columns
- Filter by severity, asset, CVE
- Search by name, template ID
- Click card to view details
- Batch status updates

**Finding Detail Modal:**
- Full finding information
- CVSS score and vector
- Evidence/proof
- Affected assets
- Remediation guidance
- Status change + notes
- Export report

### 5. Certificate Monitor

**Certificate List View** (`views/certificates/CertificateListView.vue`)
- Table with expiry warnings
- Color-coded by days until expiry:
  - 🔴 Expired or <7 days
  - 🟠 <30 days
  - 🟡 <60 days
  - 🟢 >60 days
- Filter: expired, expiring soon, self-signed, weak signature
- Certificate health dashboard (pie charts)

### 6. Dark Mode

**Theme System**
- Use Tailwind dark mode (class strategy)
- Toggle in navbar
- Persist preference to localStorage
- Smooth transitions between modes

**Color Palette:**
```css
/* Light Mode */
--bg-primary: #ffffff
--bg-secondary: #f3f4f6
--text-primary: #111827
--text-secondary: #6b7280

/* Dark Mode */
--bg-primary: #1f2937
--bg-secondary: #111827
--text-primary: #f9fafb
--text-secondary: #9ca3af
```

### 7. Data Visualization

**Chart Types:**
- Line Chart - Asset growth over time
- Doughnut Chart - Severity distribution
- Bar Chart - Findings by asset type
- Stacked Area Chart - Finding trends
- Radar Chart - Technology stack risk

**Chart Components:**
- `LineChart.vue`
- `DoughnutChart.vue`
- `BarChart.vue`
- `AreaChart.vue`
- `RadarChart.vue`

**Configuration:**
- Responsive sizing
- Dark mode compatible colors
- Tooltips with detailed info
- Click to drill down
- Export chart as PNG

---

## State Management (Pinia)

### Auth Store (`stores/auth.ts`)
```typescript
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    accessToken: localStorage.getItem('accessToken'),
    refreshToken: localStorage.getItem('refreshToken'),
  }),

  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    currentUser: (state) => state.user,
  },

  actions: {
    async login(email: string, password: string) {
      const response = await authApi.login({ email, password })
      this.setTokens(response.access_token, response.refresh_token)
      this.user = response.user
    },

    logout() {
      this.clearTokens()
      router.push('/login')
    },

    setTokens(access: string, refresh: string) {
      this.accessToken = access
      this.refreshToken = refresh
      localStorage.setItem('accessToken', access)
      localStorage.setItem('refreshToken', refresh)
    },

    clearTokens() {
      this.accessToken = null
      this.refreshToken = null
      this.user = null
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
    }
  }
})
```

### Tenant Store (`stores/tenant.ts`)
```typescript
export const useTenantStore = defineStore('tenant', {
  state: () => ({
    currentTenant: null,
    tenants: [],
  }),

  actions: {
    async fetchTenants() {
      this.tenants = await tenantApi.list()
    },

    selectTenant(tenantId: number) {
      this.currentTenant = this.tenants.find(t => t.id === tenantId)
      localStorage.setItem('currentTenantId', String(tenantId))
    }
  }
})
```

### Theme Store (`stores/theme.ts`)
```typescript
export const useThemeStore = defineStore('theme', {
  state: () => ({
    isDark: localStorage.getItem('theme') === 'dark',
  }),

  actions: {
    toggleTheme() {
      this.isDark = !this.isDark
      document.documentElement.classList.toggle('dark')
      localStorage.setItem('theme', this.isDark ? 'dark' : 'light')
    }
  }
})
```

---

## API Client (`api/client.ts`)

```typescript
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:18000',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - Add auth token
apiClient.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.accessToken) {
    config.headers.Authorization = `Bearer ${authStore.accessToken}`
  }
  return config
})

// Response interceptor - Handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const authStore = useAuthStore()
      try {
        const response = await authApi.refresh(authStore.refreshToken)
        authStore.setTokens(response.access_token, response.refresh_token)
        return apiClient(originalRequest)
      } catch (refreshError) {
        authStore.logout()
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
```

---

## Routing (`router/index.ts`)

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/layouts/DashboardLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/DashboardView.vue')
      },
      {
        path: 'assets',
        name: 'AssetList',
        component: () => import('@/views/assets/AssetListView.vue')
      },
      {
        path: 'assets/tree',
        name: 'AssetTree',
        component: () => import('@/views/assets/AssetTreeView.vue')
      },
      {
        path: 'assets/:id',
        name: 'AssetDetail',
        component: () => import('@/views/assets/AssetDetailView.vue')
      },
      {
        path: 'findings',
        name: 'FindingList',
        component: () => import('@/views/findings/FindingListView.vue')
      },
      {
        path: 'findings/board',
        name: 'FindingBoard',
        component: () => import('@/views/findings/FindingBoardView.vue')
      },
      {
        path: 'certificates',
        name: 'CertificateList',
        component: () => import('@/views/certificates/CertificateListView.vue')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/settings/SettingsView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    next('/')
  } else {
    next()
  }
})

export default router
```

---

## Docker Integration

### Frontend Dockerfile
```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### Update docker-compose.yml
```yaml
services:
  ui:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: easm-ui
    ports:
      - "13000:80"
    environment:
      - VITE_API_BASE_URL=http://localhost:18000
    depends_on:
      - api
    networks:
      - easm-network
```

---

## Development Workflow

### Initial Setup
```bash
# Create Vue project
npm create vite@latest frontend -- --template vue-ts
cd frontend

# Install dependencies
npm install vue-router@4 pinia
npm install axios @tanstack/vue-query
npm install @headlessui/vue @heroicons/vue
npm install chart.js vue-chartjs
npm install @vueuse/core date-fns zod clsx
npm install -D tailwindcss postcss autoprefixer
npm install -D @types/node

# Initialize Tailwind
npx tailwindcss init -p
```

### Development Server
```bash
npm run dev
# Runs on http://localhost:5173
```

### Build for Production
```bash
npm run build
# Output: dist/
```

### Docker Build
```bash
docker-compose build ui
docker-compose up ui
# Access at http://localhost:13000
```

---

## Testing Strategy

### Unit Tests (Vitest)
- Component tests
- Store tests
- Utility function tests

### E2E Tests (Playwright)
- Login flow
- Dashboard navigation
- Asset CRUD operations
- Finding triage workflow

---

## Performance Optimizations

1. **Code Splitting** - Route-based lazy loading
2. **Tree Shaking** - Remove unused code
3. **Image Optimization** - WebP format, lazy loading
4. **Caching** - Vue Query with stale-while-revalidate
5. **Virtual Scrolling** - For large tables/lists
6. **Debouncing** - Search inputs, API calls
7. **Memoization** - Expensive computed values

---

## Accessibility (a11y)

- Semantic HTML
- ARIA labels
- Keyboard navigation
- Focus management
- Color contrast (WCAG AA)
- Screen reader support
- Alt text for images

---

## Deliverables

### Code
- [ ] Vue 3 project with TypeScript
- [ ] 15+ reusable components
- [ ] 8+ view pages
- [ ] 3+ Pinia stores
- [ ] API client with auth interceptors
- [ ] Router with guards
- [ ] Tailwind CSS config
- [ ] Dark mode theme

### Features
- [ ] Login/logout flow
- [ ] Main dashboard with stats
- [ ] Asset list + tree view
- [ ] Finding Kanban board
- [ ] Certificate monitor
- [ ] Multi-tenant selector
- [ ] Dark mode toggle
- [ ] Charts and graphs

### Documentation
- [ ] Component documentation
- [ ] API integration guide
- [ ] Deployment guide
- [ ] User guide (screenshots)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Page Load Time | <2s |
| Time to Interactive | <3s |
| Lighthouse Score | >90 |
| Bundle Size | <500KB |
| API Response Time | <200ms |
| Test Coverage | >80% |
| Accessibility | WCAG AA |

---

## Timeline

### Day 1: Foundation
- ✅ Sprint 4 plan
- [ ] Vue project setup
- [ ] Tailwind configuration
- [ ] Router + stores
- [ ] API client
- [ ] Auth flow

### Day 2: Core Views
- [ ] Dashboard view
- [ ] Asset list + detail
- [ ] Finding list + board
- [ ] Certificate list

### Day 3: Advanced Features
- [ ] Asset tree visualization
- [ ] Charts integration
- [ ] Dark mode
- [ ] Real-time updates

### Day 4: Polish
- [ ] Responsive design
- [ ] Performance optimization
- [ ] Testing
- [ ] Documentation

---

**Sprint 4 Ready to Start!** 🚀
