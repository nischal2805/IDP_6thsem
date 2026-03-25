/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'primary': '#0ea5e9',
        'danger': '#ef4444',
        'warning': '#f59e0b',
        'success': '#22c55e',
        'dark': '#0f172a',
        'darker': '#020617',
        'card': '#1e293b',
        'border': '#334155',
      }
    },
  },
  plugins: [],
}
