import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';

// Report and ensemble routes. Two groups, each skipped unless the server runs in its mode:
// - mock: prototype data (?seed=7), every stats block present;
// - live-shaped: a live-mode server with /api/harness/* answered from tests/fixtures/live and
//   runs/<id>/ files (route-mocked in the browser), so stats are absent and blocks say "not computed".

const FIXTURES = path.join(__dirname, '..', 'tests', 'fixtures', 'live');
const RUNS = path.join(__dirname, '..', '..', 'runs');

async function serverMode(page: Page): Promise<string | null> {
  await page.goto('/runs/new');
  const status = page.getByTestId('api-status');
  await expect(status).toBeVisible();
  return status.getAttribute('data-state');
}

function fixture(name: string): string {
  return readFileSync(path.join(FIXTURES, name), 'utf8');
}

async function routeLive(page: Page) {
  await page.route('**/api/harness/**', async (route) => {
    const url = new URL(route.request().url());
    const p = decodeURIComponent(url.pathname.replace(/^\/api\/harness/, ''));
    const json = (body: string) => route.fulfill({ status: 200, contentType: 'application/json', body });
    if (p === '/health') return json(JSON.stringify({ status: 'ok', version: 'fixture' }));
    if (p === '/ui/jobs') return json(fixture('jobs.json'));
    if (p === '/ui/tools') return json(fixture('tools.json'));
    if (p === '/ui/tasks') return json(fixture('tasks.json'));
    if (p === '/ui/agent/tasks') return json('[]');
    const rec = p.match(/^\/ui\/runs\/([^/]+)\/record$/);
    if (rec) {
      const name = ({ 'ui-3ptb': 'ui-record-3ptb.json', 'ui-faulty': 'ui-record-faulty.json', 'ui-vina': 'ui-record-vina.json' } as Record<string, string>)[rec[1]] ?? null;
      if (name) return json(fixture(name));
      return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: { code: 'not_found', message: rec[1] } }) });
    }
    const file = p.match(/^\/runs\/([^/]+)\/files\/(.+)$/);
    if (file) {
      const f = path.join(RUNS, file[1], file[2]);
      if (f.startsWith(RUNS) && existsSync(f)) return route.fulfill({ status: 200, body: readFileSync(f), contentType: f.endsWith('.svg') ? 'image/svg+xml' : f.endsWith('.png') ? 'image/png' : 'application/octet-stream' });
      return route.fulfill({ status: 404, body: '' });
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: { code: 'not_found', message: p } }) });
  });
}

