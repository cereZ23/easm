<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { RouterView, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { useThemeStore } from '@/stores/theme'

const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()
const themeStore = useThemeStore()

const isLoading = ref(true)
const isSidebarOpen = ref(true)

onMounted(async () => {
  try {
    // Check if we have a token first
    if (!authStore.accessToken) {
      console.log('No access token, redirecting to login')
      router.push('/login')
      return
    }

    await authStore.fetchCurrentUser()
    await tenantStore.fetchTenants()
    isLoading.value = false
  } catch (error: any) {
    console.error('Failed to load user or tenants:', error)
    isLoading.value = false

    // If unauthorized, clear tokens and redirect to login
    if (error?.response?.status === 401 || error?.message?.includes('401')) {
      console.log('Unauthorized, clearing tokens and redirecting to login')
      authStore.clearTokens()
      router.push('/login')
    }
  }
})

const currentTenant = computed(() => tenantStore.currentTenant)

function handleLogout() {
  authStore.logout()
}

function toggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-dark-bg-primary">
    <!-- Top Navigation -->
    <nav class="bg-white dark:bg-dark-bg-secondary border-b border-gray-200 dark:border-dark-border">
      <div class="px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center">
            <button
              @click="toggleSidebar"
              class="mr-4 p-2 rounded-md text-gray-600 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <h1 class="text-xl font-bold text-gray-900 dark:text-dark-text-primary">EASM Platform</h1>
          </div>

          <div class="flex items-center space-x-4">
            <!-- Tenant Selector -->
            <div v-if="currentTenant" class="text-sm">
              <span class="text-gray-600 dark:text-dark-text-secondary">Tenant:</span>
              <span class="ml-2 font-medium text-gray-900 dark:text-dark-text-primary">{{ currentTenant.name }}</span>
            </div>

            <!-- Theme Toggle -->
            <button
              @click="themeStore.toggleTheme"
              class="p-2 rounded-md text-gray-600 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
            >
              <svg v-if="themeStore.isDark" class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" />
              </svg>
              <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
              </svg>
            </button>

            <!-- User Menu -->
            <div class="flex items-center space-x-3">
              <span class="text-sm text-gray-700 dark:text-dark-text-secondary">
                {{ authStore.currentUser?.email }}
              </span>
              <button
                @click="handleLogout"
                class="px-3 py-2 text-sm font-medium text-gray-700 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary rounded-md"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <div class="flex">
      <!-- Sidebar -->
      <aside
        v-show="isSidebarOpen"
        class="w-64 bg-white dark:bg-dark-bg-secondary border-r border-gray-200 dark:border-dark-border min-h-screen"
      >
        <nav class="p-4 space-y-1">
          <router-link
            to="/"
            class="flex items-center px-3 py-2 text-sm font-medium rounded-md text-gray-700 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
            :class="{ 'bg-gray-100 dark:bg-dark-bg-tertiary': $route.name === 'Dashboard' }"
          >
            <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            Dashboard
          </router-link>

          <router-link
            to="/assets"
            class="flex items-center px-3 py-2 text-sm font-medium rounded-md text-gray-700 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
            :class="{ 'bg-gray-100 dark:bg-dark-bg-tertiary': $route.name === 'AssetList' }"
          >
            <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
            </svg>
            Assets
          </router-link>

          <router-link
            to="/findings"
            class="flex items-center px-3 py-2 text-sm font-medium rounded-md text-gray-700 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
            :class="{ 'bg-gray-100 dark:bg-dark-bg-tertiary': $route.name === 'FindingList' }"
          >
            <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Findings
          </router-link>

          <router-link
            to="/services"
            class="flex items-center px-3 py-2 text-sm font-medium rounded-md text-gray-700 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
            :class="{ 'bg-gray-100 dark:bg-dark-bg-tertiary': $route.name === 'ServiceList' }"
          >
            <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
            </svg>
            Services
          </router-link>

          <router-link
            to="/certificates"
            class="flex items-center px-3 py-2 text-sm font-medium rounded-md text-gray-700 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
            :class="{ 'bg-gray-100 dark:bg-dark-bg-tertiary': $route.name === 'CertificateList' }"
          >
            <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Certificates
          </router-link>

          <!-- Admin Section -->
          <div v-if="authStore.currentUser?.is_superuser" class="pt-4 mt-4 border-t border-gray-200 dark:border-dark-border">
            <p class="px-3 mb-2 text-xs font-semibold text-gray-500 dark:text-dark-text-tertiary uppercase tracking-wider">
              Admin
            </p>
            <router-link
              to="/admin/onboard-customer"
              class="flex items-center px-3 py-2 text-sm font-medium rounded-md text-gray-700 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
              :class="{ 'bg-gray-100 dark:bg-dark-bg-tertiary': $route.name === 'OnboardCustomer' }"
            >
              <svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
              </svg>
              Onboard Customer
            </router-link>
          </div>
        </nav>
      </aside>

      <!-- Main Content -->
      <main class="flex-1 p-6">
        <div v-if="isLoading" class="flex items-center justify-center h-64">
          <div class="text-gray-600 dark:text-dark-text-secondary">Loading...</div>
        </div>
        <RouterView v-else />
      </main>
    </div>
  </div>
</template>
