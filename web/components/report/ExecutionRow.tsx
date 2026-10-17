'use client';

// Execution row (record.execution): executor, GPU, route, total and per-seed timings.

import clsx from 'clsx';
import { fmtMs } from '@/lib/format';
import { executionRows } from '@/lib/selectors/report';
import type { ReportBlockProps } from './types';

const PHASE_COLOR: Record<string, string> = { done: 'text-pass', failed: 'text-stop', running: 'text-accent-deep', skipped: 'text-faint' };

export function ExecutionRow({ record, variant, className }: ReportBlockProps) {
  const rows = executionRows(record);
  const print = variant === 'print';
  if (!rows.length) return null;
  return (
    <div className={clsx('flex flex-col', className)} data-testid="execution">
      {rows.map((e) => (
        <div key={e.executor} className={clsx('flex flex-wrap items-baseline gap-x-3 gap-y-0.5 border-b border-line2 py-1 font-mono tabular-nums', print ? 'text-[8pt]' : 'text-[11px]')} data-testid="execution-row" data-executor={e.executor} data-state={e.phase} title={e.message ?? e.routeNote ?? undefined}>
          <span className={clsx('font-sans tracking-[.06em] text-muted uppercase', print ? 'text-[7.5pt]' : 'text-[10.5px]')}>Execution</span>
          <span className="text-ink">{e.name}</span>
          <span className={PHASE_COLOR[e.phase] ?? 'text-ink2'}>{e.phase}</span>
          {e.gpu && <span className="text-ink2">GPU {e.gpu}</span>}
          {e.route && (
            <span className="text-ink2">
              route {e.route}
              {e.routeNote ? <span className="text-muted"> ({e.routeNote})</span> : null}
            </span>
          )}
          <span className="text-ink2">
            total <span className="text-ink">{fmtMs(e.elapsedMs)}</span>
          </span>
          {e.seeds.length > 0 && (
            <span className="text-muted">
              {e.seeds.map((s, i) => (
                <span key={s.seed} data-testid="execution-seed" data-state={s.phase}>
                  {i > 0 && ' · '}
                  seed {s.seed} <span className={s.phase === 'failed' ? 'text-stop' : 'text-ink2'}>{s.ms === null || s.ms === undefined ? s.phase : fmtMs(s.ms)}</span>
                </span>
              ))}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
