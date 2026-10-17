import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { B, CAPTIONS, CLOSE, COLD } from '../src/videos/demo-b/cues';

/**
 * Film B's subtitles: the burned-in captions plus the opening question and the closing line,
 * on the same cue times as the film.
 *
 *   bun scripts/srt.ts [out dir]   (default out/demo-b)
 */
const out = resolve(process.argv[2] ?? join(import.meta.dirname, '..', 'out', 'demo-b'));
mkdirSync(out, { recursive: true });

const lines = [
  { from: COLD.words[0], to: COLD.sub, text: 'Does this prediction support the claim?' },
  { from: COLD.sub, to: COLD.out + 0.3, text: 'Harness checks co-folding and docking results, layer by layer.' },
  ...CAPTIONS,
  { from: CLOSE.words[0], to: CLOSE.lineOut + 0.25, text: 'Every number traceable to a check, a tool and a source.' },
  { from: CLOSE.logo + 0.6, to: B(51) - 0.05, text: 'Harness. Prediction Assurance Harness.' },
];

const stamp = (s: number) => {
  const ms = Math.round(s * 1000);
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const sec = Math.floor((ms % 60000) / 1000);
  const rest = ms % 1000;
  const p = (n: number, w = 2) => String(n).padStart(w, '0');
  return `${p(h)}:${p(m)}:${p(sec)},${p(rest, 3)}`;
};

const body = lines.map((l, i) => `${i + 1}\n${stamp(l.from)} --> ${stamp(Math.min(l.to, 120))}\n${l.text}\n`).join('\n');
writeFileSync(join(out, 'demo-b.srt'), body);
console.log(`${join(out, 'demo-b.srt')}: ${lines.length} cues`);
