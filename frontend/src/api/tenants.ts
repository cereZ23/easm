import apiClient from './client'
import type { Tenant, DashboardStats } from './types'

export const tenantApi = {
  async list(): Promise<Tenant[]> {
    const response = await apiClient.get<Tenant[]>('/api/v1/tenants')
    return response.data
  },

  async get(tenantId: number): Promise<Tenant> {
    const response = await apiClient.get<Tenant>(`/api/v1/tenants/${tenantId}`)
    return response.data
  },

  async getDashboard(tenantId: number): Promise<DashboardStats> {
    const response = await apiClient.get<DashboardStats>(`/api/v1/tenants/${tenantId}/dashboard`)
    return response.data
  },
}
