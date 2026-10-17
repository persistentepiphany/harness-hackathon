// Number display rules (docs/UI.md "Number display"). Render the strings in Geist Mono
// (components/ui/MonoNum). Missing values are an en dash, never 0.

import type { Result, UiCheck } from './types';

/** En dash shown for a missing value (render it in muted ink). */
export const DASH = '–';
/** Thin space between a number and its unit. */
export const THIN = ' ';
/** Middle dot separator used across the UI. */
export const SEP = ' · ';

export type Maybe<T> = T | null | undefined;

export function isMissing(v: unknown): v is null | undefined {
  return v === null || v === undefined || (typeof v === 'number' && !Number.isFinite(v)) || v === '';
}

/** Value with its unit after a thin space: `2.1 Å`. Numbers keep `digits` decimals when given. */
export function fmtNum(value: Maybe<number | string>, unit?: string | null, digits?: number): string {
  if (isMissing(value)) return DASH;
  let s: string;
  if (typeof value === 'number') {
    s = digits === undefined ? String(+value.toPrecision(12)) : value.toFixed(digits);
    if (s.startsWith('-')) s = `−${s.slice(1)}`;
  } else {
    s = value;
  }
  return unit ? `${s}${THIN}${unit}` : s;
}

/** Duration: below 1 s in ms (`412 ms`), otherwise seconds to one decimal (`12.4 s`). */
export function fmtMs(ms: Maybe<number>): string {
  if (isMissing(ms)) return DASH;
  if (Math.abs(ms) < 1000) return `${Math.round(ms)}${THIN}ms`;
  return `${(ms / 1000).toFixed(1)}${THIN}s`;
}

/** Elapsed clock as the prototype shows it, always seconds to one decimal (`0.4 s`). */
export function fmtSeconds(ms: Maybe<number>): string {
  if (isMissing(ms)) return DASH;
  return `${(ms / 1000).toFixed(1)}${THIN}s`;
}

/** First 12 hex characters of a sha256 (put the full value in `title`). */
export function fmtSha(sha: Maybe<string>, opts: { ellipsis?: boolean } = {}): string {
  if (isMissing(sha)) return DASH;
  const short = sha.slice(0, 12);
  return opts.ellipsis && sha.length > 12 ? `${short}…` : short;
}

/** Fraction that keeps its denominator: `13/41`. */
export function fmtFraction(n: Maybe<number>, d: Maybe<number>): string {
  if (isMissing(n) || isMissing(d)) return DASH;
  return `${n}/${d}`;
}

/** Percentage of a 0..1 fraction: `42%`. */
export function fmtPct(frac: Maybe<number>, digits = 0): string {
  if (isMissing(frac)) return DASH;
  return `${(frac * 100).toFixed(digits)}%`;
}

/** Bytes as B, kB, MB, GB (powers of 1000). */
export function fmtBytes(n: Maybe<number>): string {
  if (isMissing(n)) return DASH;
  const units = ['B', 'kB', 'MB', 'GB'];
  let v = n;
  let i = 0;
  while (Math.abs(v) >= 1000 && i < units.length - 1) {
    v /= 1000;
    i++;
  }
  return `${i === 0 ? v : v.toFixed(v < 10 ? 1 : 0)}${THIN}${units[i]}`;
}

/** Local 24-hour time `14:05:09`. */
export function fmtTime(iso: Maybe<string>): string {
  if (isMissing(iso)) return DASH;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? DASH : d.toLocaleTimeString(undefined, { hour12: false });
}

