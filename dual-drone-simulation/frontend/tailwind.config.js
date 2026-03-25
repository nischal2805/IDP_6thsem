/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'sim-green': '#22c55e',
        'sim-yellow': '#eab308',
        'sim-orange': '#f97316',
        'sim-red': '#ef4444',
        'sim-dark': '#1a1a2e',
        'sim-darker': '#0f0f1a',
        'sim-card': '#252540',
        'sim-border': '#3a3a5c',
      }
    },
  },
  plugins: [],
}
