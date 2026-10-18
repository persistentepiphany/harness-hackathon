// When each recorded log line of run ui-vina appears in the film. Lines up to the card-to-log cut
// keep their recorded timing (the job card replays the run at its real speed); the lines after the
// cut land one per beat, and the clock on screen still shows each line's recorded time.

import { CARD_CUT_REAL, LOG_SLOTS, RUN_T0 } from './cues';
import { layers, logLines, tallyFromLines, type LogLine, type Tally } from './data';

const after = logLines.map((l, i) => ({ l, i })).filter(({ l }) => l.sec > CARD_CUT_REAL);
if (after.length !== LOG_SLOTS.length) throw new Error(`log slots ${LOG_SLOTS.length} != lines after the cut ${after.length}`);

/** Film second at which each log line appears. */
export const lineAt: number[] = logLines.map((l) => (l.sec <= CARD_CUT_REAL ? RUN_T0 + l.sec : LOG_SLOTS[after.findIndex((a) => a.l === l)]));

export const linesBy = (t: number): LogLine[] => logLines.filter((_, i) => t >= lineAt[i]);

const endIdx = layers.map((L) => logLines.findIndex((x) => x.kind === 'layer' && x.layer === L.i && x.result !== null));
const startIdx = layers.map((L) => logLines.findIndex((x) => x.kind === 'layer' && x.layer === L.i && x.result === null));
const runEndIdx = logLines.findIndex((x) => x.kind === 'run' && x.text.startsWith('run  end'));

export const layerEndAt = endIdx.map((i) => lineAt[i]);
export const runEndAt = lineAt[runEndIdx];

export type LayerState = 'pending' | 'running' | 'done';
export function layerState(t: number, i: number): LayerState {
  if (t >= lineAt[endIdx[i]]) return 'done';
  if (t >= lineAt[startIdx[i]]) return 'running';
  return 'pending';
}

export function layerTally(t: number, i: number): Tally {
  return tallyFromLines(linesBy(t), i);
}

/** Share of the layer's checks reported so far (the job's `progress` within the layer). */
export function layerPct(t: number, i: number): number {
  const done = linesBy(t).filter((l) => l.kind === 'check' && l.layer === i).length;
  return Math.round((done / layers[i].checks.length) * 100);
}

export const checksDone = (t: number) => linesBy(t).filter((l) => l.kind === 'check').length;

/** Recorded elapsed seconds shown on screen at film time t. */
export function elapsedAt(t: number): number {
  if (t < RUN_T0) return 0;
  const cutAt = RUN_T0 + CARD_CUT_REAL;
  if (t < cutAt) return t - RUN_T0;
  let prevT = cutAt;
  let prevV = CARD_CUT_REAL;
  for (const { l } of after) {
    const at = LOG_SLOTS[after.findIndex((a) => a.l === l)];
    if (t < at) return prevV + ((t - prevT) / Math.max(1e-6, at - prevT)) * (l.sec - prevV);
    prevT = at;
    prevV = l.sec;
  }
  return 7.279; // jobs.json elapsedMs 7279
}

/** The layer that is running at t (or the last one). */
export function currentLayer(t: number): number {
  for (let i = 0; i < layers.length; i++) if (layerState(t, i) !== 'done') return i;
  return layers.length - 1;
}
