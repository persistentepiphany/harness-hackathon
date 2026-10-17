// Derivations for the Jobs overview and the single-job view (prototype logic-v2.js renderVals,
// "jobs + run" block). Pure functions over the wire shapes in lib/types.ts: a Job (GET /ui/jobs),
// the UI run record when it is available, the tool register and the task list. Nothing here is
// written for a particular executor; every label comes from the record or the register.

import { DASH, fmtMs, fmtSeconds, fmtSha } from '../format';
import { familyOf, toolById } from '../tools';
import type { Assessment, ExecutionPhase, Job, JobStatus, LayerStatus, Outcome, RecordLayer, RecordRender, RecordSource, Result, Task, Tool, UiCheck, UiExecution, UiPoseCheck, UiRunRecord } from '../types';
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
    case 'not_assessed':
      return { label: 'Not assessed', tone: 'muted' };
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
  /** Checks whose skip leaves the verdict incomplete; the cell is muted, not the pass colour. */
  incomplete: string[];
}

/** Skip reasons that leave the verdict incomplete (pah.core.check.INCOMPLETE_REASONS). */
const INCOMPLETE_REASONS = new Set(['tool_missing', 'error', 'unknown_check']);

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
      incomplete: jl?.incomplete ?? (rl?.checks ?? []).filter((c) => c.result === 'skip' && !!c.skipReason && INCOMPLETE_REASONS.has(c.skipReason)).map((c) => c.id),
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
  /** Checks that left the layer incomplete (muted bar, listed in `title`). */
  incomplete: string[];
  title?: string;
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
    const incomplete = c.state === 'done' && c.incomplete.length > 0;
    return {
      i: c.i,
      name: c.name,
      state: c.state,
      result: c.result,
      pct: c.pct,
      color: c.state === 'done' ? (incomplete && (c.result === 'pass' || c.result === 'skip') ? 'var(--color-faint)' : doneColor) : 'var(--color-accent)',
      active: c.state === 'done' || c.state === 'running',
      counts,
      countsMuted,
      incomplete: incomplete ? c.incomplete : [],
      title: incomplete ? `incomplete: ${c.incomplete.join(', ')}` : undefined,
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
  /** `pass 3 · warn 1 · stop 0 · skip 8` for the title attribute (`incomplete: <ids>` first). */
  title: string;
  /** Checks that left the layer incomplete; the bar is muted instead of the pass colour. */
  incomplete: string[];
}

