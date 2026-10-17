// Bars 38 to 44: /agent in mock mode. Twins of agent/TaskList, agent/TaskDetail and
// agent/StepTimeline, streaming the prototype's demo task agent_02 (web/lib/mock/data.ts
// AGENT_TASKS). Mock mode starts agent_01 as done, agent_02 running and agent_03 queued; the film
// streams agent_02 from its first step. Its values are demo data, and the tag says so.

import type { CameraKey } from '../../../kit/camera';
import { fadeIn, fadeUp, swap } from '../anim';
import { AGENT, scene } from '../cues';
import { agentTasks, fmtMs } from '../data';
import { Stage, viewAt } from '../ui/chrome';
import { Dot, Ring } from '../ui/primitives';
import { C, FONT } from '../tokens';

const ZOOM = 1.6;
const VIEW_TOP = 58;
const VIEW_H = 874 / ZOOM;
const CAM: CameraKey[] = [[scene('agent').from, 720, VIEW_TOP + VIEW_H / 2, ZOOM]];
const BOX_TOP = 88;
const BOX_H = VIEW_TOP + VIEW_H - BOX_TOP - 10;

type Kind = 'thought' | 'tool' | 'result' | 'report' | 'conclusion';
const KIND: Record<Kind, { label: string; marker: React.CSSProperties; text: React.CSSProperties }> = {
  thought: { label: C.muted, marker: { borderRadius: '50%', borderColor: C.muted, background: 'transparent' }, text: { fontFamily: FONT.sans, fontSize: 13, color: C.ink2 } },
  tool: { label: C.docking, marker: { borderRadius: 2, borderColor: C.docking, background: C.docking }, text: { fontFamily: FONT.mono, fontSize: 12, color: C.ink } },
  result: { label: C.ink2, marker: { borderRadius: 2, borderColor: C.ink2, background: C.ink2 }, text: { fontFamily: FONT.mono, fontSize: 12, color: C.ink } },
  report: { label: C.accent, marker: { borderRadius: '50%', borderColor: C.accent, background: C.accent }, text: { fontFamily: FONT.mono, fontSize: 12, color: C.ink } },
  conclusion: { label: C.ink, marker: { borderRadius: '50%', borderColor: C.ink, background: C.ink }, text: { fontFamily: FONT.sans, fontSize: 14, fontWeight: 500, color: C.ink } },
};

const RUN_ID = /run_\d{8}_[0-9a-f]+/;

const task = agentTasks.find((x) => x.id === 'agent_02')!;
const offsets = task.steps.reduce<number[]>((acc, s, i) => [...acc, i === 0 ? 0 : acc[i - 1] + task.steps[i - 1].ms], []);
const ends = task.steps.map((s, i) => offsets[i] + s.ms);
const total = ends[ends.length - 1];

function TaskCard({ goal, status, pct, steps, elapsed, selected }: { goal: string; status: 'done' | 'running' | 'queued'; pct: number; steps: string; elapsed: string; selected?: boolean }) {
  const statusColor = status === 'done' ? C.pass : C.ink2;
  const dot = status === 'done' ? C.pass : status === 'running' ? C.accent : C.faint;
  const bar = status === 'done' ? C.pass : C.accent;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, borderRadius: 8, border: `1px solid ${selected ? C.ink : C.line}`, background: selected ? C.surface : 'transparent', padding: '12px 14px', lineHeight: 'normal' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: C.ink, lineHeight: 1.3 }}>{goal}</span>
        <span style={{ display: 'flex', flex: 'none', alignItems: 'center', gap: 6, fontFamily: FONT.mono, fontSize: 11, color: statusColor }}>
          <Dot color={dot} size={6} />
          {status === 'done' ? 'completed' : status}
        </span>
      </div>
      <div style={{ height: 3, width: '100%', overflow: 'hidden', borderRadius: 2, background: C.track }}>
        <div style={{ height: '100%', width: `${pct}%`, background: bar }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: FONT.mono, fontSize: 10.5, color: C.muted }}>
        <span>{steps}</span>
        <span>{elapsed}</span>
      </div>
    </div>
  );
}

