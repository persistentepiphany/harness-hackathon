// Agent monitor derivations (prototype renderVals() `ag` block in logic-v2.js). Pure functions over
// the wire shapes of GET /ui/agent/tasks and the step stream, so they work for the live API (step
// count in `steps`, outcome only after finish) and for the mock simulator (revealed steps in
// `steps`, `stepsTotal` known).

import { fmtMs, isMissing } from '@/lib/format';
import type { AgentOutcome, AgentStep, AgentStepKind, AgentTask, AgentTaskStatus } from '@/lib/types';

export const STEP_KINDS: AgentStepKind[] = ['thought', 'tool', 'result', 'report', 'conclusion'];

export function isStepKind(kind: unknown): kind is AgentStepKind {
  return typeof kind === 'string' && (STEP_KINDS as string[]).includes(kind);
}

/** Steps reported so far. The live API sends a count, the mock sends the revealed steps. */
export function stepCount(task: Pick<AgentTask, 'steps'>): number {
  const s: unknown = task.steps;
  if (typeof s === 'number' && Number.isFinite(s)) return s;
  if (Array.isArray(s)) return s.length;
  return 0;
}

export function isActive(task: Pick<AgentTask, 'status'>): boolean {
  return task.status === 'running' || task.status === 'queued';
}

/** `1 running · 2 completed`, plus failed when any (prototype `ag.summary`). */
export function agentSummary(tasks: Pick<AgentTask, 'status'>[]): string {
  const running = tasks.filter((t) => t.status === 'running').length;
  const done = tasks.filter((t) => t.status === 'done').length;
  const failed = tasks.filter((t) => t.status === 'failed').length;
  return `${running} running · ${done} completed${failed ? ` · ${failed} failed` : ''}`;
}

/** Task to show when the viewer has not picked one: the first running task, else the first. */
export function defaultTaskId(tasks: Pick<AgentTask, 'id' | 'status'>[]): string | null {
  return tasks.find((t) => t.status === 'running')?.id ?? tasks[0]?.id ?? null;
}

export interface FollowState {
  /** Task ids seen so far; null before the list first loaded. */
  seen: string[] | null;
  /** Task shown while the viewer has not picked one. */
  auto: string | null;
}

export const INITIAL_FOLLOW: FollowState = { seen: null, auto: null };

/**
 * Selection without a pick. The task chosen when the list first loads stays selected (prototype);
 * a task that appears later while running or queued is followed, so an agent under test shows up
 * as it starts.
 */
export function nextFollow(prev: FollowState, tasks: Pick<AgentTask, 'id' | 'status'>[]): FollowState {
  if (prev.seen === null) return { seen: tasks.map((t) => t.id), auto: defaultTaskId(tasks) };
  const known = new Set(prev.seen);
  const fresh = tasks.filter((t) => !known.has(t.id));
  if (!fresh.length) return prev;
  const started = fresh.find(isActive);
  return { seen: [...prev.seen, ...fresh.map((t) => t.id)], auto: started ? started.id : prev.auto };
}

/**
 * Elapsed time of a task. A running live task is measured against the wall clock from
 * `createdAt` (the list is polled, so `elapsedMs` lags); otherwise the reported `elapsedMs`.
 */
export function taskElapsedMs(task: Pick<AgentTask, 'status' | 'createdAt' | 'elapsedMs'>, opts: { live: boolean; nowMs: number }): number | null {
  const reported = isMissing(task.elapsedMs) ? null : task.elapsedMs;
  if (opts.live && task.status === 'running') {
    const start = Date.parse(task.createdAt);
    if (Number.isFinite(start)) return Math.max(reported ?? 0, opts.nowMs - start);
  }
  return reported;
}

/** Whole seconds as the task list shows them (`16 s`). */
export function fmtElapsedShort(ms: number | null): string {
  return ms === null ? '–' : `${(ms / 1000).toFixed(0)} s`;
}

/** Seconds to one decimal as the task header shows them (`20.3 s`). */
export function fmtElapsedLong(ms: number | null): string {
  return ms === null ? '–' : `${(ms / 1000).toFixed(1)} s`;
}

export type TaskTone = AgentTaskStatus;

export interface TaskCardView {
  id: string;
  goal: string;
  status: AgentTaskStatus;
  /** `completed` (outcome label, lower case), `failed`, `running`, `queued`. */
  statusLabel: string;
  /** 0..100. */
  pct: number;
  stepsDone: number;
  /** Planned steps when known (mock), the final count once finished, otherwise null. */
  stepsTotal: number | null;
  /** `13/13 steps · 2 runs` or `4 steps` while a live task runs. */
  stepLabel: string;
  runs: number | null;
  elapsedMs: number | null;
}

export interface TaskViewOptions {
  live: boolean;
  nowMs: number;
  /** Streamed steps of this task, when it is the selected one. */
  steps?: AgentStep[];
}

function finished(status: AgentTaskStatus): boolean {
  return status === 'done' || status === 'failed';
}

/** Total steps: planned count (mock), the final count once finished, otherwise unknown. */
export function stepsTotalOf(task: Pick<AgentTask, 'status' | 'stepsTotal' | 'steps'>, done: number): number | null {
  if (!isMissing(task.stepsTotal)) return Math.max(task.stepsTotal, done);
  return finished(task.status) ? done : null;
}

export function fmtSteps(done: number, total: number | null): string {
  return total === null ? `${done} step${done === 1 ? '' : 's'}` : `${done}/${total} steps`;
}

