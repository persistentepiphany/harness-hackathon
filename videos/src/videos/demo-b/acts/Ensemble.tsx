// Bars 32 to 37: /reports/ui-vina/ensemble. Twins of ensemble/Segmented and ensemble/StructureGrid
// cells (header, PyMOL render, footer numbers) with the run's real PyMOL renders; then the overlay
// view, shown as a screenshot of the running app (Mol* with the crystal and the five mode-0 poses
// on the reference receptor), because Mol* draws with WebGL on its own clock.

import { Img, staticFile } from 'remotion';

import type { CameraKey } from '../../../kit/camera';
import { cursorAt, UserCursor, type CursorKey } from '../../../kit/cursor';
import { fadeIn, fadeUp, swap } from '../anim';
import { ENSEMBLE, scene } from '../cues';
import { fmtNum, seeds } from '../data';
import { Stage, toScreen, viewAt } from '../ui/chrome';
import { Dot } from '../ui/primitives';
import { C, DASH, FONT, THIN } from '../tokens';

const X0 = 104;
const W = 1232;
const Y_CTRL = 136;
const Y_GRID = 186;
const CELL_W = (W - 3 * 14) / 4;
// The screenshot (2x) of the overlay view is 2464x1122 px: 1232x561 product px.
const OVERLAY = { w: 1232, h: 561 };

const CAM: CameraKey[] = [
  [scene('ensemble').from, 720, 368, 1.55],
  [ENSEMBLE.readCells, 560, 345, 2.1],
  [ENSEMBLE.backToControls, 600, 330, 1.62],
  [ENSEMBLE.push, 720, 466, 1.55],
  [ENSEMBLE.pushIn, 560, 520, 2.0],
];

const CURSOR: CursorKey[] = [
  { t: scene('ensemble').from, x: 1380, y: 640, world: true },
  { t: ENSEMBLE.backToControls, x: 900, y: 420, world: true },
  { t: ENSEMBLE.clickOverlay, x: 236, y: Y_CTRL + 13, world: true, click: true },
  { t: ENSEMBLE.clickOverlay + 1.0, x: 300, y: 290, world: true },
  { t: ENSEMBLE.clickOverlay + 3.0, x: 1500, y: 900, world: true },
];

type Cell = { id: string; label: string; kind: 'crystal' | 'medoid' | 'seed' | 'docking'; tool: string; img: string; rmsd: string; pb: string; lb: string; ub: string; score: string | null; note: string };

const seedCell = (i: number): Cell => {
  const s = seeds[i];
  return {
    id: s.pose,
    label: s.pose,
    kind: i === 0 ? 'medoid' : 'seed',
    tool: 'AutoDock Vina',
    img: `stills/seed${i}-overview.png`,
    rmsd: i === 0 ? DASH : `${fmtNum(s.rmsdToMedoid, 'Å', 1)} · c${s.cluster}`,
    pb: '20/20',
    lb: '0',
    ub: '0',
    score: `Vina score ${fmtNum(s.score, 'kcal/mol')}`,
    note: 'PyMOL render · placeholder mode',
  };
};

const CELLS: Cell[] = [
  { id: '3PTB', label: '3PTB', kind: 'crystal', tool: 'RCSB PDB file se…', img: 'stills/3ptb-overview.png', rmsd: `0.4${THIN}Å`, pb: DASH, lb: DASH, ub: DASH, score: DASH, note: 'PyMOL render · placeholder mode' },
  seedCell(0),
  seedCell(1),
  seedCell(2),
  seedCell(3),
  seedCell(4),
  { id: 'vina/seed0/mode1', label: 'vina/seed0/mode1', kind: 'docking', tool: 'AutoDock Vina', img: 'stills/seed0-mode1-overview.png', rmsd: DASH, pb: DASH, lb: DASH, ub: DASH, score: DASH, note: 'PyMOL render · viewer slots full' },
  { id: 'vina/seed0/mode2', label: 'vina/seed0/mode2', kind: 'docking', tool: 'AutoDock Vina', img: 'stills/seed0-mode2-overview.png', rmsd: DASH, pb: DASH, lb: DASH, ub: DASH, score: DASH, note: 'PyMOL render · viewer slots full' },
];

const KIND_COLOR = { crystal: C.ink, medoid: C.accent, seed: C.seed, docking: C.docking };

