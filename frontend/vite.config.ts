/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: {
    sourcemap: true,
    // MapLibre alone is ~940 kB minified (~255 kB gzip) and is split into its
    // own long-cached chunk; the limit reflects that known size.
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: { manualChunks: { maplibre: ['maplibre-gl'] } },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: { modules: { classNameStrategy: 'non-scoped' } },
  },
})
