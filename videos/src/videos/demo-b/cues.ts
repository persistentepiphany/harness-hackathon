// Film B's beat sheet as data. Every moment is a bar and beat on the measured grid; scene code
// never holds a literal frame number or second.

import beats from './beats.json';
import peaks from './sfx-peaks.json';

export const DURATION = 120; // 50 bars at 100 BPM

const BEAT = beats.beatSeconds;
const BAR = 4 * BEAT;
// beats.json counts bars from the first full measured bar; film bar 1 opens at frame 0.
const FIRST_FILM_BAR = Math.round(beats.firstDownbeat / BAR) + 1;

/** Seconds at a film bar (1-based), beat (1-based) and fraction of a beat. Clamped at 0. */
export function B(bar: number, beat = 1, fraction = 0): number {
  const index = (bar - FIRST_FILM_BAR) * 4 + (beat - 1) + fraction;
  return Math.max(0, beats.firstDownbeat + index * BEAT);
}
export const beatSeconds = BEAT;
export const barSeconds = BAR;

// ------------------------------------------------------------------ scenes
export type SceneId = 'cold' | 'newRun' | 'jobCard' | 'jobLog' | 'verdict' | 'report' | 'ensemble' | 'agent' | 'close';
export const SCENES: { id: SceneId; from: number; to: number }[] = [
  { id: 'cold', from: 0, to: B(5) },
  { id: 'newRun', from: B(5), to: B(14) },
  { id: 'jobCard', from: B(14), to: B(16) },
  { id: 'jobLog', from: B(16), to: B(20) },
  { id: 'verdict', from: B(20), to: B(24) },
  { id: 'report', from: B(24), to: B(32) },
  { id: 'ensemble', from: B(32), to: B(38) },
  { id: 'agent', from: B(38), to: B(45) },
  { id: 'close', from: B(45), to: DURATION },
];
export const scene = (id: SceneId) => SCENES.find((s) => s.id === id)!;

// ------------------------------------------------------------------ cold open
export const COLD = {
  words: [B(1, 1, 0.15), B(1, 2), B(1, 3), B(1, 4), B(2, 1), B(2, 2)],
  sub: B(3, 1),
  out: B(4, 4, 0.5),
};

// ------------------------------------------------------------------ new run
export const PROMPT = 'Benzamidine pose in trypsin with Vina, 5 seeds at pH 7.4, against 3PTB';

/** Per-character reveal times: about 11 characters a second, a little longer after spaces and commas. */
export const TYPE_START = B(5, 2, 0.6);
export const charTimes: number[] = (() => {
  const out: number[] = [];
  let t = TYPE_START;
  for (let i = 0; i < PROMPT.length; i++) {
    out.push(t);
    const ch = PROMPT[i];
    const jitter = ((i * 37) % 7) / 7 - 0.5; // deterministic, -0.5..0.5
    t += 0.082 + jitter * 0.02 + (ch === ' ' ? 0.03 : 0) + (ch === ',' ? 0.12 : 0);
  }
  return out;
})();
export const TYPE_END = charTimes[charTimes.length - 1];

export const NEW_RUN = {
  in: B(5),
  clickPrompt: B(5, 2),
  sourcesPan: B(7, 4, 0.5),
  // entity rows resolve one per two beats: UniProt, RCSB PDB, AlphaFold DB, PubChem, PDB CCD
  sources: [B(8, 2), B(8, 4), B(9, 2), B(9, 4), B(10, 2)],
  backPan: B(10, 3, 0.5),
  clickQuick: B(11, 1),
  requestOk: B(11, 2),
  // eight interpreter steps, one per beat
  steps: [B(11, 3), B(11, 4), B(12, 1), B(12, 2), B(12, 3), B(12, 4), B(13, 1), B(13, 2)],
  checkDelay: 0.3, // spinner, then the dot and the reason (product CHECK_MS)
  done: B(13, 3),
  clickStart: B(13, 4),
};

// ------------------------------------------------------------------ the run
/** Run start on the job card; the card replays the run at its recorded speed. */
export const RUN_T0 = B(14);
/** Recorded elapsed seconds when the film cuts from the card to the job page. */
export const CARD_CUT_REAL = B(16) - RUN_T0;
/** Log lines after the cut land one per beat (slower than recorded); the clock shows recorded times. */
export const LOG_SLOTS = [B(16, 2), B(16, 3), B(16, 4), B(17, 1), B(17, 2), B(18, 1), B(18, 2), B(18, 3), B(18, 4), B(19, 1), B(19, 2), B(19, 3), B(19, 3), B(19, 4)];
export const VERDICT = { in: B(20), statement: B(20, 3), out: B(24) };

// ------------------------------------------------------------------ report
export const REPORT = {
  in: B(24),
  rowStep: BEAT / 2,
  pushRow: B(25),
  thresholds: B(25, 3),
  toPb: B(26, 4),
  pb: B(27),
  pbStep: BEAT / 4,
  toSeeds: B(28, 4),
  points: [B(29, 2), B(29, 3), B(29, 4), B(30, 1), B(30, 2)],
  stats: B(30, 3),
  pose: B(30, 4),
};

