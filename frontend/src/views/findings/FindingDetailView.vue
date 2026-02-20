<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTenantStore } from '@/stores/tenant'
import { findingApi } from '@/api/findings'
import { assetApi } from '@/api/assets'
import type { Finding, Asset } from '@/api/types'
import { ArrowLeftIcon } from '@heroicons/vue/24/outline'

const route = useRoute()
const router = useRouter()
const tenantStore = useTenantStore()

const findingId = computed(() => parseInt(route.params.id as string))
const finding = ref<Finding | null>(null)
const asset = ref<Asset | null>(null)
const isLoading = ref(true)
const error = ref('')

async function loadFindingDetails() {
  try {
    isLoading.value = true
    error.value = ''

    if (!tenantStore.currentTenantId) {
      await tenantStore.fetchTenants()
    }

    if (!tenantStore.currentTenantId) {
      error.value = 'No tenant available'
      return
    }

    // Fetch finding details
    const findingsRes = await findingApi.list(tenantStore.currentTenantId, {})
    finding.value = findingsRes.items.find(f => f.id === findingId.value) || null

    if (!finding.value) {
      error.value = 'Finding not found'
      return
    }

    // Fetch related asset
    const assetsRes = await assetApi.list(tenantStore.currentTenantId, {})
    asset.value = assetsRes.items.find(a => a.id === finding.value!.asset_id) || null

  } catch (err: any) {
    console.error('Failed to load finding details:', err)
    error.value = err.response?.data?.detail || 'Failed to load finding details'
  } finally {
    isLoading.value = false
  }
}

function getSeverityColor(severity: string): string {
  const colors: Record<string, string> = {
    critical: 'bg-severity-critical text-white',
    high: 'bg-severity-high text-white',
    medium: 'bg-severity-medium text-white',
    low: 'bg-severity-low text-white',
    info: 'bg-severity-info text-white',
  }
  return colors[severity.toLowerCase()] || 'bg-gray-500 text-white'
}

function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    open: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
    suppressed: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
    fixed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  }
  return colors[status.toLowerCase()] || 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300'
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString()
}

onMounted(() => {
  loadFindingDetails()
})
</script>

<template>
  <div>
    <!-- Header with back button -->
    <div class="mb-6 flex items-center">
      <button
        @click="router.push('/findings')"
        class="mr-4 p-2 rounded-md text-gray-500 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
      >
        <ArrowLeftIcon class="h-5 w-5" />
      </button>
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-dark-text-primary">
          Finding Details
        </h1>
        <p v-if="finding" class="mt-1 text-sm text-gray-500 dark:text-dark-text-secondary">
          {{ finding.name }}
        </p>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="error" class="rounded-md bg-red-50 dark:bg-red-900/20 p-4 mb-6">
      <p class="text-sm text-red-800 dark:text-red-200">{{ error }}</p>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-8">
      <div class="animate-pulse space-y-4">
        <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full"></div>
        <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
      </div>
    </div>

    <!-- Finding Details -->
    <div v-else-if="finding" class="space-y-6">
      <!-- Overview Card -->
      <div class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-6">
        <div class="flex items-start justify-between mb-4">
          <div class="flex items-center gap-3">
            <span
              :class="['inline-flex items-center px-3 py-1 rounded-full text-sm font-medium', getSeverityColor(finding.severity)]"
            >
              {{ finding.severity.toUpperCase() }}
            </span>
            <span
              :class="['inline-flex items-center px-3 py-1 rounded-full text-sm font-medium', getStatusColor(finding.status)]"
            >
              {{ finding.status }}
            </span>
          </div>
          <span v-if="finding.cvss_score" class="text-sm font-medium text-gray-900 dark:text-dark-text-primary">
            CVSS: {{ finding.cvss_score }}
          </span>
        </div>

        <h2 class="text-xl font-semibold text-gray-900 dark:text-dark-text-primary mb-4">
          {{ finding.name }}
        </h2>

        <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div v-if="finding.cve_id">
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">CVE ID</dt>
            <dd class="mt-1 text-sm font-mono text-gray-900 dark:text-dark-text-primary">
              {{ finding.cve_id }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Source</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary capitalize">
              {{ finding.source }}
            </dd>
          </div>
          <div v-if="finding.template_id">
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Template ID</dt>
            <dd class="mt-1 text-sm font-mono text-gray-900 dark:text-dark-text-primary">
              {{ finding.template_id }}
            </dd>
          </div>
          <div v-if="finding.matcher_name">
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Matcher</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ finding.matcher_name }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">First Seen</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ formatDate(finding.first_seen) }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Last Seen</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ formatDate(finding.last_seen) }}
            </dd>
          </div>
          <div v-if="finding.host" class="sm:col-span-2">
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Host</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ finding.host }}
            </dd>
          </div>
          <div v-if="finding.matched_at" class="sm:col-span-2">
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Matched At</dt>
            <dd class="mt-1 text-sm text-blue-600 dark:text-blue-400 break-all">
              <a :href="finding.matched_at" target="_blank" rel="noopener">
                {{ finding.matched_at }}
              </a>
            </dd>
          </div>
        </dl>
      </div>

      <!-- Evidence -->
      <div v-if="finding.evidence" class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-6">
        <h3 class="text-lg font-medium text-gray-900 dark:text-dark-text-primary mb-4">
          Evidence
        </h3>
        <pre class="bg-gray-50 dark:bg-dark-bg-tertiary rounded-lg p-4 text-xs overflow-x-auto">
          <code class="text-gray-900 dark:text-dark-text-primary">{{ JSON.stringify(finding.evidence, null, 2) }}</code>
        </pre>
      </div>

      <!-- Related Asset -->
      <div v-if="asset" class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-6">
        <h3 class="text-lg font-medium text-gray-900 dark:text-dark-text-primary mb-4">
          Related Asset
        </h3>
        <div
          @click="router.push(`/assets/${asset.id}`)"
          class="border border-gray-200 dark:border-dark-border rounded-lg p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-bg-tertiary"
        >
          <div class="flex justify-between items-start">
            <div>
              <div class="text-sm font-medium text-gray-900 dark:text-dark-text-primary">
                {{ asset.identifier }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-text-secondary capitalize">
                {{ asset.type }}
              </div>
            </div>
            <div class="text-right">
              <div class="text-sm font-medium text-gray-900 dark:text-dark-text-primary">
                Risk: {{ asset.risk_score?.toFixed(1) || 'N/A' }}
              </div>
              <div class="mt-1">
                <span v-if="asset.is_active" class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                  Active
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
