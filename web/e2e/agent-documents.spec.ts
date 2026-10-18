import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test, type Page, type Route } from '@playwright/test';

// Agent monitor (/agent) and printable documents (/documents/[runId]). Two groups, each skipped
// unless the server runs in its mode:
// - mock: the prototype's AGENT_TASKS and records (?seed=7), played with window.__harnessMock;
// - live-shaped: a live-mode server with /api/harness/* answered in the browser from
//   tests/fixtures/live, runs/<id>/ files and agent tasks in the `pah agent-log` wire shape.

const FIXTURES = path.join(__dirname, '..', 'tests', 'fixtures', 'live');
const RUNS = path.join(__dirname, '..', '..', 'runs');
const fixture = (name: string) => readFileSync(path.join(FIXTURES, name), 'utf8');
const RECORDS: Record<string, string> = { 'ui-3ptb': 'ui-record-3ptb.json', 'ui-faulty': 'ui-record-faulty.json', 'ui-vina': 'ui-record-vina.json' };

interface FixtureCheck {
  id: string;
  result: string;
  skipReason?: string;
}
interface FixtureRecord {
  verdict: { outcome: string | null };
  layers: { i: number; status: string; checks: FixtureCheck[] }[];
  stats: Record<string, unknown>;
}
const record = (id: string): FixtureRecord => JSON.parse(fixture(RECORDS[id])) as FixtureRecord;
const checksOf = (r: FixtureRecord) => r.layers.flatMap((l) => l.checks);

async function serverMode(page: Page): Promise<string | null> {
  await page.goto('/runs/new');
  const status = page.getByTestId('api-status');
  await expect(status).toBeVisible();
  return status.getAttribute('data-state');
}

async function advance(page: Page, ms: number) {
  await page.waitForFunction(() => !!(window as unknown as { __harnessMock?: unknown }).__harnessMock);
  await page.evaluate((n) => (window as unknown as { __harnessMock: { advance: (ms: number) => void } }).__harnessMock.advance(n), ms);
}

// ---------------------------------------------------------------- live-shaped agent task

const T0 = Date.parse('2026-10-17T16:09:11.000Z');
const at = (s: number) => new Date(T0 + s * 1000).toISOString();
const TASK_ID = '20261017160911-b2490c';
const STEPS = [
  { seq: 1, ts: at(2), kind: 'thought', text: 'Ligand pose task; layers 0 and 1 run as checks', ms: 1400, data: null },
  { seq: 2, ts: at(4), kind: 'tool', text: 'harness.submit · ligand_pose · examples/3ptb_ligand_pose/manifest.yaml', ms: 900, data: { runId: 'ui-3ptb', progress: 0.3 } },
  { seq: 3, ts: at(6.3), kind: 'result', text: 'run ui-3ptb finished · layers 0,1 · verdict incomplete', ms: 4100, data: { runId: 'ui-3ptb', progress: 0.6 } },
  { seq: 4, ts: at(8.1), kind: 'report', text: 'incomplete · L2-L5 checks not implemented', ms: 700, data: { progress: 0.85 } },
  { seq: 5, ts: at(9.9), kind: 'conclusion', text: 'The pose claim is not decided because layers 2-5 did not run.', ms: 600, data: null },
];

function task(stepsSent: number) {
  const done = stepsSent >= STEPS.length;
  return {
    id: TASK_ID,
    goal: 'Decide whether the 3PTB benzamidine inputs support a pose claim',
    status: done ? 'done' : 'running',
    createdAt: at(0),
    updatedAt: at(stepsSent * 2),
    finishedAt: done ? at(11) : null,
    progress: done ? 1 : 0.3,
    steps: stepsSent,
    outcome: done ? { label: 'Completed', detail: '1 run · verdict incomplete', runs: 1 } : null,
    elapsedMs: done ? 11000 : stepsSent * 2000,
  };
}

