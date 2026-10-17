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

function CountsText({ d }: { d: UiDimension }) {
  const parts = counts(d).split(' · ');
  return (
    <>
      {parts.map((p, i) => (
        <span key={p} className="whitespace-nowrap">
          {i > 0 && ' · '}
          {p}
        </span>
      ))}
    </>
  );
}

const ORDER = ['inputs', 'applicability', 'exposure', 'geometry', 'physical_validity', 'physics', 'interactions', 'chemical_plausibility', 'stability', 'confidence', 'support', 'corroboration'];

function rank(id: string): number {
  const i = ORDER.indexOf(id);
  return i < 0 ? ORDER.length : i;
}

export function DimensionStrip({ record, variant, className, onSelect }: ReportBlockProps & { onSelect?: (d: UiDimension) => void }) {
  const dims = [...dimensionsOf(record)].sort((a, b) => rank(a.id) - rank(b.id));
  const print = variant === 'print';
  if (!dims.length) return null;
  return (
    <div className={clsx('flex flex-none flex-wrap overflow-hidden rounded-card border border-line bg-surface', className)} data-testid="dimension-strip">
      {dims.map((d) => {
        const muted = d.result === 'na' || d.result === 'pending';
        const Tag = onSelect ? 'button' : 'div';
        return (
          <Tag
            key={d.id}
            type={onSelect ? 'button' : undefined}
            onClick={onSelect ? () => onSelect(d) : undefined}
            className={clsx(
              '-mr-px -mb-px min-w-0 flex-1 basis-[150px] border-0 border-r border-b border-line bg-surface text-left',
              print ? 'px-1.5 py-1' : 'px-3 py-2.5',
              onSelect && 'transition-colors duration-200 hover:bg-canvas',
            )}
            data-testid="dimension"
            data-dimension={d.id}
            data-state={d.result}
            data-certainty={d.certainty}
            title={`${d.label}: ${RESULT_TEXT[d.result]} · ${counts(d)} · weakest threshold evidence: ${CERTAINTY_TEXT[d.certainty]}\n${d.checkIds.join('\n')}`}
          >
            <div className={clsx('flex items-center gap-1.5', muted ? 'text-muted' : 'text-ink')}>
              <DimensionIcon id={d.id} size={print ? 11 : 13} />
              <span className={clsx('truncate font-medium', print ? 'text-[8pt]' : 'text-[12.5px]')}>{d.label}</span>
            </div>
            <div className={clsx('mt-1 flex items-baseline gap-2 whitespace-nowrap tabular-nums', print ? 'text-[7pt]' : 'text-[11.5px]')}>
              <span className="font-semibold tracking-[.04em] uppercase" style={{ color: resultColor(d.result) }}>
                {RESULT_TEXT[d.result]}
              </span>
              <span className="truncate text-muted">
                <CountsText d={d} />
              </span>
            </div>
            <div className={clsx('truncate', print ? 'text-[7pt]' : 'text-[11px]', d.certainty === 'uncalibrated' ? 'text-accent-deep' : d.certainty === 'none' ? 'text-faint' : 'text-ink2')} data-testid="dimension-certainty">
              {CERTAINTY_TEXT[d.certainty]}
            </div>
          </Tag>
        );
      })}
    </div>
  );
}
