import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';

// Two setups: `mock` (NEXT_PUBLIC_HARNESS_MODE=mock, port 3100, always runs) and `live`
// (expects HARNESS_API_URL; tests skip themselves when the API is not reachable).
// Each server uses its own dist dir so it can run next to other servers. E2E_PROD=1 (CI) tests a
// production build (`next build` + `next start`) instead of `next dev`: some failures, such as
// Mol* module-order crashes, only occur in the production bundle.
const MOCK_PORT = Number(process.env.E2E_MOCK_PORT || 3100);
const LIVE_PORT = Number(process.env.E2E_LIVE_PORT || 3101);
const chromium = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const launchOptions = existsSync(chromium) ? { executablePath: chromium } : {};
const project = process.env.E2E_PROJECT; // run only one webServer when set (mock | live)
// Reuse a running server only on request: a server on the same port may have other env.
const reuse = process.env.E2E_REUSE === '1';
const prod = process.env.E2E_PROD === '1';
const serve = (port: number) => (prod ? `npx next build && npx next start -p ${port}` : `npx next dev -p ${port}`);
const dist = (name: string) => `.next-e2e-${name}${prod ? '-prod' : ''}`;

const servers: { name: string; command: string; port: number; env: Record<string, string> }[] = [
  {
    name: 'mock',
    command: serve(MOCK_PORT),
    port: MOCK_PORT,
    env: { NEXT_PUBLIC_HARNESS_MODE: 'mock', NEXT_PUBLIC_MOCK_SEED: '7', NEXT_DIST_DIR: dist('mock') } as Record<string, string>,
  },
  {
    name: 'live',
    command: serve(LIVE_PORT),
    port: LIVE_PORT,
    env: { NEXT_PUBLIC_HARNESS_MODE: 'live', HARNESS_API_URL: process.env.HARNESS_API_URL || 'http://127.0.0.1:8000', NEXT_DIST_DIR: dist('live') } as Record<string, string>,
  },
].filter((s) => !project || s.name === project);

export default defineConfig({
  // tests/e2e: smoke tests per mode; e2e/: screen specs, which skip themselves in the other mode.
  testDir: '.',
  testIgnore: ['**/node_modules/**', '**/.next*/**'],
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
    { name: 'mock', testMatch: [/tests\/e2e\/.*\.mock\.spec\.ts$/, /\/web\/e2e\/[^/]+\.spec\.ts$/], use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 }, baseURL: `http://127.0.0.1:${MOCK_PORT}`, launchOptions } },
    { name: 'live', testMatch: [/tests\/e2e\/.*\.live\.spec\.ts$/, /\/web\/e2e\/[^/]+\.spec\.ts$/], use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 }, baseURL: `http://127.0.0.1:${LIVE_PORT}`, launchOptions } },
  ],
  webServer: servers.map((s) => ({
    command: s.command,
    url: `http://127.0.0.1:${s.port}/runs/new`,
    reuseExistingServer: reuse,
    // a production build runs before the server starts
    timeout: prod ? 900_000 : 180_000,
    env: s.env,
  })),
});
