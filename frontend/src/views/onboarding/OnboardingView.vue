<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// Form state
const currentStep = ref(1)
const isLoading = ref(false)
const error = ref('')
const successMessage = ref('')

// Form data
const formData = ref({
  companyName: '',
  email: '',
  password: '',
  confirmPassword: '',
  domains: ['']
})

// Validation
const errors = ref({
  companyName: '',
  email: '',
  password: '',
  confirmPassword: '',
  domains: [] as string[]
})

const isValidEmail = (email: string) => {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return re.test(email)
}

const isValidDomain = (domain: string) => {
  const re = /^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$/i
  return re.test(domain.trim())
}

const validateStep1 = () => {
  errors.value = {
    companyName: '',
    email: '',
    password: '',
    confirmPassword: '',
    domains: []
  }

  let valid = true

  if (!formData.value.companyName.trim()) {
    errors.value.companyName = 'Company name is required'
    valid = false
  } else if (formData.value.companyName.length < 2) {
    errors.value.companyName = 'Company name must be at least 2 characters'
    valid = false
  }

  if (!formData.value.email) {
    errors.value.email = 'Email is required'
    valid = false
  } else if (!isValidEmail(formData.value.email)) {
    errors.value.email = 'Please enter a valid email address'
    valid = false
  }

  return valid
}

const validateStep2 = () => {
  errors.value.password = ''
  errors.value.confirmPassword = ''

  let valid = true

  if (!formData.value.password) {
    errors.value.password = 'Password is required'
    valid = false
  } else if (formData.value.password.length < 8) {
    errors.value.password = 'Password must be at least 8 characters'
    valid = false
  }

  if (!formData.value.confirmPassword) {
    errors.value.confirmPassword = 'Please confirm your password'
    valid = false
  } else if (formData.value.password !== formData.value.confirmPassword) {
    errors.value.confirmPassword = 'Passwords do not match'
    valid = false
  }

  return valid
}

const validateStep3 = () => {
  errors.value.domains = []
  let valid = true

  // Filter out empty domains
  const nonEmptyDomains = formData.value.domains.filter(d => d.trim())

  if (nonEmptyDomains.length === 0) {
    errors.value.domains[0] = 'At least one domain is required'
    valid = false
  }

  nonEmptyDomains.forEach((domain, index) => {
    if (!isValidDomain(domain)) {
      errors.value.domains[index] = 'Invalid domain format (e.g., example.com)'
      valid = false
    }
  })

  return valid
}

const nextStep = () => {
  if (currentStep.value === 1 && validateStep1()) {
    currentStep.value = 2
  } else if (currentStep.value === 2 && validateStep2()) {
    currentStep.value = 3
  }
}

const prevStep = () => {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

const addDomain = () => {
  if (formData.value.domains.length < 10) {
    formData.value.domains.push('')
  }
}

const removeDomain = (index: number) => {
  if (formData.value.domains.length > 1) {
    formData.value.domains.splice(index, 1)
  }
}

const submitOnboarding = async () => {
  if (!validateStep3()) {
    return
  }

  isLoading.value = true
  error.value = ''
  successMessage.value = ''

  try {
    // Filter out empty domains
    const cleanDomains = formData.value.domains.filter(d => d.trim())

    const response = await fetch('http://localhost:8000/api/v1/onboarding/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        company_name: formData.value.companyName,
        email: formData.value.email,
        password: formData.value.password,
        domains: cleanDomains
      })
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.detail || 'Registration failed')
    }

    // Success!
    successMessage.value = data.message

    // Auto-login after 2 seconds
    setTimeout(async () => {
      try {
        await authStore.login({
          email: formData.value.email,
          password: formData.value.password
        })
        // Login will redirect to dashboard automatically
      } catch (loginError) {
        // If auto-login fails, redirect to login page
        router.push('/login')
      }
    }, 2000)

  } catch (err: any) {
    console.error('Onboarding error:', err)
    error.value = err.message || 'Registration failed. Please try again.'
  } finally {
    isLoading.value = false
  }
}

