'use client';

// Compact report sidebar: layer list (name, worst-result dot, counts with pending and not
// applicable apart), run totals, and the tools: executors and check libraries, exercised or only
// declared ("declared, not run", muted).

import clsx from 'clsx';
import { fmtMs } from '@/lib/format';
import { breakdownText, layerBreakdown, layerNav, runDurationMs, toolRows } from '@/lib/selectors/report';
import { ResultDot } from './parts';
import type { ReportBlockProps } from './types';

export interface LayerSidebarProps extends ReportBlockProps {
  /** Index into record.layers of the selected layer, or -1 when a whole stage is shown. */
  selected: number;
  onSelect: (index: number) => void;
  /** Indices of the layers in the selected stage (marked, not pressed). */
  inStage?: number[];
}

export function LayerSidebar({ record, tools, selected, onSelect, inStage = [], className }: LayerSidebarProps) {
  const nav = layerNav(record);
  const all = record.layers.flatMap((l) => l.checks);
  const total = runDurationMs(record);
  const rows = toolRows(record, tools);

  return (
    <div className={clsx('sticky top-[68px] flex flex-col gap-6', className)} data-testid="layer-sidebar">
      <div>
        <div className="eyebrow mb-2">Layers</div>
        {nav.map((l, idx) => {
          const on = idx === selected;
          const marked = !on && inStage.includes(idx);
          const b = layerBreakdown(record, idx);
          return (
            <button
              key={l.i}
              type="button"
              onClick={() => onSelect(idx)}
              data-testid="layer-cell"
              data-layer={l.i}
              data-state={l.status === 'done' ? (l.dot ?? 'empty') : l.status}
              aria-pressed={on}
              className={clsx(
                'block w-full border-0 border-l-2 bg-transparent py-[5px] pr-0 pl-3 text-left transition-colors duration-150',
                on ? 'border-ink' : marked ? 'border-faint' : 'border-line hover:border-faint',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={clsx('text-[12.5px]', on ? 'font-semibold text-ink' : marked ? 'font-medium text-ink' : 'font-medium text-ink2')}>
                  <span className="font-mono text-[10.5px] text-muted">L{l.i}</span> {l.name}
                </span>
                {l.status === 'running' ? (
                  <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-accent" />
                ) : l.status === 'not_run' || l.status === 'pending' ? (
                  <span className="h-[7px] w-[7px] rounded-full border-[1.5px] border-faint" title={l.status === 'not_run' ? 'layer not run' : 'pending'} />
                ) : (
                  <ResultDot result={b.pending && !b.pass && !b.warn && !b.stop ? 'pending' : l.dot} size={7} hollow={l.dot === null || l.dot === 'reported' || l.dot === 'skip' || (b.pending > 0 && !b.pass && !b.warn && !b.stop)} className="top-0" />
                )}
              </div>
              <div className="mt-px font-mono text-[10.5px] leading-[1.5] text-muted tabular-nums" data-testid="layer-counts">
                {l.status === 'not_run' ? 'not run' : l.status === 'pending' ? 'pending' : breakdownText(b, { short: true })}
              </div>
            </button>
          );
        })}
        <div className="mt-2 pl-3.5 font-mono text-[10.5px] text-muted tabular-nums">
          {all.length} checks · {fmtMs(total)}
        </div>
      </div>

      <div data-testid="tool-versions">
        <div className="eyebrow mb-1.5">Tools</div>
        {rows.map((t) => (
          <div
            key={`${t.role}:${t.name}`}
            className={clsx('flex items-baseline justify-between gap-2 py-px pl-3.5 font-mono text-[11px]', t.exercised ? 'text-ink2' : 'text-faint')}
            data-testid="tool-version"
            data-role={t.role}
            data-state={t.exercised ? 'exercised' : 'declared'}
            title={t.checks.length ? t.checks.join('\n') : t.note}
          >
            <span className="truncate">
              {t.name}
              {t.version ? ` ${t.version}` : ''}
            </span>
            <span className={clsx('flex-none text-[10px]', t.exercised ? 'text-muted' : 'text-faint')}>{t.note}</span>
          </div>
        ))}
        {record.record.pahVersion && <div className="py-px pl-3.5 font-mono text-[11px] text-ink2">pah {record.record.pahVersion}</div>}
      </div>
    </div>
  );
}

/** Executors and check libraries: exercised, or declared and not run (muted). */
export function ToolsList({ record, tools, className }: ReportBlockProps) {
  const rows = toolRows(record, tools);
  return (
    <div className={className} data-testid="tool-versions">
      {rows.map((t) => (
        <div
          key={`${t.role}:${t.name}`}
          className={clsx('grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-3 border-b border-line3 py-[3px] font-mono text-[11px]', t.exercised ? 'text-ink2' : 'text-faint')}
          data-testid="tool-version"
          data-role={t.role}
          data-state={t.exercised ? 'exercised' : 'declared'}
          title={t.checks.length ? t.checks.join('\n') : t.note}
        >
          <span className="min-w-0 break-words">
            {t.name}
            {t.version ? ` ${t.version}` : ''}
            <span className="ml-1.5 font-sans text-[10px] text-muted">{t.role === 'executor' ? 'executor' : ''}</span>
          </span>
          <span className="text-right text-[10.5px]">{t.note}</span>
        </div>
      ))}
      {record.record.pahVersion && <div className="py-[3px] font-mono text-[11px] text-ink2">pah {record.record.pahVersion}</div>}
    </div>
  );
}
