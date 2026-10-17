'use client';

// Finished runs as underlined tabs above the report and ensemble headers (prototype reportPicker).

import clsx from 'clsx';
import Link from 'next/link';
import { duplicateLabels, fmtDateTime, shortRunId } from '@/lib/format';
import { useJobs } from '@/lib/hooks';

/** Most recent finished runs shown; the current run is always included. */
const MAX_PICKS = 5;


export function ReportPicker({ runId, suffix = '' }: { runId: string; suffix?: string }) {
  const jobs = useJobs();
  const all = jobs.data ?? [];
  const done = all.filter((j) => j.status === 'done');
  const head = done.slice(0, MAX_PICKS);
  const current = all.find((j) => j.runId === runId);
  const list = head.some((j) => j.runId === runId) || !current ? head : [...head.slice(0, MAX_PICKS - 1), current];
  if (!list.length) return null;
  const dups = duplicateLabels(list, (j) => j.name);
  return (
    <div className="mb-3.5 flex flex-wrap items-baseline gap-1.5" data-testid="report-picker">
      {list.map((j) => {
        const on = j.runId === runId;
        const dup = dups.has(j.name);
        return (
          <Link
            key={j.id}
            href={`/reports/${encodeURIComponent(j.runId)}${suffix}`}
            title={`${j.runId}${j.createdAt ? ` · ${fmtDateTime(j.createdAt)}` : ''}`}
            data-testid="report-pick"
            data-state={on ? 'active' : 'idle'}
            className={clsx('mr-3.5 border-b-[1.5px] px-0 pt-0.5 pb-[5px] text-[12.5px] font-medium', on ? 'border-ink text-ink hover:text-ink' : 'border-transparent text-muted hover:text-ink')}
          >
            {j.name}
            {dup && <span className="ml-1 font-mono text-[11px] font-normal text-faint">{shortRunId(j.runId)}</span>}
          </Link>
        );
      })}
      {done.length > list.length && (
        <Link href="/jobs" className="pt-0.5 pb-[5px] font-mono text-[11.5px] text-muted hover:text-ink" data-testid="report-pick-all">
          all jobs ({done.length})
        </Link>
      )}
    </div>
  );
}
