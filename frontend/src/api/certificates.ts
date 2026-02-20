import apiClient from './client'
import type { Certificate, PaginatedResponse } from './types'

export interface CertificateListParams {
  page?: number
  page_size?: number
  asset_id?: number
  is_expired?: boolean
  is_expiring_soon?: boolean
  is_self_signed?: boolean
  is_wildcard?: boolean
  has_weak_signature?: boolean
  search?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export const certificateApi = {
  async list(tenantId: number, params?: CertificateListParams): Promise<PaginatedResponse<Certificate>> {
    const response = await apiClient.get<PaginatedResponse<Certificate>>(
      `/api/v1/tenants/${tenantId}/certificates`,
      { params }
    )
    return response.data
  },

  async get(tenantId: number, certId: number): Promise<Certificate> {
    const response = await apiClient.get<Certificate>(`/api/v1/tenants/${tenantId}/certificates/${certId}`)
    return response.data
  },
}
