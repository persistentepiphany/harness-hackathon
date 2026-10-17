import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test, type Page, type Route } from '@playwright/test';

// New run, Jobs and single-job views. Two groups:
// - mock: the app runs with NEXT_PUBLIC_HARNESS_MODE=mock (prototype data and simulator, ?seed=7);
// - live-shaped: the app runs in live mode and every /api/harness/* call is answered from
//   tests/fixtures/live (real `pah` records), so no API is needed.
// Each group skips itself when the app runs in the other mode. Selectors are data-testid hooks.

const FIXTURES = path.join(__dirname, '..', 'tests', 'fixtures', 'live');
const fixture = <T,>(name: string): T => JSON.parse(readFileSync(path.join(FIXTURES, name), 'utf8')) as T;

async function appMode(page: Page): Promise<string | null> {
  const status = page.getByTestId('api-status');
  await expect(status).toHaveAttribute('data-state', /mock|connected|checking|disconnected/);
  return status.getAttribute('data-state');
}

// ---------------------------------------------------------------- mock mode

test.describe('mock mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/runs/new?seed=7');
    test.skip((await appMode(page)) !== 'mock', 'app is not in mock mode');
  });

  test('new run: pickers, detail cards, sources and manual setup', async ({ page }) => {
    await expect(page.getByTestId('page-new-run')).toBeVisible();
    await expect(page.getByTestId('quick-setup')).toBeDisabled();
    await expect(page.getByTestId('target-chip')).toHaveCount(6);
    await expect(page.getByTestId('target-chip').first()).toHaveAttribute('data-state', 'selected');
    await expect(page.getByTestId('ligand-chip').first()).toHaveAttribute('data-state', 'selected');

    await page.getByTestId('target-chip').filter({ hasText: 'KRAS' }).click();
    await expect(page.getByTestId('target-detail')).toContainText('RASK_HUMAN');
    await expect(page.getByTestId('entity-row').first()).toBeVisible();
    await expect(page.getByTestId('sources-panel')).toHaveAttribute('data-state', 'ready');

    await page.getByTestId('manual-setup').click();
    await expect(page.getByTestId('task-chip')).toHaveCount(14);
    await expect(page.locator('[data-testid=task-chip][data-group=docking]')).toHaveCount(6);
    const unavailable = page.locator('[data-testid=executor-chip][data-state=unavailable]');
    await expect(unavailable.first()).toBeDisabled();
    await expect(unavailable.first()).toHaveAttribute('title', /not available/);
    await page.locator('[data-testid=task-chip][data-task=interaction_discovery]').click();
    await expect(page.getByTestId('input-partner')).toHaveValue('P04049');
    await expect(page.getByTestId('ligand-picker')).toHaveCount(0);
    await expect(page.getByTestId('plan-tools')).toHaveText('Boltz-2 · Protenix');
  });

  test('quick setup streams decisions, Start run opens the job and its log streams', async ({ page }) => {
    await page.getByTestId('sample-prompt').first().click();
    await page.getByTestId('quick-setup').click();
    const rows = page.getByTestId('decision-row');
    await expect(rows.first()).toBeVisible();
    await expect(page.locator('[data-testid=decision-row][data-field=claim]')).toHaveAttribute('data-state', 'ok', { timeout: 10_000 });
    await expect(rows).toHaveCount(9);
    await page.getByTestId('start-run').click();
    await expect(page).toHaveURL(/\/jobs\/run_/);
    await expect(page.getByTestId('run-header')).toContainText('ABL1 kinase · ligand pose');
    await expect(page.locator('[data-testid=layer-strip] [data-testid=layer-cell]')).toHaveCount(6);
    const lines = page.getByTestId('log-line');
    await expect(lines.first()).toBeVisible();
    const before = await lines.count();
    await expect.poll(() => lines.count(), { timeout: 10_000 }).toBeGreaterThan(before);
  });

  test('jobs overview: three cards with six layer segments each', async ({ page }) => {
    await page.goto('/jobs?seed=7');
    const cards = page.getByTestId('job-card');
    await expect(cards).toHaveCount(3);
    await expect(cards.nth(0)).toHaveAttribute('data-state', 'done');
    await expect(cards.nth(0).getByTestId('verdict')).toHaveAttribute('data-state', 'narrowed');
    await expect(cards.nth(1)).toHaveAttribute('data-state', 'running');
    await expect(cards.nth(0).getByTestId('layer-cell')).toHaveCount(6);
    await expect(cards.nth(1).locator('[data-testid=layer-cell][data-state=running]')).toHaveCount(1);
    await expect(page.getByTestId('jobs-summary')).toContainText('running');
  });

  test('job page: elapsed time ticks, log toggles Plain/Terminal', async ({ page }) => {
    await page.goto('/jobs?seed=7');
    await page.getByTestId('job-card').nth(1).click();
    await expect(page).toHaveURL(/\/jobs\/run_/);
    const elapsed = page.getByTestId('elapsed');
    await expect(elapsed).toHaveText(/\d+\.\d/);
    const t0 = await elapsed.textContent();
    await expect.poll(() => elapsed.textContent(), { timeout: 5_000 }).not.toBe(t0);
    await expect(page.getByTestId('log-panel')).toHaveAttribute('data-mode', 'plain');
    await page.getByTestId('log-mode-terminal').click();
    await expect(page.getByTestId('log-panel')).toHaveAttribute('data-mode', 'terminal');
    await expect(page.getByTestId('executor-row')).toHaveCount(2);
  });

  test('drop zone uploads files and shows the parse status', async ({ page }) => {
    await page.getByTestId('file-input').setInputFiles({ name: 'ligand.sdf', mimeType: 'chemical/x-mdl-sdfile', buffer: Buffer.from('benzamidine\n') });
    const chip = page.getByTestId('file-chip');
    await expect(chip).toHaveCount(1);
    await expect(chip).toHaveAttribute('data-state', 'ok');
    await expect(chip).toContainText('ligand.sdf');
  });
});

