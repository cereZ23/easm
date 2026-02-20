<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTenantStore } from '@/stores/tenant'
import { assetApi } from '@/api/assets'
import type { Asset, Service, Finding, Certificate } from '@/api/types'
import { ArrowLeftIcon } from '@heroicons/vue/24/outline'

const route = useRoute()
const router = useRouter()
const tenantStore = useTenantStore()

const assetId = computed(() => parseInt(route.params.id as string))
const asset = ref<Asset | null>(null)
const services = ref<Service[]>([])
const findings = ref<Finding[]>([])
const certificates = ref<Certificate[]>([])
const isLoading = ref(true)
const error = ref('')

async function loadAssetDetails() {
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

    // Fetch asset details using the dedicated endpoint
    const assetDetails = await assetApi.get(tenantStore.currentTenantId, assetId.value)

    if (!assetDetails) {
      error.value = 'Asset not found'
      return
    }

    // The API now returns the asset with related data
    asset.value = assetDetails
    services.value = assetDetails.services || []
    findings.value = assetDetails.findings || []
    certificates.value = assetDetails.certificates || []

  } catch (err: any) {
    console.error('Failed to load asset details:', err)
    error.value = err.response?.data?.detail || 'Failed to load asset details'
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

function getRiskScoreColor(score: number | undefined): string {
  if (!score) return 'text-gray-400 dark:text-dark-text-tertiary'
  if (score >= 80) return 'text-severity-critical'
  if (score >= 60) return 'text-severity-high'
  if (score >= 40) return 'text-severity-medium'
  return 'text-severity-low'
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString()
}

onMounted(() => {
  loadAssetDetails()
})
</script>

<template>
  <div>
    <!-- Header with back button -->
    <div class="mb-6 flex items-center">
      <button
        @click="router.push('/assets')"
        class="mr-4 p-2 rounded-md text-gray-500 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
      >
        <ArrowLeftIcon class="h-5 w-5" />
      </button>
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-dark-text-primary">
          Asset Details
        </h1>
        <p v-if="asset" class="mt-1 text-sm text-gray-500 dark:text-dark-text-secondary">
          {{ asset.identifier }}
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

    <!-- Asset Details -->
    <div v-else-if="asset" class="space-y-6">
      <!-- Overview Card -->
      <div class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-6">
        <h2 class="text-lg font-medium text-gray-900 dark:text-dark-text-primary mb-4">
          Overview
        </h2>
        <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Type</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary capitalize">
              {{ asset.type }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Risk Score</dt>
            <dd class="mt-1 text-sm font-semibold" :class="getRiskScoreColor(asset.risk_score)">
              {{ asset.risk_score?.toFixed(1) || 'N/A' }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Status</dt>
            <dd class="mt-1">
              <span v-if="asset.is_active" class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                Active
              </span>
              <span v-else class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300">
                Inactive
              </span>
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Priority</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary capitalize">
              {{ asset.priority || 'N/A' }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">First Seen</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ asset.first_seen ? formatDate(asset.first_seen) : 'N/A' }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Last Seen</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ asset.last_seen ? formatDate(asset.last_seen) : 'N/A' }}
            </dd>
          </div>
        </dl>
      </div>

      <!-- Services -->
      <div class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-6">
        <h2 class="text-lg font-medium text-gray-900 dark:text-dark-text-primary mb-4">
          Services ({{ services.length }})
        </h2>
        <div v-if="services.length > 0" class="space-y-3">
          <div
            v-for="service in services"
            :key="service.id"
            class="border border-gray-200 dark:border-dark-border rounded-lg p-4"
          >
            <div class="flex justify-between items-start">
              <div>
                <div class="text-sm font-medium text-gray-900 dark:text-dark-text-primary">
                  {{ service.product || 'Unknown' }}
                  <span v-if="service.version" class="text-gray-500 dark:text-dark-text-tertiary">
                    v{{ service.version }}
                  </span>
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-text-secondary">
                  Port {{ service.port }}/{{ service.protocol }}
                  <span v-if="service.has_tls" class="ml-2 text-green-600 dark:text-green-400">
                    🔒 {{ service.tls_version }}
                  </span>
                </div>
                <div v-if="service.http_title" class="mt-1 text-xs text-gray-500 dark:text-dark-text-tertiary">
                  {{ service.http_title }}
                </div>
              </div>
            </div>
          </div>
        </div>
        <p v-else class="text-sm text-gray-500 dark:text-dark-text-secondary">
          No services discovered
        </p>
      </div>

      <!-- Findings -->
      <div class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-6">
        <h2 class="text-lg font-medium text-gray-900 dark:text-dark-text-primary mb-4">
          Findings ({{ findings.length }})
        </h2>
        <div v-if="findings.length > 0" class="space-y-3">
          <div
            v-for="finding in findings"
            :key="finding.id"
            @click="router.push(`/findings/${finding.id}`)"
            class="border border-gray-200 dark:border-dark-border rounded-lg p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-bg-tertiary"
          >
            <div class="flex justify-between items-start">
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span
                    :class="['inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium', getSeverityColor(finding.severity)]"
                  >
                    {{ finding.severity.toUpperCase() }}
                  </span>
                  <span v-if="finding.cve_id" class="text-xs font-mono text-gray-600 dark:text-dark-text-secondary">
                    {{ finding.cve_id }}
                  </span>
                </div>
                <div class="mt-2 text-sm font-medium text-gray-900 dark:text-dark-text-primary">
                  {{ finding.name }}
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-text-tertiary">
                  {{ finding.source }} · {{ formatDate(finding.last_seen) }}
                </div>
              </div>
            </div>
          </div>
        </div>
        <p v-else class="text-sm text-gray-500 dark:text-dark-text-secondary">
          No findings reported
        </p>
      </div>

      <!-- Certificates -->
      <div class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-6">
        <h2 class="text-lg font-medium text-gray-900 dark:text-dark-text-primary mb-4">
          Certificates ({{ certificates.length }})
        </h2>
        <div v-if="certificates.length > 0" class="space-y-3">
          <div
            v-for="cert in certificates"
            :key="cert.id"
            @click="router.push(`/certificates/${cert.id}`)"
            class="border border-gray-200 dark:border-dark-border rounded-lg p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-bg-tertiary"
          >
            <div class="text-sm font-medium text-gray-900 dark:text-dark-text-primary">
              {{ cert.subject_cn }}
            </div>
            <div class="mt-1 text-xs text-gray-500 dark:text-dark-text-secondary">
              Issuer: {{ cert.issuer }}
            </div>
            <div class="mt-2 flex gap-2">
              <span v-if="cert.is_expired" class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300">
                Expired
              </span>
              <span v-else-if="cert.days_until_expiry && cert.days_until_expiry <= 30" class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300">
                Expires in {{ cert.days_until_expiry }} days
              </span>
              <span v-if="cert.is_wildcard" class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                Wildcard
              </span>
            </div>
          </div>
        </div>
        <p v-else class="text-sm text-gray-500 dark:text-dark-text-secondary">
          No certificates found
        </p>
      </div>
    </div>
  </div>
</template>
