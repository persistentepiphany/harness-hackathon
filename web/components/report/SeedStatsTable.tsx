'use client';

// Per-seed statistics (stats.physics) with a median row.

import clsx from 'clsx';
import { blockSource, physicsTable, sourceLabel } from '@/lib/selectors/report';
import { BlockLabel, NotComputed, SectionTitle } from './parts';
import type { ReportBlockProps } from './types';

export function SeedStatsTable({ record, variant, className }: ReportBlockProps) {
  const print = variant === 'print';
  const t = physicsTable(record);
  const cols = t ? `${print ? '60px' : '70px'} repeat(${t.columns.length},minmax(0,1fr))` : undefined;
  return (
    <div className={className} data-testid="seed-stats" data-state={t ? 'computed' : 'not-computed'} title={sourceLabel(blockSource(record, 'physics'))}>
      {print ? <BlockLabel print>Per-seed statistics</BlockLabel> : <SectionTitle>Per-seed statistics</SectionTitle>}
      <div className={clsx('border-t font-mono', print ? 'border-ink text-[8.5pt]' : 'border-line text-[11.5px]')}>
        {t ? (
          <>
            <div className={clsx('grid border-b border-line2 text-muted', print ? 'gap-1.5 py-1' : 'gap-2 py-[7px] text-[10.5px]')} style={{ gridTemplateColumns: cols }}>
              <span>seed</span>
              {t.columns.map((c) => (
                <span key={c.key} className="text-right" title={sourceLabel(blockSource(record, `physics.${c.key}`))}>
                  {c.label}
                </span>
              ))}
            </div>
            {t.rows.map((r) => (
              <div key={r.key} className={clsx('grid border-b border-line3', print ? 'gap-1.5 py-[3px]' : 'gap-2 py-1.5', r.flagged ? 'text-accent-deep' : 'text-ink2')} style={{ gridTemplateColumns: cols }} data-testid="seed-row" data-state={r.flagged ? 'flagged' : 'ok'}>
                <span>{r.seed}</span>
                {r.cells.map((v, k) => (
                  <span key={t.columns[k].key} className="text-right">
                    {v}
                  </span>
                ))}
              </div>
            ))}
            <div className={clsx('grid font-medium text-ink', print ? 'gap-1.5 py-1' : 'gap-2 py-[7px]')} style={{ gridTemplateColumns: cols }}>
              <span>median</span>
              {t.median.map((v, k) => (
                <span key={t.columns[k].key} className="text-right">
                  {v}
                </span>
              ))}
            </div>
          </>
        ) : (
          <NotComputed what="physics" print={print} />
        )}
      </div>
    </div>
  );
}