test.describe('mock', () => {
  test.beforeEach(async ({ page }) => {
    test.skip((await serverMode(page)) !== 'mock', 'server is not in mock mode');
  });

  test('report renders every block from prototype data', async ({ page }) => {
    await page.goto('/reports/latest?seed=7');
    await expect(page).toHaveURL(/\/reports\/run_[0-9a-z_]+\?seed=7$/);
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', 'narrowed');
    await expect(page.getByTestId('layer-cell')).toHaveCount(6);
    await expect(page.getByTestId('layer-cell').nth(4)).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('check-table')).toHaveAttribute('data-layer', '4');
    await expect(page.getByTestId('check-row').first()).toHaveAttribute('data-state', /pass|warn|stop/);

    await expect(page.getByTestId('structure-chip')).toHaveCount(10);
    await expect(page.locator('[data-testid=structure-chip][data-structure=medoid]')).toHaveAttribute('data-state', 'selected');
    await expect(page.getByTestId('ensemble-row')).toHaveCount(9);
    await expect(page.getByTestId('ensemble-table')).toHaveAttribute('data-state', 'computed');
    await expect(page.getByTestId('stat-card')).toHaveCount(3);
    await expect(page.locator('[data-testid=stat-card][data-state=not-computed]')).toHaveCount(0);
    await expect(page.getByTestId('pb-test')).toHaveCount(20);
    await expect(page.getByTestId('seed-row')).toHaveCount(5);
    await expect(page.getByTestId('figure-pae')).toBeVisible();
    await expect(page.getByTestId('accent-rule')).toBeVisible();
    await expect(page.locator('[data-testid=metric-row][data-ranking=true]')).toHaveCount(2);
    await expect(page.getByTestId('not-computed')).toHaveCount(0);
  });

  test('layer, structure and figure selection', async ({ page }) => {
    await page.goto('/reports/latest?seed=7');
    await page.getByTestId('layer-cell').nth(0).click();
    await expect(page.getByTestId('check-table')).toHaveAttribute('data-layer', '0');
    await page.locator('[data-testid=structure-chip][data-kind=crystal]').click();
    await expect(page.locator('[data-testid=structure-chip][data-kind=crystal]')).toHaveAttribute('data-state', 'selected');
    await expect(page.getByTestId('structure-caption')).toContainText('experimental');
    for (const tab of ['inter', 'seeds', 'agree', 'calib']) {
      await page.locator(`[data-testid=figure-tab][data-tab=${tab}]`).click();
      await expect(page.locator(`[data-testid=figure-tab][data-tab=${tab}]`)).toHaveAttribute('data-state', 'active');
    }
    await expect(page.getByTestId('figure-calibration')).toBeVisible();
  });

  test('ensemble grid caps viewers and shows summary statistics', async ({ page }) => {
    await page.goto('/reports/latest/ensemble?seed=7&gridViewers=0');
    await expect(page).toHaveURL(/\/reports\/run_[0-9a-z_]+\/ensemble/);
    await expect(page.getByTestId('structure-cell')).toHaveCount(9);
    await expect(page.locator('[data-testid=structure-cell][data-kind=medoid]')).toHaveCount(1);
    await expect(page.getByTestId('cell-viewer').first()).toHaveAttribute('data-state', 'placeholder');
    await expect(page.getByTestId('cell-viewer').first()).toContainText('viewer slots full');
    await expect(page.getByTestId('summary-row')).toHaveCount(8);
    await expect(page.getByTestId('summary-medoid').first()).toBeAttached();
  });

  test('ensemble controls: sort, flagged colour mode, overlay, detail', async ({ page }) => {
    await page.goto('/reports/latest/ensemble?seed=7&viewerMode=placeholder');
    await expect(page).toHaveURL(/\/reports\/run_[0-9a-z_]+\/ensemble/);
    await page.locator('[data-testid=sort-mode] button[data-value=rmsd]').click();
    await expect(page.getByTestId('structure-cell').first()).toHaveAttribute('data-kind', 'crystal');
    await expect(page.getByTestId('structure-cell').nth(1)).toHaveAttribute('data-kind', 'medoid');
    await page.locator('[data-testid=color-mode] button[data-value=flagged]').click();
    await expect(page.getByTestId('color-mode')).toHaveAttribute('data-state', 'flagged');
    await page.getByTestId('filter-pb').click();
    await expect(page.getByTestId('structure-cell')).toHaveCount(3);
    await page.getByTestId('filter-pb').click();
    await page.locator('[data-testid=structure-cell][data-kind=medoid] button').click();
    await expect(page.getByTestId('member-detail')).toHaveAttribute('data-structure', 'medoid');
    await expect(page.locator('[data-testid=member-output]').first()).toBeVisible();
    await page.locator('[data-testid=view-mode] button[data-value=overlay]').click();
    await expect(page.getByTestId('overlay-member')).toHaveCount(9);
    await expect(page.locator('[data-testid=overlay-member][data-state=visible]')).toHaveCount(1);
  });
});

