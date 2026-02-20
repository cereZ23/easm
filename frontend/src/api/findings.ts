import apiClient from './client'
import type { Finding, PaginatedResponse } from './types'

export interface FindingListParams {
  page?: number
  page_size?: number
  asset_id?: number
  severity?: string
  min_severity?: string
  status?: string
  source?: string
  cve_id?: string
  template_id?: string
  search?: string
  min_cvss_score?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export const findingApi = {
  async list(tenantId: number, params?: FindingListParams): Promise<PaginatedResponse<Finding>> {
    const response = await apiClient.get<PaginatedResponse<Finding>>(
      `/api/v1/tenants/${tenantId}/findings`,
      { params }
    )
    return response.data
  },

  async get(tenantId: number, findingId: number): Promise<Finding> {
    const response = await apiClient.get<Finding>(`/api/v1/tenants/${tenantId}/findings/${findingId}`)
    return response.data
  },

  async update(tenantId: number, findingId: number, updates: Partial<Finding>): Promise<Finding> {
    const response = await apiClient.patch<Finding>(
      `/api/v1/tenants/${tenantId}/findings/${findingId}`,
      updates
    )
    return response.data
  },
}