/** Runs the task reported: outcome.runs once finished, else distinct run ids its steps reference. */
export function runsOf(outcome: AgentOutcome | null | undefined, steps?: AgentStep[]): number | null {
  if (outcome && !isMissing(outcome.runs)) return outcome.runs;
  if (steps && steps.length) {
    const n = new Set(steps.flatMap((s) => runRefs(s).map((r) => r.id))).size;
    return n || null;
  }
  return null;
}

export function taskCard(task: AgentTask, opts: TaskViewOptions): TaskCardView {
  const stepsDone = Math.max(stepCount(task), opts.steps?.length ?? 0);
  const stepsTotal = stepsTotalOf(task, stepsDone);
  const runs = runsOf(task.outcome, opts.steps);
  const progress = isMissing(task.progress) ? (task.status === 'done' ? 1 : 0) : task.progress;
  const statusLabel =
    task.status === 'done' ? (task.outcome?.label ? task.outcome.label.toLowerCase() : 'done') : task.status;
  return {
    id: task.id,
    goal: task.goal,
    status: task.status,
    statusLabel,
    pct: Math.round(Math.min(1, Math.max(0, progress)) * 100),
    stepsDone,
    stepsTotal,
    stepLabel: `${fmtSteps(stepsDone, stepsTotal)}${runs !== null ? ` · ${runs} runs` : ''}`,
    runs,
    elapsedMs: taskElapsedMs(task, opts),
  };
}

// ---------------------------------------------------------------- steps

export interface RunRef {
  id: string;
  /** Where the id came from: `data.runId`/`data.runIds`, `data.jobId`/`data.jobIds`, or the text. */
  from: 'run' | 'job' | 'text';
}

const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
// harness run ids `<prefix>-<12 hex>` (pah.core.events.new_run_id, e.g. ligand_pose-04e7e402bf85)
// and the mock form `run_YYYYMMDD_<hex>`; a word that only starts with `run_` (run_id) is not an id
const TEXT_RUN = /\b(?:[a-z][a-z0-9_]*-[0-9a-f]{12}|run_\d{8}_[0-9a-f]{6,})\b/g;

function idsOf(v: unknown): string[] {
  if (typeof v === 'string') return [v];
  if (Array.isArray(v)) return v.filter((x): x is string => typeof x === 'string');
  return [];
}

/**
 * Run or job ids a step refers to: `data.runId`, `data.runIds`, `data.jobId`, `data.jobIds`, then
 * run ids in the text (`<task>-<12 hex>`, mock `run_YYYYMMDD_<hex>`). Deduplicated, in that order; ids that are not path-safe are dropped.
 */
export function runRefs(step: Pick<AgentStep, 'text' | 'data'>): RunRef[] {
  const out: RunRef[] = [];
  const seen = new Set<string>();
  const add = (id: string, from: RunRef['from']) => {
    const v = id.trim();
    if (!SAFE_ID.test(v) || seen.has(v)) return;
    seen.add(v);
    out.push({ id: v, from });
  };
  const data = step.data && typeof step.data === 'object' ? step.data : null;
  if (data) {
    for (const id of [...idsOf(data.runId), ...idsOf(data.runIds)]) add(id, 'run');
    for (const id of [...idsOf(data.jobId), ...idsOf(data.jobIds)]) add(id, 'job');
  }
  for (const m of (step.text ?? '').matchAll(TEXT_RUN)) add(m[0], 'text');
  return out;
}

export interface RunLink {
  id: string;
  jobHref: string;
  reportHref: string;
}

export function runLinks(step: Pick<AgentStep, 'text' | 'data'>): RunLink[] {
  return runRefs(step).map((r) => {
    const id = encodeURIComponent(r.id);
    return { id: r.id, jobHref: `/jobs/${id}`, reportHref: `/reports/${id}` };
  });
}

export interface StepView {
  seq: number;
  kind: AgentStepKind;
  text: string;
  /** Time of the step relative to the task start, ms; null when a timestamp is missing. */
  offsetMs: number | null;
  /** `1.5s` as the prototype timeline shows it. */
  offsetLabel: string;
  /** Duration the agent reported for the step. */
  ms: number | null;
  msLabel: string | null;
  links: RunLink[];
}

/** Timeline rows. The offset is the step timestamp minus the task's createdAt. */
export function stepViews(steps: AgentStep[], createdAt: string | null | undefined): StepView[] {
  const start = createdAt ? Date.parse(createdAt) : NaN;
  return steps.map((s) => {
    const ts = Date.parse(s.ts);
    const offset = Number.isFinite(ts) && Number.isFinite(start) ? Math.max(0, ts - start) : null;
    const ms = isMissing(s.ms) ? null : s.ms;
    return {
      seq: s.seq,
      kind: isStepKind(s.kind) ? s.kind : 'thought',
      text: s.text ?? '',
      offsetMs: offset,
      offsetLabel: offset === null ? '–' : `${(offset / 1000).toFixed(1)}s`,
      ms,
      msLabel: ms === null ? null : fmtMs(ms),
      links: runLinks(s),
    };
  });
}

export interface StepCounts {
  toolCalls: number;
  reports: number;
}

export function stepCounts(steps: Pick<AgentStep, 'kind'>[]): StepCounts {
  return {
    toolCalls: steps.filter((s) => s.kind === 'tool').length,
    reports: steps.filter((s) => s.kind === 'report').length,
  };
}

/**
 * Label of the pending row while a task runs (prototype `nextKind`). The next step is not known
 * ahead of time, so the label follows from the last step: after a tool call the agent waits for
 * its result, otherwise it is thinking.
 */
export function pendingLabel(last: Pick<AgentStep, 'kind'> | undefined, status: AgentTaskStatus): string {
  if (status === 'queued') return 'queued';
  if (last?.kind === 'tool') return 'waiting for result';
  if (last?.kind === 'conclusion') return 'finishing';
  return 'thinking';
}
