import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The desk runs at http://localhost:5173 and calls the FastAPI backend at
// http://localhost:8000 directly (see src/api.ts). The backend's CORS settings
// allow exactly this origin, so the port is fixed.
export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    // `npm run dev` opens the desk in the browser; other ways of starting Vite don't.
    open: process.env.npm_lifecycle_event === 'dev',
  },
})