const stepClasses = computed(() => (step: number) => {
  if (step < currentStep.value) {
    return 'bg-primary-600 text-white'
  } else if (step === currentStep.value) {
    return 'bg-primary-600 text-white ring-2 ring-primary-300'
  } else {
    return 'bg-gray-300 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-dark-bg-primary py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-2xl w-full space-y-8">
      <!-- Header -->
      <div class="text-center">
        <h2 class="text-3xl font-extrabold text-gray-900 dark:text-dark-text-primary">
          Start Monitoring Your Attack Surface
        </h2>
        <p class="mt-2 text-sm text-gray-600 dark:text-dark-text-secondary">
          Complete setup in 3 easy steps
        </p>
      </div>

      <!-- Progress Steps -->
      <div class="flex items-center justify-center space-x-4 mb-8">
        <div class="flex items-center">
          <div
            :class="stepClasses(1)"
            class="w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-all"
          >
            1
          </div>
          <span class="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">Company</span>
        </div>
        <div class="w-16 h-1 bg-gray-300 dark:bg-gray-700"></div>
        <div class="flex items-center">
          <div
            :class="stepClasses(2)"
            class="w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-all"
          >
            2
          </div>
          <span class="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">Account</span>
        </div>
        <div class="w-16 h-1 bg-gray-300 dark:bg-gray-700"></div>
        <div class="flex items-center">
          <div
            :class="stepClasses(3)"
            class="w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-all"
          >
            3
          </div>
          <span class="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">Domains</span>
        </div>
      </div>

      <!-- Success Message -->
      <div v-if="successMessage" class="rounded-md bg-green-50 dark:bg-green-900/20 p-4">
        <div class="flex">
          <div class="flex-shrink-0">
            <svg class="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
          </div>
          <div class="ml-3">
            <h3 class="text-sm font-medium text-green-800 dark:text-green-200">
              {{ successMessage }}
            </h3>
            <div class="mt-2 text-sm text-green-700 dark:text-green-300">
              <p>Redirecting to your dashboard...</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Error Message -->
      <div v-if="error" class="rounded-md bg-red-50 dark:bg-red-900/20 p-4">
        <p class="text-sm text-red-800 dark:text-red-200">{{ error }}</p>
      </div>

      <!-- Form Card -->
      <div class="bg-white dark:bg-dark-bg-secondary shadow-xl rounded-lg p-8">
        <form @submit.prevent="currentStep === 3 ? submitOnboarding() : nextStep()">
          <!-- Step 1: Company Information -->
          <div v-show="currentStep === 1" class="space-y-6">
            <div>
              <label for="companyName" class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary">
                Company Name
              </label>
              <input
                id="companyName"
                v-model="formData.companyName"
                type="text"
                required
                class="mt-1 appearance-none block w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md shadow-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-primary-500 focus:border-primary-500 dark:bg-dark-bg-primary dark:text-dark-text-primary sm:text-sm"
                placeholder="Acme Corporation"
              />
              <p v-if="errors.companyName" class="mt-1 text-sm text-red-600 dark:text-red-400">
                {{ errors.companyName }}
              </p>
            </div>

            <div>
              <label for="email" class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary">
                Email Address
              </label>
              <input
                id="email"
                v-model="formData.email"
                type="email"
                required
                class="mt-1 appearance-none block w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md shadow-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-primary-500 focus:border-primary-500 dark:bg-dark-bg-primary dark:text-dark-text-primary sm:text-sm"
                placeholder="you@company.com"
              />
              <p v-if="errors.email" class="mt-1 text-sm text-red-600 dark:text-red-400">
                {{ errors.email }}
              </p>
            </div>
          </div>

          <!-- Step 2: Account Setup -->
          <div v-show="currentStep === 2" class="space-y-6">
            <div>
              <label for="password" class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary">
                Password
              </label>
              <input
                id="password"
                v-model="formData.password"
                type="password"
                required
                class="mt-1 appearance-none block w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md shadow-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-primary-500 focus:border-primary-500 dark:bg-dark-bg-primary dark:text-dark-text-primary sm:text-sm"
                placeholder="Minimum 8 characters"
              />
              <p v-if="errors.password" class="mt-1 text-sm text-red-600 dark:text-red-400">
                {{ errors.password }}
              </p>
            </div>

            <div>
              <label for="confirmPassword" class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                v-model="formData.confirmPassword"
                type="password"
                required
                class="mt-1 appearance-none block w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md shadow-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-primary-500 focus:border-primary-500 dark:bg-dark-bg-primary dark:text-dark-text-primary sm:text-sm"
                placeholder="Re-enter your password"
              />
              <p v-if="errors.confirmPassword" class="mt-1 text-sm text-red-600 dark:text-red-400">
                {{ errors.confirmPassword }}
              </p>
            </div>
          </div>

          <!-- Step 3: Domains -->
          <div v-show="currentStep === 3" class="space-y-6">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary mb-2">
                Domains to Monitor
              </label>
              <p class="text-sm text-gray-500 dark:text-dark-text-tertiary mb-4">
                Enter your root domains (e.g., example.com). We'll automatically discover all subdomains.
              </p>

              <div v-for="(domain, index) in formData.domains" :key="index" class="flex items-center space-x-2 mb-3">
                <input
                  v-model="formData.domains[index]"
                  type="text"
                  :placeholder="`example${index > 0 ? index + 1 : ''}.com`"
                  class="flex-1 appearance-none block w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md shadow-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-primary-500 focus:border-primary-500 dark:bg-dark-bg-primary dark:text-dark-text-primary sm:text-sm"
                />
                <button
                  v-if="formData.domains.length > 1"
                  type="button"
                  @click="removeDomain(index)"
                  class="px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                >
                  Remove
                </button>
              </div>

              <div v-if="errors.domains[0]" class="mb-3">
                <p class="text-sm text-red-600 dark:text-red-400">
                  {{ errors.domains[0] }}
                </p>
              </div>

              <button
                v-if="formData.domains.length < 10"
                type="button"
                @click="addDomain"
                class="mt-2 inline-flex items-center px-3 py-2 border border-gray-300 dark:border-dark-border shadow-sm text-sm font-medium rounded-md text-gray-700 dark:text-dark-text-secondary bg-white dark:bg-dark-bg-primary hover:bg-gray-50 dark:hover:bg-dark-bg-secondary"
              >
                <svg class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
                Add Another Domain
              </button>
            </div>
          </div>

          <!-- Navigation Buttons -->
          <div class="mt-8 flex justify-between">
            <button
              v-if="currentStep > 1"
              type="button"
              @click="prevStep"
              class="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-dark-border shadow-sm text-sm font-medium rounded-md text-gray-700 dark:text-dark-text-secondary bg-white dark:bg-dark-bg-primary hover:bg-gray-50 dark:hover:bg-dark-bg-secondary"
            >
              <svg class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </button>
            <div v-else></div>

            <button
              type="submit"
              :disabled="isLoading"
              class="inline-flex items-center px-6 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span v-if="isLoading">
                <svg class="animate-spin h-4 w-4 mr-2 inline" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {{ currentStep === 3 ? 'Creating...' : 'Loading...' }}
              </span>
              <span v-else>
                {{ currentStep === 3 ? 'Complete Setup' : 'Continue' }}
                <svg v-if="currentStep < 3" class="h-4 w-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </span>
            </button>
          </div>
        </form>
      </div>

      <!-- Login Link -->
      <p class="text-center text-sm text-gray-600 dark:text-dark-text-secondary">
        Already have an account?
        <router-link to="/login" class="font-medium text-primary-600 hover:text-primary-500">
          Sign in
        </router-link>
      </p>
    </div>
  </div>
</template>