function sse(steps: typeof STEPS, end: boolean): string {
  // `retry` makes the browser reconnect quickly when the response ends without `event: end`
  return `retry: 150\n\n${steps.map((s) => `id: ${s.seq}\nevent: step\ndata: ${JSON.stringify(s)}\n\n`).join('')}${end ? `event: end\ndata: ${JSON.stringify(task(STEPS.length))}\n\n` : ''}`;
}

/** Live API in the browser. The agent stream grows by one step per connection, like a tailing log. */
async function routeLive(page: Page, agent: { stream: 'growing' | 'finished' } = { stream: 'finished' }) {
  let sent = agent.stream === 'finished' ? STEPS.length : 0;
  const json = (route: Route, body: string, status = 200) => route.fulfill({ status, contentType: 'application/json', body });
  await page.route('**/api/harness/**', async (route) => {
    const url = new URL(route.request().url());
    const p = decodeURIComponent(url.pathname.replace(/^\/api\/harness/, ''));
    if (p === '/health') return json(route, JSON.stringify({ status: 'ok', version: 'fixture' }));
    if (p === '/ui/jobs') return json(route, fixture('jobs.json'));
    if (p === '/ui/tools') return json(route, fixture('tools.json'));
    if (p === '/ui/tasks') return json(route, fixture('tasks.json'));
    if (p === '/ui/agent/tasks') return json(route, JSON.stringify([task(sent)]));
    if (p === `/ui/agent/tasks/${TASK_ID}/steps`) {
      if (agent.stream === 'growing' && sent < STEPS.length) sent += 1;
      const last = Number(route.request().headers()['last-event-id'] ?? 0);
      // the server replays after Last-Event-ID; the client also drops seq it has seen
      const body = sse(STEPS.slice(0, sent).filter((s) => s.seq > last), sent >= STEPS.length);
      return route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' }, body });
    }
    const rec = p.match(/^\/ui\/runs\/([^/]+)\/record$/);
    if (rec) {
      const name = RECORDS[rec[1]];
      if (name && existsSync(path.join(FIXTURES, name))) return json(route, fixture(name));
      return json(route, JSON.stringify({ error: { code: 'not_found', message: rec[1] } }), 404);
    }
    const file = p.match(/^\/runs\/([^/]+)\/files\/(.+)$/);
    if (file) {
      const f = path.join(RUNS, file[1], file[2]);
      const type = f.endsWith('.svg') ? 'image/svg+xml' : f.endsWith('.png') ? 'image/png' : 'application/octet-stream';
      if (f.startsWith(RUNS) && existsSync(f)) return route.fulfill({ status: 200, body: readFileSync(f), contentType: type });
      return route.fulfill({ status: 404, body: '' });
    }
    return json(route, JSON.stringify({ error: { code: 'not_found', message: p } }), 404);
  });
}

// ---------------------------------------------------------------- mock

