import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      usePolling: true // Required for Docker on some systems
    },
    proxy: {
      '/api': {
        target: 'http://api:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor': ['vue', 'vue-router', 'pinia'],
          'charts': ['chart.js', 'vue-chartjs'],
          'utils': ['axios', '@tanstack/vue-query', '@vueuse/core']
        }
      }
    }
  }
})
