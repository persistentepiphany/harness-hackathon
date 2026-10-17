// Small presentational pieces shared by the report blocks (prototype inline styles as classes).

import clsx from 'clsx';
import type { ReactNode } from 'react';
import { EmptyState } from '@/components/ui';
import { RESULT_COLOR } from '@/lib/selectors/report';
import type { Result } from '@/lib/types';

/** 14px semibold section title with an optional mono note on the right. */
export function SectionTitle({ children, note, className }: { children: ReactNode; note?: ReactNode; className?: string }) {
  return (
    <div className={clsx('mb-2 flex items-baseline justify-between gap-3', className)}>
      <div className="text-[14px] font-semibold">{children}</div>
      {note !== undefined && note !== null && <span className="font-mono text-[11px] text-muted">{note}</span>}
    </div>
  );
}

/** Uppercase muted label (11px screen, 8.5pt print). */
export function BlockLabel({ children, print, className, right }: { children: ReactNode; print?: boolean; className?: string; right?: ReactNode }) {
  return (
    <div className={clsx('flex items-baseline justify-between gap-3', print ? 'mb-1.5' : 'mb-2', className)}>
      <div className={print ? 'text-[8.5pt] tracking-[.08em] text-muted uppercase' : 'eyebrow'}>{children}</div>
      {right}
    </div>
  );
}

/** Result dot: filled by result colour; `reported` hollow; not implemented hollow faint. */
export function ResultDot({ result, size = 6, hollow, className }: { result: Result | null | undefined; size?: number; hollow?: boolean; className?: string }) {
  const color = result ? RESULT_COLOR[result] : 'var(--color-faint)';
  const isHollow = hollow ?? (result === 'reported' || !result);
  return (
    <span
      aria-hidden
      className={clsx('relative top-px inline-block flex-none rounded-full', className)}
      style={{ width: size, height: size, background: isHollow ? 'transparent' : color, border: `1.5px solid ${color}` }}
    />
  );
}

/** Muted "not computed" line in a block's slot. */
export function NotComputed({ what, className, print }: { what?: string; className?: string; print?: boolean }) {
  return (
    <EmptyState className={clsx(print ? 'py-1 text-[8.5pt]' : 'py-2', className)} data-testid="not-computed">
      <span data-block={what}>not computed</span>
    </EmptyState>
  );
}

/** k / v row of a stat card. */
export function KvRow({ k, v, print, muted, title }: { k: ReactNode; v: ReactNode; print?: boolean; muted?: boolean; title?: string }) {
  return (
    <div className={clsx('flex justify-between gap-3', print ? 'gap-2 py-px text-[9pt]' : 'py-[3px] text-[12px]')} title={title}>
      <span className="text-ink2">{k}</span>
      <span className={clsx('text-right font-mono', print ? 'text-[8.5pt]' : 'text-[11.5px]', muted && 'text-faint')}>{v}</span>
    </div>
  );
}
