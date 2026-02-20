import apiClient from './client'
import type { Service, PaginatedResponse } from './types'

export interface ServiceListParams {
  page?: number
  page_size?: number
  asset_id?: number
  port?: number
  protocol?: string
  product?: string
  has_tls?: boolean
  search?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export const serviceApi = {
  async list(tenantId: number, params?: ServiceListParams): Promise<PaginatedResponse<Service>> {
    const response = await apiClient.get<PaginatedResponse<Service>>(
      `/api/v1/tenants/${tenantId}/services`,
      { params }
    )
    return response.data
  },

  async get(tenantId: number, serviceId: number): Promise<Service> {
    const response = await apiClient.get<Service>(`/api/v1/tenants/${tenantId}/services/${serviceId}`)
    return response.data
  },
}
