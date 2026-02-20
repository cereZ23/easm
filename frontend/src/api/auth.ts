import apiClient from './client'
import type { LoginRequest, LoginResponse, RefreshResponse, User } from './types'

export const authApi = {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', credentials)
    return response.data
  },

  async logout(): Promise<void> {
    await apiClient.post('/api/v1/auth/logout')
  },

  async refresh(refreshToken: string): Promise<RefreshResponse> {
    const response = await apiClient.post<RefreshResponse>('/api/v1/auth/refresh', {
      refresh_token: refreshToken,
    })
    return response.data
  },

  async me(): Promise<User> {
    const response = await apiClient.get<User>('/api/v1/auth/me')
    return response.data
  },
}
