<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTenantStore } from '@/stores/tenant'
import { certificateApi } from '@/api/certificates'
import type { Certificate, PaginatedResponse } from '@/api/types'

const router = useRouter()
const tenantStore = useTenantStore()

const certificates = ref<Certificate[]>([])
const isLoading = ref(true)
const error = ref('')
const currentPage = ref(1)
const pageSize = ref(25)
const totalItems = ref(0)
const totalPages = ref(0)

// Filters
const searchQuery = ref('')
const isExpiredFilter = ref('')
const isExpiringSoonFilter = ref('')
const isSelfSignedFilter = ref('')
const isWildcardFilter = ref('')

const currentTenantId = computed(() => tenantStore.currentTenantId)

onMounted(async () => {
  await loadCertificates()
})

watch(currentTenantId, () => {
  if (currentTenantId.value) {
    loadCertificates()
  }
})

async function loadCertificates() {
  if (!currentTenantId.value) {
    error.value = 'No tenant selected'
    isLoading.value = false
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchQuery.value || undefined,
      is_expired: isExpiredFilter.value === 'true' ? true : isExpiredFilter.value === 'false' ? false : undefined,
      is_expiring_soon: isExpiringSoonFilter.value === 'true' ? true : isExpiringSoonFilter.value === 'false' ? false : undefined,
      is_self_signed: isSelfSignedFilter.value === 'true' ? true : isSelfSignedFilter.value === 'false' ? false : undefined,
      is_wildcard: isWildcardFilter.value === 'true' ? true : isWildcardFilter.value === 'false' ? false : undefined,
    }

    const response: PaginatedResponse<Certificate> = await certificateApi.list(currentTenantId.value, params)
    certificates.value = response.items
    totalItems.value = response.total
    totalPages.value = response.total_pages
  } catch (err: any) {
    console.error('Failed to load certificates:', err)
    error.value = err.message || 'Failed to load certificates'
  } finally {
    isLoading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  loadCertificates()
}

function goToPage(page: number) {
  currentPage.value = page
  loadCertificates()
}

function viewCertificate(certId: number) {
  router.push({ name: 'CertificateDetail', params: { id: certId } })
}

function getExpiryColor(cert: Certificate): string {
  if (cert.is_expired) {
    return 'text-red-600 dark:text-red-400'
  }
  if (cert.days_until_expiry && cert.days_until_expiry <= 30) {
    return 'text-orange-600 dark:text-orange-400'
  }
  if (cert.days_until_expiry && cert.days_until_expiry <= 90) {
    return 'text-yellow-600 dark:text-yellow-400'
  }
  return 'text-green-600 dark:text-green-400'
}

