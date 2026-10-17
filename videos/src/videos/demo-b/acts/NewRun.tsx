// Bars 5 to 13: /runs/new. Twins of run/PromptBox, run/SourcesPanel and run/DecisionStream, laid out
// as the live page at 1440x900 (positions measured from a 2x screenshot of the running app).
// Values: the prompt's real interpreter output (POST /ui/interpret) and real source lookups
// (GET /ui/entities), both captured from `pah serve` on 2026-10-17.

import type { CameraKey } from '../../../kit/camera';
import { cursorAt, UserCursor, type CursorKey } from '../../../kit/cursor';
import { fadeIn, fadeUp, swap } from '../anim';
import { charTimes, NEW_RUN, PROMPT, scene, TYPE_END } from '../cues';
import { decisionRows, entityGroups, requestSummary } from '../data';
import { Stage, toScreen, viewAt } from '../ui/chrome';
import { Button, Eyebrow, OkDot, Ring } from '../ui/primitives';
import { C, FONT, THIN } from '../tokens';

const SAMPLES = [
  'Dock imatinib into the ABL1 kinase pocket with Boltz-2 and Gnina',
  'Does KRAS interact with RAF1?',
  'Rank the imatinib congeneric series against ABL1 by Boltz-2 affinity',
  'Screen the erlotinib library against EGFR with Vina and DiffDock-L',
  'Protein–protein dock KRAS with RAF1 using pyDock and HADDOCK',
];

const CAM: CameraKey[] = [
  [scene('newRun').from, 520, 262, 1.74],
  [NEW_RUN.clickPrompt - 0.3, 490, 226, 1.98],
  [NEW_RUN.sourcesPan, 1126, 290, 2.2],
  [NEW_RUN.sources[2] - 0.3, 1126, 420, 2.2],
  [NEW_RUN.sources[3] - 0.3, 1126, 540, 2.2],
  [NEW_RUN.backPan, 478, 320, 1.95],
  [NEW_RUN.steps[1] - 0.3, 478, 400, 1.95],
  [NEW_RUN.steps[3] - 0.3, 478, 470, 1.95],
  [NEW_RUN.steps[5] - 0.3, 478, 540, 1.95],
  [NEW_RUN.steps[7] - 0.3, 478, 600, 1.95],
  [NEW_RUN.done - 0.2, 478, 630, 1.95],
];

const CURSOR: CursorKey[] = [
  { t: scene('newRun').from, x: 760, y: 330, world: true },
  { t: NEW_RUN.clickPrompt, x: 862, y: 220, world: true, click: true },
  { t: NEW_RUN.clickPrompt + 0.9, x: 968, y: 236, world: true },
  { t: NEW_RUN.clickQuick, x: 880, y: 364, world: true, click: true },
  { t: NEW_RUN.clickQuick + 0.9, x: 640, y: 392, world: true },
  { t: NEW_RUN.clickStart, x: 258, y: 744, world: true, click: true },
];

const sourceTimes = (() => {
  // flatten groups into items in order; each item resolves at its cue
  const out: number[][] = [];
  let k = 0;
  const titles = Array.from(new Set(entityGroups.map((g) => g.title)));
  for (const title of titles) {
    const items = entityGroups.filter((g) => g.title === title);
    out.push(items.map(() => NEW_RUN.sources[k++]));
  }
  return out;
})();

function PromptBox({ t }: { t: number }) {
  const typed = charTimes.filter((c) => t >= c).length;
  const focused = t >= NEW_RUN.clickPrompt && t < NEW_RUN.clickQuick;
  const typing = t >= charTimes[0] - 0.2 && t <= TYPE_END + 0.25;
  const caretOn = focused && (typing || Math.floor((t - NEW_RUN.clickPrompt) / 0.53) % 2 === 0);
  return (
    <div>
      <div
        style={{
          minHeight: 92,
          boxSizing: 'border-box',
          borderRadius: 8,
          border: `1px solid ${focused ? C.accent : C.line}`,
          background: C.surface,
          padding: '14px 16px',
          fontSize: 15,
          lineHeight: 1.5,
          color: typed ? C.ink : '#757575',
          height: 97,
        }}
      >
        {typed ? PROMPT.slice(0, typed) : !focused ? 'Dock imatinib into the ABL1 pocket with Boltz-2, 5 seeds, compare against 1IEP' : null}
        <span style={{ display: 'inline-block', width: 1.5, height: 19, marginLeft: 1, translate: '0 4px', background: C.ink, opacity: caretOn ? 1 : 0 }} />
      </div>
      <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', columnGap: 14, rowGap: 14 }}>
        {SAMPLES.map((p) => (
          <span key={p} style={{ fontSize: 12, lineHeight: 'normal', color: C.muted, whiteSpace: 'nowrap' }}>
            {p}
          </span>
        ))}
      </div>
      <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <Button variant="secondary">Manual setup</Button>
        <Button disabled={typed === 0} pressed={press(t, NEW_RUN.clickQuick)}>
          Quick setup
        </Button>
      </div>
    </div>
  );
}

/** 0..1..0 over 0.16 s after a click: the press of the button under the cursor. */
const press = (t: number, at: number) => (t >= at && t < at + 0.16 ? Math.sin((Math.PI * (t - at)) / 0.16) : 0);

