// Bars 16 to 19: /jobs/ui-vina. Twins of jobs/RunHeader, jobs/LayerStrip, jobs/LogPanel (Plain) and
// jobs/ExecutorList. The log body is 400 px tall, the height LogPanel takes in a 700 px window
// (min(620px, 100vh - 300px)).

import type { CameraKey } from '../../../kit/camera';
import { fadeIn, fadeUp, swap } from '../anim';
import { B, scene } from '../cues';
import { fmtMs, fmtSeconds, layers, logLines, run, toolLabel, totalChecks, totals, worst } from '../data';
import { checksDone, currentLayer, elapsedAt, layerPct, layerState, layerTally, lineAt, linesBy, runEndAt } from '../runtime';
import { Stage, viewAt } from '../ui/chrome';
import { Dot, Eyebrow, Meta } from '../ui/primitives';
import { C, FONT, RESULT_COLOR, THIN, type Result } from '../tokens';

const LOG_TOP = 437;
const LOG_H = 400;

const CAM: CameraKey[] = [
  [scene('jobLog').from, 716, 598, 1.7],
  [B(17, 1, 0.5), 455, 700, 2.15],
  [B(18, 1), 716, 598, 1.7],
  [B(19, 1), 716, 680, 1.7],
];

function lineView(kind: string, result: Result | null) {
  const dot = result ? RESULT_COLOR[result] : kind === 'fetch' ? C.accent : C.dashed;
  const color = kind === 'layer' ? C.ink : result === 'stop' ? C.stop : result === 'warn' ? C.accentDeep : C.ink2;
  return { dot, color, weight: kind === 'layer' ? 500 : 400 };
}

function LogPanel({ t }: { t: number }) {
  const shown = linesBy(t);
  const done = t >= runEndAt;
  const header = done ? `finished · ${fmtSeconds(7279)}` : (shown[shown.length - 1]?.text ?? '');
  const stats = { pass: 0, warn: 0, stop: 0, skip: 0 } as Record<string, number>;
  for (const l of shown) if (l.kind === 'check' && l.result && l.result in stats) stats[l.result]++;
  return (
    <div style={{ position: 'relative', height: LOG_H, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRadius: 8, border: `1px solid ${C.line}`, background: C.surface }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, borderBottom: `1px solid ${C.line2}`, padding: '10px 12px 10px 14px' }}>
        <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: FONT.mono, fontSize: 12, color: C.faint }}>{header}</span>
        <div style={{ display: 'flex', flex: 'none', gap: 2, borderRadius: 5, padding: 2, background: C.tabs }}>
          <span style={{ borderRadius: 4, padding: '3px 9px', fontSize: 11, fontWeight: 500, background: C.surface, color: C.ink }}>Plain</span>
          <span style={{ borderRadius: 4, padding: '3px 9px', fontSize: 11, fontWeight: 500, color: C.muted }}>Terminal</span>
        </div>
      </div>
      <div style={{ position: 'relative', flex: 1, overflow: 'hidden' }}>
        {/* Bottom-anchored like the product's stick-to-bottom scroll; a new line opens its row over
            0.2 s so older lines slide up instead of jumping. */}
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: '10px 14px', display: 'flex', flexDirection: 'column' }}>
          {shown.map((l) => {
            const v = lineView(l.kind, (l.result as Result | null) ?? null);
            const at = lineAt[logLines.indexOf(l)];
            const open = Math.min(1, Math.max(0, (t - at) / 0.2));
            return (
              <div key={l.seq} style={{ flex: 'none', overflow: 'hidden', maxHeight: open * 90 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '44px 14px minmax(0,1fr)', gap: 10, padding: '4px 0', fontSize: 12.5, lineHeight: 1.6, ...fadeIn(t, at) }}>
                  <span style={{ color: C.faint }}>{l.t}</span>
                  <span style={{ position: 'relative', top: 6, width: 6, height: 6, borderRadius: '50%', background: v.dot }} />
                  <span style={{ color: v.color, fontWeight: v.weight, overflowWrap: 'anywhere' }}>{l.plain}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 14, borderTop: `1px solid ${C.line2}`, padding: '9px 14px', fontFamily: FONT.mono, fontSize: 11, color: C.faint, background: C.surface }}>
        <span style={{ color: '#6FBF8A' }}>{stats.pass} pass</span>
        <span style={{ color: '#E3B45A' }}>{stats.warn} warn</span>
        <span style={{ color: '#E8826E' }}>{stats.stop} stop</span>
        {stats.skip > 0 ? <span>{stats.skip} skip</span> : null}
        <span style={{ marginLeft: 'auto' }}>0 fetched · {checksDone(t)} checks</span>
      </div>
    </div>
  );
}

