// Derivations for the Jobs overview and the single-job view (prototype logic-v2.js renderVals,
// "jobs + run" block). Pure functions over the wire shapes in lib/types.ts: a Job (GET /ui/jobs),
// the UI run record when it is available, the tool register and the task list. Nothing here is
// written for a particular executor; every label comes from the record or the register.

import { DASH, fmtMs, fmtSeconds, fmtSha } from '../format';
import { familyOf, toolById } from '../tools';
import type { Job, JobStatus, LayerStatus, Outcome, RecordLayer, Result, Task, Tool, UiCheck, UiRunRecord } from '../types';
import { LAYER_COUNT } from '../types';

/** Layer names of the specification, used until a record names them. */
export const LAYER_NAMES = ['Provenance', 'Input integrity', 'Input adequacy', 'Applicability', 'Output validity', 'Output support'] as const;

/** Severity order of check results, as the adapter ranks them (skip < pass < reported < warn < stop). */
export const RESULT_RANK: Record<Result, number> = { pending: -1, skip: 0, pass: 1, reported: 2, warn: 3, stop: 4 };

/** Worst result of a list (pending ignored); null when nothing finished. */
export function worstResult(results: (Result | null | undefined)[]): Result | null {
  let worst: Result | null = null;
  for (const r of results) {
    if (!r || r === 'pending') continue;
    if (worst === null || RESULT_RANK[r] > RESULT_RANK[worst]) worst = r;
  }
  return worst;
}

// ---------------------------------------------------------------- verdict and status

export type VerdictTone = 'pass' | 'narrowed' | 'stop' | 'muted';

export interface VerdictMeta {
  label: string;
  tone: VerdictTone;
}

/** Label and colour of an outcome (prototype `vmeta`, plus `incomplete`). */
export function verdictMeta(outcome: Outcome | null | undefined): VerdictMeta {
  switch (outcome) {
    case 'refused':
      return { label: 'Refused', tone: 'stop' };
    case 'narrowed':
      return { label: 'Narrowed', tone: 'narrowed' };
    case 'supported':
      return { label: 'Supported', tone: 'pass' };
    case 'incomplete':
      return { label: 'Incomplete', tone: 'muted' };
    default:
      return { label: 'No verdict', tone: 'muted' };
  }
}

/** `2 running · 0 queued · 1 done` (failed jobs appended when there are any). */
export function jobsSummary(jobs: Pick<Job, 'status'>[]): string {
  const n = (s: JobStatus) => jobs.filter((j) => j.status === s).length;
  const parts = [`${n('running')} running`, `${n('queued')} queued`, `${n('done')} done`];
  const failed = n('failed');
  if (failed) parts.push(`${failed} failed`);
  return parts.join(' · ');
}

/** The live API adds `error` to a failed job; the TS shape does not declare it. */
export function jobError(job: Job | null | undefined): string | null {
  const e = (job as (Job & { error?: unknown }) | null | undefined)?.error;
  return typeof e === 'string' && e ? e : null;
}

// ---------------------------------------------------------------- layers

export type LayerState = LayerStatus;

export interface LayerTally {
  pass: number;
  warn: number;
  stop: number;
  reported: number;
  /** Skipped for a reason other than "not implemented". */
  skip: number;
  /** Listed by the task but not registered (`skipReason: unknown_check`). */
  notImplemented: number;
  pending: number;
  total: number;
}

export interface LayerCell {
  i: number;
  name: string;
  state: LayerState;
  /** Worst finished result of the layer, for the colour. */
  result: Result | null;
  /** 0..100: 100 when done, progress of the running layer, else 0. */
  pct: number;
  durationMs?: number;
  tally: LayerTally;
  /** First key figure of the layer (record summary), shown while it runs. */
  summary?: string;
}

const isNotImplemented = (c: Pick<UiCheck, 'result' | 'skipReason'>) => c.result === 'skip' && c.skipReason === 'unknown_check';

