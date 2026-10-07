import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/media': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  // Vitest transforms test files outside the React plugin's reach; without the
  // automatic runtime they would need `import React` for their JSX.
  esbuild: {
    jsx: 'automatic',
    jsxImportSource: 'react',
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    css: false,
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    reporters: ['default'],
  },
})
