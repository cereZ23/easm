import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Tenant } from '@/api/types'
import { tenantApi } from '@/api/tenants'

export const useTenantStore = defineStore('tenant', () => {
  const currentTenant = ref<Tenant | null>(null)
  const tenants = ref<Tenant[]>([])

  const currentTenantId = computed(() => currentTenant.value?.id)

  async function fetchTenants() {
    tenants.value = await tenantApi.list()

    // Auto-select first tenant if none selected
    if (!currentTenant.value && tenants.value.length > 0) {
      const storedId = localStorage.getItem('currentTenantId')
      if (storedId) {
        const tenant = tenants.value.find(t => t.id === parseInt(storedId))
        if (tenant) {
          currentTenant.value = tenant
          return
        }
      }
      currentTenant.value = tenants.value[0]
    }
  }

  function selectTenant(tenantId: number) {
    const tenant = tenants.value.find(t => t.id === tenantId)
    if (tenant) {
      currentTenant.value = tenant
      localStorage.setItem('currentTenantId', String(tenantId))
    }
  }

  return {
    currentTenant,
    tenants,
    currentTenantId,
    fetchTenants,
    selectTenant,
  }
})
