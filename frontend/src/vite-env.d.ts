/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  // Add more env variables as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Extend Vue Router meta types
import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    requiresAdmin?: boolean
  }
}