export function tallyLayer(layer: Pick<RecordLayer, 'checks' | 'counts'> | null | undefined): LayerTally {
  const t: LayerTally = { pass: 0, warn: 0, stop: 0, reported: 0, skip: 0, notImplemented: 0, pending: 0, total: 0 };
  if (!layer) return t;
  if (layer.checks.length) {
    for (const c of layer.checks) {
      t.total += 1;
      if (isNotImplemented(c)) t.notImplemented += 1;
      else if (c.result in t) t[c.result as keyof LayerTally] += 1;
    }
    return t;
  }
  // a record without check rows still carries counts
  const c = layer.counts ?? {};
  t.pass = c.pass ?? 0;
  t.warn = c.warn ?? 0;
  t.stop = c.stop ?? 0;
  t.reported = c.reported ?? 0;
  t.skip = c.skip ?? 0;
  t.pending = c.pending ?? 0;
  t.total = t.pass + t.warn + t.stop + t.reported + t.skip + t.pending;
  return t;
}

function recordLayer(record: UiRunRecord | null | undefined, i: number): RecordLayer | undefined {
  return record?.layers.find((l) => l.i === i) ?? record?.layers[i];
}

/**
 * The six layer cells of a job. The job decides the state (it is polled with the run), the record
 * supplies names, durations, check counts and key figures.
 */
export function layerCells(job: Job | null | undefined, record?: UiRunRecord | null): LayerCell[] {
  const out: LayerCell[] = [];
  for (let i = 0; i < LAYER_COUNT; i++) {
    const rl = recordLayer(record, i);
    const jl = job?.layers?.find((l) => l.i === i) ?? job?.layers?.[i];
    let state: LayerState;
    if (job) {
      if (jl?.done) state = 'done';
      else if (job.status === 'running' && i === job.layerIdx) state = 'running';
      else if (job.status === 'done' || job.status === 'failed') state = 'not_run';
      else state = 'pending';
    } else {
      state = rl?.status ?? 'pending';
    }
    const tally = tallyLayer(rl);
    const finished = rl ? rl.checks.map((c) => c.result) : [];
    const result = jl?.result ?? worstResult(finished);
    out.push({
      i,
      name: rl?.name ?? LAYER_NAMES[i],
      state,
      result: state === 'pending' ? null : result,
      pct: state === 'done' ? 100 : state === 'running' ? Math.max(0, Math.min(100, Math.round((job?.progress ?? 0) * 100))) : 0,
      durationMs: rl?.durationMs,
      tally,
      summary: rl?.summary?.[0],
    });
  }
  return out;
}

/** Colour token of a finished result (pass/warn/stop; skip faint; reported muted). */
export function resultColorVar(result: Result | null | undefined): string {
  switch (result) {
    case 'pass':
      return 'var(--color-pass)';
    case 'warn':
      return 'var(--color-warn)';
    case 'stop':
      return 'var(--color-stop)';
    case 'reported':
      return 'var(--color-reported)';
    case 'skip':
      return 'var(--color-faint)';
    default:
      return 'var(--color-line)';
  }
}

export interface SegmentModel {
  i: number;
  name: string;
  state: LayerState;
  result: Result | null;
  pct: number;
  /** Bar fill: ink for a clean layer, warn or stop colour, faint when only skips; accent while running. */
  color: string;
  /** Label colour: ink2 for a started layer, faint otherwise. */
  active: boolean;
  /** `1 stop` · `2 warn` · `8` (checks that ran) · `8 skip` · `not run` · ''. */
  counts: string;
  countsMuted: boolean;
}

/** Job card segments (prototype `segs`). */
export function jobSegments(cells: LayerCell[]): SegmentModel[] {
  return cells.map((c) => {
    const ran = c.tally.pass + c.tally.warn + c.tally.stop + c.tally.reported;
    const skipped = c.tally.skip + c.tally.notImplemented;
    let counts = '';
    let countsMuted = false;
    if (c.state === 'done') {
      if (c.tally.stop) counts = `${c.tally.stop} stop`;
      else if (c.tally.warn) counts = `${c.tally.warn} warn`;
      else if (ran) counts = `${ran}`;
      else if (skipped) {
        counts = `${skipped} skip`;
        countsMuted = true;
      }
    } else if (c.state === 'not_run') {
      counts = 'not run';
      countsMuted = true;
    }
    const doneColor =
      c.result === 'stop'
        ? 'var(--color-stop)'
        : c.result === 'warn'
          ? 'var(--color-warn)'
          : c.result === 'skip'
            ? 'var(--color-faint)'
            : c.result === 'reported'
              ? 'var(--color-reported)'
              : 'var(--color-ink)';
    return {
      i: c.i,
      name: c.name,
      state: c.state,
      result: c.result,
      pct: c.pct,
      color: c.state === 'done' ? doneColor : 'var(--color-accent)',
      active: c.state === 'done' || c.state === 'running',
      counts,
      countsMuted,
    };
  });
}

