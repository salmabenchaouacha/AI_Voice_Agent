import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// En dev, le front (5173) relaie /api et /ws vers FastAPI (8000) : pas de CORS à gérer.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
});