import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';

// Two setups: `mock` (NEXT_PUBLIC_HARNESS_MODE=mock, port 3100, always runs) and `live`
// (expects HARNESS_API_URL; tests skip themselves when the API is not reachable).
// The dev server uses its own dist dir so it can run next to other servers.
const MOCK_PORT = Number(process.env.E2E_MOCK_PORT || 3100);
const LIVE_PORT = Number(process.env.E2E_LIVE_PORT || 3101);
const chromium = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const launchOptions = existsSync(chromium) ? { executablePath: chromium } : {};
const project = process.env.E2E_PROJECT; // run only one webServer when set (mock | live)
// Reuse a running server only on request: a server on the same port may have other env.
const reuse = process.env.E2E_REUSE === '1';

const servers: { name: string; command: string; port: number; env: Record<string, string> }[] = [
  {
    name: 'mock',
    command: `npx next dev -p ${MOCK_PORT}`,
    port: MOCK_PORT,
    env: { NEXT_PUBLIC_HARNESS_MODE: 'mock', NEXT_PUBLIC_MOCK_SEED: '7', NEXT_DIST_DIR: '.next-e2e-mock' } as Record<string, string>,
  },
  {
    name: 'live',
    command: `npx next dev -p ${LIVE_PORT}`,
    port: LIVE_PORT,
    env: { NEXT_PUBLIC_HARNESS_MODE: 'live', HARNESS_API_URL: process.env.HARNESS_API_URL || 'http://127.0.0.1:8000', NEXT_DIST_DIR: '.next-e2e-live' } as Record<string, string>,
  },
].filter((s) => !project || s.name === project);

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    viewport: { width: 1440, height: 900 },
    launchOptions,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'mock', testMatch: /.*\.mock\.spec\.ts/, use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 }, baseURL: `http://127.0.0.1:${MOCK_PORT}`, launchOptions } },
    { name: 'live', testMatch: /.*\.live\.spec\.ts/, use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 }, baseURL: `http://127.0.0.1:${LIVE_PORT}`, launchOptions } },
  ],
  webServer: servers.map((s) => ({
    command: s.command,
    url: `http://127.0.0.1:${s.port}/runs/new`,
    reuseExistingServer: reuse,
    timeout: 180_000,
    env: s.env,
  })),
});
