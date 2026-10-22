import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/teams': 'http://127.0.0.1:8000',
      '/players': 'http://127.0.0.1:8000',
      '/matches': 'http://127.0.0.1:8000',
      '/innings': 'http://127.0.0.1:8000',
    },
  },
})
