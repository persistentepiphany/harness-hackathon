import clsx from 'clsx';
import type { ReactNode } from 'react';
import type { DetailRow } from '@/lib/selectors/run';

/** Target or ligand detail card (prototype `td` / `ld`): title, mono subtitle, key/value grid. */
export function DetailCard({ title, sub, rows, ellipsis, 'data-testid': testId }: { title: ReactNode; sub: ReactNode; rows: DetailRow[]; ellipsis?: boolean; 'data-testid'?: string }) {
  return (
    <div className="mt-3.5 animate-fade-up rounded-card border border-line bg-surface px-[18px] py-4" data-testid={testId}>
      <div className="mb-2.5 flex items-baseline justify-between gap-3">
        <div className="text-[14px] font-semibold">
          {title} <span className="ml-1.5 font-mono text-[12px] font-normal text-muted">{sub}</span>
        </div>
      </div>
      <div className="grid animate-fade-in grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-x-[18px] gap-y-2.5 text-[12.5px]">
        {rows.map((r) => (
          <div key={r.k} className="min-w-0" data-testid="detail-row" data-missing={r.missing ? 'true' : undefined}>
            <div className="text-[11px] text-muted">{r.k}</div>
            <div
              title={ellipsis || r.missing ? (r.missing ? 'not in the catalog' : r.v) : undefined}
              className={clsx('mt-px font-mono text-[12px]', ellipsis && 'overflow-hidden text-ellipsis whitespace-nowrap', r.missing && 'text-faint')}
            >
              {r.v}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