function DecisionStream({ t }: { t: number }) {
  if (t < NEW_RUN.clickQuick) return null;
  const rows: { label: string; value: string; because?: string; at: number; okAt: number }[] = [
    { label: 'Request', value: requestSummary, at: NEW_RUN.clickQuick + 0.05, okAt: NEW_RUN.requestOk },
    ...decisionRows.map((r, i) => ({ ...r, at: NEW_RUN.steps[i], okAt: NEW_RUN.steps[i] + NEW_RUN.checkDelay })),
  ];
  return (
    <div style={{ marginTop: 24, marginLeft: 6, display: 'flex', flexDirection: 'column', borderLeft: `1px solid ${C.line}`, paddingLeft: 18 }}>
      {rows.map((r) => {
        if (t < r.at) return null;
        const ok = t >= r.okAt;
        return (
          <div key={r.label} style={{ display: 'grid', gridTemplateColumns: '14px 92px minmax(0,1fr)', alignItems: 'baseline', gap: 12, padding: '7px 0', ...fadeUp(t, r.at) }}>
            {ok ? <OkDot size={10} style={{ position: 'relative', top: 2 }} /> : <Ring t={t} size={10} style={{ position: 'relative', top: 2 }} />}
            <span style={{ fontSize: 12, color: C.muted }}>{r.label}</span>
            <span style={{ fontSize: 13.5, color: ok || r.label !== 'Request' ? (ok ? C.ink : C.muted) : C.muted, overflowWrap: 'anywhere' }}>
              {r.label === 'Request' && !ok ? 'Reading' : r.value}
              {ok && r.because ? <span style={fadeIn(t, r.okAt, 0.2)}>{'  —  '}{r.because}</span> : null}
            </span>
          </div>
        );
      })}
      {t >= NEW_RUN.done && (
        <div style={{ display: 'flex', gap: 10, padding: '14px 0 4px 26px', ...fadeUp(t, NEW_RUN.done) }}>
          <Button pressed={press(t, NEW_RUN.clickStart)}>Start run</Button>
          <Button variant="ghost">Adjust manually</Button>
        </div>
      )}
    </div>
  );
}

function SourcesPanel({ t }: { t: number }) {
  const first = NEW_RUN.sources[0];
  const last = NEW_RUN.sources[NEW_RUN.sources.length - 1];
  const busy = t >= first - 0.6 && t < last;
  const titles = Array.from(new Set(entityGroups.map((g) => g.title)));
  return (
    <div>
      <div style={{ marginBottom: 10, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <Eyebrow>Sources</Eyebrow>
        {busy ? <Ring t={t} size={9} /> : null}
      </div>
      {t < first ? <div style={{ fontSize: 12.5, color: C.faint }}>Records load here as targets and ligands are named.</div> : null}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {titles.map((title, gi) => {
          const items = entityGroups.filter((g) => g.title === title);
          const times = sourceTimes[gi];
          if (t < times[0]) return null;
          return (
            <div key={title} style={fadeUp(t, times[0])}>
              <div style={{ marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600 }}>
                <span style={{ width: 7, height: 7, borderRadius: 2, background: items[0].kind === 'protein' ? C.accent : C.docking }} />
                {title}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {items.map((e, ii) => {
                  if (t < times[ii]) return null;
                  return (
                    <div key={e.key} style={{ display: 'grid', gridTemplateColumns: '12px 84px minmax(0,1fr)', alignItems: 'start', gap: 8, borderTop: `1px solid ${C.line2}`, padding: '5px 0', ...fadeIn(t, times[ii]) }}>
                      <OkDot size={8} style={{ position: 'relative', top: 4 }} />
                      <span style={{ paddingTop: 1, fontSize: 11.5, color: C.muted }}>
                        {e.source}
                        <span style={{ display: 'block', fontFamily: FONT.mono, fontSize: 10.5, color: C.faint }}>
                          {e.ms}
                          {THIN}ms
                        </span>
                      </span>
                      <div style={{ minWidth: 0, fontSize: 12 }}>
                        {(e.rows as [string, string][]).map(([k, v], i) => (
                          <div key={`${k}-${i}`} style={{ display: 'flex', minWidth: 0, gap: 8 }}>
                            <span style={{ flex: 'none', color: C.muted }}>{k}</span>
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: FONT.mono, fontSize: 11.5 }}>{v}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function NewRun({ t }: { t: number }) {
  const s = scene('newRun');
  if (t < s.from || t >= s.to) return null;
  const view = viewAt(t, CAM);
  const cursor = cursorAt(t, CURSOR, (x, y) => toScreen(view, x, y));
  return (
    <div style={{ position: 'absolute', inset: 0, ...swap(t, s.from, s.to, 0.2, 0.001) }}>
      <Stage view={view}>
        <div style={{ position: 'absolute', left: 164, top: 84, width: 764 }}>
          <h1 style={{ margin: 0, fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em', lineHeight: '25px', marginBottom: 35 }}>New run</h1>
          <PromptBox t={t} />
          <DecisionStream t={t} />
        </div>
        <div style={{ position: 'absolute', left: 976, top: 88, width: 300 }}>
          <SourcesPanel t={t} />
        </div>
      </Stage>
      <UserCursor {...cursor} />
    </div>
  );
}
