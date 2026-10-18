'use client';

// PoseBusters battery (stats.posebusters). Absent: "not computed". Present but empty (task without
// a ligand): hidden, as in the prototype.

import clsx from 'clsx';
import { blockSource, sourceLabel } from '@/lib/selectors/report';
import { NotComputed, SectionTitle, BlockLabel } from './parts';
import type { ReportBlockProps } from './types';

export function PoseBustersGrid({ record, variant, className }: ReportBlockProps) {
  const pb = record.stats.posebusters;
  const print = variant === 'print';
  if (pb && pb.length === 0) return null;
  const src = blockSource(record, 'posebusters');
  const pose = typeof src?.pose === 'string' ? src.pose : undefined;
  const summary = pb ? `${pb.filter((p) => p.pass).length}/${pb.length} tests · ${pose ?? 'medoid pose'}` : undefined;
  return (
    <div className={className} data-testid="posebusters" data-state={pb ? 'computed' : 'not-computed'} title={sourceLabel(src)}>
      {print ? <BlockLabel print>PoseBusters{summary ? ` · ${summary}` : ''}</BlockLabel> : <SectionTitle note={summary}>Physical validity · PoseBusters</SectionTitle>}
      {pb ? (
        <div
          className={clsx('grid border-t', print ? 'grid-cols-2 gap-x-5 gap-y-0.5 border-ink pt-1.5' : 'gap-x-4 gap-y-1 border-line pt-2')}
          style={print ? undefined : { gridTemplateColumns: 'repeat(auto-fill,minmax(210px,1fr))' }}
        >
          {pb.map((p) => (
            <div key={p.test} className={clsx('flex justify-between gap-2 font-mono', print ? 'py-px text-[8pt]' : 'py-1 text-[11px]')} data-testid="pb-test" data-state={p.pass ? 'pass' : 'stop'}>
              <span className="flex min-w-0 items-center gap-[7px] text-ink2">
                <span className={clsx('flex-none rounded-full', print ? 'h-[5px] w-[5px]' : 'h-1.5 w-1.5', p.pass ? 'bg-pass' : 'bg-stop')} />
                <span className="truncate" title={p.test}>
                  {p.test}
                </span>
              </span>
              <span className="flex-none text-muted">{p.value}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="border-t border-line">
          <NotComputed what="posebusters" print={print} record={record} />
        </div>
      )}
    </div>
  );
}
