// Bars 45 to 50: one number traced to its check, tools and source (run ui-vina: finding
// L5_l5.controls.redocking.json, graph.json edge rcsb_files:3PTB -> check), then the closing line and
// the logo mark (web/app/icon.svg proportions: rounded square outline, accent inner square).

import { clamp01 } from '../../../kit/time';
import { ease, fadeUp, landWord } from '../anim';
import { CLOSE, scene } from '../cues';
import { checkById, measuredVsThreshold, run } from '../data';
import { C, FONT, THIN } from '../tokens';

const redock = checkById('l5.controls.redocking');
const th = redock.thresholds![0];
const src = run.sources.find((s) => s.sourceId === 'rcsb_files')!;
const v = run.toolVersions as Record<string, string>;

const NODES = [
  { label: 'value', main: `${redock.measurements![0].value}${THIN}Å`, sub: 'redocking control RMSD, top pose vina/seed0/mode0 against BEN in 3PTB', big: true },
  { label: 'check', main: redock.id, sub: `${measuredVsThreshold(redock)} · ${th.origin} · ${th.evidenceLevel}`, result: redock.result },
  { label: 'tools', main: `spyrmsd ${v.spyrmsd}`, sub: `numpy ${v.numpy} · rdkit ${v.rdkit} · gemmi ${v.gemmi}` },
  { label: 'source', main: `${src.source} · ${src.accession}.cif`, sub: `sha256 ${src.sha256.slice(0, 12)} · ${src.url?.replace('https://', '')}` },
];

const WORDS: { text: string; accent?: boolean }[][] = [
  [{ text: 'Every' }, { text: 'number' }, { text: 'traceable', accent: true }],
  [{ text: 'to a check,' }, { text: 'a tool' }, { text: 'and a source.' }],
];

function Trace({ t }: { t: number }) {
  if (t >= CLOSE.traceOut + 0.3) return null;
  const leave = clamp01((t - CLOSE.traceOut) / 0.25);
  return (
    <div style={{ position: 'absolute', left: 400, top: 250, width: 1120, opacity: 1 - leave, filter: leave > 0 ? `blur(${leave * 8}px)` : undefined, fontFamily: FONT.sans }}>
      {NODES.map((n, i) => {
        const at = CLOSE.nodes[i];
        const lineIn = i === 0 ? 1 : ease(t, at - 0.35, 0.35);
        return (
          <div key={n.label} style={{ position: 'relative', display: 'grid', gridTemplateColumns: '36px 120px minmax(0,1fr)', alignItems: 'baseline', columnGap: 18, padding: '18px 0' }}>
            {i > 0 ? <div style={{ position: 'absolute', left: 8, top: -32, width: 2, height: 62 * lineIn, background: C.line }} /> : null}
            <span style={{ position: 'relative', top: 4, width: 18, height: 18, borderRadius: '50%', background: i === 1 ? C.pass : i === 0 ? C.accent : C.ink2, opacity: clamp01((t - at) / 0.2) }} />
            <span style={{ fontSize: 20, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase', color: C.muted, ...fadeUp(t, at, 12) }}>{n.label}</span>
            <div style={fadeUp(t, at + 0.05, 12)}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 18, fontFamily: FONT.mono, fontSize: n.big ? 64 : 34, fontWeight: n.big ? 500 : 400, letterSpacing: n.big ? '-0.02em' : undefined, color: C.ink }}>
                {n.main}
                {n.result ? <span style={{ fontFamily: FONT.sans, fontSize: 22, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: C.pass }}>{n.result}</span> : null}
              </div>
              <div style={{ marginTop: 6, fontFamily: FONT.mono, fontSize: 21, color: C.muted, lineHeight: 1.4 }}>{n.sub}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Line({ t }: { t: number }) {
  if (t < CLOSE.words[0] - 0.05 || t >= CLOSE.lineOut + 0.3) return null;
  const leave = clamp01((t - CLOSE.lineOut) / 0.25);
  let k = 0;
  return (
    <div style={{ position: 'absolute', left: 0, right: 0, top: 470, translate: '0 -50%', display: 'grid', justifyItems: 'center', fontFamily: FONT.sans, fontSize: 104, fontWeight: 600, letterSpacing: '-0.025em', lineHeight: 1.1, color: C.ink, opacity: 1 - leave, filter: leave > 0 ? `blur(${leave * 10}px)` : undefined }}>
      {WORDS.map((line, row) => (
        <div key={row} style={{ display: 'flex', gap: '0.24em', whiteSpace: 'nowrap' }}>
          {line.map((w) => {
            const at = CLOSE.words[k++];
            return (
              <span key={w.text} style={{ display: 'inline-block', color: w.accent ? C.accent : undefined, ...landWord(t, at) }}>
                {w.text}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function Logo({ t }: { t: number }) {
  if (t < CLOSE.logo) return null;
  const size = 168;
  const draw = ease(t, CLOSE.logo, 0.7);
  const fill = ease(t, CLOSE.logo + 0.55, 0.35);
  const perimeter = 4 * 18 - (8 - 2 * Math.PI) * 4; // rounded square, side 18, radius 4 (icon.svg units)
  return (
    <div style={{ position: 'absolute', left: 0, right: 0, top: 455, translate: '0 -50%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 44 }}>
      <svg width={size} height={size} viewBox="0 0 32 32" style={{ overflow: 'visible' }}>
        <rect x={7} y={7} width={18} height={18} rx={4} fill="none" stroke={C.ink} strokeWidth={2.5} strokeDasharray={perimeter} strokeDashoffset={perimeter * (1 - draw)} />
        <rect x={12} y={12} width={8} height={8} rx={1.5} fill={C.accent} opacity={fill} transform={`translate(16 16) scale(${0.6 + 0.4 * fill}) translate(-16 -16)`} />
      </svg>
      <div style={{ ...fadeUp(t, CLOSE.wordmark, 14) }}>
        <div style={{ fontFamily: FONT.sans, fontSize: 116, fontWeight: 600, letterSpacing: '-0.03em', color: C.ink, lineHeight: 1 }}>Harness</div>
        <div style={{ marginTop: 14, fontFamily: FONT.sans, fontSize: 34, color: C.ink2 }}>Prediction Assurance Harness</div>
      </div>
    </div>
  );
}

export function Close({ t }: { t: number }) {
  const s = scene('close');
  if (t < s.from) return null;
  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <Trace t={t} />
      <Line t={t} />
      <Logo t={t} />
    </div>
  );
}