// ------------------------------------------------------------------ ensemble
export const ENSEMBLE = {
  in: B(32),
  cells: [B(32, 1, 0.2), B(32, 2), B(32, 3), B(32, 4), B(33, 1), B(33, 2), B(33, 3), B(33, 4)],
  readCells: B(33, 3),
  backToControls: B(34, 4) - 0.3,
  clickOverlay: B(35),
  push: B(35, 1, 0.2),
  pushIn: B(36, 3),
};

// ------------------------------------------------------------------ agent
export const AGENT = {
  in: B(38),
  steps: Array.from({ length: 13 }, (_, k) => B(38, 2) + 2 * k * BEAT),
  outcome: B(44, 3),
};

// ------------------------------------------------------------------ close
export const CLOSE = {
  nodes: [B(45, 1, 0.2), B(45, 3), B(46, 1), B(46, 3)],
  traceOut: B(46, 4, 0.6),
  words: [B(47), B(47, 2), B(47, 3), B(47, 4), B(48), B(48, 2)],
  lineOut: B(49) - 0.25,
  logo: B(49),
  wordmark: B(49, 3),
};

// ------------------------------------------------------------------ captions and provenance tags
export const CAPTIONS: { from: number; to: number; text: string }[] = [
  { from: B(5), to: B(8), text: 'Describe the run in one sentence.' },
  { from: B(8), to: B(11), text: 'Named proteins and ligands resolve to source records, each with a checksum.' },
  { from: B(11), to: B(14), text: 'Quick setup turns it into settings and says why it chose each one.' },
  { from: B(14), to: B(16), text: 'Six layers of checks run in order, from provenance to output support.' },
  { from: B(16), to: B(20), text: 'The log reports every check as it runs.' },
  { from: B(20), to: B(24), text: 'One check could not run, so the claim is not assessed yet.' },
  { from: B(24), to: B(27), text: 'Each check shows its measured value, the threshold and where it comes from.' },
  { from: B(27), to: B(29), text: 'PoseBusters: 20 of 20 tests pass on all five poses.' },
  { from: B(29), to: B(32), text: 'All five seeds sit within 0.08 Å of the medoid, 0.38 Å from the crystal pose.' },
  { from: B(32), to: B(35), text: 'Each pose in a cell, with its numbers.' },
  { from: B(35), to: B(38), text: 'Overlay: five seeds and the crystal ligand on one receptor.' },
  { from: B(38), to: B(42), text: 'Agentic tests: the monitor shows each step the agent takes.' },
  { from: B(42), to: B(45), text: 'The agent task shown here is the prototype’s demo data.' },
];

export const TAGS: { from: number; to: number; text: string }[] = [
  { from: B(5), to: B(14), text: 'live interpreter and source lookups · 17 Oct 2026' },
  { from: B(14), to: B(38), text: 'run ui-vina · AutoDock Vina 1.2.7 outputs supplied · 17 Oct 2026' },
  { from: B(38), to: B(45), text: 'prototype demo data · mock mode' },
  { from: B(45), to: B(47), text: 'run ui-vina' },
];

// ------------------------------------------------------------------ sound effects
export type SfxName = keyof typeof peaks;
export type SfxEvent = { at: number; name: SfxName; volume: number };

/** Sounds only on real on-screen events; `at` is the frame the transient must land on. */
export function sfxEvents(extra: { layerEnds: number[]; logEnds: number[] }): SfxEvent[] {
  const list: SfxEvent[] = [];
  const push = (at: number, name: SfxName, volume: number) => list.push({ at, name, volume });
  push(B(5), 'whoosh', 0.28);
  push(NEW_RUN.clickPrompt, 'click', 0.35);
  charTimes.forEach((at, i) => {
    if (PROMPT[i] !== ' ') push(at, (['key1', 'key2', 'key3'] as const)[i % 3], 0.1);
  });
  NEW_RUN.sources.forEach((at) => push(at + 0.25, 'tick', 0.16));
  push(NEW_RUN.clickQuick, 'click', 0.35);
  push(NEW_RUN.requestOk, 'tick', 0.14);
  NEW_RUN.steps.forEach((at) => push(at + NEW_RUN.checkDelay, 'tick', 0.14));
  push(NEW_RUN.clickStart, 'click', 0.35);
  extra.layerEnds.forEach((at) => push(at, 'tick', 0.2));
  extra.logEnds.forEach((at) => push(at, 'tick', 0.2));
  push(VERDICT.in, 'chime', 0.32);
  REPORT.points.forEach((at) => push(at, 'tick', 0.16));
  push(B(32), 'whoosh', 0.22);
  push(ENSEMBLE.clickOverlay, 'click', 0.35);
  AGENT.steps.forEach((at) => push(at, 'tick', 0.12));
  push(B(45), 'whoosh', 0.24);
  CLOSE.nodes.forEach((at) => push(at, 'tick', 0.18));
  push(CLOSE.logo + 0.6, 'chime', 0.26);
  return list.sort((a, b) => a.at - b.at);
}

export const sfxPeak = (name: SfxName) => peaks[name];
