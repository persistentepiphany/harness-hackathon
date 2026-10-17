// Design tokens of the Harness web UI, as hex (anything that animates needs hex).
// Source: web/app/globals.css @theme and web/design/prototype/HANDOFF.md §3. Do not invent shades:
// the only values here that are not tokens are greys the components themselves hard-code, each
// marked with the component it comes from.

export const C = {
  canvas: '#F7F7F4',
  surface: '#FFFFFF',
  line: '#E6E6E1',
  line2: '#EFEFEB',
  line3: '#F3F3EF',
  ink: '#1A1A18',
  ink2: '#55554F',
  muted: '#8B8B85',
  faint: '#B9B9B3',
  accent: '#B07E2C',
  accentDeep: '#8E6420',
  accentTint: '#F6EEDC',
  accentSoft: '#FBF7EE',
  pass: '#3B8A58',
  passTint: '#E4F1E8',
  warn: '#C28A1A',
  warnTint: '#FAF0D9',
  stop: '#C4513B',
  stopTint: '#F9E5E0',
  reported: '#8B8B85',
  cofolding: '#B07E2C',
  docking: '#5B7FA6',
  seed: '#C9A86A',
  model: '#8B6FB5',
  // hard-coded in components
  track: '#ECECE8', // LayerProgress and TaskList progress track
  labelOff: '#C9C9C3', // LayerProgress label of a pending layer
  dashed: '#D7D7D2', // AddInput dashed border, idle log dot
  tabs: '#F1F1ED', // LogPanel Plain/Terminal switch background
} as const;

export const FONT = {
  sans: '"Geist", system-ui, sans-serif',
  mono: '"Geist Mono", ui-monospace, monospace',
} as const;

/** Thin space between a number and its unit (web/lib/format.ts THIN). */
export const THIN = ' ';
/** En dash for a missing value (web/lib/format.ts DASH). */
export const DASH = '–';

export type Result = 'pass' | 'warn' | 'stop' | 'skip' | 'reported' | 'pending';

/** StatusDot fill per result (web/components/ui/StatusDot.tsx). */
export const RESULT_COLOR: Record<Result, string> = {
  pass: C.pass,
  warn: C.warn,
  stop: C.stop,
  skip: C.faint,
  reported: C.reported,
  pending: C.faint,
};
