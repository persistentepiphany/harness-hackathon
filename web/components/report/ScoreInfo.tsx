'use client';

// Score info affordance: a small (i) beside a score label. Hover, focus or click shows which tool
// produced the score and what goes into it (GET /ui/glossary, else the tool output description).

import clsx from 'clsx';
import { useMemo, useState } from 'react';
import type { HarnessApi } from '@/lib/harness-api';
import { useSharedQuery } from '@/lib/hooks';
import { scoreLookup, type ScoreEntry } from '@/lib/selectors/report';
import type { Tool, UiGlossary, UiRunRecord } from '@/lib/types';
import { InfoIcon } from './icons';

type GlossaryApi = HarnessApi & { getGlossary?: (opts?: { signal?: AbortSignal }) => Promise<UiGlossary> };

/** GET /ui/glossary once per session (null when the API has no glossary). */
export function useGlossary(): UiGlossary | null {
  const q = useSharedQuery<UiGlossary | null>('glossary', (api, signal) => {
    const g = (api as GlossaryApi).getGlossary;
    return g ? g.call(api, { signal }).catch(() => null) : Promise.resolve(null);
  });
  return q.data ?? null;
}

/** Lookup of score entries for one record (glossary first, then the record's tool outputs). */
export function useScoreLookup(record: UiRunRecord, tools?: Tool[] | null) {
  const glossary = useGlossary();
  return useMemo(() => scoreLookup(record, tools, glossary), [record, tools, glossary]);
}

export function scoreInfoText(e: ScoreEntry): string {
  return [
    `${e.label}${e.unit ? ` (${e.unit})` : ''}`,
    `Produced by ${e.producedBy.join(', ') || 'not recorded'}`,
    e.what,
    e.inputs.length ? `Inputs: ${e.inputs.join(', ')}` : null,
    e.higherIsBetter === true ? 'Higher is better' : e.higherIsBetter === false ? 'Lower is better' : null,
    e.rankingOnly ? 'Ranking score: compare within this run only' : null,
  ]
    .filter(Boolean)
    .join('\n');
}

export function ScoreInfo({ entry, align = 'left', className }: { entry: ScoreEntry | null | undefined; align?: 'left' | 'right'; className?: string }) {
  const [open, setOpen] = useState(false);
  if (!entry) return null;
  return (
    <span className={clsx('score-info relative inline-flex align-[-1px]', className)} data-open={open ? 'true' : 'false'} data-testid="score-info" data-score={entry.key}>
      <button
        type="button"
        aria-label={`About ${entry.label}`}
        aria-expanded={open}
        onClick={(ev) => {
          ev.stopPropagation();
          setOpen((v) => !v);
        }}
        onBlur={() => setOpen(false)}
        className="inline-flex border-0 bg-transparent p-0 text-faint hover:text-ink focus-visible:text-ink"
      >
        <InfoIcon />
      </button>
      <span
        role="tooltip"
        className={clsx(
          'score-info-pop absolute top-[calc(100%+4px)] z-20 hidden w-[260px] rounded border border-line bg-surface px-2.5 py-2 text-left font-sans text-[11.5px] leading-[1.45] font-normal tracking-normal whitespace-normal text-ink2 normal-case shadow-[0_4px_16px_rgba(0,0,0,.08)]',
          align === 'right' ? 'right-0' : 'left-0',
        )}
        data-testid="score-info-pop"
      >
        <span className="block font-medium text-ink">
          {entry.label}
          {entry.unit && <span className="num-unit">{entry.unit}</span>}
        </span>
        <span className="mt-1 block">
          <span className="text-muted">Produced by </span>
          {entry.producedBy.join(', ') || 'not recorded'}
        </span>
        <span className="mt-0.5 block">{entry.what}</span>
        {entry.inputs.length > 0 && (
          <span className="mt-0.5 block">
            <span className="text-muted">Inputs </span>
            {entry.inputs.join(', ')}
          </span>
        )}
        {(entry.higherIsBetter !== null || entry.rankingOnly) && (
          <span className="mt-0.5 block text-muted">
            {[entry.higherIsBetter === true ? 'higher is better' : entry.higherIsBetter === false ? 'lower is better' : null, entry.rankingOnly ? 'ranking score, compare within this run only' : null]
              .filter(Boolean)
              .join(' · ')}
          </span>
        )}
      </span>
    </span>
  );
}
