import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PARITY_WEB_PORT ?? 5173),
    proxy: {
      '/api': { target: process.env.PARITY_API_URL ?? 'http://127.0.0.1:8000', changeOrigin: false }
    }
  }
})
