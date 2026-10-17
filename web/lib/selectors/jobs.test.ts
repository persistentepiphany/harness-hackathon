import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { THIN, fmtMs } from '@/lib/format';
import { Simulator } from '@/lib/mock/simulator';
import type { Job, UiRunRecord } from '@/lib/types';
import {
  checkTotals,
  checksLine,
  inputsSummary,
  jobCardModel,
  jobSegments,
  jobStatusLabel,
  jobsSummary,
  layerCells,
  layerStrip,
  tallyLayer,
  toolLabel,
  verdictMeta,
  worstResult,
} from './jobs';

const dir = path.join(__dirname, '..', '..', 'tests', 'fixtures', 'live');
const load = <T,>(name: string): T | null => {
  const p = path.join(dir, name);
  return existsSync(p) ? (JSON.parse(readFileSync(p, 'utf8')) as T) : null;
};
const liveJobs = load<Job[]>('jobs.json') ?? [];
const rec3ptb = load<UiRunRecord>('ui-record-3ptb.json');
const recFaulty = load<UiRunRecord>('ui-record-faulty.json');
const recVina = load<UiRunRecord>('ui-record-vina.json');
const doneJob = (outcome: string) => liveJobs.find((j) => j.verdict === outcome && j.layers.every((l) => l.done));

describe('worstResult / verdictMeta / jobsSummary', () => {
  it('ranks skip < pass < reported < warn < stop and ignores pending', () => {
    expect(worstResult(['skip', 'pass'])).toBe('pass');
    expect(worstResult(['pass', 'reported'])).toBe('reported');
    expect(worstResult(['reported', 'warn', 'pending'])).toBe('warn');
    expect(worstResult(['warn', 'stop', 'pass'])).toBe('stop');
    expect(worstResult(['skip', 'skip'])).toBe('skip');
    expect(worstResult(['pending', null])).toBeNull();
  });
  it('labels every outcome', () => {
    expect(verdictMeta('refused')).toEqual({ label: 'Refused', tone: 'stop' });
    expect(verdictMeta('narrowed')).toEqual({ label: 'Narrowed', tone: 'narrowed' });
    expect(verdictMeta('supported')).toEqual({ label: 'Supported', tone: 'pass' });
    expect(verdictMeta('incomplete')).toEqual({ label: 'Incomplete', tone: 'muted' });
    expect(verdictMeta(null).tone).toBe('muted');
  });
  it('summarises statuses as the prototype header does', () => {
    expect(jobsSummary([{ status: 'running' }, { status: 'running' }, { status: 'done' }])).toBe('2 running · 0 queued · 1 done');
    expect(jobsSummary([{ status: 'failed' }])).toBe('0 running · 0 queued · 0 done · 1 failed');
  });
  it('shortens a git sha version', () => {
    expect(toolLabel({ name: 'AlphaFold3', version: '03f4f48867748c164ae6d5144ae0529477df02e3' })).toBe('AlphaFold3 03f4f4886774');
    expect(toolLabel({ name: 'Gnina', version: '1.3' })).toBe('Gnina 1.3');
    expect(toolLabel({ name: 'x', version: null })).toBe('x');
  });
});

describe('tallyLayer', () => {
  it('separates not-implemented skips from skips with a reason', () => {
    const t = tallyLayer({
      counts: {},
      checks: [
        { id: 'a', name: 'a', gate: 'Stop', result: 'pass' },
        { id: 'b', name: 'b', gate: 'Stop', result: 'skip', skipReason: 'unknown_check' },
        { id: 'c', name: 'c', gate: 'Stop', result: 'skip', skipReason: 'no learned executor declared' },
        { id: 'd', name: 'd', gate: 'Reported', result: 'reported' },
        { id: 'e', name: 'e', gate: 'Warn', result: 'pending' },
      ],
    });
    expect(t).toEqual({ pass: 1, warn: 0, stop: 0, reported: 1, skip: 1, notImplemented: 1, pending: 1, total: 5 });
  });
  it('falls back to counts when the layer has no check rows', () => {
    expect(tallyLayer({ checks: [], counts: { pass: 2, skip: 3 } }).total).toBe(5);
  });
});

