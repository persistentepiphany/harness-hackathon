// Small presentational pieces shared by the report blocks (prototype inline styles as classes).

import clsx from 'clsx';
import type { ReactNode } from 'react';
import { DASH, splitUnit } from '@/lib/format';
import { blockAvailability, RESULT_COLOR } from '@/lib/selectors/report';
import type { Result, Tool, UiRunRecord } from '@/lib/types';

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

/**
 * Muted line in a block's slot. With `record`, says why the block is empty: `not applicable` with
 * the reason (its checks were skipped as not applicable), `pending` (waits for predictions), or
 * `not computed` (the block should exist and does not).
 */
export function NotComputed({ what, className, print, record, tools }: { what?: string; className?: string; print?: boolean; record?: UiRunRecord; tools?: Tool[] | null }) {
  const a = record && what ? blockAvailability(record, what, false, tools) : null;
  const state = a?.state ?? 'not_computed';
  const word = state === 'not_applicable' ? 'not applicable' : state === 'pending' ? 'pending' : 'not computed';
  return (
    <div className={clsx('text-muted', print ? 'py-1 text-[8.5pt]' : 'py-2 text-[12px]', className)} data-testid="not-computed" data-state={state}>
      <span data-block={what}>
        {word}
        {a?.reason ? <span className="text-faint"> · {a.reason}</span> : null}
      </span>
    </div>
  );
}

/** k / v row of a stat card. */
export function KvRow({ k, v, print, muted, title }: { k: ReactNode; v: ReactNode; print?: boolean; muted?: boolean; title?: string }) {
  return (
    <div className={clsx('kv-grid', print ? 'py-px text-[9pt] [--kv-label:minmax(0,1fr)]' : 'py-[3px] text-[12px] [--kv-label:minmax(0,1fr)]')} title={title}>
      <span className="min-w-0 text-ink2">{k}</span>
      <span className={clsx('num font-mono', print ? 'text-[8.5pt]' : 'text-[11.5px]', muted && 'text-faint')}>{v}</span>
    </div>
  );
}

/** Value with its unit in muted text after it (number alignment standard, lib/format.ts). */
export function Num({ value, unit, className, title }: { value: string; unit?: string | null; className?: string; title?: string }) {
  return (
    <span className={clsx('whitespace-nowrap tabular-nums', className)} title={title}>
      {value}
      {unit && value !== DASH ? <span className="num-unit">{unit}</span> : null}
    </span>
  );
}

/** A formatted `value unit` string (`−6.1 kcal/mol`) rendered as Num. */
export function NumText({ text, className, title }: { text: string | null | undefined; className?: string; title?: string }) {
  const p = splitUnit(text);
  return <Num value={p.value} unit={p.unit} className={className} title={title} />;
}
