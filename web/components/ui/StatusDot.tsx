import clsx from 'clsx';
import type { JobStatus, Outcome, Result } from '@/lib/types';

export type DotState = Result | Outcome | JobStatus | 'idle' | 'connected' | 'disconnected' | 'checking' | 'mock' | null | undefined;

/** Fill colour per state (prototype palette P/T in logic-v2.js). */
const COLOR: Record<string, string> = {
  pass: 'var(--color-pass)',
  warn: 'var(--color-warn)',
  stop: 'var(--color-stop)',
  reported: 'var(--color-reported)',
  skip: 'var(--color-faint)',
  pending: 'var(--color-faint)',
  supported: 'var(--color-pass)',
  narrowed: 'var(--color-accent-deep)',
  refused: 'var(--color-stop)',
  incomplete: 'var(--color-faint)',
  running: 'var(--color-accent)',
  queued: 'var(--color-faint)',
  done: 'var(--color-pass)',
  failed: 'var(--color-stop)',
  idle: 'var(--color-faint)',
  connected: 'var(--color-pass)',
  disconnected: 'var(--color-stop)',
  checking: 'var(--color-faint)',
  mock: 'var(--color-faint)',
};

export function dotColor(state: DotState): string {
  return (state && COLOR[state]) || 'var(--color-faint)';
}

export interface StatusDotProps {
  state: DotState;
  /** 6 to 8 px. */
  size?: number;
  /** Pulse (defaults to true for `running`). */
  pulse?: boolean;
  /** Ring only; `reported` checks render hollow in the prototype. */
  hollow?: boolean;
  /** Square marker (agent tool/result steps). */
  square?: boolean;
  className?: string;
  title?: string;
  'data-testid'?: string;
}

/** 6–8 px status dot coloured by result, outcome or job status. */
export function StatusDot({ state, size = 6, pulse, hollow, square, className, title, ...rest }: StatusDotProps) {
  const color = dotColor(state);
  const isHollow = hollow ?? state === 'reported';
  const isPulse = pulse ?? state === 'running';
  return (
    <span
      aria-hidden={title ? undefined : true}
      title={title}
      data-state={state ?? undefined}
      data-testid={rest['data-testid']}
      className={clsx('inline-block flex-none', square ? 'rounded-[2px]' : 'rounded-full', isPulse && 'animate-pulse', className)}
      style={{
        width: size,
        height: size,
        background: isHollow ? 'transparent' : color,
        border: isHollow ? `1.5px solid ${color}` : undefined,
      }}
    />
  );
}
