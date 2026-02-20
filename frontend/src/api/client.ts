import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { useAuthStore } from '@/stores/auth'

const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:18000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - Add auth token
apiClient.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    if (authStore.accessToken) {
      config.headers.Authorization = `Bearer ${authStore.accessToken}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor - Handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Don't retry if this is already a refresh request
    if (originalRequest.url?.includes('/auth/refresh')) {
      const authStore = useAuthStore()
      authStore.clearTokens()
      window.location.href = '/login'
      return Promise.reject(error)
    }

    // Handle 401 errors (expired token)
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const authStore = useAuthStore()

      try {
        await authStore.refreshAccessToken()
        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${authStore.accessToken}`
        return apiClient(originalRequest)
      } catch (refreshError) {
        // Refresh failed, logout user
        authStore.clearTokens()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
