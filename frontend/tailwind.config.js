/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
        },
        // GitHub dark theme colors
        github: {
          dark: {
            bg: '#0d1117',
            'bg-secondary': '#161b22',
            'bg-tertiary': '#21262d',
            border: '#30363d',
            'border-secondary': '#21262d',
            text: '#c9d1d9',
            'text-secondary': '#8b949e',
            'text-muted': '#6e7681',
            hover: '#1f2328',
            'hover-secondary': '#161b22',
          },
        },
      },
    },
  },
  plugins: [],
}

