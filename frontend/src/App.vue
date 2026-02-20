<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { onMounted } from 'vue'

const themeStore = useThemeStore()

onMounted(() => {
  // Initialize theme from localStorage
  themeStore.initTheme()
})
</script>

<template>
  <RouterView />
</template>