/** Layer strip columns of the single-job view (prototype `rj.layers`). */
export function layerStrip(cells: LayerCell[]): StripModel[] {
  return cells.map((c) => {
    const t = c.tally;
    const incomplete = c.state === 'done' && c.incomplete.length > 0;
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
      // a pass with an incomplete skip is drawn muted: the layer did not run all of its checks
      bar: c.state === 'done' ? (incomplete && (c.result ?? 'pass') === 'pass' ? 'var(--color-faint)' : resultColorVar(c.result ?? 'pass')) : c.state === 'running' ? 'var(--color-accent)' : 'var(--color-line)',
      value,
      valueTone,
      nameTone: c.state === 'done' || c.state === 'running' ? 'ink' : 'faint',
      counts,
      title: `${incomplete ? `incomplete: ${c.incomplete.join(', ')} · ` : ''}pass ${t.pass} · warn ${t.warn} · stop ${t.stop} · skip ${t.skip + t.notImplemented}${t.notImplemented ? ` (${t.notImplemented} not implemented)` : ''}`,
      incomplete: incomplete ? c.incomplete : [],
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

// ---------------------------------------------------------------- execution (executor progress)

const ACTIVE_PHASES: ExecutionPhase[] = ['queued', 'building', 'running'];

/** Executions of the run: the job's (fresher, pushed with every poll) else the record's. */
export function executionOf(job: Pick<Job, 'execution'> | null | undefined, record: Pick<UiRunRecord, 'execution'> | null | undefined): UiExecution[] {
  if (job?.execution?.length) return job.execution;
  return record?.execution ?? [];
}

export function isExecutionActive(execs: Pick<UiExecution, 'phase'>[] | null | undefined): boolean {
  return (execs ?? []).some((e) => ACTIVE_PHASES.includes(e.phase));
}

export function assessmentOf(job: Pick<Job, 'assessment'> | null | undefined, record: Pick<UiRunRecord, 'assessment'> | null | undefined): Assessment | null {
  return job?.assessment ?? record?.assessment ?? null;
}

const where = (e: Pick<UiExecution, 'gpu' | 'route'>) => [e.gpu ?? 'CPU', e.route ? `${e.route} route` : ''].filter(Boolean).join(' · ');

/**
 * One line on what the executors do now: `Boltz-2 engaged · A100 · stock route · seed 2/5`,
 * `Boltz-2 building · A100 · stock route`, `Boltz-2 · Protenix ran · 17.4 s`; null without executions.
 */
export function engagedLine(execs: UiExecution[]): { text: string; active: boolean } | null {
  if (!execs.length) return null;
  const order: ExecutionPhase[] = ['running', 'building', 'queued'];
  for (const ph of order) {
    const e = execs.find((x) => x.phase === ph);
    if (!e) continue;
    const done = e.seeds.filter((x) => x.phase === 'done').length;
    const label = ph === 'running' ? 'engaged' : ph;
    const seed = ph === 'running' && e.seeds.length ? ` · seed ${Math.min(e.seeds.length, done + 1)}/${e.seeds.length}` : '';
    return { text: `${e.name} ${label} · ${where(e)}${seed}`, active: true };
  }
  const ran = execs.filter((e) => e.phase === 'done');
  const failed = execs.filter((e) => e.phase === 'failed');
  const total = Math.max(0, ...execs.map((e) => e.elapsedMs ?? 0));
  if (failed.length) return { text: `${failed.map((e) => e.name).join(' · ')} failed${ran.length ? ` · ${ran.map((e) => e.name).join(' · ')} ran` : ''}`, active: false };
  if (ran.length) return { text: `${ran.map((e) => e.name).join(' · ')} ran · ${[...new Set(ran.map((e) => e.gpu ?? 'CPU'))].join(' + ')}${total ? ` · ${fmtSeconds(total)}` : ''}`, active: false };
  return { text: `executors not run: ${execs.map((e) => e.message ?? e.phase).join('; ')}`, active: false };
}

export type PhaseStepState = 'done' | 'active' | 'todo' | 'failed';

export interface ExecutionView {
  key: string;
  name: string;
  phase: ExecutionPhase;
  where: string;
  routeNote: string | null;
  elapsed: string;
  message: string | null;
  /** queued → building → running → done, with the state of each step. */
  steps: { phase: 'queued' | 'building' | 'running' | 'done'; state: PhaseStepState }[];
  seeds: { seed: number; phase: string; ms: number | null; label: string; frac: number }[];
}

const STEP_ORDER = ['queued', 'building', 'running', 'done'] as const;

export function executionViews(execs: UiExecution[]): ExecutionView[] {
  return execs.map((e) => {
    const idx = STEP_ORDER.indexOf(e.phase as (typeof STEP_ORDER)[number]);
    const steps = STEP_ORDER.map((ph, i) => {
      let state: PhaseStepState = 'todo';
      if (e.phase === 'failed') state = i === 0 ? 'done' : i === 3 ? 'failed' : 'todo';
      else if (e.phase === 'done') state = 'done';
      else if (idx >= 0) state = i < idx ? 'done' : i === idx ? 'active' : 'todo';
      return { phase: ph, state };
    });
    const max = Math.max(1, ...e.seeds.map((x) => x.ms ?? 0));
    return {
      key: e.executor,
      name: e.name,
      phase: e.phase,
      where: where(e),
      routeNote: e.routeNote ?? null,
      elapsed: e.elapsedMs === null || e.elapsedMs === undefined ? DASH : fmtSeconds(e.elapsedMs),
      message: e.message ?? null,
      steps,
      seeds: e.seeds.map((x) => ({ seed: x.seed, phase: String(x.phase), ms: x.ms ?? null, label: x.ms === null || x.ms === undefined ? DASH : fmtMs(x.ms), frac: Math.max(0.04, (x.ms ?? 0) / max) })),
    };
  });
}

export type StageKey = 'pre' | 'execute' | 'output' | 'report';
export type StageState = 'done' | 'active' | 'todo' | 'skipped';

export interface StageView {
  key: StageKey;
  label: string;
  ms: number | null;
  text: string;
  state: StageState;
}

const sumDur = (record: UiRunRecord | null | undefined, from: number, to: number) => {
  const ls = (record?.layers ?? []).filter((l) => l.i >= from && l.i <= to && typeof l.durationMs === 'number');
  return ls.length ? ls.reduce((a, l) => a + (l.durationMs ?? 0), 0) : null;
};

/** Execution span: first start to last end when start times are known, else the longest executor. */
function executeMs(execs: UiExecution[]): number | null {
  const timed = execs.filter((e) => typeof e.elapsedMs === 'number');
  if (!timed.length) return null;
  const starts = timed.filter((e) => e.startedAt).map((e) => ({ s: Date.parse(e.startedAt as string), e: Date.parse(e.startedAt as string) + (e.elapsedMs ?? 0) }));
  if (starts.length === timed.length && starts.every((x) => Number.isFinite(x.s))) return Math.max(...starts.map((x) => x.e)) - Math.min(...starts.map((x) => x.s));
  return Math.max(...timed.map((e) => e.elapsedMs ?? 0));
}

/** Stage timings: pre-run layers 0–3, execute, output layers 4–5, report. */
export function stageTimings(job: Job, record: UiRunRecord | null | undefined, execs: UiExecution[]): StageView[] {
  const pre = assessmentOf(job, record) === 'pre-run';
  const active = isExecutionActive(execs);
  const reporting = job.reportStatus === 'running' || record?.report?.status === 'running';
  const running = job.status === 'running';
  const preMs = sumDur(record, 0, 3);
  const outMs = sumDur(record, 4, 5);
  const exMs = executeMs(execs);
  const done = job.status === 'done';
  let reportMs: number | null = null;
  if (done && job.elapsedMs) {
    const rest = job.elapsedMs - (preMs ?? 0) - (exMs ?? 0) - (outMs ?? 0);
    reportMs = rest > 0 ? rest : null;
  }
  const preState: StageState = job.layerIdx >= 4 || done ? 'done' : running ? 'active' : 'todo';
  const exState: StageState = pre || (!execs.length && (done || job.layerIdx >= 4)) ? 'skipped' : active ? 'active' : execs.length && execs.every((e) => !ACTIVE_PHASES.includes(e.phase)) ? 'done' : 'todo';
  const outState: StageState = pre ? 'skipped' : done || (job.layerIdx >= 6) ? 'done' : running && job.layerIdx >= 4 && !active ? 'active' : 'todo';
  const repState: StageState = reporting ? 'active' : done ? 'done' : 'todo';
  const t = (ms: number | null, st: StageState) => (st === 'skipped' ? 'not run' : ms === null ? (st === 'active' ? 'running' : DASH) : fmtSeconds(ms));
  return [
    { key: 'pre', label: 'Pre-run layers', ms: preMs, state: preState, text: t(preMs, preState) },
    { key: 'execute', label: 'Execute', ms: exMs, state: exState, text: t(exMs, exState) },
    { key: 'output', label: 'Output layers', ms: outMs, state: outState, text: t(outMs, outState) },
    { key: 'report', label: 'Report', ms: reportMs, state: repState, text: t(reportMs, repState) },
  ];
}

/** Execution line of a job card: what runs now, what ran, or that the run is a pre-run check. */
export function jobExecutionLine(job: Job, record: UiRunRecord | null | undefined): { text: string; active: boolean } | null {
  const execs = executionOf(job, record);
  if (assessmentOf(job, record) === 'pre-run') return { text: 'pre-run check · executors not run', active: false };
  const line = engagedLine(execs);
  if (line) return line;
  return null;
}

// ---------------------------------------------------------------- job story (provenance → report)

export interface SourceRowView {
  key: string;
  source: string;
  accession: string;
  release: string;
  sha: string;
  shaTitle: string;
  cached: boolean | null;
  ms: string;
}

/**
 * Source rows revealed so far: in step with the fetch/cache log lines when the log has them,
 * else every record source once layer 0 has started.
 */
export function sourceRows(sources: RecordSource[] | null | undefined, fetchLines: number | null, layer0Started: boolean): SourceRowView[] {
  const list = sources ?? [];
  const shown = fetchLines !== null && fetchLines > 0 ? list.slice(0, fetchLines) : layer0Started ? list : [];
  return shown.map((x, i) => ({
    key: x.id ?? `${x.source}-${x.accession}-${i}`,
    source: x.source,
    accession: x.accession,
    release: x.release || x.version || DASH,
    sha: fmtSha(x.sha256),
    shaTitle: x.sha256,
    cached: typeof x.cached === 'boolean' ? x.cached : null,
    ms: typeof x.ms === 'number' ? fmtMs(x.ms) : DASH,
  }));
}

/** `8 identifiers → 7 records · 1 failed · 4 cache hits · chains A, B` from record.sourceSummary, else from the rows. */
export function sourceCounts(record: UiRunRecord | null | undefined, rows: SourceRowView[]): string {
  const s = record?.sourceSummary;
  const parts: string[] = [];
  if (s && typeof s.identifiers === 'number' && typeof s.records === 'number') parts.push(`${s.identifiers} identifiers → ${s.records} records`);
  else if (rows.length) parts.push(`${rows.length} records`);
  if (s?.failed) parts.push(`${s.failed} failed`);
  const hits = typeof s?.cacheHits === 'number' ? s.cacheHits : rows.filter((r) => r.cached === true).length;
  if (rows.length || s) parts.push(`${hits} from cache`);
  if (s?.chains?.length) parts.push(`chains ${s.chains.join(', ')}`);
  return parts.join(' · ');
}

export interface CheckRowView {
  id: string;
  name: string;
  layer: number;
  result: Result;
  gate: string;
  /** `0.62 Å · ≤ 2 Å` or the evidence text. */
  value: string;
  origin: string | null;
  category: string | null;
  standing: string | null;
}

const cmpText = (c: string) => ({ '<=': '≤', '>=': '≥', '<': '<', '>': '>', '==': '=', '!=': '≠' })[c] ?? c;

/** Finished checks of layers `from`..`to` (pending ones left out), with value vs threshold. */
export function checkRows(record: UiRunRecord | null | undefined, from: number, to: number): CheckRowView[] {
  const out: CheckRowView[] = [];
  for (const l of record?.layers ?? []) {
    if (l.i < from || l.i > to) continue;
    for (const c of l.checks) {
      if (c.result === 'pending') continue;
      const extra = c as UiCheck & { category?: string | null; standing?: string | null };
      const m = c.measurements?.find((x) => typeof x.value === 'number') ?? c.measurements?.[0];
      const th = c.thresholds?.find((t) => !t.measurement || t.measurement === m?.name) ?? c.thresholds?.[0];
      let value = '';
      if (m && m.value !== null && m.value !== undefined) value = `${typeof m.value === 'number' ? +m.value.toPrecision(4) : String(m.value)}${m.unit ? `${' '}${m.unit}` : ''}`;
      if (th) value = `${value ? `${value} · ` : ''}${cmpText(th.comparator)} ${th.value}`;
      else if (c.threshold?.value) value = `${value ? `${value} · ` : ''}${c.threshold.value}`;
      if (!value) value = c.result === 'skip' ? `skip${c.skipReason ? ` · ${c.skipReason.replace(/_/g, ' ')}` : ''}` : (c.evidence ?? c.message ?? '');
      out.push({
        id: c.id,
        name: c.name,
        layer: l.i,
        result: c.result,
        gate: c.gate,
        value,
        origin: th?.origin ?? c.threshold?.origin ?? null,
        category: extra.category ?? null,
        standing: extra.standing ?? null,
      });
    }
  }
  return out;
}

/** Output checks waiting for predictions (skip with pending_input, or verdict.pending). */
export function pendingOutputChecks(record: UiRunRecord | null | undefined): number {
  const own = (record?.layers ?? []).filter((l) => l.i >= 4).flatMap((l) => l.checks).filter((c) => c.result === 'skip' && c.skipReason === 'pending_input').length;
  return Math.max(own, record?.verdict.pending?.length ?? 0);
}

export interface PoseThumbView {
  key: string;
  png: string;
  alt: string;
  caption: string;
  executor: string | null;
  /** `seed 0 · #1`. */
  label: string;
  /** `Confidence 0.81`, `Vina score −9.2 kcal/mol`; null when the pose reports none. */
  score: string | null;
  badge: { text: string; tone: 'pass' | 'warn' | 'stop' | 'muted' };
  /** `pending` while the report stage has not rendered this structure yet. */
  status: 'rendered' | 'pending' | 'failed';
  /** The structure rendered first (medoid or top-ranked pose). */
  main: boolean;
}

function poseBadge(checks: UiPoseCheck[]): PoseThumbView['badge'] {
  if (!checks.length) return { text: 'checks pending', tone: 'muted' };
  const stop = checks.filter((c) => c.result === 'stop');
  if (stop.length) return { text: `fails ${stop[0].name.toLowerCase()}${stop[0].failed?.length ? ` · ${stop[0].failed.slice(0, 2).join(', ')}` : ''}`, tone: 'stop' };
  const warn = checks.filter((c) => c.result === 'warn');
  if (warn.length) return { text: `warn · ${warn[0].name.toLowerCase()}`, tone: 'warn' };
  const pass = checks.filter((c) => c.result === 'pass');
  if (pass.length) return { text: `${pass.length}/${checks.length} checks pass`, tone: 'pass' };
  return { text: 'values reported', tone: 'muted' };
}

/** Thumbnails of predicted poses (renders with an executor, or every render when none says). */
export function poseThumbs(record: UiRunRecord | null | undefined, executor?: string | null): PoseThumbView[] {
  const renders: RecordRender[] = record?.renders ?? [];
  const poseRenders = renders.filter((r) => (r.executor || r.seed !== undefined || r.pose) && (!executor || r.executor === executor));
  // one thumbnail per structure (the overview view when there are several), main structure first
  const byStructure = new Map<string, RecordRender>();
  for (const r of poseRenders) {
    const cur = byStructure.get(r.structure);
    if (!cur || (cur.view !== 'overview' && r.view === 'overview')) byStructure.set(r.structure, r);
  }
  return [...byStructure.values()]
    .sort((a, b) => Number(!!b.main) - Number(!!a.main))
    .map((r, i) => {
      const fromRecord = r.pose ? record?.poseChecks?.find((p) => p.pose === r.pose)?.checks : undefined;
      const checks = r.checks?.length ? r.checks : (fromRecord ?? []);
      const label = [r.seed !== null && r.seed !== undefined ? `seed ${r.seed}` : r.pose ?? '', r.rank !== null && r.rank !== undefined ? `#${r.rank}` : ''].filter(Boolean).join(' · ') || `pose ${i + 1}`;
      return {
        key: `${r.structure}-${r.view}-${i}`,
        png: r.png,
        alt: r.alt ?? r.caption ?? `PyMOL render ${label}`,
        caption: r.caption ?? label,
        executor: r.executor ?? null,
        label,
        score: r.score ? `${r.score.label} ${fmtNumber(r.score.value)}${r.score.unit ? `${' '}${r.score.unit}` : ''}` : null,
        badge: poseBadge(checks),
        status: r.status ?? (r.png ? 'rendered' : 'pending'),
        main: !!r.main,
      };
    });
}

const fmtNumber = (v: number) => {
  const s = String(+v.toPrecision(3));
  return s.startsWith('-') ? `−${s.slice(1)}` : s;
};
