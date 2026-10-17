'use client';

// One job of the Jobs overview (prototype `jobCards`): number, name, task, models, inputs, claim,
// six-segment layer progress; verdict or status, elapsed time, checks, id on the right.

import clsx from 'clsx';
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { StatusDot } from '@/components/ui';
import { shortRunId } from '@/lib/format';
import { useRunRecord } from '@/lib/hooks';
import { jobCardModel } from '@/lib/selectors/jobs';
import type { Job, Task, Tool } from '@/lib/types';
import { LayerProgress } from './LayerProgress';
import { VERDICT_TEXT } from './tone';

export interface JobCardProps {
  job: Job;
  index: number;
  total: number;
  tasks?: Task[];
  register?: Tool[];
  /** Another job has the same name: show the short run id after the name. */
  showRunId?: boolean;
}

/**
 * True once the element has come within 600 px of the viewport (and from then on), so a long jobs
 * list does not read every run record at once. Without IntersectionObserver: true.
 */
function useSeen<T extends Element>(): [(el: T | null) => void, boolean] {
  const [seen, setSeen] = useState(() => typeof IntersectionObserver === 'undefined');
  const io = useRef<IntersectionObserver | null>(null);
  const ref = useCallback((el: T | null) => {
    io.current?.disconnect();
    io.current = null;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    io.current = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          io.current?.disconnect();
          io.current = null;
        }
      },
      { rootMargin: '600px 0px' },
    );
    io.current.observe(el);
  }, []);
  useEffect(() => () => io.current?.disconnect(), []);
  return [ref, seen];
}

export function JobCard({ job, index, total, tasks, register, showRunId }: JobCardProps) {
  // the record supplies inputs, claim and per-layer counts; the card renders from the job until
  // then, and reads it once the card is near the viewport
  const [cardRef, seen] = useSeen<HTMLAnchorElement>();
  const record = useRunRecord(seen ? job.runId || job.id : null);
  const m = jobCardModel(job, index, total, record.data, tasks, register);
  return (
    <Link
      ref={cardRef}
      href={m.href}
      data-testid="job-card"
      data-state={m.status}
      data-verdict={m.outcome ?? undefined}
      data-job={m.id}
      className="grid animate-fade-up grid-cols-[44px_minmax(0,1fr)_180px] items-start gap-6 border-t border-line bg-transparent pt-[22px] pb-6 text-ink hover:bg-surface hover:text-ink"
    >
      <div className="pt-[3px] font-mono text-[12px] text-muted">{m.num}</div>
      <div className="flex min-w-0 flex-col gap-3.5">
        <div className="text-[15px] font-semibold tracking-[-0.01em]">
          {m.name}
          {showRunId && (
            <span className="ml-2 font-mono text-[11.5px] font-normal text-faint" data-testid="job-card-run">
              {shortRunId(job.runId || job.id)}
            </span>
          )}
        </div>
        <div className="grid grid-cols-[72px_minmax(0,1fr)] gap-x-4 gap-y-[5px] text-[12.5px]">
          <span className="text-muted">Task</span>
          <span>{m.taskLong}</span>
          <span className="text-muted">Models</span>
          <span>{m.toolsLong}</span>
          <span className="text-muted">Inputs</span>
          <span className="font-mono text-[12px]">{m.inputs}</span>
          <span className="text-muted">Claim</span>
          <span className="text-pretty">{m.claim}</span>
        </div>
        <LayerProgress segments={m.segments} />
      </div>
      <div className="flex flex-col items-end gap-1.5 pt-0.5">
        {m.verdict ? (
          <span className={clsx('text-[14px] font-semibold', VERDICT_TEXT[m.verdict.tone])} data-testid="verdict" data-state={m.outcome ?? undefined}>
            {m.verdict.label}
          </span>
        ) : (
          <span className={clsx('flex items-center gap-[7px] text-[13px] font-medium', m.status === 'failed' ? 'text-stop' : 'text-ink')} data-testid="job-status" data-state={m.status}>
            <StatusDot state={m.status} size={6} />
            {m.statusLabel}
          </span>
        )}
        <span className="font-mono text-[12px] text-ink2">{m.elapsed}</span>
        {m.checks.text && <span className="text-right text-[11.5px] text-muted">{m.checks.text}</span>}
        {m.checks.skip && <span className="-mt-1 text-right text-[11.5px] text-faint">{m.checks.skip}</span>}
        {m.error && (
          <span className="line-clamp-2 text-right text-[11.5px] text-stop" title={m.error}>
            {m.error}
          </span>
        )}
        <span className="font-mono text-[10.5px] text-faint">{m.id}</span>
      </div>
    </Link>
  );
}
