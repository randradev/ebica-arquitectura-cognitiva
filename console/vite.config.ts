import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// CONSTANTE: dirección del backend de EBICA (`python -m ebica.api`).
const BACKEND = 'http://127.0.0.1:8000'

// El servidor de Vite sirve la consola y reenvía /api y /ws al backend.
// Así el navegador ve un solo origen y el backend no necesita CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': BACKEND,
      '/ws': { target: BACKEND, ws: true },
    },
  },
})
