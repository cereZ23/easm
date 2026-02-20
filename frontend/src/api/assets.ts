import apiClient from './client'
import type { Asset, PaginatedResponse } from './types'

export interface AssetListParams {
  page?: number
  page_size?: number
  asset_type?: string
  priority?: string
  enrichment_status?: string
  is_active?: boolean
  search?: string
  min_risk_score?: number
  max_risk_score?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export const assetApi = {
  async list(tenantId: number, params?: AssetListParams): Promise<PaginatedResponse<Asset>> {
    const response = await apiClient.get<PaginatedResponse<Asset>>(
      `/api/v1/tenants/${tenantId}/assets`,
      { params }
    )
    return response.data
  },

  async get(tenantId: number, assetId: number): Promise<Asset> {
    const response = await apiClient.get<Asset>(`/api/v1/tenants/${tenantId}/assets/${assetId}`)
    return response.data
  },

  async create(tenantId: number, asset: Partial<Asset>): Promise<Asset> {
    const response = await apiClient.post<Asset>(`/api/v1/tenants/${tenantId}/assets`, asset)
    return response.data
  },

  async update(tenantId: number, assetId: number, updates: Partial<Asset>): Promise<Asset> {
    const response = await apiClient.patch<Asset>(
      `/api/v1/tenants/${tenantId}/assets/${assetId}`,
      updates
    )
    return response.data
  },

  async delete(tenantId: number, assetId: number): Promise<void> {
    await apiClient.delete(`/api/v1/tenants/${tenantId}/assets/${assetId}`)
  },
}
