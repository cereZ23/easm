<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useTenantStore } from '@/stores/tenant'
import { tenantApi } from '@/api/tenants'
import type { DashboardStats } from '@/api/types'

const tenantStore = useTenantStore()
const dashboardData = ref<DashboardStats | null>(null)
const isLoading = ref(true)
const error = ref('')

const currentTenantId = computed(() => tenantStore.currentTenantId)

onMounted(async () => {
  await loadDashboard()
})

async function loadDashboard() {
  if (!currentTenantId.value) {
    error.value = 'No tenant selected'
    isLoading.value = false
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    dashboardData.value = await tenantApi.getDashboard(currentTenantId.value)
  } catch (err: any) {
    console.error('Failed to load dashboard:', err)
    error.value = err.message || 'Failed to load dashboard data'
  } finally {
    isLoading.value = false
  }
}

function getSeverityColor(severity: string): string {
  const colors: Record<string, string> = {
    critical: 'text-red-600 bg-red-100 dark:bg-red-900/20 dark:text-red-400',
    high: 'text-orange-600 bg-orange-100 dark:bg-orange-900/20 dark:text-orange-400',
    medium: 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/20 dark:text-yellow-400',
    low: 'text-blue-600 bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400',
    info: 'text-gray-600 bg-gray-100 dark:bg-gray-900/20 dark:text-gray-400',
  }
  return colors[severity] || colors.info
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleString()
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex justify-between items-center">
      <h2 class="text-2xl font-bold text-gray-900 dark:text-dark-text-primary">Dashboard</h2>
      <button
        @click="loadDashboard"
        :disabled="isLoading"
        class="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
      >
        Refresh
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex items-center justify-center h-64">
      <div class="text-gray-600 dark:text-dark-text-secondary">Loading dashboard...</div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-red-50 dark:bg-red-900/20 p-4 rounded-md">
      <p class="text-red-800 dark:text-red-200">{{ error }}</p>
    </div>

    <!-- Dashboard Content -->
    <div v-else-if="dashboardData">
      <!-- Stats Cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Total Assets -->
        <div class="bg-white dark:bg-dark-bg-secondary p-6 rounded-lg border border-gray-200 dark:border-dark-border">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-600 dark:text-dark-text-secondary">Total Assets</p>
              <p class="text-3xl font-bold text-gray-900 dark:text-dark-text-primary mt-2">
                {{ dashboardData.stats.total_assets.toLocaleString() }}
              </p>
            </div>
            <div class="p-3 bg-blue-100 dark:bg-blue-900/20 rounded-lg">
              <svg class="w-8 h-8 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Total Findings -->
        <div class="bg-white dark:bg-dark-bg-secondary p-6 rounded-lg border border-gray-200 dark:border-dark-border">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-600 dark:text-dark-text-secondary">Total Findings</p>
              <p class="text-3xl font-bold text-gray-900 dark:text-dark-text-primary mt-2">
                {{ dashboardData.stats.total_findings.toLocaleString() }}
              </p>
            </div>
            <div class="p-3 bg-red-100 dark:bg-red-900/20 rounded-lg">
              <svg class="w-8 h-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Critical Findings -->
        <div class="bg-white dark:bg-dark-bg-secondary p-6 rounded-lg border border-gray-200 dark:border-dark-border">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-600 dark:text-dark-text-secondary">Critical Findings</p>
              <p class="text-3xl font-bold text-red-600 dark:text-red-400 mt-2">
                {{ dashboardData.stats.critical_findings.toLocaleString() }}
              </p>
            </div>
            <div class="p-3 bg-red-100 dark:bg-red-900/20 rounded-lg">
              <svg class="w-8 h-8 text-red-600 dark:text-red-400" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Services -->
        <div class="bg-white dark:bg-dark-bg-secondary p-6 rounded-lg border border-gray-200 dark:border-dark-border">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-600 dark:text-dark-text-secondary">Total Services</p>
              <p class="text-3xl font-bold text-gray-900 dark:text-dark-text-primary mt-2">
                {{ dashboardData.stats.total_services.toLocaleString() }}
              </p>
            </div>
            <div class="p-3 bg-green-100 dark:bg-green-900/20 rounded-lg">
              <svg class="w-8 h-8 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      <!-- Findings by Severity -->
      <div class="bg-white dark:bg-dark-bg-secondary p-6 rounded-lg border border-gray-200 dark:border-dark-border">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-dark-text-primary mb-4">Findings by Severity</h3>
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div
            v-for="(count, severity) in dashboardData.stats.findings_by_severity"
            :key="severity"
            class="text-center p-4 rounded-lg"
            :class="getSeverityColor(severity)"
          >
            <p class="text-2xl font-bold">{{ count }}</p>
            <p class="text-sm capitalize mt-1">{{ severity }}</p>
          </div>
        </div>
      </div>

      <!-- Assets by Type -->
      <div class="bg-white dark:bg-dark-bg-secondary p-6 rounded-lg border border-gray-200 dark:border-dark-border">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-dark-text-primary mb-4">Assets by Type</h3>
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div
            v-for="(count, type) in dashboardData.stats.assets_by_type"
            :key="type"
            class="text-center p-4 rounded-lg bg-gray-50 dark:bg-dark-bg-tertiary"
          >
            <p class="text-2xl font-bold text-gray-900 dark:text-dark-text-primary">{{ count }}</p>
            <p class="text-sm text-gray-600 dark:text-dark-text-secondary capitalize mt-1">{{ type }}</p>
          </div>
        </div>
      </div>

      <!-- Recent Activity -->
      <div class="bg-white dark:bg-dark-bg-secondary p-6 rounded-lg border border-gray-200 dark:border-dark-border">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-dark-text-primary mb-4">Recent Activity</h3>
        <div v-if="dashboardData.recent_activity && dashboardData.recent_activity.length > 0" class="space-y-3">
          <div
            v-for="activity in dashboardData.recent_activity"
            :key="activity.id"
            class="flex items-start p-3 rounded-lg bg-gray-50 dark:bg-dark-bg-tertiary"
          >
            <div class="flex-1">
              <p class="text-sm font-medium text-gray-900 dark:text-dark-text-primary">{{ activity.description }}</p>
              <p class="text-xs text-gray-600 dark:text-dark-text-secondary mt-1">
                {{ formatDate(activity.timestamp) }}
              </p>
            </div>
          </div>
        </div>
        <p v-else class="text-sm text-gray-600 dark:text-dark-text-secondary">No recent activity</p>
      </div>

      <!-- Additional Stats -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="bg-white dark:bg-dark-bg-secondary p-6 rounded-lg border border-gray-200 dark:border-dark-border">
          <p class="text-sm text-gray-600 dark:text-dark-text-secondary">Certificates</p>
          <p class="text-2xl font-bold text-gray-900 dark:text-dark-text-primary mt-2">
            {{ dashboardData.stats.total_certificates.toLocaleString() }}
          </p>
        </div>
        <div class="bg-white dark:bg-dark-bg-secondary p-6 rounded-lg border border-gray-200 dark:border-dark-border">
          <p class="text-sm text-gray-600 dark:text-dark-text-secondary">Expiring Certificates</p>
          <p class="text-2xl font-bold text-orange-600 dark:text-orange-400 mt-2">
            {{ dashboardData.stats.expiring_certificates.toLocaleString() }}
          </p>
        </div>
        <div class="bg-white dark:bg-dark-bg-secondary p-6 rounded-lg border border-gray-200 dark:border-dark-border">
          <p class="text-sm text-gray-600 dark:text-dark-text-secondary">Average Risk Score</p>
          <p class="text-2xl font-bold text-gray-900 dark:text-dark-text-primary mt-2">
            {{ dashboardData.stats.average_risk_score.toFixed(1) }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