export function Agent({ t }: { t: number }) {
  const s = scene('agent');
  if (t < s.from || t >= s.to) return null;
  const view = viewAt(t, CAM);
  const revealed = AGENT.steps.filter((at) => t >= at).length;
  const done = revealed === task.steps.length && t >= AGENT.outcome;
  // elapsed ticks from one step's end to the next one's while the task runs
  const k = revealed;
  const prevAt = k === 0 ? s.from : AGENT.steps[k - 1];
  const nextAt = k < AGENT.steps.length ? AGENT.steps[k] : prevAt + 1;
  const prevMs = k === 0 ? 0 : ends[k - 1];
  const nextMs = k < ends.length ? ends[k] : total;
  const elapsed = done ? total : prevMs + (nextMs - prevMs) * Math.min(1, Math.max(0, (t - prevAt) / Math.max(0.01, nextAt - prevAt)));
  const shown = task.steps.slice(0, revealed);
  const tools = shown.filter((x) => x.kind === 'tool').length;
  const reports = shown.filter((x) => x.kind === 'report').length;
  const runs = new Set(shown.map((x) => x.text.match(RUN_ID)?.[0]).filter(Boolean)).size;
  const last = shown[shown.length - 1];
  const pending = done ? null : last?.kind === 'tool' ? 'waiting for result' : last?.kind === 'conclusion' ? 'finishing' : 'thinking';
  const t01 = agentTasks[0];
  const t03 = agentTasks[2];
  const t01Total = t01.steps.reduce((a, x) => a + x.ms, 0);
  return (
    <div style={{ position: 'absolute', inset: 0, ...swap(t, s.from, s.to, 0.16, 0.12) }}>
      <Stage view={view}>
        <div style={{ position: 'absolute', left: 144, top: 88, width: 340, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ marginBottom: 6, fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>
            Agent
            <span style={{ marginLeft: 8, fontSize: 13, fontWeight: 400, color: C.muted }}>{done ? '0 running · 2 completed' : '1 running · 1 completed'}</span>
          </div>
          <TaskCard goal={t01.goal} status="done" pct={100} steps={`${t01.steps.length}/${t01.steps.length} steps · ${t01.outcome.runs} runs`} elapsed={`${(t01Total / 1000).toFixed(0)} s`} />
          <TaskCard
            goal={task.goal}
            status={done ? 'done' : 'running'}
            pct={Math.round((elapsed / total) * 100)}
            steps={`${revealed}/${task.steps.length} steps${runs || done ? ` · ${done ? task.outcome.runs : runs} runs` : ''}`}
            elapsed={`${(elapsed / 1000).toFixed(0)} s`}
            selected
          />
          <TaskCard goal={t03.goal} status="queued" pct={0} steps={`0/${t03.steps.length} steps`} elapsed="0 s" />
        </div>
        <div style={{ position: 'absolute', left: 524, top: BOX_TOP, width: 772, height: BOX_H }}>
          {/* Bottom-anchored once the steps outgrow the view, as the page follows new steps. */}
          <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, minHeight: '100%', display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.01em' }}>{task.goal}</div>
              <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 16, fontFamily: FONT.mono, fontSize: 11.5, color: C.muted }}>
                <span>{task.id}</span>
                <span>{`${revealed}/${task.steps.length} steps`}</span>
                <span>{`${tools} tool calls`}</span>
                <span>{`${reports} reports read`}</span>
                <span>{`${(elapsed / 1000).toFixed(1)} s`}</span>
              </div>
            </div>
            {done ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 14, borderTop: `1px solid ${C.ink}`, paddingTop: 12, ...fadeUp(t, AGENT.outcome) }}>
                <span style={{ fontSize: 14, fontWeight: 600, color: C.pass }}>{task.outcome.label}</span>
                <span style={{ fontFamily: FONT.mono, fontSize: 12, color: C.ink2 }}>{task.outcome.detail}</span>
              </div>
            ) : null}
            <div style={{ marginLeft: 6, display: 'flex', flexDirection: 'column', borderLeft: `1px solid ${C.line}` }}>
              {shown.map((st, i) => {
                const kind = KIND[st.kind as Kind];
                const at = AGENT.steps[i];
                const open = Math.min(1, Math.max(0, (t - at) / 0.25));
                const runId = st.text.match(RUN_ID)?.[0];
                return (
                  <div key={i} style={{ overflow: 'hidden', maxHeight: open * 160 }}>
                    <div style={{ marginLeft: -6, display: 'grid', gridTemplateColumns: '24px 60px minmax(0,1fr)', alignItems: 'baseline', columnGap: 12, padding: '9px 0', ...fadeUp(t, at) }}>
                      <span style={{ position: 'relative', top: 2, width: 11, height: 11, border: '1.5px solid', boxSizing: 'border-box', ...kind.marker }} />
                      <span style={{ fontFamily: FONT.mono, fontSize: 10.5, color: C.muted }}>{`${(offsets[i] / 1000).toFixed(1)}s`}</span>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ marginBottom: 2, fontSize: 10.5, letterSpacing: '0.06em', textTransform: 'uppercase', color: kind.label }}>
                          {st.kind}
                          <span style={{ marginLeft: 8, fontFamily: FONT.mono, letterSpacing: 'normal', textTransform: 'none', color: C.faint }}>{fmtMs(st.ms)}</span>
                        </div>
                        <div style={{ lineHeight: 1.55, overflowWrap: 'anywhere', ...kind.text }}>{st.text}</div>
                        {runId ? (
                          <div style={{ marginTop: 4, display: 'flex', gap: 8, fontFamily: FONT.mono, fontSize: 10.5, color: C.muted }}>
                            <span>{runId}</span>
                            <span style={{ color: C.docking, textDecoration: 'underline', textDecorationColor: C.line, textUnderlineOffset: 2 }}>job</span>
                            <span style={{ color: C.docking, textDecoration: 'underline', textDecorationColor: C.line, textUnderlineOffset: 2 }}>report</span>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                );
              })}
              {pending ? (
                <div style={{ marginLeft: -6, display: 'grid', gridTemplateColumns: '24px 60px minmax(0,1fr)', alignItems: 'baseline', columnGap: 12, padding: '9px 0', ...fadeIn(t, s.from + 0.2) }}>
                  <Ring t={t} size={11} style={{ position: 'relative', top: 2 }} />
                  <span />
                  <span style={{ fontSize: 12, color: C.faint }}>{pending}</span>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </Stage>
    </div>
  );
}