/** Medium date with short time, as the prototype report header. */
export function fmtDateTime(iso: Maybe<string>): string {
  if (isMissing(iso)) return DASH;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? DASH : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export const COUNT_ORDER: Result[] = ['pass', 'warn', 'stop', 'skip'];

export interface CountSegment {
  result: Result;
  n: number;
  /** Zero counts are shown muted, not hidden. */
  muted: boolean;
  text: string;
}

/** Segments for `pass 12 · warn 1 · stop 0 · skip 8`. */
export function countSegments(counts: Maybe<Partial<Record<Result, number>>>, order: Result[] = COUNT_ORDER): CountSegment[] {
  return order.map((result) => {
    const n = counts?.[result] ?? 0;
    return { result, n, muted: n === 0, text: `${result} ${n}` };
  });
}

/** `pass 12 · warn 1 · stop 0 · skip 8`. */
export function fmtCounts(counts: Maybe<Partial<Record<Result, number>>>, order: Result[] = COUNT_ORDER): string {
  return countSegments(counts, order)
    .map((s) => s.text)
    .join(SEP);
}

/** Counts of check results in a list. */
export function tallyResults(items: { result: Result }[]): Partial<Record<Result, number>> {
  const out: Partial<Record<Result, number>> = {};
  for (const it of items) out[it.result] = (out[it.result] ?? 0) + 1;
  return out;
}

function fmtValue(v: number | string | boolean | null | undefined): string {
  if (isMissing(v)) return DASH;
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  return fmtNum(v);
}

/**
 * `pocket_distance <= 8` for a check whose threshold pairs with no measurement: the first
 * threshold in the number style the Thresholds list uses. Falls back to the adapter's
 * `threshold.value` string when the check carries no threshold list; null without either.
 */
export function thresholdText(check: Pick<UiCheck, 'thresholds' | 'threshold'>): string | null {
  const t = check.thresholds?.[0];
  if (t) return `${t.name} ${t.comparator} ${fmtValue(t.value)}`;
  return check.threshold ? `threshold ${check.threshold.value}` : null;
}

/**
 * `measured cmp threshold` for a check row when both exist (`undefined 1 == 0`).
 * Pairs them with pairMeasurement().
 * Returns null when the check has no measurement or no threshold.
 */
export function measuredVsThreshold(check: Pick<UiCheck, 'measurements' | 'thresholds'>): string | null {
  const pair = pairMeasurement(check);
  if (!pair) return null;
  const { m, t } = pair;
  const unit = m.unit ? `${THIN}${m.unit}` : '';
  return `${humanName(m.name)} ${fmtValue(m.value)}${unit} · ${limitWord(t.comparator)} ${fmtValue(t.value)}${unit}`;
}

/** `max_states` → `max states`: measurement names read as words. */
export function humanName(name: string): string {
  return name.replace(/_/g, ' ');
}

/** The comparator as a limit a reader understands: `<=` → `at most`, `==` → `must be`. */
export function limitWord(comparator: string): string {
  return ({ '<': 'below', '<=': 'at most', '>': 'above', '>=': 'at least', '==': 'must be', '!=': 'must not be', in: 'one of' } as Record<string, string>)[comparator] ?? comparator;
}

const sameKind = (a: unknown, b: unknown) => (typeof a === 'boolean') === (typeof b === 'boolean');

/**
 * The measurement a threshold applies to: the one the threshold names (`measurement`, set by the
 * check when the names differ), else the measurement with the threshold's own name. Names are
 * never matched by substring, so a row never shows a comparison the harness did not make.
 */
export function pairMeasurement(
  check: Pick<UiCheck, 'measurements' | 'thresholds'>,
): { m: NonNullable<UiCheck['measurements']>[number]; t: NonNullable<UiCheck['thresholds']>[number] } | null {
  const ms = check.measurements ?? [];
  const ts = check.thresholds ?? [];
  for (const t of ts) {
    const name = t.measurement ?? t.name;
    const m = ms.find((x) => x.name === name && sameKind(x.value, t.value));
    if (m) return { m, t };
  }
  return null;
}

/** Short run id for telling runs with the same label apart: the hex suffix of `<task>-<hex>` ids, otherwise the id. */
export function shortRunId(runId: string): string {
  const m = runId.match(/[-_]([0-9a-f]{6,})$/);
  return m ? m[1].slice(0, 6) : runId;
}

/** Labels that occur more than once in `items` (those rows get a shortRunId suffix). */
export function duplicateLabels<T>(items: readonly T[], label: (item: T) => string): Set<string> {
  const counts = new Map<string, number>();
  for (const it of items) counts.set(label(it), (counts.get(label(it)) ?? 0) + 1);
  return new Set([...counts].filter(([, n]) => n > 1).map(([k]) => k));
}

// ---------------------------------------------------------------- quantities (number alignment standard)
//
// One rule per quantity: fixed decimals and the unit printed after the value in muted text.
// Tables render these with the `num` utility (tabular figures, right aligned) and the `num-unit`
// utility for the unit (globals.css). Durations keep fmtMs (ms below 1 s, else s to one decimal).

export type Quantity = 'rmsd' | 'distance' | 'energy' | 'probability' | 'plddt' | 'pae' | 'count' | 'percent' | 'other';

export interface QuantityRule {
  /** Decimals; null keeps the value as recorded (float noise removed). */
  digits: number | null;
  /** Unit printed when the value carries none. */
  unit: string | null;
}

export const QUANTITY_RULES: Record<Quantity, QuantityRule> = {
  rmsd: { digits: 2, unit: 'Å' },
  distance: { digits: 2, unit: 'Å' },
  energy: { digits: 1, unit: 'kcal/mol' },
  probability: { digits: 2, unit: null },
  plddt: { digits: 1, unit: null },
  pae: { digits: 1, unit: 'Å' },
  count: { digits: 0, unit: null },
  percent: { digits: 0, unit: '%' },
  other: { digits: null, unit: null },
};

/** What a value measures, from its ToolOutput-like description (kind, unit, key, range). */
export function quantityOf(o: { kind?: string | null; unit?: string | null; key?: string | null; range?: [number, number] | null }): Quantity {
  const kind = (o.kind ?? '').toLowerCase();
  const unit = (o.unit ?? '').trim();
  const key = (o.key ?? '').toLowerCase();
  if (kind === 'rmsd' || /rmsd/.test(key)) return 'rmsd';
  if (kind === 'pae' || /(^|_)pae($|_)/.test(key)) return 'pae';
  if (unit === 'kcal/mol' || kind === 'affinity' || kind === 'energy') return 'energy';
  if (unit === '%') return 'percent';
  if (unit === 'Å') return 'distance';
  if (kind === 'count' || /(^|_)(n|count|clashes|contacts|passed|failed|outliers|torsions|unsatisfied)(_|$)|pbpassed|pbtotal/.test(key)) return 'count';
  if (kind === 'plddt' || /plddt/.test(key)) return o.range && o.range[1] <= 1 ? 'probability' : 'plddt';
  if ((kind === 'confidence' || kind === 'interface' || kind === 'probability') && (!o.range || o.range[1] <= 1)) return 'probability';
  return 'other';
}

/** Value and unit as separate strings (render the unit muted after the value). */
export function fmtQuantityParts(value: Maybe<number | string>, q: Quantity, unit?: string | null): { value: string; unit: string | null } {
  const rule = QUANTITY_RULES[q];
  const u = unit === undefined || unit === null || unit === '' ? rule.unit : unit;
  if (isMissing(value)) return { value: DASH, unit: null };
  if (typeof value !== 'number') return { value, unit: u };
  // a count that is not an integer is not a count: keep the recorded value
  const digits = q === 'count' && !Number.isInteger(value) ? null : rule.digits;
  return { value: fmtNum(value, null, digits ?? undefined), unit: u };
}

/** `2.13 Å`, `−6.1 kcal/mol`, `0.87`, `12`: the value with the quantity's decimals and unit. */
export function fmtQuantity(value: Maybe<number | string>, q: Quantity, unit?: string | null): string {
  const p = fmtQuantityParts(value, q, unit);
  return p.unit && p.value !== DASH ? `${p.value}${THIN}${p.unit}` : p.value;
}

/**
 * Splits a formatted `value unit` string (`−6.131 kcal/mol`, `2.1 Å`, `20/20`) into its value and
 * trailing unit. Strings without a numeric head come back whole as the value.
 */
export function splitUnit(text: Maybe<string>): { value: string; unit: string | null } {
  if (isMissing(text)) return { value: DASH, unit: null };
  const m = text.match(/^([−\-+]?[\d.,/]+(?:[eE][−\-+]?\d+)?)[\s  ]+([^\d\s][^\s]*)$/);
  return m ? { value: m[1], unit: m[2] } : { value: text, unit: null };
}

/**
 * The value a check row shows, numbers first: the measured value against its threshold when the
 * check pairs them, else up to three numeric measurements (those with units first, then counts),
 * else the first clause of the evidence text.
 */
export function checkValue(check: Pick<UiCheck, 'measurements' | 'thresholds' | 'evidence' | 'message'>): string {
  const cmp = measuredVsThreshold(check);
  if (cmp) return cmp;
  const nums = (check.measurements ?? []).filter((m) => typeof m.value === 'number' && Number.isFinite(m.value));
  if (nums.length) {
    const ranked = [...nums].sort((a, b) => Number(!!b.unit) - Number(!!a.unit));
    return ranked
      .slice(0, 3)
      .map((m) => `${humanName(m.name)} ${fmtValue(m.value)}${m.unit ? `${THIN}${m.unit}` : ''}`)
      .join(' · ');
  }
  return (check.evidence ?? check.message ?? '').split(' · ')[0];
}
