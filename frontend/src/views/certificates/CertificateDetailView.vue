<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTenantStore } from '@/stores/tenant'
import { certificateApi } from '@/api/certificates'
import { assetApi } from '@/api/assets'
import type { Certificate, Asset } from '@/api/types'
import { ArrowLeftIcon } from '@heroicons/vue/24/outline'

const route = useRoute()
const router = useRouter()
const tenantStore = useTenantStore()

const certId = computed(() => parseInt(route.params.id as string))
const certificate = ref<Certificate | null>(null)
const asset = ref<Asset | null>(null)
const isLoading = ref(true)
const error = ref('')

async function loadCertificateDetails() {
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

    // Fetch certificate details
    const certsRes = await certificateApi.list(tenantStore.currentTenantId, {})
    certificate.value = certsRes.items.find(c => c.id === certId.value) || null

    if (!certificate.value) {
      error.value = 'Certificate not found'
      return
    }

    // Fetch related asset
    const assetsRes = await assetApi.list(tenantStore.currentTenantId, {})
    asset.value = assetsRes.items.find(a => a.id === certificate.value!.asset_id) || null

  } catch (err: any) {
    console.error('Failed to load certificate details:', err)
    error.value = err.response?.data?.detail || 'Failed to load certificate details'
  } finally {
    isLoading.value = false
  }
}

function getExpiryColor(cert: Certificate): string {
  if (cert.is_expired) {
    return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
  }
  if (cert.days_until_expiry !== undefined && cert.days_until_expiry <= 30) {
    return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300'
  }
  return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString()
}

onMounted(() => {
  loadCertificateDetails()
})
</script>

<template>
  <div>
    <!-- Header with back button -->
    <div class="mb-6 flex items-center">
      <button
        @click="router.push('/certificates')"
        class="mr-4 p-2 rounded-md text-gray-500 dark:text-dark-text-secondary hover:bg-gray-100 dark:hover:bg-dark-bg-tertiary"
      >
        <ArrowLeftIcon class="h-5 w-5" />
      </button>
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-dark-text-primary">
          Certificate Details
        </h1>
        <p v-if="certificate" class="mt-1 text-sm text-gray-500 dark:text-dark-text-secondary">
          {{ certificate.subject_cn }}
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

    <!-- Certificate Details -->
    <div v-else-if="certificate" class="space-y-6">
      <!-- Overview Card -->
      <div class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-6">
        <div class="flex items-center gap-2 mb-4">
          <span :class="['inline-flex items-center px-3 py-1 rounded-full text-sm font-medium', getExpiryColor(certificate)]">
            <template v-if="certificate.is_expired">Expired</template>
            <template v-else-if="certificate.days_until_expiry !== undefined && certificate.days_until_expiry <= 30">
              Expires in {{ certificate.days_until_expiry }} days
            </template>
            <template v-else>Valid</template>
          </span>
          <span v-if="certificate.is_wildcard" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
            Wildcard
          </span>
          <span v-if="certificate.is_self_signed" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">
            Self-Signed
          </span>
          <span v-if="certificate.has_weak_signature" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300">
            Weak Signature
          </span>
        </div>

        <h2 class="text-xl font-semibold text-gray-900 dark:text-dark-text-primary mb-6">
          {{ certificate.subject_cn }}
        </h2>

        <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Issuer</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ certificate.issuer }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Serial Number</dt>
            <dd class="mt-1 text-sm font-mono text-gray-900 dark:text-dark-text-primary">
              {{ certificate.serial_number }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Valid From</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ certificate.not_before ? formatDate(certificate.not_before) : 'N/A' }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Valid Until</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ certificate.not_after ? formatDate(certificate.not_after) : 'N/A' }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Signature Algorithm</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ certificate.signature_algorithm || 'N/A' }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Public Key</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ certificate.public_key_algorithm }} {{ certificate.public_key_bits }} bits
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">First Seen</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ certificate.first_seen ? formatDate(certificate.first_seen) : 'N/A' }}
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500 dark:text-dark-text-secondary">Last Seen</dt>
            <dd class="mt-1 text-sm text-gray-900 dark:text-dark-text-primary">
              {{ certificate.last_seen ? formatDate(certificate.last_seen) : 'N/A' }}
            </dd>
          </div>
        </dl>
      </div>

      <!-- SAN Domains -->
      <div v-if="certificate.san_domains && certificate.san_domains.length > 0" class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-6">
        <h3 class="text-lg font-medium text-gray-900 dark:text-dark-text-primary mb-4">
          Subject Alternative Names ({{ certificate.san_domains.length }})
        </h3>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="domain in certificate.san_domains"
            :key="domain"
            class="inline-flex items-center px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300"
          >
            {{ domain }}
          </span>
        </div>
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
