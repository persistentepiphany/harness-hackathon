// Re-capture public/stills/molstar-overlay.png: the ensemble overlay view of run ui-vina in the
// running app, with the crystal and the five mode-0 poses checked. Mol* draws with WebGL on its own
// clock, so film B uses this screenshot instead of a frame-driven twin.
//
//   .venv/bin/pah serve --port 8401 &
//   (cd web && NEXT_PUBLIC_HARNESS_MODE=live HARNESS_API_URL=http://127.0.0.1:8401 NEXT_DIST_DIR=.next-filmb npx next dev -p 3401) &
//   node videos/scripts/capture-overlay.cjs http://127.0.0.1:3401 videos/public/stills
//
// Uses the repository's Playwright (root package.json) and the preinstalled Chromium with SwiftShader.

const path = require('path');
const { chromium } = require(path.resolve(__dirname, '../../node_modules/playwright'));

const [base = 'http://127.0.0.1:3401', out = path.resolve(__dirname, '../public/stills')] = process.argv.slice(2);

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 })).newPage();
  page.setDefaultTimeout(180000);
  await page.goto(`${base}/reports/ui-vina/ensemble?gridViewers=0`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="structure-grid"]');
  await page.locator('[data-testid="view-mode"] button[data-value="overlay"]').click();
  await page.waitForTimeout(20000);
  await page.locator('[data-testid="overlay-legend"]').getByRole('button', { name: 'none' }).click();
  const boxes = page.locator('[data-testid="overlay-member"] input[type=checkbox]');
  for (let i = 0; i < 6; i++) await boxes.nth(i).check(); // 3PTB and vina/seed0..4/mode0
  await page.mouse.move(5, 5);
  await page.waitForTimeout(8000);
  const view = page.locator('[data-testid="overlay-view"]');
  await view.scrollIntoViewIfNeeded();
  await page.waitForTimeout(4000);
  await view.screenshot({ path: path.join(out, 'molstar-overlay.png') });
  await browser.close();
})();