describe('mock simulator jobs', () => {
  const sim = new Simulator({ seed: 7 });
  const snaps = sim.jobs.map((j) => ({ job: sim.jobSnapshot(j), record: sim.recordSnapshot(j) }));
  const [done, running, queued] = snaps;

  it('derives layer states from the job', () => {
    expect(layerCells(done.job, done.record).map((c) => c.state)).toEqual(['done', 'done', 'done', 'done', 'done', 'done']);
    expect(layerCells(running.job, running.record).map((c) => c.state)).toEqual(['done', 'done', 'done', 'running', 'pending', 'pending']);
    expect(layerCells(queued.job, queued.record).every((c) => c.state === 'pending' && c.pct === 0)).toBe(true);
  });

  it('colours segments ink when clean, warn or stop otherwise, accent while running', () => {
    const segs = jobSegments(layerCells(running.job, running.record));
    expect(segs[0].color).toBe('var(--color-ink)');
    expect(segs[2].color).toBe('var(--color-stop)');
    expect(segs[2].counts).toBe('1 stop');
    expect(segs[3].color).toBe('var(--color-accent)');
    expect(segs[4].active).toBe(false);
    expect(segs[4].counts).toBe('');
  });

  it('builds the card text', () => {
    const m = jobCardModel(done.job, 0, 3, done.record);
    expect(m.num).toBe('03');
    expect(m.verdict?.label).toBe('Narrowed');
    expect(m.toolsLong).toBe('Boltz-2 2.1.1, Gnina 1.3');
    expect(m.inputs).toBe('P00519 · 1IEP · 5 seeds · pH 7.4');
    expect(m.checks.text).toMatch(/^45 checks · \d+ warn · 0 stop$/);
    const r = jobCardModel(running.job, 1, 3, running.record);
    expect(r.verdict).toBeNull();
    expect(r.statusLabel).toMatch(/^applicability · \d+\.\ds$/);
    expect(r.checks.text).toMatch(/^\d+ of 36 checks$/);
    expect(r.inputs).toBe('P01116 + P04049 · 6VJJ · 5 seeds · pH 7.4');
  });

  it('shows the running layer as a percentage with its key figure', () => {
    const strip = layerStrip(layerCells(running.job, running.record));
    expect(strip[3].value).toMatch(/^\d+%$/);
    expect(strip[3].valueTone).toBe('accent');
    expect(strip[4].value).toBe('–');
    expect(strip[0].value).toMatch(new RegExp(`${THIN}s$`));
    expect(strip[0].counts.map((c) => c.text).join('')).toMatch(/^\d+$/);
  });
});

describe.skipIf(!rec3ptb)('live record 3PTB', () => {
  const job = (liveJobs.find((j) => j.id === 'ui-3ptb') ?? doneJob('incomplete')) as Job;
  const rec = rec3ptb as UiRunRecord;
  // expectations are computed from the fixture, so a regenerated fixture (real L2-L5 results) still checks the rules
  const count = (l: UiRunRecord['layers'][number], pred: (c: UiRunRecord['layers'][number]['checks'][number]) => boolean) => l.checks.filter(pred).length;

  it('renders every layer from its checks: pass/warn/stop, skips muted, not implemented muted', () => {
    const cells = layerCells(job, rec);
    const strip = layerStrip(cells);
    const segs = jobSegments(cells);
    rec.layers.forEach((l, i) => {
      if (l.status !== 'done') return;
      expect(cells[i].state).toBe('done');
      const pass = count(l, (c) => c.result === 'pass');
      const warn = count(l, (c) => c.result === 'warn');
      const stop = count(l, (c) => c.result === 'stop');
      const ni = count(l, (c) => c.result === 'skip' && c.skipReason === 'unknown_check');
      const skip = count(l, (c) => c.result === 'skip' && c.skipReason !== 'unknown_check');
      expect(strip[i].value).toBe(l.durationMs === undefined ? '–' : fmtMs(l.durationMs));
      expect(strip[i].counts[0]).toEqual({ text: `${pass}${warn ? ` · ${warn}w` : ''}${stop ? ` · ${stop}s` : ''}`, muted: false });
      expect(strip[i].counts.slice(1)).toEqual([...(skip ? [{ text: ` · ${skip} skip`, muted: true }] : []), ...(ni ? [{ text: ` · ${ni} not implemented`, muted: true }] : [])]);
      const ran = l.checks.length - ni - skip;
      expect(segs[i].counts).toBe(stop ? `${stop} stop` : warn ? `${warn} warn` : ran ? `${ran}` : l.checks.length ? `${ni + skip} skip` : '');
      if (l.checks.length && l.checks.every((c) => c.result === 'skip')) expect(strip[i].bar).toBe('var(--color-faint)');
    });
  });

  it('renders a layer whose checks are all not implemented as done, faint, counted', () => {
    const l2 = { ...rec.layers[2], status: 'done' as const, checks: rec.layers[2].checks.map((c) => ({ ...c, result: 'skip' as const, skipReason: 'unknown_check' })) };
    const synthetic = { ...rec, layers: rec.layers.map((l, i) => (i === 2 ? l2 : l)) };
    const syntheticJob = { ...job, layers: job.layers.map((l) => (l.i === 2 ? { ...l, result: 'skip' as const, done: true } : l)) };
    const strip = layerStrip(layerCells(syntheticJob, synthetic));
    expect(strip[2].bar).toBe('var(--color-faint)');
    expect(strip[2].counts).toEqual([
      { text: '0', muted: false },
      { text: ` · ${l2.checks.length} not implemented`, muted: true },
    ]);
  });

  it('builds the card from the record', () => {
    const m = jobCardModel(job, 0, 1, rec);
    expect(m.verdict).toEqual(verdictMeta(rec.verdict.outcome));
    expect(m.toolsLong).toBe(rec.tools.map((t) => `${t.name} ${t.version}`).join(', '));
    expect(m.inputs).toBe('P00760 · 3PTB · 5 seeds · pH 7.4');
    const t = checkTotals(rec);
    expect(t.total).toBe(rec.layers.reduce((a, l) => a + l.checks.length, 0));
    expect(m.checks).toEqual({ text: `${t.total} checks · ${t.warn} warn · ${t.stop} stop`, skip: t.skip ? `${t.skip} skip` : undefined });
    expect(checksLine(job, null)).toEqual({ text: `${job.checksTotal} checks` });
  });
});

