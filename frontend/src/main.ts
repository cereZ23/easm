import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)

// Pinia store
app.use(createPinia())

// Vue Router
app.use(router)

// Vue Query
app.use(VueQueryPlugin, {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: 1,
        staleTime: 30000, // 30 seconds
      },
    },
  },
})

app.mount('#app')