export interface StripCountPart {
  text: string;
  muted: boolean;
}

export interface StripModel {
  i: number;
  name: string;
  state: LayerState;
  result: Result | null;
  bar: string;
  /** Time (done), `62%` (running), en dash (pending), `not run`. */
  value: string;
  valueTone: 'ink' | 'accent' | 'faint';
  nameTone: 'ink' | 'faint';
  counts: StripCountPart[];
  /** `pass 3 · warn 1 · stop 0 · skip 8` for the title attribute. */
  title: string;
}

/** Layer strip columns of the single-job view (prototype `rj.layers`). */
export function layerStrip(cells: LayerCell[]): StripModel[] {
  return cells.map((c) => {
    const t = c.tally;
    let value: string = DASH;
    let valueTone: StripModel['valueTone'] = 'faint';
    let counts: StripCountPart[] = [];
    if (c.state === 'done') {
      value = fmtMs(c.durationMs);
      valueTone = c.durationMs === undefined ? 'faint' : 'ink';
      counts = [{ text: `${t.pass}${t.warn ? ` · ${t.warn}w` : ''}${t.stop ? ` · ${t.stop}s` : ''}`, muted: false }];
      if (t.skip) counts.push({ text: ` · ${t.skip} skip`, muted: true });
      if (t.notImplemented) counts.push({ text: ` · ${t.notImplemented} not implemented`, muted: true });
    } else if (c.state === 'running') {
      value = `${c.pct}%`;
      valueTone = 'accent';
      counts = c.summary ? [{ text: c.summary, muted: false }] : [];
    } else if (c.state === 'not_run') {
      value = 'not run';
    }
    return {
      i: c.i,
      name: c.name,
      state: c.state,
      result: c.result,
      bar: c.state === 'done' ? resultColorVar(c.result ?? 'pass') : c.state === 'running' ? 'var(--color-accent)' : 'var(--color-line)',
      value,
      valueTone,
      nameTone: c.state === 'done' || c.state === 'running' ? 'ink' : 'faint',
      counts,
      title: `pass ${t.pass} · warn ${t.warn} · stop ${t.stop} · skip ${t.skip + t.notImplemented}${t.notImplemented ? ` (${t.notImplemented} not implemented)` : ''}`,
    };
  });
}

// ---------------------------------------------------------------- checks

export interface CheckTotals {
  total: number;
  finished: number;
  pass: number;
  warn: number;
  stop: number;
  reported: number;
  skip: number;
}

export function checkTotals(record: UiRunRecord | null | undefined): CheckTotals {
  const t: CheckTotals = { total: 0, finished: 0, pass: 0, warn: 0, stop: 0, reported: 0, skip: 0 };
  for (const l of record?.layers ?? []) {
    for (const c of l.checks) {
      t.total += 1;
      if (c.result !== 'pending') t.finished += 1;
      if (c.result in t) (t as unknown as Record<string, number>)[c.result] += 1;
    }
  }
  return t;
}

export interface ChecksLine {
  text: string;
  /** `25 skip`, shown muted on its own line. */
  skip?: string;
}

/** `45 checks · 4 warn · 0 stop` when done, `21 of 36 checks` while running (prototype `checksLine`). */
export function checksLine(job: Job, record: UiRunRecord | null | undefined): ChecksLine {
  const t = checkTotals(record);
  const total = record ? t.total : (job.checksTotal ?? 0);
  if (job.status === 'done' || job.status === 'failed') {
    // warn/stop counts come from the record only; without it the job gives the total alone
    if (!record) return { text: job.checksTotal !== undefined ? `${job.checksTotal} checks` : '' };
    return { text: `${total} checks · ${t.warn} warn · ${t.stop} stop`, skip: t.skip ? `${t.skip} skip` : undefined };
  }
  const done = job.checksDone ?? t.finished;
  const of = job.checksTotal ?? total;
  if (!of && job.status === 'queued') return { text: '' };
  return { text: `${done} of ${of} checks` };
}

// ---------------------------------------------------------------- job card and header text

