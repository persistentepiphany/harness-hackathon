// Bars 20 to 23: /reports/ui-vina header. Twin of report/ReportPicker and report/VerdictHeader:
// the verdict scoped to the claim, the run metadata and the harness's own verdict statement.

import type { CameraKey } from '../../../kit/camera';
import { fadeIn, fadeUp, landWord, swap } from '../anim';
import { B, scene, VERDICT } from '../cues';
import { run, toolLabel } from '../data';
import { Stage, viewAt } from '../ui/chrome';
import { Button, Meta } from '../ui/primitives';
import { C, FONT } from '../tokens';

const CAM: CameraKey[] = [
  [scene('verdict').from, 470, 182, 2.55],
  [B(21, 2), 535, 300, 1.7],
  [B(23, 4), 540, 306, 1.74],
];

const PICKER = [
  { name: 'trypsin · benzamidine', id: 'ui-vina' },
  { name: 'trypsin · benzamidine', id: 'ui-faulty' },
  { name: 'trypsin · benzamidine', id: 'ui-3ptb' },
  { name: 'Trypsin · ligand pose', id: '' },
];

export function ReportHeader({ t, revealAt = -1, statementAt = -1 }: { t: number; revealAt?: number; statementAt?: number }) {
  const v = run.verdict;
  return (
    <div style={{ position: 'absolute', left: 104, top: 88, width: 1232 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', columnGap: 20, rowGap: 8, marginBottom: 6, fontSize: 13 }}>
            {PICKER.map((p, i) => (
              <span key={p.id || p.name} style={{ paddingBottom: 6, borderBottom: `1.5px solid ${i === 0 ? C.ink : 'transparent'}`, color: i === 0 ? C.ink : C.muted, fontWeight: i === 0 ? 500 : 400 }}>
                {p.name}
                {p.id ? <span style={{ marginLeft: 6, fontFamily: FONT.mono, fontSize: 11, color: C.faint }}>{p.id}</span> : null}
              </span>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 20, fontSize: 13, color: C.muted, marginBottom: 32 }}>
            <span>example 3ptb_faulty_inputs · ligand pose in a known pocket</span>
            <span style={{ fontFamily: FONT.mono, fontSize: 11.5 }}>all jobs (12)</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 12 }}>
            <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.015em', color: C.ink2, display: 'inline-block', ...landWord(t, revealAt, 10) }}>Incomplete</span>
            <span style={{ fontSize: 15, display: 'inline-block', ...landWord(t, revealAt + 0.15, 10) }}>{`“${v.claim}”`}</span>
          </div>
          <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(150px, max-content))', columnGap: 32, rowGap: 10, fontSize: 12.5, ...fadeIn(t, revealAt + 0.5, 0.4) }}>
            <Meta label="Task">{run.taskName}</Meta>
            <Meta label="Models">{`${toolLabel} (outputs supplied)`}</Meta>
            <Meta label="Inputs" mono>{`${run.inputs.target} · ${run.inputs.reference}`}</Meta>
            <Meta label="Sampling">{`${run.inputs.seeds} seeds`}</Meta>
            <Meta label="Run" mono>
              {run.id}
            </Meta>
            <Meta label="Completed">Oct 17, 2026, 5:12 PM</Meta>
            <Meta label="Scope" mono>
              {(v as { scope?: string }).scope ?? ''}
            </Meta>
          </div>
        </div>
        <div style={{ display: 'flex', flex: 'none', gap: 8 }}>
          <Button variant="secondary" style={{ color: C.ink }}>
            Ensemble
          </Button>
          <Button>Document</Button>
          <Button variant="secondary" style={{ color: C.ink }}>
            JSON
          </Button>
        </div>
      </div>
      <p style={{ margin: '12px 0 0', maxWidth: 880, fontSize: 12.5, color: C.ink2, ...fadeUp(t, statementAt) }}>{v.statement}</p>
    </div>
  );
}

export function Verdict({ t }: { t: number }) {
  const s = scene('verdict');
  if (t < s.from || t >= s.to) return null;
  const view = viewAt(t, CAM);
  return (
    <div style={{ position: 'absolute', inset: 0, ...swap(t, s.from, s.to, 0.16, 0.12) }}>
      <Stage view={view}>
        <ReportHeader t={t} revealAt={VERDICT.in + 0.05} statementAt={VERDICT.statement} />
      </Stage>
    </div>
  );
}
