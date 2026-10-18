// Bars 14 and 15: /jobs. Twin of jobs/JobCard and jobs/LayerProgress. The first card replays run
// ui-vina at its recorded speed (log-vina.json timestamps); the card under it is run ui-faulty from
// the same Jobs list (jobs.json, ui-record-faulty.json).

import type { CameraKey } from '../../../kit/camera';
import { swap } from '../anim';
import { scene } from '../cues';
import { fmtSeconds, inputsLine, layers, run, segmentCounts, tallyOf, toolLabel, totalChecks, worst, type Tally } from '../data';
import { checksDone, currentLayer, elapsedAt, layerPct, layerState, layerTally, type LayerState } from '../runtime';
import { Stage, viewAt } from '../ui/chrome';
import { Button, Dot } from '../ui/primitives';
import { C, FONT, THIN } from '../tokens';

const CAM: CameraKey[] = [
  [scene('jobCard').from, 720, 318, 1.78],
  [scene('jobCard').from + 0.5, 716, 300, 1.86],
];

type Segment = { name: string; state: LayerState; pct: number; tally: Tally };

function segColor(s: Segment): string {
  if (s.state !== 'done') return C.accent;
  const w = worst(s.tally);
  return w === 'stop' ? C.stop : w === 'warn' ? C.warn : w === 'skip' ? C.faint : C.ink;
}

export function LayerProgress({ segments }: { segments: Segment[] }) {
  return (
    <div style={{ marginTop: 2, display: 'grid', gridTemplateColumns: 'repeat(6, minmax(0,1fr))', gap: 3 }}>
      {segments.map((s) => {
        const counts = s.state === 'done' ? segmentCounts(s.tally) : { text: '', muted: false };
        const active = s.state !== 'pending';
        return (
          <div key={s.name}>
            <div style={{ height: 3, overflow: 'hidden', borderRadius: 2, background: C.track }}>
              <div style={{ height: '100%', width: `${s.state === 'done' ? 100 : s.state === 'running' ? s.pct : 0}%`, background: segColor(s) }} />
            </div>
            <div style={{ marginTop: 5, display: 'flex', justifyContent: 'space-between', gap: 6, fontSize: 10.5, color: active ? C.ink2 : C.labelOff }}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name}</span>
              <span style={{ flex: 'none', fontFamily: FONT.mono, color: counts.muted ? C.faint : undefined }}>{counts.text}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CardBody({ num, name, task, models, inputs, claim, segments, right }: { num: string; name: string; task: string; models: string; inputs: string; claim: string; segments: Segment[]; right: React.ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '44px minmax(0,1fr) 180px', alignItems: 'start', gap: 24, borderTop: `1px solid ${C.line}`, padding: '22px 0 24px' }}>
      <div style={{ paddingTop: 3, fontFamily: FONT.mono, fontSize: 12, color: C.muted }}>{num}</div>
      <div style={{ display: 'flex', minWidth: 0, flexDirection: 'column', gap: 14 }}>
        <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: '-0.01em' }}>{name}</div>
        <div style={{ display: 'grid', gridTemplateColumns: '72px minmax(0,1fr)', columnGap: 16, rowGap: 5, fontSize: 12.5 }}>
          <span style={{ color: C.muted }}>Task</span>
          <span>{task}</span>
          <span style={{ color: C.muted }}>Models</span>
          <span>{models}</span>
          <span style={{ color: C.muted }}>Inputs</span>
          <span style={{ fontFamily: FONT.mono, fontSize: 12 }}>{inputs}</span>
          <span style={{ color: C.muted }}>Claim</span>
          <span>{claim}</span>
        </div>
        <LayerProgress segments={segments} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, paddingTop: 2 }}>{right}</div>
    </div>
  );
}

export function JobsPage({ t, live }: { t: number; live: boolean }) {
  const running = live && layerState(t, 5) !== 'done';
  const segments: Segment[] = layers.map((L, i) => ({ name: L.name, state: layerState(t, i), pct: layerPct(t, i), tally: layerTally(t, i) }));
  const e = elapsedAt(t);
  const cur = currentLayer(t);
  const other = run.otherJob;
  const otherSegs: Segment[] = other.layers.map((L) => ({ name: L.name, state: 'done', pct: 100, tally: tallyOf(L.counts) }));
  return (
    <div style={{ position: 'absolute', left: 244, top: 88, width: 952 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <span style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>Jobs</span>
          <span style={{ fontSize: 13, color: C.muted }}>{running ? '1 running · 0 queued · 11 done' : '0 running · 0 queued · 12 done'}</span>
        </div>
        <Button variant="secondary" style={{ color: C.ink }}>
          New run
        </Button>
      </div>
      <CardBody
        num="12"
        name={run.job.name}
        task={run.taskName}
        models={toolLabel}
        inputs={inputsLine}
        claim={run.claim}
        segments={segments}
        right={
          <>
            <span style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, fontWeight: 500 }}>
              <Dot color={C.accent} pulseAt={t} />
              {`${layers[cur].name.toLowerCase()} · ${e.toFixed(1)}s`}
            </span>
            <span style={{ fontFamily: FONT.mono, fontSize: 12, color: C.ink2 }}>{fmtSeconds(e * 1000)}</span>
            <span style={{ textAlign: 'right', fontSize: 11.5, color: C.muted }}>{`${checksDone(t)} of ${totalChecks} checks`}</span>
            <span style={{ fontFamily: FONT.mono, fontSize: 10.5, color: C.faint }}>{run.id}</span>
          </>
        }
      />
      <CardBody
        num="11"
        name={other.name}
        task={other.taskName}
        models={other.tools.join(', ')}
        inputs={`${other.inputs.target} · ${other.inputs.reference}`}
        claim={other.claim}
        segments={otherSegs}
        right={
          <>
            <span style={{ fontSize: 14, fontWeight: 600, color: C.stop }}>Refused</span>
            <span style={{ fontFamily: FONT.mono, fontSize: 12, color: C.ink2 }}>{`${((other.elapsedMs ?? 0) / 1000).toFixed(1)}${THIN}s`}</span>
            <span style={{ textAlign: 'right', fontSize: 11.5, color: C.muted }}>39 checks · 0 warn · 1 stop</span>
            <span style={{ marginTop: -4, textAlign: 'right', fontSize: 11.5, color: C.faint }}>36 skip</span>
            <span style={{ fontFamily: FONT.mono, fontSize: 10.5, color: C.faint }}>{other.id}</span>
          </>
        }
      />
    </div>
  );
}

export function JobCard({ t }: { t: number }) {
  const s = scene('jobCard');
  if (t < s.from || t >= s.to) return null;
  const view = viewAt(t, CAM);
  return (
    <div style={{ position: 'absolute', inset: 0, ...swap(t, s.from, s.to, 0.16, 0.001) }}>
      <Stage view={view}>
        <JobsPage t={t} live />
      </Stage>
    </div>
  );
}