/** Display name and version of each tool of the job, from the record or else the register. */
export function jobTools(job: Pick<Job, 'tools'> | null | undefined, record: UiRunRecord | null | undefined, register?: Tool[] | null): { id: string; name: string; version: string | null }[] {
  if (record?.tools?.length) return record.tools.map((t) => ({ id: t.id, name: t.name || t.id, version: t.version ?? null }));
  return (job?.tools ?? []).map((idOrName) => {
    const byName = register?.find((t) => t.name === idOrName);
    const t = byName ?? toolById(null, idOrName, register);
    return { id: t.id, name: t.name, version: t.version ?? null };
  });
}

/** `Boltz-2 2.1.1` with a long version (a git sha) shortened to 12 characters. */
export function toolLabel(t: { name: string; version: string | null }): string {
  if (!t.version) return t.name;
  const v = /^[0-9a-f]{20,}$/i.test(t.version) ? fmtSha(t.version) : t.version;
  return `${t.name} ${v}`;
}

/** `P00519 + P04049 · 1IEP · 5 seeds · pH 7.4`; parts the record does not carry are left out. */
export function inputsSummary(record: UiRunRecord | null | undefined, job?: Pick<Job, 'seeds'> | null): string {
  const inp = record?.inputs;
  const seeds = inp?.seeds ?? (job?.seeds || undefined);
  const parts: string[] = [];
  if (inp?.target) parts.push(`${inp.target}${inp.partner ? ` + ${inp.partner}` : ''}`);
  if (inp?.reference) parts.push(inp.reference);
  if (seeds) parts.push(`${seeds} seeds`);
  if (inp?.ph !== undefined && inp?.ph !== null) parts.push(`pH ${inp.ph}`);
  return parts.length ? parts.join(' · ') : DASH;
}

/** Long task name: record, then the task list, then the job's own task name. */
export function taskLongName(job: Pick<Job, 'task' | 'taskName'> | null | undefined, record: UiRunRecord | null | undefined, tasks?: Task[] | null): string {
  return record?.taskName || tasks?.find((t) => t.id === job?.task)?.long || job?.taskName || job?.task || DASH;
}

/** Running: `output validity · 11.0s`; queued: `queued`; failed: `failed` (prototype `statusLabel`). */
export function jobStatusLabel(job: Job, cells: LayerCell[]): string {
  if (job.status === 'running') {
    const cur = cells[Math.min(job.layerIdx, LAYER_COUNT - 1)];
    return `${(cur?.name ?? '').toLowerCase()} · ${(job.elapsedMs / 1000).toFixed(1)}s`;
  }
  return job.status;
}

export interface JobCardModel {
  id: string;
  href: string;
  num: string;
  name: string;
  status: JobStatus;
  taskLong: string;
  toolsLong: string;
  inputs: string;
  claim: string;
  segments: SegmentModel[];
  verdict: VerdictMeta | null;
  outcome: Outcome | null;
  statusLabel: string;
  elapsed: string;
  checks: ChecksLine;
  error: string | null;
}

/** One job card (prototype `jobCards[i]`); `index` counts from the newest job. */
export function jobCardModel(job: Job, index: number, total: number, record: UiRunRecord | null | undefined, tasks?: Task[] | null, register?: Tool[] | null): JobCardModel {
  const cells = layerCells(job, record);
  const tools = jobTools(job, record, register);
  const outcome = job.verdict ?? (job.status === 'done' ? (record?.verdict.outcome ?? null) : null);
  return {
    id: job.id,
    href: `/jobs/${encodeURIComponent(job.id)}`,
    num: String(total - index).padStart(2, '0'),
    name: job.name || job.id,
    status: job.status,
    taskLong: taskLongName(job, record, tasks),
    toolsLong: tools.length ? tools.map(toolLabel).join(', ') : DASH,
    inputs: inputsSummary(record, job),
    claim: record?.claim || tasks?.find((t) => t.id === job.task)?.claim || DASH,
    segments: jobSegments(cells),
    verdict: job.status === 'done' && outcome ? verdictMeta(outcome) : null,
    outcome,
    statusLabel: jobStatusLabel(job, cells),
    elapsed: fmtSeconds(job.elapsedMs),
    checks: checksLine(job, record),
    error: jobError(job),
  };
}

/** Family of each tool id of the job (docking tools are listed with their parameters). */
export function isDockingTool(tool: { family?: string | null } | null | undefined): boolean {
  return familyOf(tool) === 'docking';
}