function Segmented({ label, options, value, disabled = [] }: { label: string; options: string[]; value: string; disabled?: string[] }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontFamily: FONT.mono, fontSize: 10.5, color: C.muted }}>{label}</span>
      <div style={{ display: 'inline-flex', overflow: 'hidden', borderRadius: 5, border: `1px solid ${C.line}` }}>
        {options.map((o, i) => {
          const on = o === value;
          return (
            <span key={o} style={{ padding: '4px 9px', fontFamily: FONT.mono, fontSize: 11.5, fontWeight: 500, borderLeft: i > 0 ? `1px solid ${C.line}` : undefined, background: on ? C.ink : 'transparent', color: on ? '#fff' : disabled.includes(o) ? C.faint : C.ink2 }}>
              {o}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function CellView({ c, t, at }: { c: Cell; t: number; at: number }) {
  const cols: [string, string][] = [
    ['RMSD', c.rmsd],
    ['PB', c.pb],
    ['rmsd_lb', c.lb],
    ['rmsd_ub', c.ub],
  ];
  return (
    <div style={{ overflow: 'hidden', borderRadius: 8, border: `1px solid ${c.kind === 'medoid' ? C.accent : C.line}`, background: C.surface, ...fadeUp(t, at) }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, borderBottom: `1px solid ${C.line2}`, padding: '8px 12px', fontFamily: FONT.mono, fontSize: 11.5 }}>
        <span style={{ display: 'flex', minWidth: 0, alignItems: 'center', gap: 7 }}>
          <Dot color={KIND_COLOR[c.kind]} size={6} />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.kind === 'medoid' ? `${c.label} · me…` : c.label}</span>
        </span>
        <span style={{ display: 'flex', flex: 'none', alignItems: 'center', gap: 6, color: C.muted }}>
          <span style={{ fontSize: 10.5 }}>{c.tool}</span>
          <Dot color={C.faint} size={7} hollow />
        </span>
      </div>
      <div style={{ position: 'relative', height: 210 }}>
        <Img src={staticFile(c.img)} style={{ position: 'absolute', left: '50%', top: 6, height: 198, translate: '-50% 0' }} />
        <span style={{ position: 'absolute', left: 14, bottom: 8, fontFamily: FONT.mono, fontSize: 10.5, color: C.muted }}>{c.note}</span>
      </div>
      <div style={{ borderTop: `1px solid ${C.line2}`, padding: '8px 12px 10px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
          {cols.map(([k, v]) => (
            <div key={k}>
              <div style={{ fontFamily: FONT.mono, fontSize: 9.5, color: C.muted }}>{k}</div>
              <div style={{ fontFamily: FONT.mono, fontSize: 11.5, color: v === DASH ? C.faint : C.ink }}>{v}</div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 4, fontFamily: FONT.mono, fontSize: 11, color: c.score === DASH ? C.faint : C.muted }}>{c.score}</div>
      </div>
    </div>
  );
}

export function Ensemble({ t }: { t: number }) {
  const s = scene('ensemble');
  if (t < s.from || t >= s.to) return null;
  const view = viewAt(t, CAM);
  const cursor = cursorAt(t, CURSOR, (x, y) => toScreen(view, x, y));
  const overlay = t >= ENSEMBLE.clickOverlay + 0.08;
  const gridOut = Math.min(1, Math.max(0, (t - ENSEMBLE.clickOverlay - 0.08) / 0.18));
  return (
    <div style={{ position: 'absolute', inset: 0, ...swap(t, s.from, s.to, 0.16, 0.12) }}>
      <Stage view={view} height={1400}>
        <div style={{ position: 'absolute', left: X0, top: 88, width: W, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>
            Ensemble
            <span style={{ marginLeft: 8, fontFamily: FONT.mono, fontSize: 13, fontWeight: 400, color: C.muted }}>55 structures · AutoDock Vina · 3PTB</span>
          </div>
          <span style={{ borderRadius: 6, border: `1px solid ${C.line}`, padding: '7px 12px', fontSize: 12.5, fontWeight: 500, lineHeight: 'normal' }}>Report</span>
        </div>
        <div style={{ position: 'absolute', left: X0, top: Y_CTRL, width: W, display: 'flex', flexWrap: 'wrap', alignItems: 'center', columnGap: 20 }}>
          <Segmented label="view" options={['grid', 'overlay']} value={overlay ? 'overlay' : 'grid'} />
          <Segmented label="colour" options={['by chain', 'by confidence', 'flagged']} value="by chain" disabled={overlay ? ['by chain', 'by confidence', 'flagged'] : []} />
          <Segmented label="sort" options={['record', 'confidence', 'RMSD', 'cluster']} value="record" />
          <span style={{ borderRadius: 5, border: `1px solid ${C.line}`, padding: '4px 9px', fontFamily: FONT.mono, fontSize: 11.5, fontWeight: 500, color: C.ink2 }}>PoseBusters failures only</span>
        </div>
        {gridOut < 1 ? (
          <div style={{ position: 'absolute', left: X0, top: Y_GRID, width: W, display: 'grid', gridTemplateColumns: `repeat(4, ${CELL_W}px)`, gap: 14, opacity: 1 - gridOut }}>
            {CELLS.map((c, i) => (
              <CellView key={c.id} c={c} t={t} at={ENSEMBLE.cells[i]} />
            ))}
          </div>
        ) : null}
        {overlay ? (
          <div style={{ position: 'absolute', left: X0, top: Y_GRID, width: OVERLAY.w, height: OVERLAY.h, ...fadeIn(t, ENSEMBLE.clickOverlay + 0.12, 0.3) }}>
            <Img src={staticFile('stills/molstar-overlay.png')} style={{ width: OVERLAY.w, height: OVERLAY.h }} />
            <div style={{ marginTop: 10, fontSize: 11, color: C.muted }}>
              Fig. 7 · Overlay of 55 structures on the reference receptor; docking poses show the ligand only, co-folding models are superposed on the first chain by Cα.
            </div>
          </div>
        ) : null}
      </Stage>
      <UserCursor {...cursor} />
    </div>
  );
}
