'use client';

// Scores present in the record with the tool that produced each and what goes into it
// (GET /ui/glossary, else the tool output description).

import clsx from 'clsx';
import { useMemo } from 'react';
import { scoreEntries } from '@/lib/selectors/report';
import { BlockLabel } from './parts';
import { useGlossary } from './ScoreInfo';
import type { ReportBlockProps } from './types';

export function ScoresSection({ record, tools, variant, className }: ReportBlockProps) {
  const glossary = useGlossary();
  const rows = useMemo(() => scoreEntries(record, tools, glossary), [record, tools, glossary]);
  const print = variant === 'print';
  if (!rows.length) return null;
  return (
    <div className={className} data-testid="scores">
      <BlockLabel print={print}>Scores · producer · inputs</BlockLabel>
      <div className={clsx('border-t', print ? 'border-ink' : 'border-line')}>
        {rows.map((e) => (
          <div
            key={e.key}
            className={clsx('grid items-baseline gap-3 border-b border-line2 break-inside-avoid', print ? 'grid-cols-[110px_90px_minmax(0,1fr)] py-[3px] text-[8.5pt]' : 'grid-cols-[minmax(130px,0.8fr)_minmax(110px,0.6fr)_minmax(0,1.6fr)] py-1.5 text-[12px]')}
            data-testid="score-row"
            data-score={e.key}
          >
            <span>
              {e.label}
              {e.unit && <span className="num-unit">{e.unit}</span>}
              {e.rankingOnly && <span className={clsx('text-accent-deep', print ? 'text-[7.5pt]' : 'text-[10.5px]')}> ranking</span>}
            </span>
            <span className="font-mono text-[11px] text-ink2">{e.producedBy.join(', ') || '–'}</span>
            <span className="text-ink2">
              {e.what}
              {e.inputs.length > 0 && <span className="text-muted"> · inputs: {e.inputs.join(', ')}</span>}
              {e.higherIsBetter !== null && <span className="text-muted"> · {e.higherIsBetter ? 'higher is better' : 'lower is better'}</span>}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