test.describe('mock', () => {
  test.beforeEach(async ({ page }) => {
    test.skip((await serverMode(page)) !== 'mock', 'server is not in mock mode');
  });

  test('agent monitor plays back the prototype tasks', async ({ page }) => {
    await page.goto('/agent?seed=7');
    await expect(page.getByTestId('agent-task')).toHaveCount(3);
    const selected = page.locator('[data-testid=agent-task][data-selected=true]');
    await expect(selected).toHaveAttribute('data-task', 'agent_02');
    await expect(selected).toHaveAttribute('data-state', 'running');
    await expect(page.getByTestId('agent-pending')).toBeVisible();
    const before = await page.getByTestId('agent-step').count();
    expect(before).toBeGreaterThan(0);
    expect(before).toBeLessThan(13);

    await advance(page, 60000);
    await expect(page.getByTestId('agent-step')).toHaveCount(13);
    await expect(page.getByTestId('agent-outcome')).toHaveAttribute('data-state', 'done');
    await expect(page.getByTestId('agent-pending')).toHaveCount(0);
    await expect(selected).toHaveAttribute('data-task', 'agent_02');
    await expect(page.getByTestId('agent-summary')).toHaveText('0 running · 3 completed');
    await expect(page.getByTestId('agent-task-stepcount')).toHaveText('13/13 steps');
    for (const kind of ['thought', 'tool', 'result', 'report', 'conclusion']) {
      expect(await page.locator(`[data-testid=agent-step][data-state=${kind}]`).count()).toBeGreaterThan(0);
    }
    await expect(page.getByTestId('agent-step-ms').first()).toHaveText(/\d/);
    const run = page.locator('[data-testid=agent-step-run]').first();
    const id = await run.getAttribute('data-run');
    expect(id).toMatch(/^run_/);
    await expect(run.getByTestId('agent-step-job-link')).toHaveAttribute('href', `/jobs/${id}`);
    await expect(run.getByTestId('agent-step-report-link')).toHaveAttribute('href', `/reports/${id}`);
  });

  test('selecting a task keeps it in the URL', async ({ page }) => {
    await page.goto('/agent?seed=7');
    await page.locator('[data-testid=agent-task][data-task=agent_01]').click();
    await expect(page).toHaveURL(/[?&]task=agent_01/);
    await expect(page.getByTestId('agent-task-detail')).toHaveAttribute('data-task', 'agent_01');
    await expect(page.getByTestId('agent-step')).toHaveCount(13);
    await expect(page.getByTestId('agent-outcome')).toContainText('Completed');
    await page.reload();
    await expect(page.getByTestId('agent-task-detail')).toHaveAttribute('data-task', 'agent_01');
  });

  test('document renders every block from prototype data', async ({ page }) => {
    await page.goto('/documents/latest?seed=7');
    await expect(page).toHaveURL(/\/documents\/run_[0-9a-z_]+\?seed=7$/);
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', 'narrowed');
    await expect(page.getByTestId('doc-key-number')).toHaveCount(6);
    await expect(page.locator('[data-testid=doc-key-number][data-key=posebusters]')).toContainText('20/20');
    await expect(page.getByTestId('figure-pae')).toBeVisible();
    await expect(page.getByTestId('stat-card')).toHaveCount(3);
    await expect(page.getByTestId('figure-seeds')).toBeVisible();
    await expect(page.getByTestId('figure-calibration')).toBeVisible();
    await expect(page.getByTestId('figure-agreement')).toBeVisible();
    await expect(page.getByTestId('interaction-row')).toHaveCount(9);
    await expect(page.getByTestId('pb-test')).toHaveCount(20);
    await expect(page.getByTestId('seed-row')).toHaveCount(5);
    await expect(page.getByTestId('doc-layer')).toHaveCount(6);
    await expect(page.locator('[data-testid=doc-flagged] [data-testid=check-row][data-state=warn]')).toHaveCount(4);
    await expect(page.getByTestId('provenance-row')).toHaveCount(10);
    await expect(page.getByTestId('not-computed')).toHaveCount(0);
    await expect(page.getByTestId('block-error')).toHaveCount(0);
    await expect(page.getByTestId('doc-download-notebook')).toBeVisible();

    await page.emulateMedia({ media: 'print' });
    await expect(page.getByTestId('doc-sidebar')).toBeHidden();
    await expect(page.getByTestId('top-nav')).toBeHidden();
    await expect(page.getByTestId('report-document')).toBeVisible();
  });

  test('document list switches runs once more runs finish', async ({ page }) => {
    await page.goto('/documents/latest?seed=7');
    await expect(page.getByTestId('report-document')).toBeVisible();
    await advance(page, 400000);
    await expect(page.getByTestId('doc-list-item')).toHaveCount(3);
    await page.locator('[data-testid=doc-list-item][data-state=refused]').click();
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', 'refused');
    await expect(page.locator('[data-testid=doc-list-item][data-selected=true]')).toHaveAttribute('data-state', 'refused');
    // no ligand: no PoseBusters block, interface cards
    await expect(page.getByTestId('pb-test')).toHaveCount(0);
    await expect(page.locator('[data-testid=stat-card][data-card=site]')).toContainText('Interface');
  });
});

