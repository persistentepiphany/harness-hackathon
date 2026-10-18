// Bars 24 to 31: report highlights for run ui-vina. Twins of report/LayerSidebar, report/CheckTable
// (CheckRow), report/MetricsTable, report/ReportLists ThresholdsTable, report/PoseBustersGrid,
// report/figures/SeedSpread and the POSE stat card. Every string is the record's own.

import type { CameraKey } from '../../../kit/camera';
import { fadeIn, fadeUp, swap } from '../anim';
import { REPORT, scene } from '../cues';
import { checkById, fmtMs, fmtNum, layers, measuredVsThreshold, pairwise, pose, posebusters, seeds } from '../data';
import { DEBUG_VIEW, Stage, viewAt } from '../ui/chrome';
import { Dot, Eyebrow, ResultDot, SectionTitle } from '../ui/primitives';
import { C, FONT, RESULT_COLOR, THIN, type Result } from '../tokens';

const COL_X = 374;
const COL_W = 962;
const Y_CHECKS = 88;

// Measured with `stills.ts --debug` (DEBUG_VIEW prints world coordinates): redocking row 505..594,
// lists 637..927, PoseBusters 976..1151, figures 1198..1507.
const CAM: CameraKey[] = [
  [scene('report').from, 720, 330, 1.5],
  [scene('report').from + 2 * REPORT.rowStep, 865, 356, 1.82],
  [REPORT.pushRow, 868, 549, 2.05],
  [REPORT.thresholds - 0.25, 855, 790, 1.86],
  [REPORT.toPb, 855, 1070, 1.95],
  [REPORT.toSeeds, 855, 1352, 1.88],
]

const L5 = layers[5];

