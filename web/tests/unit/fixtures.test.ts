// Parses the live fixtures written by the backend (tests/fixtures/live/, real runs) into the UI
// types and runs the selectors on them. Skips files that are not present yet.
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { countSegments, fmtCounts, fmtMs, fmtSha, measuredVsThreshold } from '@/lib/format';
import { resolveFileUrl } from '@/lib/files';
import { isRecordActive } from '@/lib/harness-api';
import { familyOf, metricsFor, recordTools, toolById } from '@/lib/tools';
import type { Job, LogLine, Outcome, Result, UiRunRecord } from '@/lib/types';

const dir = path.join(__dirname, '..', 'fixtures', 'live');
const load = <T,>(name: string): T | null => {
  const p = path.join(dir, name);
  return existsSync(p) ? (JSON.parse(readFileSync(p, 'utf8')) as T) : null;
};

const RESULTS: Result[] = ['pass', 'warn', 'stop', 'skip', 'reported', 'pending'];
const OUTCOMES: (Outcome | null)[] = ['supported', 'narrowed', 'refused', 'incomplete', null];

function checkRecord(r: UiRunRecord) {
  expect(typeof r.id).toBe('string');
  expect(r.source).toBe('pah');
  expect(r.layers).toHaveLength(6);
  expect(OUTCOMES).toContain(r.verdict.outcome);
  for (const l of r.layers) {
    expect(['done', 'running', 'pending', 'not_run']).toContain(l.status);
    for (const c of l.checks) {
      expect(RESULTS).toContain(c.result);
      expect(['Stop', 'Warn', 'Reported']).toContain(c.gate);
      // a row either shows a real pairing or nothing
      const mvt = measuredVsThreshold(c);
      if (mvt !== null) expect(mvt).toMatch(/ (==|!=|<=|>=|<|>) /);
    }
    const counted = Object.values(l.counts).reduce((a, b) => a + (b ?? 0), 0);
    expect(counted).toBe(l.checks.length);
    expect(fmtCounts(l.counts)).toMatch(/^pass \d+ · warn \d+ · stop \d+ · skip \d+$/);
    expect(countSegments(l.counts)).toHaveLength(4);
    if (l.durationMs !== undefined) expect(fmtMs(l.durationMs)).not.toBe('–');
  }
  for (const s of r.sources) expect(fmtSha(s.sha256)).toHaveLength(12);
  for (const t of r.tools) {
    expect(toolById(r, t.id).name).toBe(t.name);
    expect(familyOf(t)).not.toBeNull();
  }
  expect(recordTools(r)).toHaveLength(r.tools.length);
  const m = metricsFor(r);
  expect(Array.isArray(m.columns) && Array.isArray(m.rankingOnly)).toBe(true);
  for (const s of r.structures ?? []) expect(resolveFileUrl('/api/harness', r.id, s.url)).toMatch(/^\/api\/harness\/runs\//);
  for (const x of r.renders ?? []) {
    expect(resolveFileUrl('/api/harness', r.id, x.png)).toMatch(/^\/api\/harness\/runs\/.+\.png$/);
    expect(resolveFileUrl('/api/harness', r.id, x.pse)).toMatch(/\.pse$/);
  }
  for (const f of r.report?.figures ?? []) expect(resolveFileUrl('/api/harness', r.id, f.url)).toMatch(/^\/api\/harness\//);
}

describe('live fixtures', () => {
  const rec3ptb = load<UiRunRecord>('ui-record-3ptb.json');
  const recFaulty = load<UiRunRecord>('ui-record-faulty.json');
  const jobs = load<Job[]>('jobs.json');
  const log = load<LogLine[]>('log-3ptb.json');

  it.skipIf(!rec3ptb)('ui-record-3ptb.json fits UiRunRecord', () => {
    checkRecord(rec3ptb!);
    expect(isRecordActive(rec3ptb!)).toBe(false);
    const stereo = rec3ptb!.layers[1].checks.find((c) => c.id === 'l1.ligand.stereo_defined');
    if (stereo) expect(measuredVsThreshold(stereo)).toBe('undefined 1 == 0');
  });

  it.skipIf(!recFaulty)('ui-record-faulty.json fits UiRunRecord', () => {
    checkRecord(recFaulty!);
    expect(recFaulty!.verdict.outcome).toBe('refused');
    expect(recFaulty!.layers.filter((l) => l.status === 'not_run').every((l) => l.checks.length === 0)).toBe(true);
    expect(isRecordActive(recFaulty!)).toBe(false);
  });

  it.skipIf(!jobs)('jobs.json fits Job[]', () => {
    for (const j of jobs!) {
      expect(['queued', 'running', 'done', 'failed']).toContain(j.status);
      expect(j.layers).toHaveLength(6);
      expect(OUTCOMES).toContain(j.verdict);
      expect(typeof j.runId).toBe('string');
    }
  });

  it.skipIf(!log)('log-3ptb.json fits LogLine[] with increasing seq', () => {
    const kinds = ['fetch', 'cache', 'check', 'layer', 'exec', 'run', 'artifact', 'log'];
    let last = 0;
    for (const l of log!) {
      expect(kinds).toContain(l.kind);
      expect(l.seq).toBeGreaterThan(last);
      last = l.seq;
      if (l.result) expect(RESULTS).toContain(l.result);
      expect(typeof l.plain).toBe('string');
    }
  });
});
