<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useTenantStore } from '@/stores/tenant'
import { serviceApi } from '@/api/services'
import type { Service, PaginatedResponse } from '@/api/types'

const tenantStore = useTenantStore()

const services = ref<Service[]>([])
const isLoading = ref(true)
const error = ref('')
const currentPage = ref(1)
const pageSize = ref(25)
const totalItems = ref(0)
const totalPages = ref(0)

// Filters
const searchQuery = ref('')
const selectedProtocol = ref('')
const hasTlsFilter = ref('')

const currentTenantId = computed(() => tenantStore.currentTenantId)

onMounted(async () => {
  await loadServices()
})

watch(currentTenantId, () => {
  if (currentTenantId.value) {
    loadServices()
  }
})

async function loadServices() {
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
      protocol: selectedProtocol.value || undefined,
      has_tls: hasTlsFilter.value === 'true' ? true : hasTlsFilter.value === 'false' ? false : undefined,
    }

    const response: PaginatedResponse<Service> = await serviceApi.list(currentTenantId.value, params)
    services.value = response.items
    totalItems.value = response.total
    totalPages.value = response.total_pages
  } catch (err: any) {
    console.error('Failed to load services:', err)
    error.value = err.message || 'Failed to load services'
  } finally {
    isLoading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  loadServices()
}

function goToPage(page: number) {
  currentPage.value = page
  loadServices()
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString()
}

function getPortColor(port: number): string {
  if (port === 80 || port === 443 || port === 8080 || port === 8443) {
    return 'text-green-600 dark:text-green-400'
  }
  if (port === 22 || port === 3389) {
    return 'text-orange-600 dark:text-orange-400'
  }
  if (port === 3306 || port === 5432 || port === 27017 || port === 6379) {
    return 'text-red-600 dark:text-red-400'
  }
  return 'text-gray-900 dark:text-dark-text-primary'
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex justify-between items-center">
      <h2 class="text-2xl font-bold text-gray-900 dark:text-dark-text-primary">Services</h2>
      <button
        @click="loadServices"
        :disabled="isLoading"
        class="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
      >
        Refresh
      </button>
    </div>

    <!-- Filters -->
    <div class="bg-white dark:bg-dark-bg-secondary p-4 rounded-lg border border-gray-200 dark:border-dark-border">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary mb-2">Search</label>
          <input
            v-model="searchQuery"
            @keyup.enter="handleSearch"
            type="text"
            placeholder="Search services..."
            class="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md text-gray-900 dark:text-dark-text-primary dark:bg-dark-bg-tertiary focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary mb-2">Protocol</label>
          <select
            v-model="selectedProtocol"
            @change="handleSearch"
            class="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md text-gray-900 dark:text-dark-text-primary dark:bg-dark-bg-tertiary focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All Protocols</option>
            <option value="tcp">TCP</option>
            <option value="udp">UDP</option>
            <option value="http">HTTP</option>
            <option value="https">HTTPS</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary mb-2">TLS</label>
          <select
            v-model="hasTlsFilter"
            @change="handleSearch"
            class="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md text-gray-900 dark:text-dark-text-primary dark:bg-dark-bg-tertiary focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All</option>
            <option value="true">TLS Enabled</option>
            <option value="false">No TLS</option>
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
      <div class="text-gray-600 dark:text-dark-text-secondary">Loading services...</div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-red-50 dark:bg-red-900/20 p-4 rounded-md">
      <p class="text-red-800 dark:text-red-200">{{ error }}</p>
    </div>

    <!-- Services Table -->
    <div v-else class="bg-white dark:bg-dark-bg-secondary rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200 dark:divide-dark-border">
          <thead class="bg-gray-50 dark:bg-dark-bg-tertiary">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                Port
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                Protocol
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                Product
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                HTTP Info
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                TLS
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-dark-text-secondary uppercase tracking-wider">
                First Seen
              </th>
            </tr>
          </thead>
          <tbody class="bg-white dark:bg-dark-bg-secondary divide-y divide-gray-200 dark:divide-dark-border">
            <tr v-for="service in services" :key="service.id" class="hover:bg-gray-50 dark:hover:bg-dark-bg-tertiary">
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="text-sm font-bold" :class="getPortColor(service.port || 0)">
                  {{ service.port || '-' }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="text-sm text-gray-900 dark:text-dark-text-primary uppercase">
                  {{ service.protocol || '-' }}
                </span>
              </td>
              <td class="px-6 py-4">
                <div class="text-sm text-gray-900 dark:text-dark-text-primary">{{ service.product || '-' }}</div>
                <div v-if="service.version" class="text-xs text-gray-500 dark:text-dark-text-secondary">v{{ service.version }}</div>
              </td>
              <td class="px-6 py-4">
                <div v-if="service.http_title" class="text-sm text-gray-900 dark:text-dark-text-primary truncate max-w-xs">
                  {{ service.http_title }}
                </div>
                <div class="flex items-center gap-2 mt-1">
                  <span v-if="service.http_status" class="text-xs text-gray-500 dark:text-dark-text-secondary">
                    Status: {{ service.http_status }}
                  </span>
                  <span v-if="service.web_server" class="text-xs text-gray-500 dark:text-dark-text-secondary">
                    {{ service.web_server }}
                  </span>
                </div>
                <div v-if="service.http_technologies && service.http_technologies.length > 0" class="flex flex-wrap gap-1 mt-1">
                  <span
                    v-for="tech in service.http_technologies.slice(0, 3)"
                    :key="tech"
                    class="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400 rounded"
                  >
                    {{ tech }}
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div v-if="service.has_tls" class="flex items-center">
                  <svg class="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                  </svg>
                  <span class="text-sm text-gray-900 dark:text-dark-text-primary">{{ service.tls_version || 'Enabled' }}</span>
                </div>
                <span v-else class="text-sm text-gray-500 dark:text-dark-text-secondary">-</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-dark-text-secondary">
                {{ formatDate(service.first_seen) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Empty State -->
      <div v-if="services.length === 0" class="text-center py-12">
        <p class="text-gray-500 dark:text-dark-text-secondary">No services found</p>
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
