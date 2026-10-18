import { clamp01 } from '../../../kit/time';
import { landWord } from '../anim';
import { COLD } from '../cues';
import { C, FONT } from '../tokens';

const LINES = [
  ['Does', 'this', 'prediction'],
  ['support', 'the', 'claim?'],
];

/** Bars 1 to 4: the question, then one line on what the harness does. Nothing else on the canvas. */
export function ColdOpen({ t }: { t: number }) {
  if (t >= COLD.out + 0.3) return null;
  const leave = clamp01((t - COLD.out) / 0.25);
  let k = 0;
  return (
    <div style={{ position: 'absolute', inset: 0, opacity: 1 - leave, filter: leave > 0 ? `blur(${leave * 10}px)` : undefined, fontFamily: FONT.sans }}>
      <div style={{ position: 'absolute', left: 0, right: 0, top: 452, translate: '0 -50%', display: 'grid', justifyItems: 'center', fontSize: 118, fontWeight: 600, letterSpacing: '-0.025em', lineHeight: 1.08, color: C.ink }}>
        {LINES.map((line, row) => (
          <div key={row} style={{ display: 'flex', gap: '0.24em', whiteSpace: 'nowrap' }}>
            {line.map((word) => {
              const at = COLD.words[k++];
              return (
                <span key={word} style={{ ...landWord(t, at), color: word === 'claim?' ? C.accent : undefined }}>
                  {word}
                </span>
              );
            })}
          </div>
        ))}
      </div>
      <div style={{ position: 'absolute', left: 0, right: 0, top: 700, textAlign: 'center', fontSize: 40, fontWeight: 400, letterSpacing: '-0.01em', color: C.ink2, ...landWord(t, COLD.sub, 14) }}>
        Harness checks co-folding and docking results, layer by layer.
      </div>
    </div>
  );
}
