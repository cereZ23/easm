import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, LoginRequest, LoginResponse } from '@/api/types'
import { authApi } from '@/api/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(localStorage.getItem('accessToken'))
  const refreshToken = ref<string | null>(localStorage.getItem('refreshToken'))

  const isAuthenticated = computed(() => !!accessToken.value)
  const currentUser = computed(() => user.value)

  async function login(credentials: LoginRequest) {
    const response = await authApi.login(credentials)
    setTokens(response.access_token, response.refresh_token)
    user.value = response.user
    // Clear tenant selection from previous session
    localStorage.removeItem('currentTenantId')
    router.push('/')
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      clearTokens()
      router.push('/login')
    }
  }

  async function refreshAccessToken() {
    if (!refreshToken.value) {
      throw new Error('No refresh token available')
    }
    const response = await authApi.refresh(refreshToken.value)
    setTokens(response.access_token, response.refresh_token)
  }

  async function fetchCurrentUser() {
    user.value = await authApi.me()
  }

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('accessToken', access)
    localStorage.setItem('refreshToken', refresh)
  }

  function clearTokens() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('accessToken')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('currentTenantId')
  }

  return {
    user,
    accessToken,
    refreshToken,
    isAuthenticated,
    currentUser,
    login,
    logout,
    refreshAccessToken,
    fetchCurrentUser,
    setTokens,
    clearTokens,
  }
})