// ---------------------------------------------------------------- live-shaped (fixtures)

type Json = Record<string, unknown>;

function sse(lines: { seq: number }[], end = true): string {
  const frames = lines.map((l) => `event: line\nid: ${l.seq}\ndata: ${JSON.stringify(l)}\n\n`);
  if (end) frames.push(`event: end\ndata: ${JSON.stringify({ reason: 'run_end', lastSeq: lines.at(-1)?.seq ?? 0 })}\n\n`);
  return frames.join('');
}

async function routeLive(page: Page, posts: Json[] = []) {
  const jobs = fixture<Json[]>('jobs.json');
  const tools = fixture<Json[]>('tools.json');
  const tasks = fixture<Json[]>('tasks.json');
  const rec3ptb = fixture<Json>('ui-record-3ptb.json');
  const recFaulty = fixture<Json>('ui-record-faulty.json');
  const log3ptb = fixture<{ seq: number }[]>('log-3ptb.json');
  const queued: Json = { ...(jobs.find((j) => j.id === 'ui-3ptb') as Json), id: 'ui-queued', runId: 'ui-queued', status: 'queued', layerIdx: 0, progress: 0, elapsedMs: 0, verdict: null, checksDone: 0, layers: Array.from({ length: 6 }, (_, i) => ({ i, result: null, done: false })) };
  const faultyLog = [
    { seq: 0, ts: '2026-10-17T15:31:03.400000Z', t: '0.0s', layer: null, kind: 'log', text: 'job  executors: not run (checks only)', plain: 'Executors are not run (checks only).' },
    { seq: 1, ts: '2026-10-17T15:31:03.438723Z', t: '0.0s', layer: null, kind: 'run', text: 'run  start  task=ligand_pose layers=0,1', plain: 'Run started: task ligand_pose, layers 0, 1.' },
    { seq: 2, ts: '2026-10-17T15:31:03.500000Z', t: '0.1s', layer: 0, kind: 'check', result: 'stop', text: 'L0  l0.cross.ligand_inchikey  stop', plain: 'Declared ligand SMILES does not match its CCD record (stop).' },
  ];
  const catalog = {
    proteins: [{ names: ['trypsin', 'p00760'], accession: 'P00760', label: 'Trypsin', entry: 'TRY1_BOVIN', organism: 'Bos taurus', length: 246, pdb: '3PTB', resolution: '1.70 Å', afPlddt: 93.12 }],
    ligands: [{ names: ['benzamidine'], smiles: 'NC(=N)c1ccccc1', ccd: 'BEN', cid: '2332', chembl: 'CHEMBL20936', formula: 'C7H8N2', mw: 120.15, stereo: 0 }],
    defaults: { target: 'P00760', partner: 'P04049', ligand: 'benzamidine', reference: '3PTB' },
  };
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
  await page.route('**/api/harness/**', async (route) => {
    const url = new URL(route.request().url());
    const p = url.pathname.replace(/^\/api\/harness/, '');
    const method = route.request().method();
    if (p === '/health') return json(route, { status: 'ok', version: '0.1.0', profile: 'local' });
    if (p === '/ui/jobs') return json(route, posts.length ? [queued, ...jobs] : jobs);
    if (p === '/ui/tools' && method === 'POST') return json(route, { error: { code: 'not_implemented', message: 'tool registry writes are not implemented; executors are declared in configs/executors.yaml' } }, 501);
    if (p === '/ui/tools') return json(route, tools);
    if (p === '/ui/tasks') return json(route, tasks);
    if (p === '/ui/catalog') return json(route, catalog);
    if (p === '/ui/agent/tasks') return json(route, []);
    if (p === '/ui/entities') return json(route, []);
    if (p === '/ui/runs' && method === 'POST') {
      posts.push(route.request().postDataJSON() as Json);
      return json(route, { jobId: 'ui-queued', runId: 'ui-queued' }, 202);
    }
    let m = p.match(/^\/ui\/jobs\/([^/]+)$/);
    if (m) {
      const job = m[1] === 'ui-queued' ? queued : jobs.find((j) => j.id === m?.[1]);
      return job ? json(route, job) : json(route, { error: { code: 'run_not_found', message: `no run ${m[1]}` } }, 404);
    }
    m = p.match(/^\/ui\/jobs\/([^/]+)\/log$/);
    if (m) {
      const body = m[1] === 'ui-3ptb' ? sse(log3ptb) : m[1] === 'ui-faulty' ? sse(faultyLog) : ': ping\n\n';
      return route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream', 'cache-control': 'no-store' }, body });
    }
    m = p.match(/^\/ui\/runs\/([^/]+)\/record$/);
    if (m && m[1] === 'ui-3ptb') return json(route, rec3ptb);
    if (m && m[1] === 'ui-faulty') return json(route, recFaulty);
    return json(route, { error: { code: 'run_not_found', message: `no route ${p}` } }, 404);
  });
}