function LayerStrip({ t }: { t: number }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, minmax(0,1fr))', gap: 6 }}>
      {layers.map((L, i) => {
        const st = layerState(t, i);
        const tally = layerTally(t, i);
        const bar = st === 'done' ? RESULT_COLOR[worst(tally)] : st === 'running' ? C.accent : C.line;
        const value = st === 'done' ? fmtMs(L.durationMs) : st === 'running' ? `${layerPct(t, i)}%` : '–';
        const tone = st === 'done' ? C.ink : st === 'running' ? C.accent : C.faint;
        return (
          <div key={L.key} style={{ borderTop: `2px solid ${bar}`, paddingTop: 8 }}>
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12, color: st === 'pending' ? C.faint : C.ink }}>{L.name}</div>
            <div style={{ marginTop: 3, fontFamily: FONT.mono, fontSize: 12, color: tone }}>{value}</div>
            <div style={{ marginTop: 2, minHeight: 15, fontFamily: FONT.mono, fontSize: 10.5, color: C.muted }}>
              {st === 'done' ? (
                <>
                  {`${tally.pass}${tally.warn ? ` · ${tally.warn}w` : ''}${tally.stop ? ` · ${tally.stop}s` : ''}`}
                  {tally.skip ? <span style={{ color: C.faint }}>{` · ${tally.skip} skip`}</span> : null}
                </>
              ) : st === 'running' ? (
                L.summary[0]
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function JobLog({ t }: { t: number }) {
  const s = scene('jobLog');
  if (t < s.from || t >= s.to) return null;
  const view = viewAt(t, CAM);
  const done = t >= runEndAt;
  const e = elapsedAt(t);
  const v = run.verdict;
  return (
    <div style={{ position: 'absolute', inset: 0, ...swap(t, s.from, s.to, 0.16, 0.001) }}>
      <Stage view={view}>
        <div style={{ position: 'absolute', left: 164, top: 88, width: 1112 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
            <div>
              <div style={{ marginBottom: 8, fontSize: 12, color: C.muted }}>← All jobs</div>
              <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>{run.job.name}</div>
              <div style={{ marginTop: 12, display: 'grid', rowGap: 8, fontSize: 12.5 }}>
                <Meta label="Task">{run.taskName}</Meta>
                <Meta label="Models">{toolLabel}</Meta>
                <Meta label="Sampling">{`${run.inputs.seeds} seeds`}</Meta>
                <Meta label="Run" mono>
                  {run.id}
                </Meta>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontFamily: FONT.mono, fontSize: 30, lineHeight: 1, fontWeight: 500, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>{fmtSeconds(e * 1000)}</div>
              <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 7, fontSize: 12, color: done ? C.pass : C.ink2 }}>
                <Dot color={done ? C.pass : C.accent} pulseAt={done ? undefined : t} />
                {done ? `complete · ${totalChecks} checks` : `${layers[currentLayer(t)].name.toLowerCase()} · ${layerPct(t, currentLayer(t))}%`}
              </div>
              {done ? <div style={{ marginTop: 10, display: 'inline-block', borderRadius: 6, background: C.ink, color: '#fff', padding: '7px 12px', fontSize: 12.5, lineHeight: 'normal', fontWeight: 500, ...fadeUp(t, runEndAt) }}>Open report</div> : null}
            </div>
          </div>
        </div>
        <div style={{ position: 'absolute', left: 164, top: 344, width: 1112 }}>
          <LayerStrip t={t} />
        </div>
        <div style={{ position: 'absolute', left: 164, top: LOG_TOP, width: 720 }}>
          <LogPanel t={t} />
        </div>
        <div style={{ position: 'absolute', left: 916, top: LOG_TOP, width: 360 }}>
          <Eyebrow style={{ paddingBottom: 10, borderBottom: `1px solid ${C.line2}` }}>Executors</Eyebrow>
          <div style={{ display: 'grid', gridTemplateColumns: '14px minmax(0,1fr)', gap: 12, padding: '12px 0' }}>
            <Dot color={C.pass} size={8} style={{ marginTop: 5 }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 500 }}>{toolLabel}</div>
              <div style={{ fontSize: 12.5, color: C.ink2 }}>version {run.tools[0].version}</div>
              <div style={{ marginTop: 8, display: 'grid', rowGap: 3 }}>
                {run.docking.map((p) => (
                  <div key={p.label} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, fontSize: 11.5 }}>
                    <span style={{ color: C.muted }}>{p.label}</span>
                    <span style={{ fontFamily: FONT.mono }}>
                      {p.value}
                      {p.unit ? `${THIN}${p.unit}` : ''}
                      {p.isDefault ? <span style={{ marginLeft: 4, fontFamily: FONT.sans, color: C.faint }}>default</span> : null}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <Eyebrow style={{ marginTop: 22, marginBottom: 10 }}>Inputs</Eyebrow>
          <div style={{ fontFamily: FONT.mono, fontSize: 12, lineHeight: 1.75 }}>
            <div>{`${run.inputs.target} · ${run.inputs.reference} · pH ${run.inputs.ph}`}</div>
            <div>{`${run.inputs.seeds} seeds`}</div>
            <div>{run.inputs.ligand}</div>
          </div>
          {done ? (
            <div style={{ marginTop: 22, paddingTop: 16, borderTop: `1px solid ${C.line}`, ...fadeUp(t, runEndAt) }}>
              <div style={{ fontSize: 18, fontWeight: 600, color: C.ink2 }}>Incomplete</div>
              <div style={{ marginTop: 2, fontSize: 13 }}>{`“${v.claim}”`}</div>
              <div style={{ marginTop: 6, fontFamily: FONT.mono, fontSize: 12, color: C.muted }}>
                {`${totals.pass} pass · ${totals.warn} warn · ${totals.stop} stop · `}
                <span style={{ color: C.faint }}>{`${totals.skip} skip`}</span>
              </div>
            </div>
          ) : null}
        </div>
      </Stage>
    </div>
  );
}
