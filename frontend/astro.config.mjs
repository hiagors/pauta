// @ts-check
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'astro/config';

// §10.4: site estático, sem adapter nem SSR. O Astro entrega o shell e as ilhas
// React buscam tudo da API local. O redirect de "/" mora aqui, não em <meta>.
export default defineConfig({
  output: 'static',
  redirects: {
    '/': '/planning',
  },
  integrations: [react()],
  vite: {
    // Tailwind v4 no Astro é o plugin do Vite, nunca @astrojs/tailwind (v3-only).
    plugins: [tailwindcss()],
  },
});
