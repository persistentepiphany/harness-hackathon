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
  return `${m.name} ${fmtValue(m.value)}${unit} ${t.comparator} ${fmtValue(t.value)}${unit}`;
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
