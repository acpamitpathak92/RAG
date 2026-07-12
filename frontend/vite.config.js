import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxies API calls to the FastAPI backend during development so the frontend
// code can just call relative paths like fetch('/query') - no CORS juggling,
// no hardcoded backend URL. Override the backend port/host by setting
// RAG_API_PROXY_TARGET before running `npm run dev` if needed.
const API_TARGET = process.env.RAG_API_PROXY_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true, // listen on all interfaces (IPv4 + IPv6) - Vite defaults to IPv6-only loopback otherwise
    proxy: {
      '/query': API_TARGET,
      '/ingest': API_TARGET,
      '/documents': API_TARGET,
      '/health': API_TARGET,
    },
  },
})