test.describe('live-shaped (fixtures)', () => {
  const posts: Json[] = [];
  test.beforeEach(async ({ page }) => {
    posts.length = 0;
    await routeLive(page, posts);
    await page.goto('/jobs');
    test.skip((await appMode(page)) === 'mock', 'app is in mock mode');
  });

  test('jobs overview renders incomplete and refused runs', async ({ page }) => {
    const card3ptb = page.locator('[data-testid=job-card][data-job=ui-3ptb]');
    await expect(card3ptb.getByTestId('verdict')).toHaveAttribute('data-state', 'incomplete');
    const job3ptb = fixture<{ id: string; layers: { result: string | null }[] }[]>('jobs.json').find((j) => j.id === 'ui-3ptb');
    const skipLayers = job3ptb?.layers.filter((l) => l.result === 'skip').length ?? 0;
    await expect(card3ptb.locator('[data-testid=layer-cell][data-state=skip]')).toHaveCount(skipLayers);
    await expect(card3ptb).toContainText('P00760 · 3PTB · 5 seeds · pH 7.4');
    const faulty = page.locator('[data-testid=job-card][data-job=ui-faulty]');
    await expect(faulty.getByTestId('verdict')).toHaveAttribute('data-state', 'refused');
    const notRun = fixture<{ layers: { status: string }[] }>('ui-record-faulty.json').layers.filter((l) => l.status === 'not_run').length;
    await expect(faulty.locator('[data-testid=layer-cell][data-state=not_run]')).toHaveCount(notRun);
  });

  test('job page of an incomplete run: not-implemented counts, full log, verdict', async ({ page }) => {
    await page.goto('/jobs/ui-3ptb');
    const strip = page.getByTestId('layer-strip');
    const rec = fixture<{ layers: { checks: { result: string; skipReason?: string }[] }[] }>('ui-record-3ptb.json');
    // every layer shows its own counts: not-implemented and other skips are counted, muted
    for (const [i, l] of rec.layers.entries()) {
      const ni = l.checks.filter((c) => c.result === 'skip' && c.skipReason === 'unknown_check').length;
      const skip = l.checks.filter((c) => c.result === 'skip' && c.skipReason !== 'unknown_check').length;
      const cell = strip.getByTestId('layer-cell').nth(i);
      if (ni) await expect(cell).toContainText(`${ni} not implemented`);
      if (skip) await expect(cell).toContainText(`${skip} skip`);
    }
    await expect(strip.getByTestId('layer-cell').nth(0)).toHaveAttribute('data-state', 'pass');
    await expect(page.getByTestId('log-line')).toHaveCount(fixture<unknown[]>('log-3ptb.json').length);
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', 'incomplete');
    await expect(page.getByTestId('executor-row')).toContainText('not run (checks only)');
    await expect(page.getByTestId('open-report')).toHaveAttribute('href', '/reports/ui-3ptb');
    await expect(page.getByTestId('job-status')).toContainText(`complete · ${rec.layers.reduce((a, l) => a + l.checks.length, 0)} checks`);
  });

  test('job page of a refused run shows the seq-0 line and layers not run', async ({ page }) => {
    await page.goto('/jobs/ui-faulty');
    await expect(page.locator('[data-testid=log-line][data-seq="0"]')).toContainText('Executors are not run (checks only).');
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', 'refused');
    const notRun = fixture<{ layers: { status: string }[] }>('ui-record-faulty.json').layers.filter((l) => l.status === 'not_run').length;
    await expect(page.locator('[data-testid=layer-strip] [data-testid=layer-cell][data-state=not_run]')).toHaveCount(notRun);
  });

  test('new run: register drives the chips, + executor shows the 501, Start run opens a queued job', async ({ page }) => {
    await page.goto('/runs/new');
    await expect(page.getByTestId('target-chip')).toHaveAttribute('data-state', 'selected');
    await page.getByTestId('manual-setup').click();
    const boltz = page.locator('[data-testid=executor-chip][data-tool=boltz2]');
    await expect(boltz).toHaveAttribute('data-state', 'selected');
    await expect(page.locator('[data-testid=executor-chip][data-tool=protenix]')).toBeDisabled();
    // a selected tool the host cannot run can still be removed
    await page.locator('[data-testid=executor-chip][data-tool=gnina]').click();
    await expect(page.getByTestId('plan-tools')).toHaveText('Boltz-2');
    await page.getByTestId('add-executor').fill('mytool:1.0');
    await page.getByTestId('add-executor').press('Enter');
    await expect(page.getByTestId('add-executor-message')).toContainText('501 not_implemented');
    await page.getByTestId('start-run').click();
    await expect(page).toHaveURL(/\/jobs\/ui-queued$/);
    expect(posts[0]).toMatchObject({ task: 'ligand_pose', tools: ['boltz2'], target: 'P00760', reference: '3PTB', ligand: 'NC(=N)c1ccccc1', seeds: 5, ph: 7.4 });
    await expect(page.getByTestId('page-job')).toHaveAttribute('data-state', 'queued');
    await expect(page.getByTestId('log-empty')).toHaveText('Waiting for a slot.');
  });
});