test.describe('live-shaped (fixtures)', () => {
  type Rec = { verdict: { outcome: string }; layers: { checks: { result: string }[] }[]; stats: Record<string, unknown> };
  const rec = (name: string) => JSON.parse(fixture(name)) as Rec;

  test.beforeEach(async ({ page }) => {
    await routeLive(page);
    const mode = await serverMode(page);
    test.skip(mode === 'mock', 'server is in mock mode');
  });

  test('3PTB run: verdict, layers and checks from the record, renders and figures', async ({ page }) => {
    const r = rec('ui-record-3ptb.json');
    await page.goto('/reports/ui-3ptb?viewerMode=placeholder');
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', r.verdict.outcome);
    await expect(page.getByTestId('layer-cell')).toHaveCount(r.layers.length);
    for (let i = 0; i < r.layers.length; i++) {
      await page.getByTestId('layer-cell').nth(i).click();
      await expect(page.getByTestId('check-row')).toHaveCount(r.layers[i].checks.length);
      const stops = r.layers[i].checks.filter((c) => c.result === 'stop').length;
      await expect(page.locator('[data-testid=check-row][data-state=stop]')).toHaveCount(stops);
    }
    await page.getByTestId('layer-cell').nth(0).click();
    await expect(page.locator('[data-testid=check-row][data-check="l0.cross.uniprot_seqres"] [data-testid=check-cmp]')).toHaveText('mismatches 0 == 0');
    await expect(page.getByTestId('posebusters')).toHaveAttribute('data-state', r.stats.posebusters ? 'computed' : 'not-computed');
    await expect(page.getByTestId('seed-stats')).toHaveAttribute('data-state', r.stats.physics ? 'computed' : 'not-computed');

    // structure: 3PTB from the files route; placeholder mode shows the PyMOL render
    await expect(page.locator('[data-testid=structure-chip][data-kind=crystal]').first()).toBeVisible();
    await expect(page.getByTestId('structure-viewer')).toHaveAttribute('data-state', /render|placeholder/);
    const img = page.getByTestId('render-image').locator('img');
    if (await img.count()) await expect.poll(() => img.first().evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0);

    // real report figure and provenance graph
    await page.locator('[data-testid=figure-tab][data-tab="fig:gates_by_layer"]').click();
    await expect(page.getByTestId('report-figure').locator('img')).toHaveAttribute('src', '/api/harness/runs/ui-3ptb/files/figures/gates_by_layer.svg');
    await page.locator('[data-testid=figure-tab][data-tab=graph]').click();
    await expect(page.getByTestId('provenance-graph')).toBeVisible();
  });

  test('refused run opens on the first layer with a stop', async ({ page }) => {
    const r = rec('ui-record-faulty.json');
    const first = r.layers.findIndex((l) => l.checks.some((c) => c.result === 'stop'));
    await page.goto('/reports/ui-faulty?viewerMode=placeholder');
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', 'refused');
    await expect(page.getByTestId('check-table')).toHaveAttribute('data-layer', String(first));
    await expect(page.locator('[data-testid=check-row][data-state=stop]')).toHaveCount(r.layers[first].checks.filter((c) => c.result === 'stop').length);
  });

  test('Vina run: stats blocks present, few structure chips, columns from the outputs', async ({ page }) => {
    const r = rec('ui-record-vina.json');
    await page.goto('/reports/ui-vina?viewerMode=placeholder');
    await expect(page.getByTestId('posebusters')).toHaveAttribute('data-state', 'computed');
    await expect(page.getByTestId('pb-test')).toHaveCount((r.stats.posebusters as unknown[]).length);
    await expect(page.getByTestId('seed-stats')).toHaveAttribute('data-state', 'computed');
    await expect(page.locator('[data-testid=stat-card][data-card=docking]')).toHaveAttribute('data-state', 'computed');
    await expect(page.getByTestId('structure-more')).toContainText('Ensemble');
    expect(await page.getByTestId('structure-chip').count()).toBeLessThanOrEqual(9);
    await expect(page.locator('[data-testid=ensemble-columns] [data-column=plddt]')).toHaveCount(0);
    await expect(page.locator('[data-testid=metric-row][data-ranking=true]').first()).toBeVisible();
    await expect(page.getByTestId('posebusters')).toHaveAttribute('title', /source: l4\.posebusters/);
  });

  test('Vina ensemble: one cell per member, overlay legend, filter', async ({ page }) => {
    const r = rec('ui-record-vina.json');
    const n = (r.stats.ensemble as unknown[]).length;
    await page.goto('/reports/ui-vina/ensemble?viewerMode=placeholder');
    await expect(page.getByTestId('structure-cell')).toHaveCount(n);
    await expect(page.getByTestId('summary-stats')).toHaveAttribute('data-state', 'computed');
    await expect(page.locator('[data-testid=color-mode] button[data-value=confidence]')).toBeDisabled();
    await page.locator('[data-testid=structure-cell] button').nth(1).click();
    await expect(page.getByTestId('member-detail')).toBeVisible();
    await expect(page.getByTestId('member-table')).toBeVisible();
    await page.getByTestId('member-close').click();
    await page.locator('[data-testid=view-mode] button[data-value=overlay]').click();
    await expect(page.getByTestId('overlay-member')).toHaveCount(n);
    await page.locator('[data-testid=view-mode] button[data-value=grid]').click();
    await page.getByTestId('filter-pb').click();
    const failing = (r.stats.ensemble as { posebusters?: number; posebustersTotal?: number }[]).filter((e) => typeof e.posebusters === 'number' && typeof e.posebustersTotal === 'number' && e.posebusters < e.posebustersTotal).length;
    await expect(page.getByTestId('structure-cell')).toHaveCount(failing);
  });
});
