// Printable report document derivations (prototype renderVals() `rp` and `docList` for the docs
// view, logic-v2.js). Values come from the record only: a stats block the harness did not compute
// yields no key number, and the run-level facts (checks evaluated, layers run, sources, check
// time) fill the row instead. Tool names and metric labels come from the record and its tools.

import { DASH, SEP, fmtMs, fmtNum, isMissing, measuredVsThreshold } from '@/lib/format';
import { medoidClusterPopulation, methodName, metricRows, seedAxis, seedConfidenceLabel, totalDurationMs, verdictMeta } from '@/lib/selectors/report';
import { outputFor, recordTools, toolById } from '@/lib/tools';
import type { Job, Outcome, Result, Tool, UiCheck, UiRunRecord } from '@/lib/types';

type Register = Tool[] | null | undefined;

// ---------------------------------------------------------------- document list

export interface DocListItem {
  /** Run id the document route takes. */
  runId: string;
  name: string;
  outcome: Outcome | null;
  verdictLabel: string;
  verdictColor: string;
  /** `Oct 17`. */
  date: string;
}

export function shortDate(iso: string | null | undefined): string {
  if (isMissing(iso)) return DASH;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? DASH : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Finished jobs, in list order (newest first live, prototype order in mock). */
export function docList(jobs: Job[] | null | undefined): DocListItem[] {
  return (jobs ?? [])
    .filter((j) => j.status === 'done')
    .map((j) => {
      const v = verdictMeta(j.verdict);
      return { runId: j.runId, name: j.name, outcome: j.verdict, verdictLabel: v.label, verdictColor: v.color, date: shortDate(j.createdAt) };
    });
}

/** Document title: the job's name, else the task name, else the run id. */
export function documentName(record: Pick<UiRunRecord, 'id' | 'taskName' | 'task'>, jobs: Job[] | null | undefined): string {
  const job = (jobs ?? []).find((j) => j.runId === record.id || j.id === record.id);
  return job?.name || record.taskName || record.task || record.id;
}

// ---------------------------------------------------------------- header line

/** `<tool> + <tool> · <target> · <reference> · 5 seeds`; tools that did not run are marked; the verdict scope last. */
export function metaLine(record: UiRunRecord, register?: Register): string {
  const tools = recordTools(record, register)
    .map((t) => `${t.name}${t.ran === false ? ' (not run)' : ''}`)
    .join(' + ');
  const { target, partner, reference, seeds } = record.inputs;
  const scope = record.verdict.scope ? `verdict scope ${record.verdict.scope}` : null;
  return [tools || null, target, partner, reference, isMissing(seeds) ? null : `${seeds} seeds`, scope]
    .filter((x): x is string => !isMissing(x))
    .join(SEP);
}

// ---------------------------------------------------------------- key numbers

export type Tone = 'ink' | 'warn' | 'stop' | 'muted';

export interface KeyNumber {
  id: string;
  value: string;
  label: string;
  tone: Tone;
  /** Full statement for the title attribute. */
  title?: string;
}

const KEY_COUNT = 6;

function allChecks(record: Pick<UiRunRecord, 'layers'>): UiCheck[] {
  return record.layers.flatMap((l) => l.checks);
}

function countOf(checks: UiCheck[], r: Result): number {
  return checks.filter((c) => c.result === r).length;
}

/** Key numbers from stats blocks, in prototype order: PoseBusters, metrics, medoid cluster, agreement. */
function statsKeyNumbers(record: UiRunRecord, register?: Register): KeyNumber[] {
  const S = record.stats;
  const out: KeyNumber[] = [];
  if (S.posebusters?.length) {
    const passed = S.posebusters.filter((p) => p.pass).length;
    out.push({ id: 'posebusters', value: `${passed}/${S.posebusters.length}`, label: 'PoseBusters', tone: passed === S.posebusters.length ? 'ink' : 'stop' });
  }
  // metrics: the first harness-derived value and the first value a tool reported (in the prototype
  // a pocket-level value and an interface score), then the rest in record order, until three cells
  // are filled
  const m = metricRows(record, register);
  if (m.computed && S.metrics) {
    const used = new Set(out.map((k) => k.label.toLowerCase()));
    const metricOf = (r: { id: string }) => S.metrics?.[Number(r.id.split(':')[0])];
    // RMSD-kind values are geometry, already in the cluster and agreement cells
    const isRmsd = (r: { id: string }) => {
      const mm = metricOf(r);
      const kind = (mm as { kind?: unknown } | undefined)?.kind ?? (mm?.toolId && mm.key ? outputFor(toolById(record, mm.toolId, register), mm.key)?.kind : undefined);
      return kind === 'rmsd';
    };
    const rows = m.rows.filter((r) => r.value !== null && !used.has(r.name.toLowerCase()) && !isRmsd(r));
    const linked = (r: (typeof rows)[number]) => !!metricOf(r)?.toolId;
    const prefer = [rows.find((r) => !linked(r)), rows.find(linked), ...rows].filter((r): r is (typeof rows)[number] => !!r);
    const picked: typeof rows = [];
    for (const r of prefer) {
      if (out.length + picked.length >= 3) break;
      if (!picked.includes(r)) picked.push(r);
    }
    picked.sort((a, b) => rows.indexOf(a) - rows.indexOf(b));
    for (const row of picked) {
      out.push({ id: `metric:${row.id}`, value: row.value as string, label: row.name, tone: 'ink', title: row.tool ? `${row.name} · ${row.tool}` : row.name });
    }
  }
  const cluster = medoidClusterPopulation(record);
  if (cluster) out.push({ id: 'cluster', value: cluster.replace(/ seeds$/, ''), label: 'seeds in medoid cluster', tone: 'ink' });
  const ag = S.agreement;
  if (ag && ag.length >= 2) {
    const cell = ag[0].cells.find((c) => c.vs === ag[1].method);
    if (cell) {
      out.push({
        id: 'agreement',
        value: fmtNum(cell.value, cell.unit),
        label: `${methodName(record, ag[0].method, register)} vs ${methodName(record, ag[1].method, register)}`,
        tone: 'ink',
      });
    }
  }
  return out;
}

/** Run-level facts the harness always records: checks evaluated, layers run, sources, check time. */
function runKeyNumbers(record: UiRunRecord): KeyNumber[] {
  const checks = allChecks(record);
  const evaluated = checks.filter((c) => c.result !== 'skip' && c.result !== 'pending').length;
  const run = record.layers.filter((l) => l.status === 'done').length;
  const sha = record.sources.filter((s) => !isMissing(s.sha256)).length;
  const dur = totalDurationMs(record);
  const out: KeyNumber[] = [
    { id: 'checks', value: `${evaluated}/${checks.length}`, label: 'checks evaluated', tone: 'ink', title: `${evaluated} of ${checks.length} listed checks returned pass, warn or stop` },
    { id: 'layers', value: `${run}/${record.layers.length}`, label: 'layers run', tone: 'ink' },
    { id: 'sources', value: String(record.sources.length), label: `sources · ${sha} with sha256`, tone: 'ink' },
  ];
  if (dur !== null) out.push({ id: 'time', value: fmtMs(dur), label: 'check time', tone: 'ink' });
  return out;
}

/** The flagged-checks cell: stops when any, else warnings. */
function flaggedKeyNumber(record: UiRunRecord): KeyNumber {
  const checks = allChecks(record);
  const stops = countOf(checks, 'stop');
  const warns = countOf(checks, 'warn');
  if (stops) return { id: 'flagged', value: String(stops), label: stops === 1 ? 'check stopped' : 'checks stopped', tone: 'stop' };
  if (warns) return { id: 'flagged', value: String(warns), label: warns === 1 ? 'check warned' : 'checks warned', tone: 'warn' };
  return { id: 'flagged', value: '0', label: 'checks warned or stopped', tone: 'ink' };
}

/** Stop and warning counts as two cells (run-level row); zero counts are muted, not hidden. */
function countKeyNumbers(record: UiRunRecord): KeyNumber[] {
  const checks = allChecks(record);
  const stops = countOf(checks, 'stop');
  const warns = countOf(checks, 'warn');
  return [
    { id: 'stops', value: String(stops), label: stops === 1 ? 'check stopped' : 'checks stopped', tone: stops ? 'stop' : 'muted' },
    { id: 'warnings', value: String(warns), label: warns === 1 ? 'check warned' : 'checks warned', tone: warns ? 'warn' : 'muted' },
  ];
}

/**
 * Six key numbers. With stats: five stats-derived cells and the flagged-checks cell (prototype).
 * Without enough stats: what there is, run-level facts, then stop and warning counts.
 */
export function keyNumbers(record: UiRunRecord, register?: Register): KeyNumber[] {
  const head = statsKeyNumbers(record, register);
  if (head.length >= KEY_COUNT - 1) return [...head.slice(0, KEY_COUNT - 1), flaggedKeyNumber(record)];
  return [...head, ...runKeyNumbers(record)].slice(0, KEY_COUNT - 2).concat(countKeyNumbers(record));
}

// ---------------------------------------------------------------- layers and flagged checks

export interface DocLayerRow {
  i: number;
  name: string;
  summary: string;
  /** `p/w/s`. */
  countsShort: string;
  /** Full counts for the title: `pass 2 · warn 0 · stop 1 · skip 0`. */
  countsLong: string;
  worst: Result | null;
  status: string;
}

function worst(checks: UiCheck[]): Result | null {
  if (checks.some((c) => c.result === 'stop')) return 'stop';
  if (checks.some((c) => c.result === 'warn')) return 'warn';
  if (checks.some((c) => c.result === 'pass')) return 'pass';
  return null;
}

/** Skipped checks grouped by skipReason, in first-seen order (`skip` without a reason: `no reason`). */
export function skipReasons(checks: UiCheck[]): [string, number][] {
  const m = new Map<string, number>();
  for (const c of checks) if (c.result === 'skip') m.set(c.skipReason || 'no_reason', (m.get(c.skipReason || 'no_reason') ?? 0) + 1);
  return Array.from(m.entries());
}

export function docLayers(record: Pick<UiRunRecord, 'layers'>): DocLayerRow[] {
  return record.layers.map((l) => {
    const p = countOf(l.checks, 'pass');
    const w = countOf(l.checks, 'warn');
    const s = countOf(l.checks, 'stop');
    const skip = countOf(l.checks, 'skip');
    const parts = [...(l.summary ?? [])];
    for (const [reason, n] of skipReasons(l.checks)) {
      const text = reason === 'unknown_check' ? `${n} not implemented` : `${n} skipped (${reason.replace(/_/g, ' ')})`;
      if (!parts.includes(text)) parts.push(text);
    }
    const summary = parts.length ? parts.join(SEP) : l.status === 'not_run' ? 'not run' : l.status === 'done' ? DASH : l.status;
    const ran = l.status !== 'not_run' && l.checks.length > 0;
    return {
      i: l.i,
      name: l.name,
      summary,
      countsShort: ran ? `${p}/${w}/${s}` : DASH,
      countsLong: `pass ${p}${SEP}warn ${w}${SEP}stop ${s}${SEP}skip ${skip}`,
      worst: worst(l.checks),
      status: l.status,
    };
  });
}

export interface FlaggedCheck {
  id: string;
  name: string;
  result: 'warn' | 'stop';
  layer: number;
  /** Evidence, plus `measured cmp threshold` when the check carries both. */
  evidence: string;
}

export function flaggedChecks(record: Pick<UiRunRecord, 'layers'>): FlaggedCheck[] {
  return record.layers.flatMap((l) =>
    l.checks
      .filter((c): c is UiCheck & { result: 'warn' | 'stop' } => c.result === 'warn' || c.result === 'stop')
      .map((c) => {
        const mvt = measuredVsThreshold(c);
        const ev = c.evidence ?? c.message ?? '';
        return { id: c.id, name: c.name || c.id, result: c.result, layer: l.i, evidence: [ev, mvt && !ev.includes(mvt) ? mvt : null].filter(Boolean).join(SEP) };
      }),
  );
}

// ---------------------------------------------------------------- figures and record line

/** Fig. 2 caption tail: `median 0.83 · IQR 0.81–0.90 · 95% CI 0.43–1.43`, plus τ when computed. */
export function seedStatsLine(record: UiRunRecord): string {
  const p = record.stats.pairwise as Partial<NonNullable<UiRunRecord['stats']['pairwise']>> | undefined;
  const pair = (v: unknown): [number, number] | null => (Array.isArray(v) && v.length === 2 && v.every((x) => typeof x === 'number') ? (v as [number, number]) : null);
  const parts: string[] = [];
  if (p && typeof p === 'object') {
    const unit = typeof (p as { unit?: unknown }).unit === 'string' ? ((p as { unit?: string }).unit as string) : undefined;
    if (typeof p.median === 'number') parts.push(`median ${fmtNum(p.median, unit, 2)}`);
    const iqr = pair(p.iqr);
    if (iqr) parts.push(`IQR ${fmtNum(iqr[0], undefined, 2)}–${fmtNum(iqr[1], undefined, 2)}`);
    const ci = pair(p.ci95);
    if (ci) parts.push(`95% CI ${fmtNum(ci[0], undefined, 2)}–${fmtNum(ci[1], undefined, 2)}`);
    if (typeof p.n === 'number') parts.push(`n = ${p.n}`);
  }
  const tau = record.stats.kendallTau;
  if (typeof tau === 'number') parts.push(`τ ${fmtNum(tau, undefined, 2)}`);
  return parts.join(SEP);
}

/**
 * y axis of the seed spread as the figure labels it: the co-folding confidence output, or the
 * seeds' tool score (`<label> (<unit>)`, `ranking only` when the output is ranking-only).
 */
export function seedAxisLabel(record: UiRunRecord, register?: Register): string {
  const axis = seedAxis(record);
  if (axis?.field !== 'score') return seedConfidenceLabel(record, register);
  const seeds = (Array.isArray(record.stats.seeds) ? record.stats.seeds : []) as { toolId?: string }[];
  const toolId = seeds.find((x) => x.toolId)?.toolId;
  const out = axis.key && toolId ? outputFor(toolById(record, toolId, register), axis.key) : undefined;
  const ranking = out ? !!out.rankingOnly : !!record.stats.metrics?.find((m) => m.key === axis.key)?.separate;
  return `${out?.label ?? axis.key ?? 'score'}${out?.unit ? ` (${out.unit})` : ''}${ranking ? ', ranking only' : ''}`;
}

/** `7/9 seen in known complexes`, or null when interactions were not computed. */
export function interactionSummary(record: UiRunRecord): string | null {
  const it = record.stats.interactions;
  if (!it) return null;
  return `${it.filter((i) => i.known).length}/${it.length} seen in known complexes`;
}

/** `run record <id>.json · <notebook> · seeds 1000 1017 · pah 0.1.0 · rdkit 2026.09.1`. */
export function recordLine(record: UiRunRecord): string {
  const r = record.record;
  const parts = [`run record ${record.id}.json`];
  if (r.runId && r.runId !== record.id) parts.push(`harness run ${r.runId}`);
  if (r.notebook) parts.push(r.notebook);
  if (r.seeds?.length) parts.push(`seeds ${r.seeds.join(' ')}`);
  if (r.pahVersion) parts.push(`pah ${r.pahVersion}`);
  for (const [k, v] of Object.entries(r.toolVersions ?? {})) parts.push(`${k} ${v}`);
  if (r.profile) parts.push(`profile ${r.profile}`);
  return parts.join(SEP);
}

/** Files the run wrote that the sidebar links (live): harness record, markdown report, provenance graph. */
export function reportFiles(record: UiRunRecord): { id: string; label: string; url: string }[] {
  const out: { id: string; label: string; url: string }[] = [];
  if (record.source === 'pah' && record.outputs.includes('record.json')) {
    out.push({ id: 'harness-record', label: 'Harness record · JSON', url: `/runs/${encodeURIComponent(record.id)}/files/record.json` });
  }
  const rep = record.report;
  if (rep?.reports?.markdown) out.push({ id: 'markdown', label: 'Report · Markdown', url: rep.reports.markdown });
  if (rep?.graph?.svg) out.push({ id: 'graph', label: 'Provenance graph · SVG', url: rep.graph.svg });
  return out;
}

// ---------------------------------------------------------------- block provenance

export interface BlockSource {
  check?: string;
  tool?: string;
}

function asSource(v: unknown): BlockSource | null {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return null;
  const o = v as Record<string, unknown>;
  const check = typeof o.check === 'string' ? o.check : undefined;
  const tool = typeof o.tool === 'string' ? o.tool : undefined;
  return check || tool ? { check, tool } : null;
}

/**
 * Check and tool a stats block came from, when the record says: `stats.provenance[key]` (live
 * adapter), `stats[key].source` on an object block, or `source` on the first row of a list block.
 * Null for mock records and absent blocks.
 */
export function blockSource(record: Pick<UiRunRecord, 'stats'>, key: string): BlockSource | null {
  const stats = record.stats as Record<string, unknown>;
  const prov = stats.provenance;
  if (prov && typeof prov === 'object' && !Array.isArray(prov)) {
    const hit = asSource((prov as Record<string, unknown>)[key]);
    if (hit) return hit;
  }
  const v = stats[key];
  if (Array.isArray(v)) return asSource((v[0] as { source?: unknown } | undefined)?.source);
  if (v && typeof v === 'object') return asSource((v as { source?: unknown }).source);
  return null;
}

/** ` · check l4.posebusters · posebusters` for a caption, or ''. */
export function sourceSuffix(src: BlockSource | null): string {
  if (!src) return '';
  return [src.check ? `check ${src.check}` : null, src.tool ?? null]
    .filter(Boolean)
    .map((s) => `${SEP}${s}`)
    .join('');
}
