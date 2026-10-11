import { defineConfig } from '@playwright/test';

const requestedURL = process.env.COUNTERPOINT_BASE_URL ?? 'http://127.0.0.1:8000/';
const baseURL = requestedURL.endsWith('/') ? requestedURL : `${requestedURL}/`;
const username = process.env.COUNTERPOINT_AUTH_USER;
const password = process.env.COUNTERPOINT_AUTH_PASSWORD;
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  use: {
    baseURL,
    ...(username && password ? { httpCredentials: { username, password } } : {}),
    channel: process.env.PLAYWRIGHT_CHANNEL ?? 'chrome',
    viewport: { width: 1512, height: 1100 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
