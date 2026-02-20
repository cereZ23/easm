/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // EASM Brand Colors
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
        },
        // Severity Colors
        severity: {
          critical: '#dc2626', // red-600
          high: '#ea580c',     // orange-600
          medium: '#f59e0b',   // amber-500
          low: '#eab308',      // yellow-500
          info: '#3b82f6',     // blue-500
        },
        // Status Colors
        status: {
          open: '#dc2626',       // red-600
          suppressed: '#f59e0b', // amber-500
          fixed: '#16a34a',      // green-600
        },
        // Dark mode overrides
        dark: {
          bg: {
            primary: '#0f172a',   // slate-900
            secondary: '#1e293b', // slate-800
            tertiary: '#334155',  // slate-700
          },
          text: {
            primary: '#f1f5f9',   // slate-100
            secondary: '#cbd5e1', // slate-300
            tertiary: '#94a3b8',  // slate-400
          },
          border: '#334155',      // slate-700
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'Monaco', 'Courier New', 'monospace'],
      },
      boxShadow: {
        'glow-sm': '0 0 10px rgba(59, 130, 246, 0.3)',
        'glow-md': '0 0 20px rgba(59, 130, 246, 0.4)',
        'glow-lg': '0 0 30px rgba(59, 130, 246, 0.5)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-in': 'slideIn 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
