import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Django runs on the host in development; see compose.dev.yaml.
    proxy: {
      '/api': 'http://localhost:8000',
      '/accounts': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/static': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test-setup.ts'],
    coverage: {
      include: ['src/**'],
      exclude: ['src/main.tsx', 'src/test-setup.ts', 'src/test-utils.tsx', 'src/api/schema.d.ts', 'src/**/*.test.*', 'src/**/*.d.ts',
        // A thin wrapper around the charting library, which needs a real browser canvas.
        'src/components/Plot.tsx',
        // Glue between the OAuth library and the device; runs only on a device against Authentik.
        'src/native/oidc.ts', 'src/test-native.ts'],
      thresholds: { lines: 100, functions: 100, branches: 100, statements: 100 },
    },
  },
})