// ---------------------------------------------------------------- live-shaped

test.describe('live-shaped (fixtures)', () => {
  test('agent steps appear as the stream delivers them, with run links', async ({ page }) => {
    await routeLive(page, { stream: 'growing' });
    test.skip((await serverMode(page)) === 'mock', 'server is in mock mode');
    await page.goto('/agent');
    await expect(page.locator('[data-testid=agent-task][data-selected=true]')).toHaveAttribute('data-task', TASK_ID);
    // one step per connection: the timeline grows without a reload, deduplicated by seq
    for (let n = 1; n <= STEPS.length; n++) {
      await expect.poll(() => page.getByTestId('agent-step').count(), { timeout: 15000 }).toBeGreaterThanOrEqual(n);
    }
    await expect(page.getByTestId('agent-step')).toHaveCount(STEPS.length);
    await expect(page.getByTestId('agent-step').nth(1)).toHaveAttribute('data-state', 'tool');
    await expect(page.getByTestId('agent-step').nth(1)).toContainText('4.0s');
    await expect(page.getByTestId('agent-step').nth(1).getByTestId('agent-step-ms')).toHaveText('900 ms');
    await expect(page.getByTestId('agent-step-job-link').first()).toHaveAttribute('href', '/jobs/ui-3ptb');
    await expect(page.getByTestId('agent-outcome')).toContainText('1 run · verdict incomplete', { timeout: 15000 });
    await page.getByTestId('agent-step-report-link').first().click();
    await expect(page).toHaveURL(/\/reports\/ui-3ptb$/);
  });

  test('refused run document: real renders and figures, stats not computed, two A4 pages', async ({ page }) => {
    await routeLive(page);
    test.skip((await serverMode(page)) === 'mock', 'server is in mock mode');
    const r = record('ui-faulty');
    const checks = checksOf(r);
    const stops = checks.filter((c) => c.result === 'stop');
    const evaluated = checks.filter((c) => c.result !== 'skip' && c.result !== 'pending').length;
    await page.goto('/documents/ui-faulty');
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', r.verdict.outcome ?? 'pending');
    await expect(page.locator('[data-testid=doc-key-number][data-key=stops]')).toContainText(String(stops.length));
    await expect(page.locator('[data-testid=doc-key-number][data-key=checks]')).toContainText(`${evaluated}/${checks.length}`);
    await expect(page.locator('[data-testid=doc-flagged] [data-testid=check-row][data-state=stop]')).toHaveCount(stops.length);
    for (const s of stops) await expect(page.locator(`[data-testid=doc-flagged] [data-testid=check-row][data-check="${s.id}"]`)).toHaveAttribute('data-state', 'stop');
    for (const l of r.layers) {
      const row = page.locator(`[data-testid=doc-layer][data-layer="${l.i}"]`);
      if (l.status === 'not_run') await expect(row).toHaveAttribute('data-state', 'not_run');
      if (l.checks.some((c) => c.skipReason === 'upstream_stop')) await expect(row).toContainText('skipped (upstream stop)');
    }
    for (const block of ['pae', 'seeds', 'calibration', 'agreement', 'interactions', 'posebusters', 'physics', 'metrics']) {
      await expect(page.locator(`[data-testid=not-computed][data-block=${block}], [data-testid=not-computed] [data-block=${block}]`).first()).toBeVisible();
    }
    await expect(page.locator('[data-testid=doc-structure] [data-testid=render-image] img').first()).toHaveAttribute('src', '/api/harness/runs/ui-faulty/files/renders/3PTB_overview.png');
    await expect(page.locator('[data-testid=doc-report-figure]')).toHaveCount(2);
    await expect(page.locator('[data-testid=doc-report-figure][data-figure=gates_by_layer] img')).toHaveAttribute('src', '/api/harness/runs/ui-faulty/files/figures/gates_by_layer.svg');
    await expect(page.locator('[data-testid=doc-report-figure][data-figure=provenance-graph] img')).toHaveAttribute('src', '/api/harness/runs/ui-faulty/files/graph.svg');
    await expect(page.getByTestId('doc-record-line')).toContainText('harness run ligand_pose-');
    await expect(page.getByTestId('doc-file-harness-record')).toHaveAttribute('href', '/api/harness/runs/ui-faulty/files/record.json');
    await expect(page.getByTestId('block-error')).toHaveCount(0);

    await expect.poll(() => page.evaluate(() => Array.from(document.images).every((i) => i.complete))).toBe(true);
    const pdf = await page.pdf({ format: 'A4', printBackground: true, preferCSSPageSize: true });
    const pages = (pdf.toString('latin1').match(/\/Type\s*\/Page(?!s)/g) ?? []).length;
    expect(pages).toBeGreaterThan(0);
    expect(pages).toBeLessThanOrEqual(2);
  });

  test('docking run document shows the numbers the harness computed', async ({ page }) => {
    test.skip(!existsSync(path.join(FIXTURES, RECORDS['ui-vina'])), 'no ui-vina fixture');
    await routeLive(page);
    test.skip((await serverMode(page)) === 'mock', 'server is in mock mode');
    const r = record('ui-vina');
    const pb = (r.stats.posebusters ?? []) as { pass: boolean }[];
    await page.goto('/documents/ui-vina');
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', r.verdict.outcome ?? 'pending');
    if (pb.length) {
      await expect(page.locator('[data-testid=doc-key-number][data-key=posebusters]')).toContainText(`${pb.filter((p) => p.pass).length}/${pb.length}`);
      await expect(page.getByTestId('pb-test')).toHaveCount(pb.length);
    }
    if (Array.isArray(r.stats.physics)) await expect(page.getByTestId('seed-row')).toHaveCount((r.stats.physics as unknown[]).length);
    if (r.stats.site) await expect(page.locator('[data-testid=stat-card][data-card=site]')).toHaveAttribute('data-state', 'computed');
    await expect(page.locator('[data-testid=stat-card][data-card=docking]')).toBeVisible();
    // block provenance from stats.provenance in the captions
    if (pb.length) await expect(page.getByText(/check l4\.posebusters/).first()).toBeVisible();
    await expect(page.getByTestId('block-error')).toHaveCount(0);
  });

  test('narrowed or incomplete run document gives the skip reason of each layer', async ({ page }) => {
    await routeLive(page);
    test.skip((await serverMode(page)) === 'mock', 'server is in mock mode');
    const r = record('ui-3ptb');
    await page.goto('/documents/ui-3ptb');
    await expect(page.getByTestId('verdict')).toHaveAttribute('data-state', r.verdict.outcome ?? 'pending');
    const evaluated = checksOf(r).filter((c) => c.result !== 'skip' && c.result !== 'pending').length;
    await expect(page.locator('[data-testid=doc-key-number][data-key=checks]')).toContainText(`${evaluated}/${checksOf(r).length}`);
    for (const c of checksOf(r).filter((x) => x.result === 'warn' || x.result === 'stop')) {
      await expect(page.locator(`[data-testid=doc-flagged] [data-testid=check-row][data-check="${c.id}"]`)).toHaveAttribute('data-state', c.result);
    }
    for (const l of r.layers) {
      const reasons = new Set(l.checks.filter((c) => c.result === 'skip').map((c) => c.skipReason));
      for (const reason of reasons) {
        const text = reason === 'unknown_check' ? 'not implemented' : `skipped (${String(reason).replace(/_/g, ' ')})`;
        await expect(page.locator(`[data-testid=doc-layer][data-layer="${l.i}"]`)).toContainText(text);
      }
    }
    await expect(page.locator('[data-testid=doc-list-item][data-selected=true]')).toHaveAttribute('data-run', 'ui-3ptb');
  });
});
