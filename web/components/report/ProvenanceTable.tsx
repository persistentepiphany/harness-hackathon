'use client';

// Provenance of every input (record.sources): source, accession, release, retrieval time, fetch
// time, sha256 (12 characters, full value in title), plus a summary line. Print wraps the text
// cells (no tooltip on paper); the sha256 stays shortened.

import clsx from 'clsx';
import { fmtMs, fmtSha, fmtTime, SEP } from '@/lib/format';
import { BlockLabel, NotComputed } from './parts';
import type { ReportBlockProps } from './types';

export function ProvenanceTable({ record, variant, className }: ReportBlockProps) {
  const print = variant === 'print';
  const src = record.sources;
  const cached = src.filter((s) => s.cached).length;
  const msKnown = src.filter((s) => typeof s.ms === 'number');
  const summary = [
    `${src.length} objects`,
    `${cached} cached`,
    `${src.length - cached} network`,
    msKnown.length ? fmtMs(msKnown.reduce((a, s) => a + (s.ms ?? 0), 0)) : null,
  ]
    .filter(Boolean)
    .join(SEP);
  const cols = 'grid-cols-[100px_minmax(0,1fr)_80px_70px_50px_110px]';
  return (
    <div className={className} data-testid="provenance-table">
      <BlockLabel print={print}>Provenance · {summary}</BlockLabel>
      <div className={clsx('border-t', print ? 'border-ink' : 'border-line')}>
        <div className={clsx('grid gap-2 border-b border-line py-[3px] font-mono text-muted', cols, print ? 'text-[7.5pt]' : 'text-[10.5px]')}>
          <span>source</span>
          <span>accession</span>
          <span>release</span>
          <span>retrieved</span>
          <span className="text-right">time</span>
          <span>sha256</span>
        </div>
        {src.map((s, i) => (
          <div
            key={s.id ?? `${s.source}:${s.accession}:${i}`}
            className={clsx('grid items-baseline gap-2 border-b border-line2 py-[3px] font-mono text-ink2', cols, print ? 'text-[8pt]' : 'text-[11px]')}
            data-testid="provenance-row"
            title={s.supplies}
          >
            <span className={clsx(print ? 'break-words' : 'truncate', 'text-ink')} title={s.source}>
              {s.source}
            </span>
            <span className={print ? 'break-words' : 'truncate'} title={s.url ?? s.accession}>
              {s.accession}
            </span>
            <span className={print ? 'break-words' : 'truncate'}>{s.release}</span>
            <span>{fmtTime(s.retrievedAt)}</span>
            <span className={clsx('text-right', s.cached ? 'text-muted' : 'text-ink')}>{typeof s.ms === 'number' ? fmtMs(s.ms) : s.cached ? 'cache' : '–'}</span>
            <span className="text-muted" title={s.sha256}>
              {fmtSha(s.sha256, { ellipsis: true })}
            </span>
          </div>
        ))}
        {!src.length && <NotComputed what="sources" print={print} />}
      </div>
    </div>
  );
}
