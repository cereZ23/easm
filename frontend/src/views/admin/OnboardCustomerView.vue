<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import axios from 'axios'

const authStore = useAuthStore()

// Form state
const isLoading = ref(false)
const error = ref('')
const successMessage = ref('')
const showForm = ref(true)

// Form data
const formData = ref({
  companyName: '',
  email: '',
  password: '',
  domains: ['']
})

// Validation errors
const errors = ref({
  companyName: '',
  email: '',
  password: '',
  domains: [] as string[]
})

const resetForm = () => {
  formData.value = {
    companyName: '',
    email: '',
    password: '',
    domains: ['']
  }
  errors.value = {
    companyName: '',
    email: '',
    password: '',
    domains: []
  }
  error.value = ''
  successMessage.value = ''
}

const isValidEmail = (email: string) => {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return re.test(email)
}

const isValidDomain = (domain: string) => {
  const re = /^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$/i
  return re.test(domain.trim())
}

const validateForm = () => {
  errors.value = {
    companyName: '',
    email: '',
    password: '',
    domains: []
  }

  let valid = true

  // Validate company name
  if (!formData.value.companyName.trim()) {
    errors.value.companyName = 'Company name is required'
    valid = false
  } else if (formData.value.companyName.length < 2) {
    errors.value.companyName = 'Company name must be at least 2 characters'
    valid = false
  }

  // Validate email
  if (!formData.value.email) {
    errors.value.email = 'Email is required'
    valid = false
  } else if (!isValidEmail(formData.value.email)) {
    errors.value.email = 'Please enter a valid email address'
    valid = false
  }

  // Validate password
  if (!formData.value.password) {
    errors.value.password = 'Password is required'
    valid = false
  } else if (formData.value.password.length < 8) {
    errors.value.password = 'Password must be at least 8 characters'
    valid = false
  }

  // Validate domains
  const nonEmptyDomains = formData.value.domains.filter(d => d.trim())

  if (nonEmptyDomains.length === 0) {
    errors.value.domains[0] = 'At least one domain is required'
    valid = false
  } else {
    nonEmptyDomains.forEach((domain, index) => {
      if (!isValidDomain(domain)) {
        errors.value.domains[index] = 'Invalid domain format (e.g., example.com)'
        valid = false
      }
    })
  }

  return valid
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
  if (!validateForm()) {
    return
  }

  isLoading.value = true
  error.value = ''
  successMessage.value = ''

  try {
    // Filter out empty domains
    const cleanDomains = formData.value.domains.filter(d => d.trim())

    const response = await axios.post(
      'http://localhost:18000/api/v1/onboarding/register',
      {
        company_name: formData.value.companyName,
        email: formData.value.email,
        password: formData.value.password,
        domains: cleanDomains
      },
      {
        headers: {
          'Authorization': `Bearer ${authStore.accessToken}`
        }
      }
    )

    // Success!
    successMessage.value = response.data.message
    showForm.value = false

    // Reset form after 3 seconds
    setTimeout(() => {
      resetForm()
      showForm.value = true
    }, 3000)

  } catch (err: any) {
    console.error('Onboarding error:', err)
    if (err.response?.status === 403) {
      error.value = 'You must be an admin to onboard customers'
    } else if (err.response?.data?.detail) {
      error.value = err.response.data.detail
    } else {
      error.value = 'Failed to onboard customer. Please try again.'
    }
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-dark-text-primary">Onboard New Customer</h1>
      <p class="mt-1 text-sm text-gray-500 dark:text-dark-text-secondary">
        Add a new organization to the EASM platform
      </p>
    </div>

    <!-- Success Message -->
    <div v-if="successMessage" class="mb-6 rounded-md bg-green-50 dark:bg-green-900/20 p-4">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-green-800 dark:text-green-200">
            Customer onboarded successfully!
          </h3>
          <div class="mt-2 text-sm text-green-700 dark:text-green-300">
            <p>{{ successMessage }}</p>
            <p class="mt-1">The customer can now log in and their initial scan is running.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="error" class="mb-6 rounded-md bg-red-50 dark:bg-red-900/20 p-4">
      <p class="text-sm text-red-800 dark:text-red-200">{{ error }}</p>
    </div>

    <!-- Onboarding Form -->
    <div v-if="showForm" class="bg-white dark:bg-dark-bg-secondary shadow rounded-lg p-6">
      <form @submit.prevent="submitOnboarding">
        <div class="space-y-6">
          <!-- Company Name -->
          <div>
            <label for="companyName" class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary">
              Company Name
            </label>
            <input
              id="companyName"
              v-model="formData.companyName"
              type="text"
              required
              class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md shadow-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-primary-500 focus:border-primary-500 dark:bg-dark-bg-primary dark:text-dark-text-primary sm:text-sm"
              placeholder="Acme Corporation"
            />
            <p v-if="errors.companyName" class="mt-1 text-sm text-red-600 dark:text-red-400">
              {{ errors.companyName }}
            </p>
          </div>

          <!-- Email -->
          <div>
            <label for="email" class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary">
              Customer Admin Email
            </label>
            <input
              id="email"
              v-model="formData.email"
              type="email"
              required
              class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md shadow-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-primary-500 focus:border-primary-500 dark:bg-dark-bg-primary dark:text-dark-text-primary sm:text-sm"
              placeholder="admin@customer.com"
            />
            <p v-if="errors.email" class="mt-1 text-sm text-red-600 dark:text-red-400">
              {{ errors.email }}
            </p>
            <p class="mt-1 text-xs text-gray-500 dark:text-dark-text-tertiary">
              This will be the customer's login email
            </p>
          </div>

          <!-- Password -->
          <div>
            <label for="password" class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary">
              Initial Password
            </label>
            <input
              id="password"
              v-model="formData.password"
              type="password"
              autocomplete="new-password"
              required
              class="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md shadow-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-primary-500 focus:border-primary-500 dark:bg-dark-bg-primary dark:text-dark-text-primary sm:text-sm"
              placeholder="Minimum 8 characters"
            />
            <p v-if="errors.password" class="mt-1 text-sm text-red-600 dark:text-red-400">
              {{ errors.password }}
            </p>
            <p class="mt-1 text-xs text-gray-500 dark:text-dark-text-tertiary">
              Share this with the customer - they can change it after first login
            </p>
          </div>

          <!-- Domains -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-dark-text-secondary mb-2">
              Domains to Monitor
            </label>
            <p class="text-sm text-gray-500 dark:text-dark-text-tertiary mb-4">
              Enter root domains (e.g., example.com). The system will automatically discover all subdomains.
            </p>

            <div v-for="(domain, index) in formData.domains" :key="index" class="flex items-center space-x-2 mb-3">
              <input
                v-model="formData.domains[index]"
                type="text"
                :placeholder="`example${index > 0 ? index + 1 : ''}.com`"
                class="flex-1 block w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md shadow-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-primary-500 focus:border-primary-500 dark:bg-dark-bg-primary dark:text-dark-text-primary sm:text-sm"
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

            <div v-for="(err, errIndex) in errors.domains" :key="`error-${errIndex}`" class="mb-2">
              <p v-if="err" class="text-sm text-red-600 dark:text-red-400">
                Domain {{ errIndex + 1 }}: {{ err }}
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

          <!-- Submit Button -->
          <div class="flex justify-end space-x-3 pt-4 border-t border-gray-200 dark:border-dark-border">
            <button
              type="button"
              @click="resetForm"
              class="px-4 py-2 border border-gray-300 dark:border-dark-border shadow-sm text-sm font-medium rounded-md text-gray-700 dark:text-dark-text-secondary bg-white dark:bg-dark-bg-primary hover:bg-gray-50 dark:hover:bg-dark-bg-secondary"
            >
              Reset
            </button>
            <button
              type="submit"
              :disabled="isLoading"
              class="inline-flex items-center px-6 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg v-if="isLoading" class="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ isLoading ? 'Onboarding...' : 'Onboard Customer' }}
            </button>
          </div>
        </div>
      </form>
    </div>

    <!-- Info Box -->
    <div class="mt-6 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md p-4">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="ml-3">
          <h3 class="text-sm font-medium text-blue-800 dark:text-blue-200">
            What happens after onboarding?
          </h3>
          <div class="mt-2 text-sm text-blue-700 dark:text-blue-300">
            <ul class="list-disc list-inside space-y-1">
              <li>Customer account and tenant are created immediately</li>
              <li>Initial reconnaissance scan starts automatically (1-2 hours)</li>
              <li>Customer can log in with the email and password you provided</li>
              <li>Send the login credentials to the customer securely</li>
              <li>Customer should change their password after first login</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
