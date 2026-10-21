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
      // Precache every design-system SVG (wordmark, Japa poses, icons) so a
      // flaky connection never leaves a screen without its images, and
      // cache the Google Fonts the bundle imports (Andika included) so the
      // story font survives offline too.
      includeAssets: ['design-system/assets/**/*.svg'],
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,webmanifest}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'alo-google-fonts-css',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'alo-google-fonts-files',
              expiration: { maxEntries: 30, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
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