function Sidebar({ t }: { t: number }) {
  const items: { name: string; summary: string; dot: Result }[] = [
    { name: 'Provenance', summary: '7 objects · 7 cached · 3 checks', dot: 'pass' },
    { name: 'Input integrity', summary: '10 checks · 1 warn', dot: 'warn' },
    { name: 'Input adequacy', summary: '8 checks · 2 warn', dot: 'warn' },
    { name: 'Applicability', summary: '6 checks', dot: 'pass' },
    { name: 'Output validity', summary: '7 checks', dot: 'pass' },
    { name: 'Output support', summary: '5 checks', dot: 'pass' },
  ];
  return (
    <div style={{ position: 'absolute', left: 104, top: Y_CHECKS, width: 230, ...fadeIn(t, scene('report').from) }}>
      <Eyebrow style={{ marginBottom: 14 }}>Layers</Eyebrow>
      <div style={{ borderLeft: `1px solid ${C.line}` }}>
        {items.map((it, i) => (
          <div key={it.name} style={{ position: 'relative', padding: '8px 0 8px 14px', marginLeft: i === 5 ? -1 : 0, borderLeft: i === 5 ? `2px solid ${C.ink}` : undefined }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: i === 5 ? 600 : 500, color: C.ink }}>{it.name}</span>
              <Dot color={RESULT_COLOR[it.dot]} size={6} />
            </div>
            <div style={{ marginTop: 3, fontFamily: FONT.mono, fontSize: 10.5, color: C.muted }}>{it.summary}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CheckRow({ id, t, at }: { id: string; t: number; at: number }) {
  const c = checkById(id);
  const cmp = measuredVsThreshold(c);
  const meta = [c.tool, c.gate].filter(Boolean).join(' · ');
  return (
    <div data-target={`row-${id}`} style={{ display: 'grid', gridTemplateColumns: '12px minmax(0,1.2fr) minmax(0,1fr) 150px 56px', alignItems: 'baseline', gap: 14, padding: '10px 0', borderBottom: `1px solid ${C.line2}`, ...fadeUp(t, at) }}>
      <ResultDot result={c.result as Result} size={8} />
      <span style={{ fontSize: 13 }}>{c.name}</span>
      <span style={{ fontFamily: FONT.mono, fontSize: 11.5, color: C.ink2 }}>
        {c.evidence}
        {cmp ? <span style={{ display: 'block', color: C.muted }}>{cmp}</span> : c.threshold ? <span style={{ display: 'block', color: C.muted }}>threshold {c.threshold.value}</span> : null}
      </span>
      <span style={{ minWidth: 0, fontFamily: FONT.mono, fontSize: 10.5, color: C.muted }}>
        <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.id}</span>
        <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{[meta, c.ms === null || c.ms === undefined ? null : fmtMs(c.ms)].filter(Boolean).join(' · ')}</span>
      </span>
      <span style={{ textAlign: 'right', fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: RESULT_COLOR[c.result as Result] }}>{c.result}</span>
    </div>
  );
}

function Lists({ t }: { t: number }) {
  const at = REPORT.thresholds;
  const metrics = [
    { name: 'RMSD lower bound to best mode', tool: 'AutoDock Vina', value: '0' },
    { name: 'RMSD upper bound to best mode', tool: 'AutoDock Vina', value: '0' },
  ];
  const ths = L5.checks.flatMap((c) => (c.thresholds ?? []).slice(0, 1).map((th) => ({ id: c.id, ...th })));
  return (
    <div data-target="lists" style={{ marginTop: 44, display: 'grid', gridTemplateColumns: '461px 461px', columnGap: 40 }}>
      <div style={fadeUp(t, at)}>
        <Eyebrow style={{ paddingBottom: 8, borderBottom: `1px solid ${C.line}` }}>Confidence · interface metrics</Eyebrow>
        {metrics.map((m) => (
          <div key={m.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: `1px solid ${C.line2}`, fontSize: 12.5 }}>
            <span>
              {m.name} <span style={{ fontSize: 11, color: C.muted }}>{m.tool}</span>
            </span>
            <span style={{ fontFamily: FONT.mono }}>{m.value}</span>
          </div>
        ))}
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderTop: `1px solid ${C.accent}`, borderBottom: `1px solid ${C.accent}`, marginTop: 4, fontSize: 12.5 }}>
          <span>
            Vina score <span style={{ fontSize: 11, color: C.muted }}>AutoDock Vina</span>
          </span>
          <span style={{ fontFamily: FONT.mono, color: C.accentDeep }}>{fmtNum(seeds[0].score, 'kcal/mol')}</span>
        </div>
        <div style={{ marginTop: 8, fontSize: 11, color: C.muted }}>Values below the rule are ranking scores, read on their own line.</div>
      </div>
      <div style={fadeUp(t, at + 0.15)}>
        <Eyebrow style={{ paddingBottom: 8, borderBottom: `1px solid ${C.line}` }}>Thresholds · origin</Eyebrow>
        {ths.map((th) => {
          const soft = /borrowed|suspected|uncalibrated/i.test(th.evidenceLevel);
          return (
            <div key={th.id} data-target={`th-${th.id}`} style={{ padding: '7px 0', borderBottom: `1px solid ${C.line2}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontFamily: FONT.mono, fontSize: 12 }}>
                <span>{`${th.id} · ${th.name}`}</span>
                <span style={{ fontSize: 11, color: soft ? C.accentDeep : C.pass }}>{th.evidenceLevel}</span>
              </div>
              <div style={{ marginTop: 2, fontFamily: FONT.mono, fontSize: 11, color: C.muted }}>{`${th.comparator} ${fmtNum(th.value as number)} · ${th.origin}`}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PoseBusters({ t }: { t: number }) {
  const passed = posebusters.filter((p) => p.pass).length;
  return (
    <div data-target="pb" style={{ marginTop: 48, ...fadeIn(t, REPORT.pb - 0.3) }}>
      <SectionTitle note={`${passed}/${posebusters.length} tests · vina/seed0/mode0`}>Physical validity · PoseBusters</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0,1fr))', columnGap: 16, rowGap: 4, borderTop: `1px solid ${C.line}`, paddingTop: 8 }}>
        {posebusters.map((p, i) => {
          const at = REPORT.pb + i * REPORT.pbStep;
          return (
            <div key={p.test} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '4px 0', fontFamily: FONT.mono, fontSize: 11, ...fadeIn(t, at, 0.2) }}>
              <span style={{ display: 'flex', minWidth: 0, alignItems: 'center', gap: 7, color: C.ink2 }}>
                <Dot color={p.pass ? C.pass : C.stop} size={6} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.test}</span>
              </span>
              <span style={{ flex: 'none', color: C.muted }}>{p.value}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// SeedSpread geometry (selectors/report.ts seedSpreadPoints): viewBox 360x170, x 0..8 Å over 40..350,
// y = the seeds' Vina score range padded by 10 %, cut line at 2 Å.
const SEED_X_MAX = 8;
const xOf = (v: number) => 40 + (Math.min(SEED_X_MAX, Math.max(0, v)) / SEED_X_MAX) * 310;
const scores = seeds.map((s) => s.score);
const sMin = Math.min(...scores) - (Math.max(...scores) - Math.min(...scores)) * 0.1;
const sMax = Math.max(...scores) + (Math.max(...scores) - Math.min(...scores)) * 0.1;
const yOf = (c: number) => 128 - ((c - sMin) / (sMax - sMin)) * 108;
const SVG_TEXT = { fontSize: 8.5, fill: C.muted, fontFamily: FONT.mono } as const;

function SeedSpread({ t }: { t: number }) {
  const band = { x: xOf(pairwise.iqr[0]), w: Math.max(2, xOf(pairwise.iqr[1]) - xOf(pairwise.iqr[0])) };
  const cut = xOf(2);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 150px', alignItems: 'start', gap: 20 }}>
      <svg viewBox="0 0 360 170" style={{ display: 'block', width: '100%', height: 'auto' }}>
        <line x1={40} y1={130} x2={350} y2={130} stroke={C.line} />
        <rect x={band.x} y={124} width={band.w} height={12} fill={C.accentTint} />
        <line x1={cut} y1={14} x2={cut} y2={130} stroke={C.warn} strokeDasharray="3 3" />
        <text x={cut} y={10} {...SVG_TEXT} fill={C.warn} textAnchor="middle">
          {`2${THIN}Å`}
        </text>
        {seeds.map((s, i) => {
          const at = REPORT.points[i];
          const u = Math.min(1, Math.max(0, (t - at) / 0.3));
          return (
            <g key={s.pose} opacity={u}>
              <circle cx={xOf(s.rmsdToMedoid)} cy={yOf(s.score) + (1 - u) * 5} r={5.5} fill={s.rmsdToMedoid < 2 ? C.pass : C.warn} stroke="#fff" strokeWidth={1.5} />
              <text x={xOf(s.rmsdToMedoid)} y={yOf(s.score) + 15} {...SVG_TEXT} fontSize={8} textAnchor="middle">{`s${s.seed}`}</text>
            </g>
          );
        })}
        <text x={40} y={150} {...SVG_TEXT}>
          0
        </text>
        <text x={350} y={150} {...SVG_TEXT} textAnchor="end">
          {`8${THIN}Å RMSD to medoid`}
        </text>
        <text x={12} y={75} {...SVG_TEXT} textAnchor="middle" transform="rotate(-90 12 75)">
          Vina score (kcal/mol), ranking only
        </text>
        <text x={36} y={22} {...SVG_TEXT} textAnchor="end">
          {fmtNum(sMax, undefined, 1)}
        </text>
        <text x={36} y={128} {...SVG_TEXT} textAnchor="end">
          {fmtNum(sMin, undefined, 1)}
        </text>
      </svg>
      <div style={{ fontFamily: FONT.mono, fontSize: 11.5, lineHeight: 1.9, color: C.ink2, ...fadeIn(t, REPORT.stats) }}>
        <div>median {fmtNum(pairwise.median, 'Å', 2)}</div>
        <div>
          IQR {fmtNum(pairwise.iqr[0], undefined, 2)}–{fmtNum(pairwise.iqr[1], undefined, 2)}
        </div>
        <div>n = {pairwise.n}</div>
      </div>
    </div>
  );
}

function Figures({ t }: { t: number }) {
  const tabs = ['PAE', 'Interactions', 'Seeds', 'Agreement', 'Calibration', 'Gates by layer', 'Seed spread', 'Posebusters grid'];
  const rows: [string, string][] = [
    ['medoid', pose['medoid']],
    ['RMSD to crystal', pose['RMSD to crystal']],
    ['clusters', pose['clusters']],
    ['largest cluster', pose['largest cluster']],
    ['within 2 Å of medoid', pose['within 2 Å of medoid']],
    ['best sampled RMSD to crystal', pose['best sampled RMSD to crystal']],
    ['PoseBusters', pose['PoseBusters']],
    ['redocking control RMSD', pose['redocking control RMSD']],
  ];
  return (
    <div data-target="fig" style={{ marginTop: 48, ...fadeIn(t, REPORT.toSeeds - 0.2) }}>
      <div style={{ display: 'flex', gap: 18, borderBottom: `1px solid ${C.line}`, marginBottom: 16, fontSize: 13 }}>
        {tabs.map((tab) => (
          <span key={tab} style={{ padding: '0 0 9px', borderBottom: `1.5px solid ${tab === 'Seeds' ? C.ink : 'transparent'}`, marginBottom: -1, color: tab === 'Seeds' ? C.ink : C.muted, fontWeight: tab === 'Seeds' ? 500 : 400 }}>
            {tab}
          </span>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '640px 1fr', columnGap: 36 }}>
        <div>
          <SeedSpread t={t} />
          <div style={{ marginTop: 10, fontSize: 11, color: C.muted }}>
            Fig. 3 · Seed spread, RMSD to the medoid against Vina score (kcal/mol), ranking only; shaded band is the IQR of pairwise RMSD. Source: l5.sampling.clusters · spyrmsd 0.9.0.
          </div>
        </div>
        <div style={fadeUp(t, REPORT.pose)}>
          <Eyebrow style={{ paddingTop: 8, paddingBottom: 8, borderTop: `1px solid ${C.ink}` }}>Pose</Eyebrow>
          {rows.map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: '3px 0', fontSize: 12.5 }}>
              <span>{k}</span>
              <span style={{ fontFamily: FONT.mono }}>{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function Report({ t, debug }: { t: number; debug?: boolean }) {
  const s = scene('report');
  if (t < s.from || t >= s.to) return null;
  const view = debug ? DEBUG_VIEW : viewAt(t, CAM);
  return (
    <div style={{ position: 'absolute', inset: 0, ...swap(t, s.from, s.to, 0.16, 0.12) }}>
      <Stage view={view} height={1600}>
        <Sidebar t={t} />
        <div style={{ position: 'absolute', left: COL_X, top: Y_CHECKS, width: COL_W }}>
          <SectionTitle note={fmtMs(L5.durationMs)} style={{ marginBottom: 6 }}>
            {L5.name}
          </SectionTitle>
          <div style={{ borderTop: `1px solid ${C.line}` }}>
            {L5.checks.map((c, i) => (
              <CheckRow key={c.id} id={c.id} t={t} at={s.from + 0.1 + i * REPORT.rowStep} />
            ))}
          </div>
          <Lists t={t} />
          <PoseBusters t={t} />
          <Figures t={t} />
        </div>
      </Stage>
    </div>
  );
}

