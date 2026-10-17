import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { Simulator } from '@/lib/mock/simulator';
import type { Job, UiRunRecord } from '@/lib/types';
import {
  blockSource,
  docLayers,
  docList,
  documentName,
  flaggedChecks,
  interactionSummary,
  keyNumbers,
  metaLine,
  recordLine,
  reportFiles,
  seedAxisLabel,
  seedStatsLine,
  shortDate,
  skipReasons,
  sourceSuffix,
} from './document';

const FIXTURES = path.join(__dirname, '..', '..', 'tests', 'fixtures', 'live');
const load = <T,>(name: string): T | null => {
  const p = path.join(FIXTURES, name);
  return existsSync(p) ? (JSON.parse(readFileSync(p, 'utf8')) as T) : null;
};

/** The finished ligand-pose preset of a seeded simulator (prototype data). */
function mockRecord(): UiRunRecord {
  const sim = new Simulator({ seed: 7 });
  const done = sim.jobs.find((j) => j.status === 'done');
  if (!done) throw new Error('no finished preset job');
  return done.record;
}

const faulty = load<UiRunRecord>('ui-record-faulty.json');
const ptb = load<UiRunRecord>('ui-record-3ptb.json');
const jobs = load<Job[]>('jobs.json');

describe('keyNumbers (mock record)', () => {
  const r = mockRecord();
  const k = keyNumbers(r);
  it('has six cells in prototype order, read from stats', () => {
    expect(k).toHaveLength(6);
    expect(k.map((x) => x.id)).toEqual(['posebusters', expect.stringMatching(/^metric:/), expect.stringMatching(/^metric:/), 'cluster', 'agreement', 'flagged']);
    expect(k[0]).toMatchObject({ value: '20/20', label: 'PoseBusters' });
    expect(k[3]).toMatchObject({ value: '4/5', label: 'seeds in medoid cluster' });
  });
  it('takes one harness-derived and one tool-reported metric', () => {
    const metrics = r.stats.metrics ?? [];
    const derived = metrics.find((m) => !m.toolId && !m.separate);
    const reported = metrics.find((m) => m.toolId && !m.separate);
    expect(k[1]).toMatchObject({ value: derived?.value, label: derived?.name });
    expect(k[2]).toMatchObject({ value: reported?.value, label: reported?.name });
  });
  it('labels agreement with the record methods and counts warnings', () => {
    const ag = r.stats.agreement ?? [];
    expect(k[4].label).toBe(`${ag[0].method} vs ${ag[1].method}`);
    const warns = r.layers.flatMap((l) => l.checks).filter((c) => c.result === 'warn').length;
    expect(k[5]).toMatchObject({ value: String(warns), tone: 'warn' });
  });
});

describe.skipIf(!faulty)('keyNumbers (live record without stats)', () => {
  it('uses run-level facts and the stop and warning counts', () => {
    const r = faulty as UiRunRecord;
    const all = r.layers.flatMap((l) => l.checks);
    const evaluated = all.filter((c) => c.result !== 'skip' && c.result !== 'pending').length;
    const stops = all.filter((c) => c.result === 'stop').length;
    const warns = all.filter((c) => c.result === 'warn').length;
    const k = keyNumbers(r);
    expect(k.map((x) => x.id)).toEqual(['checks', 'layers', 'sources', 'time', 'stops', 'warnings']);
    expect(k.find((x) => x.id === 'checks')?.value).toBe(`${evaluated}/${all.length}`);
    expect(k.find((x) => x.id === 'layers')?.value).toBe(`${r.layers.filter((l) => l.status === 'done').length}/6`);
    expect(k.find((x) => x.id === 'stops')).toMatchObject({ value: String(stops), tone: stops ? 'stop' : 'muted' });
    expect(k.find((x) => x.id === 'warnings')).toMatchObject({ value: String(warns), tone: warns ? 'warn' : 'muted' });
  });
});

describe.skipIf(!ptb)('keyNumbers (incomplete live record)', () => {
  it('counts checks the harness did not evaluate in the denominator', () => {
    const r = ptb as UiRunRecord;
    const all = r.layers.flatMap((l) => l.checks);
    const evaluated = all.filter((c) => c.result !== 'skip' && c.result !== 'pending').length;
    expect(keyNumbers(r)[0].value).toBe(`${evaluated}/${all.length}`);
  });
});

