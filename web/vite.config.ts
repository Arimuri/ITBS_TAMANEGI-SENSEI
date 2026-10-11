import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'VITE_');
  return {
    base: env.VITE_BASE_PATH || '/',
    plugins: [react()],
    server: {
      proxy: {
        // Match both /api and a configured base such as /counterpoint/api.
        // The Python development server exposes its API at /api.
        '^/(?:[^/]+/)*api(?:/|$)': {
          target: 'http://127.0.0.1:8000',
          rewrite: path => path.replace(/^\/(?:[^/]+\/)*api(?=\/|$)/, '/api'),
        },
      },
    },
  };
});
