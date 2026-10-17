'use client';

// Ensemble table beside the viewer (prototype ensembleRows): one row per member, columns built
// from the fields and tool outputs present in at least one row (memberColumns), then the sampling
// summary. A ranking-only column is muted. "not computed" when the record has no stats.ensemble.

import clsx from 'clsx';
import { DASH } from '@/lib/format';
import { blockSource, KIND_COLOR, medoidClusterPopulation, memberColumns, pairwiseLine, sourceLabel, type EnsembleMember } from '@/lib/selectors/report';
import type { ReportBlockProps } from './types';

export interface EnsembleTableProps extends ReportBlockProps {
  members: EnsembleMember[];
  selected: string | null;
  onSelect: (id: string) => void;
  /** Members beyond the table (listed on the ensemble page). */
  more?: number;
}

export function EnsembleTable({ record, members, selected, onSelect, className }: EnsembleTableProps) {
  const cols = memberColumns(members);
  const grid = { gridTemplateColumns: `minmax(104px,1.5fr) repeat(${Math.max(1, cols.length)},minmax(0,1fr))` };
  const computed = !!record.stats.ensemble;
  const summary: [string, string | null | undefined, string?][] = [
    ['medoid cluster', medoidClusterPopulation(record), 'ensemble.cluster'],
    ['pairwise RMSD', pairwiseLine(record), 'pairwise'],
    ['site placement', record.stats.sitePlacement, 'sitePlacement'],
    ['pose accuracy', record.stats.poseAccuracy, 'poseAccuracy'],
  ];
  return (
    <div className={clsx('max-h-[460px] overflow-auto rounded-card border border-line bg-surface text-[11.5px]', className)} data-testid="ensemble-table" data-state={computed ? 'computed' : 'not-computed'} title={sourceLabel(blockSource(record, 'ensemble.rmsdToMedoid'))}>
      <div className="sticky top-0 z-[1] grid gap-1.5 border-b border-line2 bg-surface px-3 py-2 font-mono text-[10.5px] text-muted" style={grid} data-testid="ensemble-columns">
        <span>structure</span>
        {cols.map((c) => (
          <span key={c.id} className={clsx('truncate text-right', c.ranking && 'text-accent-deep')} title={c.title} data-column={c.id}>
            {c.header}
          </span>
        ))}
      </div>
      {members.map((m) => {
        const on = selected === m.id;
        return (
          <div
            key={m.id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(m.id)}
            onKeyDown={(ev) => {
              if (ev.key !== 'Enter' && ev.key !== ' ') return;
              // Space selects the row without scrolling the page
              ev.preventDefault();
              onSelect(m.id);
            }}
            className={clsx('grid cursor-pointer gap-1.5 border-b border-line3 px-3 py-1.5 font-mono text-[11.5px] hover:bg-canvas', on && 'bg-canvas')}
            style={grid}
            data-testid="ensemble-row"
            data-structure={m.id}
            data-state={on ? 'selected' : 'idle'}
          >
            <span className="flex min-w-0 items-center gap-1.5">
              <span className="h-1.5 w-1.5 flex-none rounded-full" style={{ background: KIND_COLOR[m.kind] }} />
              <span className={clsx('truncate', on ? 'text-ink' : 'text-ink2')} title={m.structure?.path ?? m.label}>
                {m.kind === 'medoid' ? `${m.label} · medoid` : m.label}
              </span>
            </span>
            {cols.map((c) => {
              const t = c.text(m);
              return (
                <span key={c.id} className={clsx('text-right', t === DASH ? 'text-faint' : c.warn?.(m) ? 'text-warn' : c.ranking ? 'text-accent-deep' : 'text-ink')}>
                  {t}
                </span>
              );
            })}
          </div>
        );
      })}
      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-[5px] px-3 py-2.5 font-mono text-[11.5px] text-ink2">
        {summary.map(([k, v, key]) => (
          <span key={k} className="contents" title={key ? sourceLabel(blockSource(record, key)) : undefined}>
            <span className="text-muted">{k}</span>
            <span className={v ? undefined : 'text-faint'}>{v ?? DASH}</span>
          </span>
        ))}
      </div>
      {!computed && (
        <div className="border-t border-line3 px-3 py-2 text-[12px] text-muted" data-testid="not-computed">
          ensemble statistics not computed
        </div>
      )}
    </div>
  );
}