describe('docLayers and flaggedChecks', () => {
  it('summarises mock layers with p/w/s counts', () => {
    const rows = docLayers(mockRecord());
    expect(rows).toHaveLength(6);
    expect(rows[0].countsShort).toMatch(/^\d+\/\d+\/\d+$/);
    expect(rows[0].countsLong).toMatch(/^pass \d+ · warn \d+ · stop \d+ · skip \d+$/);
  });
  it.skipIf(!faulty)('marks layers that were not run, gives skip reasons and lists every stop with its evidence', () => {
    const r = faulty as UiRunRecord;
    const rows = docLayers(r);
    r.layers.forEach((l, i) => {
      if (l.status === 'not_run') expect(rows[i]).toMatchObject({ summary: 'not run', countsShort: '–' });
      for (const [reason, n] of skipReasons(l.checks)) {
        expect(rows[i].summary).toContain(reason === 'unknown_check' ? `${n} not implemented` : `${n} skipped (${reason.replace(/_/g, ' ')})`);
      }
    });
    const stops = r.layers.flatMap((l) => l.checks).filter((c) => c.result === 'stop').length;
    const flagged = flaggedChecks(r);
    expect(flagged.filter((f) => f.result === 'stop')).toHaveLength(stops);
    expect(flagged.every((f) => f.evidence.length > 0)).toBe(true);
  });
  it('groups skipped checks by reason', () => {
    const checks = [
      { id: 'a', name: 'a', gate: 'Stop', result: 'skip', skipReason: 'unknown_check' },
      { id: 'b', name: 'b', gate: 'Stop', result: 'skip', skipReason: 'not_applicable' },
      { id: 'c', name: 'c', gate: 'Stop', result: 'skip', skipReason: 'unknown_check' },
      { id: 'd', name: 'd', gate: 'Stop', result: 'pass' },
    ] as UiRunRecord['layers'][number]['checks'];
    expect(skipReasons(checks)).toEqual([
      ['unknown_check', 2],
      ['not_applicable', 1],
    ]);
    const rows = docLayers({ layers: [{ i: 2, key: 'adequacy', name: 'Input adequacy', question: '', status: 'done', counts: {}, summary: ['4 checks'], checks }] });
    expect(rows[0].summary).toBe('4 checks · 2 not implemented · 1 skipped (not applicable)');
  });
});

describe('header and record lines', () => {
  it('builds the meta line from the record tools and inputs', () => {
    const r = mockRecord();
    expect(metaLine(r)).toBe(`${r.tools.map((t) => t.name).join(' + ')} · ${r.inputs.target} · ${r.inputs.reference} · ${r.inputs.seeds} seeds`);
  });
  it.skipIf(!faulty)('marks tools that did not run and adds the verdict scope', () => {
    const line = metaLine(faulty as UiRunRecord);
    expect(line).toContain('(not run)');
    expect(line).toContain(`verdict scope ${(faulty as UiRunRecord).verdict.scope}`);
  });
  it.skipIf(!faulty)('lists the harness run id and versions in the record line', () => {
    const line = recordLine(faulty as UiRunRecord);
    expect(line).toContain('run record ui-faulty.json');
    expect(line).toContain('harness run ligand_pose-');
    expect(line).toContain('pah 0.1.0');
  });
  it('lists the notebook and seeds of a mock record', () => {
    const r = mockRecord();
    expect(recordLine(r)).toContain(`seeds ${r.record.seeds?.join(' ')}`);
    expect(recordLine(r)).toContain(r.record.notebook as string);
  });
  it.skipIf(!faulty)('links the harness record, the markdown report and the provenance graph', () => {
    expect(reportFiles(faulty as UiRunRecord).map((f) => f.id)).toEqual(['harness-record', 'markdown', 'graph']);
    expect(reportFiles(faulty as UiRunRecord)[0].url).toBe('/runs/ui-faulty/files/record.json');
    expect(reportFiles(mockRecord())).toEqual([]);
  });
});

describe('figure captions', () => {
  it('formats seed statistics and interactions for mock data', () => {
    const r = mockRecord();
    expect(seedStatsLine(r)).toMatch(/^median [\d.]+ · IQR [\d.]+–[\d.]+ · 95% CI [\d.]+–[\d.]+ · n = \d+$/);
    expect(interactionSummary(r)).toMatch(/^\d+\/\d+ seen in known complexes$/);
  });
  it.skipIf(!faulty)('returns nothing for blocks the harness did not compute', () => {
    expect(seedStatsLine(faulty as UiRunRecord)).toBe('');
    expect(interactionSummary(faulty as UiRunRecord)).toBeNull();
  });
});

describe('blockSource', () => {
  it('reads source from an object block or the first row of a list block', () => {
    const r = { stats: { posebusters: [{ test: 'a', pass: true, value: 'ok', source: { check: 'l4.posebusters', tool: 'posebusters' } }], pairwise: { median: 1, source: { check: 'l5.seed_spread' } } } } as unknown as UiRunRecord;
    expect(blockSource(r, 'posebusters')).toEqual({ check: 'l4.posebusters', tool: 'posebusters' });
    expect(blockSource(r, 'pairwise')).toEqual({ check: 'l5.seed_spread', tool: undefined });
    expect(sourceSuffix(blockSource(r, 'posebusters'))).toBe(' · check l4.posebusters · posebusters');
  });
  it('is null for mock records and absent blocks', () => {
    expect(blockSource(mockRecord(), 'posebusters')).toBeNull();
    expect(blockSource(mockRecord(), 'nothing')).toBeNull();
    expect(sourceSuffix(null)).toBe('');
  });
});