describe.skipIf(!recFaulty)('live record faulty (refused)', () => {
  const job = (liveJobs.find((j) => j.id === 'ui-faulty') ?? doneJob('refused')) as Job;
  const rec = recFaulty as UiRunRecord;

  it('marks unselected layers as not run', () => {
    const cells = layerCells(job, rec);
    const expected = rec.layers.map((l) => (l.status === 'not_run' ? 'not_run' : 'done'));
    expect(cells.map((c) => c.state)).toEqual(expected);
    const strip = layerStrip(cells);
    const segs = jobSegments(cells);
    expect(strip[1].bar).toBe('var(--color-stop)');
    expect(segs[1].counts).toBe(`${rec.layers[1].checks.filter((c) => c.result === 'stop').length} stop`);
    rec.layers.forEach((l, i) => {
      if (l.status !== 'not_run') return;
      expect(strip[i]).toMatchObject({ value: 'not run', nameTone: 'faint', bar: 'var(--color-line)' });
      expect(segs[i]).toMatchObject({ counts: 'not run', pct: 0 });
    });
  });

  it('omits inputs the record does not carry', () => {
    const inp = rec.inputs;
    const expected = [inp.target, inp.reference, inp.seeds ? `${inp.seeds} seeds` : '', inp.ph != null ? `pH ${inp.ph}` : ''].filter(Boolean).join(' · ');
    expect(inputsSummary(rec, { seeds: 0 })).toBe(expected);
    expect(jobCardModel(job, 0, 1, rec).verdict?.label).toBe('Refused');
  });
});

describe('queued live job without a record', () => {
  const job: Job = {
    id: 'ui-new', runId: 'ui-new', name: 'ui-new', task: 'ligand_pose', taskName: '', tools: [], seeds: 0, status: 'queued',
    layerIdx: 0, progress: 0, elapsedMs: 0, createdAt: '', layers: Array.from({ length: 6 }, (_, i) => ({ i, result: null, done: false })),
    verdict: null, checksDone: 0, checksTotal: 0,
  };
  it('renders pending layers and no checks line', () => {
    const cells = layerCells(job, null);
    expect(cells.map((c) => c.name)[0]).toBe('Provenance');
    expect(cells.every((c) => c.state === 'pending')).toBe(true);
    expect(checksLine(job, null).text).toBe('');
    expect(jobStatusLabel(job, cells)).toBe('queued');
    const m = jobCardModel(job, 0, 1, null);
    expect(m.toolsLong).toBe('–');
    expect(m.inputs).toBe('–');
  });
  it('reads checks from the job while it runs without a record', () => {
    const running: Job = { ...job, status: 'running', checksDone: 4, checksTotal: 38, layerIdx: 1, progress: 0.5 };
    expect(checksLine(running, null).text).toBe('4 of 38 checks');
    expect(layerCells(running, null)[1]).toMatchObject({ state: 'running', pct: 50 });
  });
});

describe('incomplete layers', () => {
  it.runIf(!!recVina)('mutes a passing layer whose skip left the verdict incomplete', () => {
    const r = recVina as UiRunRecord;
    const cells = layerCells(null, r);
    const l4 = cells[4];
    expect(l4.incomplete).toEqual(['l4.minimisation_drift']);
    const strip = layerStrip(cells)[4];
    expect(strip.incomplete).toEqual(['l4.minimisation_drift']);
    expect(strip.title.startsWith('incomplete: l4.minimisation_drift')).toBe(true);
    if (l4.result === 'pass') expect(strip.bar).toBe('var(--color-faint)');
    expect(cells.filter((c) => c.i !== 4).every((c) => c.incomplete.length === 0)).toBe(true);
  });
  it('takes the check ids from the job when the API sends them', () => {
    const job = { status: 'done', layerIdx: 6, progress: 1, layers: [0, 1, 2, 3, 4, 5].map((i) => ({ i, result: 'pass', done: true, ...(i === 2 ? { incomplete: ['l2.x'] } : {}) })) } as unknown as Job;
    const seg = jobSegments(layerCells(job, null));
    expect(seg[2]).toMatchObject({ incomplete: ['l2.x'], color: 'var(--color-faint)', title: 'incomplete: l2.x' });
    expect(seg[1].incomplete).toEqual([]);
  });
});
