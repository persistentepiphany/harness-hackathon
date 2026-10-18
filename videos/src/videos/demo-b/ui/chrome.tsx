// Screen chrome: the product's top nav (twin of web/components/nav/TopNav.tsx), the camera stage,
// the caption band and the provenance tag.

import type { ReactNode } from 'react';

import { camera, type CameraKey } from '../../../kit/camera';
import { clamp01 } from '../../../kit/time';
import { pulse } from '../anim';
import { CAPTION, FRAME, NAV, PAGE_W, VIEW } from '../layout';
import { C, FONT } from '../tokens';

export type TabId = 'new' | 'jobs' | 'report' | 'ensemble' | 'agent' | 'docs';

export interface NavState {
  active: TabId | null;
  badges: Partial<Record<TabId, number>>;
  status: string; // `idle` or `1 running · 0 queued`
  running: boolean;
  mode: string; // `live` or `mock`
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'new', label: 'New run' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'report', label: 'Reports' },
  { id: 'ensemble', label: 'Ensemble' },
  { id: 'agent', label: 'Agent' },
  { id: 'docs', label: 'Documents' },
];

/** The logo mark: 14 px square, 1.5 px ink border, accent inset square (TopNav). */
export const LogoMark = ({ size = 14 }: { size?: number }) => (
  <span style={{ position: 'relative', display: 'inline-block', width: size, height: size, borderRadius: (3 * size) / 14, border: `${(1.5 * size) / 14}px solid ${C.ink}`, boxSizing: 'border-box', flex: 'none' }}>
    <span style={{ position: 'absolute', inset: (3 * size) / 14, borderRadius: size / 14, background: C.accent }} />
  </span>
);

export function TopNav({ t, state, opacity = 1 }: { t: number; state: NavState; opacity?: number }) {
  return (
    <div style={{ position: 'absolute', left: 0, top: 0, width: NAV.width, height: 44, scale: String(NAV.scale), transformOrigin: '0 0', opacity }}>
      <div style={{ height: 44, display: 'flex', alignItems: 'center', gap: 32, borderBottom: `1px solid ${C.line}`, background: C.canvas, padding: '0 24px', boxSizing: 'border-box', fontFamily: FONT.sans }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, color: C.ink }}>
          <LogoMark />
          <span style={{ fontSize: 13, fontWeight: 600 }}>Harness</span>
        </div>
        <div style={{ display: 'flex', flex: 1, gap: 2 }}>
          {TABS.map((tab) => {
            const on = tab.id === state.active;
            const badge = state.badges[tab.id];
            return (
              <div
                key={tab.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 7,
                  whiteSpace: 'nowrap',
                  borderBottom: `1.5px solid ${on ? C.ink : 'transparent'}`,
                  padding: '12px 10px 11px',
                  fontSize: 13,
                  lineHeight: 'normal',
                  fontWeight: 500,
                  color: on ? C.ink : C.muted,
                }}
              >
                <span>{tab.label}</span>
                {badge ? <span style={{ fontFamily: FONT.mono, fontSize: 11, color: C.muted }}>{badge}</span> : null}
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: C.ink2 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: state.running ? C.accent : C.faint, opacity: state.running ? pulse(t, 1.4) : 1 }} />
          <span style={{ fontFamily: FONT.mono, fontSize: 11 }}>{state.status}</span>
          <span style={{ fontFamily: FONT.mono, fontSize: 11, color: C.faint }}>· {state.mode}</span>
        </div>
      </div>
    </div>
  );
}

export type View = { x: number; y: number; zoom: number };
export const viewAt = (t: number, keys: readonly CameraKey[]): View => camera(t, keys);

/** Debug camera: world x = screen x, world y = screen y - VIEW.y, so TargetLog prints world coordinates. */
export const DEBUG_VIEW: View = { x: VIEW.w / 2, y: VIEW.h / 2, zoom: 1 };

/** World (product px) to screen px. */
export function toScreen(view: View, x: number, y: number) {
  return { x: VIEW.x + VIEW.w / 2 + (x - view.x) * view.zoom, y: VIEW.y + VIEW.h / 2 + (y - view.y) * view.zoom };
}

/** The product page filmed through the camera, clipped to the picture area above the caption band. */
export function Stage({ view, children, width = PAGE_W, height = 2400, style }: { view: View; children: ReactNode; width?: number; height?: number; style?: React.CSSProperties }) {
  return (
    <div style={{ position: 'absolute', left: VIEW.x, top: VIEW.y, width: VIEW.w, height: VIEW.h, overflow: 'hidden', ...style }}>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width,
          height,
          transformOrigin: '0 0',
          transform: `translate(${VIEW.w / 2}px, ${VIEW.h / 2}px) scale(${view.zoom}) translate(${-view.x}px, ${-view.y}px)`,
          fontFamily: FONT.sans,
          fontSize: 13,
          lineHeight: 1.45,
          color: C.ink,
          WebkitFontSmoothing: 'antialiased',
        }}
      >
        {children}
      </div>
    </div>
  );
}

/** Hairline under the picture, like the nav's border: the caption band is chrome, not page. */
export const BandRule = ({ opacity = 1 }: { opacity?: number }) => (
  <div style={{ position: 'absolute', left: 0, top: CAPTION.top, width: FRAME.width, height: 1, background: C.line, opacity }} />
);

/** One short caption line; blur-swaps in and out, never re-centres while it is on screen. */
export function Captions({ t, list }: { t: number; list: { from: number; to: number; text: string }[] }) {
  return (
    <>
      {list.map((c) => {
        if (t < c.from || t >= c.to) return null;
        const enter = clamp01((t - c.from - 0.08) / 0.22);
        const leave = clamp01((t - (c.to - 0.16)) / 0.16);
        const v = enter * (1 - leave);
        return (
          <div
            key={c.from}
            style={{
              position: 'absolute',
              left: 120,
              right: 120,
              top: CAPTION.textY,
              translate: `0 -50%`,
              textAlign: 'center',
              fontFamily: FONT.sans,
              fontSize: 34,
              fontWeight: 500,
              letterSpacing: '-0.01em',
              color: C.ink,
              opacity: v,
              filter: v < 1 ? `blur(${(1 - v) * 6}px)` : undefined,
            }}
          >
            {c.text}
          </div>
        );
      })}
    </>
  );
}

/** Where the data on screen comes from, bottom right in mono. */
export function Tag({ t, list }: { t: number; list: { from: number; to: number; text: string }[] }) {
  return (
    <>
      {list.map((c) => {
        if (t < c.from || t >= c.to) return null;
        const v = clamp01((t - c.from - 0.1) / 0.25) * (1 - clamp01((t - (c.to - 0.15)) / 0.15));
        return (
          <div key={c.from} style={{ position: 'absolute', right: 40, top: CAPTION.tagY, translate: '0 -50%', fontFamily: FONT.mono, fontSize: 18, color: C.muted, opacity: v, whiteSpace: 'nowrap' }}>
            {c.text}
          </div>
        );
      })}
    </>
  );
}