describe('docList and documentName', () => {
  it('lists finished jobs with verdict labels and short dates', () => {
    const list = docList([
      { id: 'j1', runId: 'r1', name: 'A', status: 'done', verdict: 'refused', createdAt: '2026-10-17T10:00:00Z' } as Job,
      { id: 'j2', runId: 'r2', name: 'B', status: 'running', verdict: null, createdAt: '2026-10-17T10:00:00Z' } as Job,
    ]);
    expect(list).toHaveLength(1);
    expect(list[0]).toMatchObject({ runId: 'r1', name: 'A', verdictLabel: 'Refused' });
    expect(list[0].date).toBe(shortDate('2026-10-17T10:00:00Z'));
    expect(shortDate(null)).toBe('–');
    expect(list[0].runTag).toBeNull();
  });
  it('tags finished runs that share a name with a short run id', () => {
    const list = docList([
      { id: 'j1', runId: 'ligand_pose-04e7e402bf85', name: 'A', status: 'done', verdict: 'narrowed', createdAt: '2026-10-17T10:00:00Z' } as Job,
      { id: 'j2', runId: 'ligand_pose-333173a36ab5', name: 'A', status: 'done', verdict: 'narrowed', createdAt: '2026-10-17T11:00:00Z' } as Job,
      { id: 'j3', runId: 'ui-3ptb', name: 'B', status: 'done', verdict: 'refused', createdAt: '2026-10-17T12:00:00Z' } as Job,
    ]);
    expect(list.map((d) => d.runTag)).toEqual(['04e7e4', '333173', null]);
  });
  it.skipIf(!jobs || !faulty)('names the document after its job, else the task', () => {
    const r = faulty as UiRunRecord;
    const job = (jobs as Job[]).find((j) => j.runId === r.id);
    expect(documentName(r, jobs)).toBe(job?.name ?? r.taskName);
    expect(documentName(r, [])).toBe(r.taskName);
  });
});

describe('live stats shapes (adapter output)', () => {
  const live = {
    stats: {
      pairwise: { median: 0.071, unit: 'Å', iqr: [0.058, 0.081], n: 10, poses: 5, source: { check: 'l5.sampling.clusters', tool: 'spyrmsd' } },
      provenance: { posebusters: { check: 'l4.posebusters', tool: 'posebusters', version: '0.6.5' } },
      posebusters: [{ test: 'sanitization', pass: true, value: 'pass' }],
    },
  } as unknown as UiRunRecord;
  it('formats pairwise statistics without a CI', () => {
    expect(seedStatsLine(live)).toBe('median 0.07\u2009Å · IQR 0.06–0.08 · n = 10');
  });
  it('labels the seed axis with the seeds\' tool score when they carry no confidence', () => {
    const r = {
      tools: [{ id: 'dock', name: 'Dock tool', version: '1', outputs: [{ key: 'affinity', label: 'Score', unit: 'kcal/mol', kind: 'affinity', scope: 'pose', rankingOnly: true }] }],
      stats: { seeds: [{ seed: 0, rmsdToMedoid: 0, cluster: 1, toolId: 'dock', score: -6.1, scoreKey: 'affinity' }, { seed: 1, rmsdToMedoid: 0.1, cluster: 1, toolId: 'dock', score: -6.0, scoreKey: 'affinity' }] },
    } as unknown as UiRunRecord;
    expect(seedAxisLabel(r)).toBe('Score (kcal/mol), ranking only');
  });
  it('reads block provenance from stats.provenance, then the block source', () => {
    expect(blockSource(live, 'posebusters')).toEqual({ check: 'l4.posebusters', tool: 'posebusters' });
    expect(blockSource(live, 'pairwise')).toEqual({ check: 'l5.sampling.clusters', tool: 'spyrmsd' });
  });
});

describe('keyNumbers (live docking record)', () => {
  it('skips RMSD-kind metrics and fills with run-level facts', () => {
    const r = {
      ...(faulty ?? mockRecord()),
      stats: {
        posebusters: Array.from({ length: 20 }, (_, i) => ({ test: `t${i}`, pass: true, value: 'pass' })),
        metrics: [
          { name: 'RMSD lower bound to best mode', value: '0', key: 'rmsd_lb', toolId: 'vina', kind: 'rmsd', separate: false },
          { name: 'vina_affinity', value: '-6.131', key: 'vina_affinity', toolId: 'vina', separate: true },
        ],
      },
    } as unknown as UiRunRecord;
    const k = keyNumbers(r);
    expect(k).toHaveLength(6);
    expect(k[0]).toMatchObject({ id: 'posebusters', value: '20/20' });
    expect(k.some((x) => x.label.startsWith('RMSD'))).toBe(false);
    expect(k.slice(-2).map((x) => x.id)).toEqual(['stops', 'warnings']);
  });
});
