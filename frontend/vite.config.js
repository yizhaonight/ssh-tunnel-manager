import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

const backendPort = process.env.PORT || '8100';

export default defineConfig({
  plugins: [svelte()],
  base: '/dashboard/',
  server: {
    proxy: {
      '/api': `http://localhost:${backendPort}`,
    },
  },
});
