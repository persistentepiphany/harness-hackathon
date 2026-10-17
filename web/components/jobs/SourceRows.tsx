import clsx from 'clsx';
import type { SourceRowView } from '@/lib/selectors/jobs';

/** Provenance rows: source, accession, release, short sha256, cached or fetched, time. */
export function SourceRows({ rows }: { rows: SourceRowView[] }) {
  return (
    <div className="flex flex-col" data-testid="story-sources">
      {rows.map((r) => (
        <div
          key={r.key}
          data-testid="story-source"
          data-state={r.cached === null ? 'unknown' : r.cached ? 'cached' : 'fetched'}
          className="grid animate-fade-in grid-cols-[minmax(0,150px)_minmax(0,1fr)_auto] items-baseline gap-x-3 border-t border-line2 py-[5px] text-[12px] max-sm:grid-cols-[minmax(0,1fr)_auto]"
        >
          <span className="truncate font-medium" title={r.source}>
            {r.source}
          </span>
          <span className="min-w-0 truncate font-mono text-[11.5px] text-ink2 max-sm:order-3 max-sm:col-span-2" title={`${r.accession} · ${r.release} · sha256 ${r.shaTitle}`}>
            {r.accession} <span className="text-muted">· {r.release} · {r.sha}</span>
          </span>
          <span className={clsx('text-right font-mono text-[11px] whitespace-nowrap', r.cached ? 'text-muted' : 'text-ink2')}>
            {r.cached === null ? '' : r.cached ? 'cached' : 'fetched'} {r.ms}
          </span>
        </div>
      ))}
    </div>
  );
}