function formatDate(dateString: string | undefined): string {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleDateString()
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex justify-between items-center">
      <h2 class="text-2xl font-bold text-gray-900 dark:text-dark-text-primary">Certificates</h2>
      <button
        @click="loadCertificates"
        :disabled="isLoading"
        class="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
      >
        Refresh
      </button>
    </div>

    <!-- Filters -->
    <div class="bg-white dark:bg-dark-bg-secondary p-4 rounded-lg border border-gray-200 dark:border-dark-border">
      <div class="grid grid-cols-1 md:grid-cols-6 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary mb-2">Search</label>
          <input
            v-model="searchQuery"
            @keyup.enter="handleSearch"
            type="text"
            placeholder="Search certificates..."
            class="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md text-gray-900 dark:text-dark-text-primary dark:bg-dark-bg-tertiary focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary mb-2">Expired</label>
          <select
            v-model="isExpiredFilter"
            @change="handleSearch"
            class="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md text-gray-900 dark:text-dark-text-primary dark:bg-dark-bg-tertiary focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All</option>
            <option value="true">Expired</option>
            <option value="false">Valid</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary mb-2">Expiring Soon</label>
          <select
            v-model="isExpiringSoonFilter"
            @change="handleSearch"
            class="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md text-gray-900 dark:text-dark-text-primary dark:bg-dark-bg-tertiary focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary mb-2">Self-Signed</label>
          <select
            v-model="isSelfSignedFilter"
            @change="handleSearch"
            class="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md text-gray-900 dark:text-dark-text-primary dark:bg-dark-bg-tertiary focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary mb-2">Wildcard</label>
          <select
            v-model="isWildcardFilter"
            @change="handleSearch"
            class="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md text-gray-900 dark:text-dark-text-primary dark:bg-dark-bg-tertiary focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </div>

        <div class="flex items-end">
          <button
            @click="handleSearch"
            class="w-full px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700"
          >
            Apply Filters
          </button>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex items-center justify-center h-64">
      <div class="text-gray-600 dark:text-dark-text-secondary">Loading certificates...</div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-red-50 dark:bg-red-900/20 p-4 rounded-md">
      <p class="text-red-800 dark:text-red-200">{{ error }}</p>
    </div>

    <!-- Certificates Table -->
    <div v-else class="bg-white dark:bg-dark-bg-secondary rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200 dark:divide-dark-border">
          <thead class="bg-gray-50 dark:bg-dark-bg-tertiary">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                Subject
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                Issuer
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                Valid Until
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                Status
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                Key Info
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody class="bg-white dark:bg-dark-bg-secondary divide-y divide-gray-200 dark:divide-dark-border">
            <tr v-for="cert in certificates" :key="cert.id" class="hover:bg-gray-50 dark:hover:bg-dark-bg-tertiary">
              <td class="px-6 py-4">
                <div class="text-sm font-medium text-gray-900 dark:text-dark-text-primary">
                  {{ cert.subject_cn || '-' }}
                </div>
                <div v-if="cert.san_domains && cert.san_domains.length > 0" class="text-xs text-gray-500 dark:text-dark-text-secondary mt-1">
                  SANs: {{ cert.san_domains.length }}
                </div>
              </td>
              <td class="px-6 py-4">
                <div class="text-sm text-gray-900 dark:text-dark-text-primary truncate max-w-xs">
                  {{ cert.issuer || '-' }}
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm" :class="getExpiryColor(cert)">
                  {{ formatDate(cert.not_after) }}
                </div>
                <div v-if="cert.days_until_expiry !== undefined && cert.days_until_expiry !== null" class="text-xs text-gray-500 dark:text-dark-text-secondary">
                  {{ cert.days_until_expiry }} days
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex flex-wrap gap-1">
                  <span v-if="cert.is_expired" class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400">
                    Expired
                  </span>
                  <span v-if="cert.is_self_signed" class="px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400">
                    Self-Signed
                  </span>
                  <span v-if="cert.is_wildcard" class="px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400">
                    Wildcard
                  </span>
                  <span v-if="cert.has_weak_signature" class="px-2 py-1 text-xs font-semibold rounded-full bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400">
                    Weak Sig
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm text-gray-900 dark:text-dark-text-primary">
                  {{ cert.public_key_algorithm || '-' }}
                </div>
                <div v-if="cert.public_key_bits" class="text-xs text-gray-500 dark:text-dark-text-secondary">
                  {{ cert.public_key_bits }} bits
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button
                  @click="viewCertificate(cert.id)"
                  class="text-primary-600 hover:text-primary-900 dark:text-primary-400 dark:hover:text-primary-300"
                >
                  View
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Empty State -->
      <div v-if="certificates.length === 0" class="text-center py-12">
        <p class="text-gray-500 dark:text-dark-text-secondary">No certificates found</p>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="px-6 py-4 border-t border-gray-200 dark:border-dark-border">
        <div class="flex items-center justify-between">
          <div class="text-sm text-gray-700 dark:text-dark-text-secondary">
            Showing {{ ((currentPage - 1) * pageSize) + 1 }} to {{ Math.min(currentPage * pageSize, totalItems) }} of {{ totalItems }} results
          </div>
          <div class="flex space-x-2">
            <button
              @click="goToPage(currentPage - 1)"
              :disabled="currentPage === 1"
              class="px-3 py-1 border border-gray-300 dark:border-dark-border rounded-md text-sm text-gray-700 dark:text-dark-text-secondary hover:bg-gray-50 dark:hover:bg-dark-bg-tertiary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              v-for="page in Math.min(5, totalPages)"
              :key="page"
              @click="goToPage(page)"
              :class="[
                'px-3 py-1 border rounded-md text-sm',
                page === currentPage
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'border-gray-300 dark:border-dark-border text-gray-700 dark:text-dark-text-secondary hover:bg-gray-50 dark:hover:bg-dark-bg-tertiary'
              ]"
            >
              {{ page }}
            </button>
            <button
              @click="goToPage(currentPage + 1)"
              :disabled="currentPage === totalPages"
              class="px-3 py-1 border border-gray-300 dark:border-dark-border rounded-md text-sm text-gray-700 dark:text-dark-text-secondary hover:bg-gray-50 dark:hover:bg-dark-bg-tertiary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
