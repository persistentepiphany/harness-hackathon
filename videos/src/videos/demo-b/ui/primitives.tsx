// Frame-driven twins of web/components/ui/*. Same sizes, borders and tokens as the Tailwind classes;
// only the clock changes (CSS keyframes become functions of t).

import type { CSSProperties, ReactNode } from 'react';

import { pulse, spinDeg } from '../anim';
import { C, FONT, RESULT_COLOR, type Result } from '../tokens';

/** StatusDot (6 to 8 px), round or square, optional pulse (running). */
export function Dot({ color, size = 6, square, hollow, pulseAt, style }: { color: string; size?: number; square?: boolean; hollow?: boolean; pulseAt?: number; style?: CSSProperties }) {
  return (
    <span
      style={{
        display: 'inline-block',
        flex: 'none',
        width: size,
        height: size,
        borderRadius: square ? 2 : '50%',
        background: hollow ? 'transparent' : color,
        border: hollow ? `1.5px solid ${color}` : undefined,
        boxSizing: 'border-box',
        opacity: pulseAt === undefined ? 1 : pulse(pulseAt),
        ...style,
      }}
    />
  );
}

export const ResultDot = ({ result, size = 6, style }: { result: Result; size?: number; style?: CSSProperties }) => (
  <Dot color={RESULT_COLOR[result]} size={size} hollow={result === 'reported' || result === 'pending'} style={style} />
);

/** Spinner / RingDot loading: line-coloured ring with an accent top, spin 0.8 s (run/parts.tsx RingDot). */
export function Ring({ t, size = 10, style }: { t: number; size?: number; style?: CSSProperties }) {
  return (
    <span
      style={{
        display: 'inline-block',
        flex: 'none',
        width: size,
        height: size,
        borderRadius: '50%',
        border: `1.5px solid ${C.line}`,
        borderTopColor: C.accent,
        boxSizing: 'border-box',
        rotate: `${spinDeg(t)}deg`,
        ...style,
      }}
    />
  );
}

/** RingDot done: filled pass dot with a pass border. */
export const OkDot = ({ size = 10, style }: { size?: number; style?: CSSProperties }) => (
  <span style={{ display: 'inline-block', flex: 'none', width: size, height: size, borderRadius: '50%', background: C.pass, border: `1.5px solid ${C.pass}`, boxSizing: 'border-box', ...style }} />
);

/** Eyebrow: 11 px uppercase, tracking .06em, muted, weight 500. */
export const Eyebrow = ({ children, style }: { children: ReactNode; style?: CSSProperties }) => (
  <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase', color: C.muted, ...style }}>{children}</div>
);

/** Meta label (10.5 px uppercase muted) over a value, as in RunHeader and VerdictHeader. */
export const Meta = ({ label, children, mono }: { label: string; children: ReactNode; mono?: boolean }) => (
  <div>
    <div style={{ fontSize: 10.5, letterSpacing: '0.06em', textTransform: 'uppercase', color: C.muted, marginBottom: 3 }}>{label}</div>
    <div style={mono ? { fontFamily: FONT.mono, fontSize: 12 } : undefined}>{children}</div>
  </div>
);

/** Button: primary (ink fill), secondary (outlined), ghost. 6 px radius, 12.5 px medium. */
export function Button({ variant = 'primary', children, disabled, pressed, style }: { variant?: 'primary' | 'secondary' | 'ghost'; children: ReactNode; disabled?: boolean; pressed?: number; style?: CSSProperties }) {
  const base: CSSProperties = {
    display: 'inline-block',
    borderRadius: 6,
    fontSize: 12.5,
    lineHeight: 'normal',
    fontWeight: 500,
    whiteSpace: 'nowrap',
    opacity: disabled ? 0.4 : 1,
    scale: pressed ? String(1 - 0.03 * pressed) : undefined,
  };
  const v: CSSProperties =
    variant === 'primary'
      ? { background: C.ink, color: '#fff', padding: '8px 14px' }
      : variant === 'secondary'
        ? { border: `1px solid ${C.line}`, color: C.ink2, padding: '7px 12px' }
        : { color: C.muted, padding: '8px 6px' };
  return <span style={{ ...base, ...v, ...style }}>{children}</span>;
}

/** Monospace number or identifier (MonoNum / mono-data). */
export const Mono = ({ children, size = 11.5, color, style }: { children: ReactNode; size?: number; color?: string; style?: CSSProperties }) => (
  <span style={{ fontFamily: FONT.mono, fontSize: size, color, fontVariantNumeric: 'tabular-nums', ...style }}>{children}</span>
);

/** Section title used across the report (14 px semibold, note on the right in mono muted). */
export const SectionTitle = ({ children, note, style }: { children: ReactNode; note?: ReactNode; style?: CSSProperties }) => (
  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, marginBottom: 10, ...style }}>
    <span style={{ fontSize: 14, fontWeight: 600, color: C.ink }}>{children}</span>
    {note ? <span style={{ fontFamily: FONT.mono, fontSize: 11, color: C.muted }}>{note}</span> : null}
  </div>
);
