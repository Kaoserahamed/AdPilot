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
