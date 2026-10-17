// PAE matrix shape read from stats.pae (not in docs/UI.md yet; absent means not computed).

import type { UiRunRecord } from '@/lib/types';

export interface PaeData {
  /** Square matrix of predicted aligned error in Å, row = aligned token, column = scored token. */
  matrix: number[][];
  /** Block read for the verdict, half-open token ranges. */
  block?: { rows: [number, number]; cols: [number, number] };
  /** Text beside the heatmap. */
  lines?: string[];
  /** Colour scale maximum in Å (default 30). */
  max?: number;
}

export function paeFromStats(record: UiRunRecord): PaeData | null {
  const p = record.stats.pae as Partial<PaeData> | undefined;
  if (!p || !Array.isArray(p.matrix) || !p.matrix.length || !p.matrix.every((row) => Array.isArray(row))) return null;
  return { matrix: p.matrix, block: p.block, lines: Array.isArray(p.lines) ? p.lines : undefined, max: typeof p.max === 'number' ? p.max : undefined };
}

const mix = (a: number[], b: number[], t: number) => a.map((x, k) => Math.round(x + (b[k] - x) * t));
const LOW = [47, 107, 79];
const MID = [185, 215, 195];
const HIGH = [246, 246, 243];

/** Prototype colour scale: dark green (0 Å) → light green → off-white (max). */
export function paeColor(v: number, max = 30): string {
  const t = Math.min(1, Math.max(0, v / max));
  const c = t < 0.5 ? mix(LOW, MID, t * 2) : mix(MID, HIGH, (t - 0.5) * 2);
  return `rgb(${c.join(',')})`;
}
