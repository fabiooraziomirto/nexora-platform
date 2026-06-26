import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api/v2/devices':     { target: 'http://localhost:8000', changeOrigin: true },
      '/api/v2/plugins':     { target: 'http://localhost:8001', changeOrigin: true },
      '/api/v2/functions':   { target: 'http://localhost:8001', changeOrigin: true },
      '/api/v2/executions':  { target: 'http://localhost:8002', changeOrigin: true },
      '/api/v2/ports':       { target: 'http://localhost:8003', changeOrigin: true },
      '/api/v2/webservices': { target: 'http://localhost:8005', changeOrigin: true },
      '/api/v2/fleets':      { target: 'http://localhost:8006', changeOrigin: true },
    },
  },
})
