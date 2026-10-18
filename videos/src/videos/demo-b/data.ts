// The film's data: copied from the harness's own records (scripts/extract-data.py) and from the live
// API (interpret.json, entities.json), plus the prototype's demo agent task (agent.json). No value is
// computed here beyond formatting and counting what the records already hold.

import agentData from './data/agent.json';
import entitiesData from './data/entities.json';
import interpretData from './data/interpret.json';
import runData from './data/run.json';
import { DASH, THIN, type Result } from './tokens';

export const run = runData;
export const interpret = interpretData;
export const entityGroups = entitiesData.groups;
export const agentTasks = agentData.tasks;

// ------------------------------------------------------------------ formatting (web/lib/format.ts)
export function fmtNum(value: number | string | null | undefined, unit?: string | null, digits?: number): string {
  if (value === null || value === undefined || value === '') return DASH;
  let s: string;
  if (typeof value === 'number') {
    s = digits === undefined ? String(+value.toPrecision(12)) : value.toFixed(digits);
    if (s.startsWith('-')) s = `−${s.slice(1)}`;
  } else s = value;
  return unit ? `${s}${THIN}${unit}` : s;
}
export function fmtMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return DASH;
  if (Math.abs(ms) < 1000) return `${Math.round(ms)}${THIN}ms`;
  return `${(ms / 1000).toFixed(1)}${THIN}s`;
}
export const fmtSeconds = (ms: number) => `${(ms / 1000).toFixed(1)}${THIN}s`;

// ------------------------------------------------------------------ the run
export type LogLine = (typeof run.log)[number] & { sec: number };
export const logLines: LogLine[] = run.log.map((l) => ({ ...l, sec: parseFloat(l.t) }));

export const layers = run.layers;
export const LAYER_NAMES = layers.map((l) => l.name);

/** Checks of each layer, in the order the log reports them. */
export const layerCheckCount = layers.map((l) => l.checks.length);

/** Recorded second at which each layer's end line appears. */
export const layerEndSec = layers.map((l) => logLines.find((x) => x.kind === 'layer' && x.layer === l.i && x.result !== null)!.sec);
export const layerStartSec = layers.map((l) => logLines.find((x) => x.kind === 'layer' && x.layer === l.i && x.result === null)!.sec);

export type Tally = { pass: number; warn: number; stop: number; skip: number };
export const tallyOf = (counts: Partial<Record<Result, number>>): Tally => ({
  pass: counts.pass ?? 0,
  warn: counts.warn ?? 0,
  stop: counts.stop ?? 0,
  skip: counts.skip ?? 0,
});

/** Worst result of a finished layer (pass < warn < stop; skip-only is skip). */
export function worst(t: Tally): Result {
  if (t.stop) return 'stop';
  if (t.warn) return 'warn';
  if (t.pass) return 'pass';
  return 'skip';
}

/** Job card counts label (web/lib/selectors/jobs.ts jobSegments). */
export function segmentCounts(t: Tally): { text: string; muted: boolean } {
  if (t.stop) return { text: `${t.stop} stop`, muted: false };
  if (t.warn) return { text: `${t.warn} warn`, muted: false };
  if (t.pass) return { text: `${t.pass}`, muted: false };
  if (t.skip) return { text: `${t.skip} skip`, muted: true };
  return { text: '', muted: false };
}

/** Running tally of a layer from the check lines that have appeared. */
export function tallyFromLines(lines: LogLine[], layer: number): Tally {
  const t: Tally = { pass: 0, warn: 0, stop: 0, skip: 0 };
  for (const l of lines) if (l.kind === 'check' && l.layer === layer && l.result && l.result in t) t[l.result as keyof Tally]++;
  return t;
}

export const totalChecks = layers.reduce((n, l) => n + l.checks.length, 0); // 39
/** Result totals over all layers (verdict line on the job page: `31 pass · 3 warn · 0 stop · 5 skip`). */
export const totals = layers.reduce((acc, l) => {
  const t = tallyOf(l.counts);
  return { pass: acc.pass + t.pass, warn: acc.warn + t.warn, stop: acc.stop + t.stop, skip: acc.skip + t.skip };
}, { pass: 0, warn: 0, stop: 0, skip: 0 });

export const toolLabel = `${run.tools[0].name} ${run.tools[0].version}`; // AutoDock Vina 1.2.7
export const inputsLine = `${run.inputs.target} · ${run.inputs.reference} · ${run.inputs.seeds} seeds · pH ${run.inputs.ph}`;

export const checkById = (id: string) => {
  for (const l of layers) for (const c of l.checks) if (c.id === id) return c;
  throw new Error(`check ${id} not in record`);
};

/** `measured cmp threshold` (web/lib/format.ts measuredVsThreshold, same pairing rule). */
export function measuredVsThreshold(c: ReturnType<typeof checkById>): string | null {
  const ms = c.measurements ?? [];
  const ts = c.thresholds ?? [];
  const same = (a: unknown, b: unknown) => (typeof a === 'boolean') === (typeof b === 'boolean');
  let pair: { m: (typeof ms)[number]; t: (typeof ts)[number] } | null = null;
  for (const t of ts) {
    const m = ms.find((x) => x.name === t.name && same(x.value, t.value));
    if (m) {
      pair = { m, t };
      break;
    }
  }
  if (!pair)
    for (const t of ts) {
      const m = ms.find((x) => (t.name.includes(x.name) || x.name.includes(t.name)) && same(x.value, t.value));
      if (m) {
        pair = { m, t };
        break;
      }
    }
  if (!pair) return null;
  const v = (x: unknown) => (typeof x === 'boolean' ? String(x) : fmtNum(x as number));
  return `${pair.m.name} ${v(pair.m.value)} ${pair.t.comparator} ${v(pair.t.value)}`;
}

// ------------------------------------------------------------------ new run (live API captures)
const STEP_LABELS: Record<string, string> = {
  task: 'Task',
  tools: 'Executors',
  target: 'Target',
  partner: 'Partner',
  ligand: 'Ligand',
  seeds: 'Seeds',
  ph: 'pH',
  reference: 'Reference',
  claim: 'Claim',
};
const TOOL_NAMES: Record<string, string> = { vina: 'AutoDock Vina' };
const TASK_LONG: Record<string, string> = { ligand_pose: 'Ligand pose in a known pocket' };

export const decisionRows = interpret.steps.map((s) => {
  const v = s.value as unknown;
  const value =
    s.field === 'tools'
      ? (v as string[]).map((id) => TOOL_NAMES[id] ?? id).join(' · ')
      : s.field === 'task'
        ? (TASK_LONG[String(v)] ?? String(v))
        : String(v);
  return { label: STEP_LABELS[s.field] ?? s.field, value, because: s.because };
});
export const requestSummary = `${interpret.text.trim().split(/\s+/).length} tokens · ${interpret.steps.length} decisions`;

// ------------------------------------------------------------------ report values
export const pose = Object.fromEntries(run.stats.pose as [string, string][]) as Record<string, string>;
export const posebusters = run.stats.posebusters as { test: string; pass: boolean; value: string }[];
export const seeds = run.stats.seeds as { pose: string; seed: number; rmsdToMedoid: number; score: number; cluster: number }[];
export const pairwise = run.stats.pairwise as unknown as { median: number; iqr: [number, number]; n: number };
