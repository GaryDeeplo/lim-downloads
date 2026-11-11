import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Build servi par FastAPI (dm/static). En dev : `npm run dev` + backend sur :8765.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: '../dm/static', emptyOutDir: true },
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
})
