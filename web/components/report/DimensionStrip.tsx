'use client';

// Per-dimension outcome strip (record.dimensions): inputs, applicability, geometry, physics,
// interactions, confidence, support. Each cell: icon, label, result, counts and the weakest
// evidence level of the thresholds its checks used.

import clsx from 'clsx';
import { CERTAINTY_TEXT, dimensionsOf, RESULT_COLOR } from '@/lib/selectors/report';
import type { UiDimension } from '@/lib/types';
import { DimensionIcon } from './icons';
import type { ReportBlockProps } from './types';

const RESULT_TEXT: Record<UiDimension['result'], string> = { pass: 'pass', warn: 'warn', stop: 'stop', pending: 'pending', na: 'not applicable' };

function resultColor(r: UiDimension['result']): string {
  if (r === 'na') return 'var(--color-faint)';
  if (r === 'pending') return 'var(--color-muted)';
  return RESULT_COLOR[r];
}

function counts(d: UiDimension): string {
  const parts: string[] = [];
  if (d.passed) parts.push(`${d.passed} pass`);
  if (d.warned) parts.push(`${d.warned} warn`);
  if (d.stopped) parts.push(`${d.stopped} stop`);
  if (d.pending) parts.push(`${d.pending} pending`);
  const other = d.checks - d.passed - d.warned - d.stopped - d.pending;
  if (other > 0) parts.push(`${other} n/a`);
  return parts.join(' · ') || 'no checks';
}

export function DimensionStrip({ record, variant, className, onSelect }: ReportBlockProps & { onSelect?: (d: UiDimension) => void }) {
  const dims = dimensionsOf(record);
  const print = variant === 'print';
  if (!dims.length) return null;
  return (
    <div className={clsx('grid border-y border-line', className)} style={{ gridTemplateColumns: `repeat(${dims.length},minmax(0,1fr))` }} data-testid="dimension-strip">
      {dims.map((d, i) => {
        const muted = d.result === 'na' || d.result === 'pending';
        const Tag = onSelect ? 'button' : 'div';
        return (
          <Tag
            key={d.id}
            type={onSelect ? 'button' : undefined}
            onClick={onSelect ? () => onSelect(d) : undefined}
            className={clsx(
              'min-w-0 border-0 bg-transparent text-left',
              i > 0 && 'border-l border-line2',
              print ? 'px-1.5 py-1' : 'px-3 py-2.5',
              onSelect && 'hover:bg-surface',
            )}
            data-testid="dimension"
            data-dimension={d.id}
            data-state={d.result}
            data-certainty={d.certainty}
            title={`${d.label}: ${RESULT_TEXT[d.result]} · ${counts(d)} · weakest threshold evidence: ${CERTAINTY_TEXT[d.certainty]}\n${d.checkIds.join('\n')}`}
          >
            <div className={clsx('flex items-center gap-1.5', muted ? 'text-muted' : 'text-ink')}>
              <DimensionIcon id={d.id} size={print ? 11 : 14} />
              <span className={clsx('truncate font-medium', print ? 'text-[8pt]' : 'text-[12px]')}>{d.label}</span>
            </div>
            <div className={clsx('mt-1 font-semibold tracking-[.04em] uppercase', print ? 'text-[7pt]' : 'text-[10.5px]')} style={{ color: resultColor(d.result) }}>
              {RESULT_TEXT[d.result]}
            </div>
            <div className={clsx('truncate font-mono text-muted', print ? 'text-[7pt]' : 'text-[10.5px]')}>{counts(d)}</div>
            <div className={clsx('truncate font-mono', print ? 'text-[7pt]' : 'text-[10.5px]', d.certainty === 'uncalibrated' ? 'text-accent-deep' : d.certainty === 'none' ? 'text-faint' : 'text-ink2')} data-testid="dimension-certainty">
              {CERTAINTY_TEXT[d.certainty]}
            </div>
          </Tag>
        );
      })}
    </div>
  );
}
