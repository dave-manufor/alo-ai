import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';
import { VitePWA } from 'vite-plugin-pwa';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      // Assets synced from the design system (scripts/sync-design-system.mjs).
      includeAssets: ['design-system/assets/Logos/app-icon.svg'],
      manifest: {
        name: 'Alo.ai — Stories that listen back',
        short_name: 'Alo.ai',
        description:
          'A voice-first reading and comprehension screener for Nigerian primary school children.',
        lang: 'en-GB',
        display: 'standalone',
        start_url: '/',
        // Token values (surface / night, Day theme) as hex: a web manifest
        // cannot reference CSS variables.
        background_color: '#F7F5FF',
        theme_color: '#4B3BD1',
        icons: [
          {
            src: '/design-system/assets/Logos/app-icon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'any',
          },
        ],
      },
    }),
  ],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});
