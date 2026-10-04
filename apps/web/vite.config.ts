import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: { '/api': 'http://localhost:8000' },
  },
  preview: { port: 4173, host: '0.0.0.0' },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // The suites drive real user-event interactions, which are slow enough to
    // exceed the 1s default when the API suite runs in parallel on a loaded CI
    // runner. A larger budget keeps those tests from failing on timing alone.
    testTimeout: 20000,
    hookTimeout: 20000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/main.tsx',
        'src/vite-env.d.ts',
        // Type-only module: it emits no runtime code, so including it would
        // report 0% and drag the totals down without describing real risk.
        'src/types.ts',
      ],
      // Measured today: 98% statements, 84% branches, 72% functions. The floors
      // sit just below each measurement so an ordinary change does not trip
      // them, while a large untested addition will.
      thresholds: {
        statements: 90,
        branches: 75,
        functions: 65,
        lines: 90,
      },
    },
  },
});
