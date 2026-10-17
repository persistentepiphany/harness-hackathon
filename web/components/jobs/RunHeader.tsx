'use client';

// Single-job header (prototype `rj`): back link, name, task / models / sampling / run id; elapsed
// time in mono 30px (ticking while the job runs), status line and Open report.

import clsx from 'clsx';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { StatusDot } from '@/components/ui';
import { fmtSeconds } from '@/lib/format';
import type { RunHeaderModel, RunStatusModel } from '@/lib/selectors/run';

export interface RunHeaderProps {
  model: RunHeaderModel;
  status: RunStatusModel;
  elapsedMs: number | undefined;
  reportHref: string | null;
}

function Meta({ label, children, mono }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div>
      <div className="mb-0.5 text-[10.5px] tracking-[0.06em] text-muted uppercase">{label}</div>
      <div className={mono ? 'font-mono text-[12px]' : undefined}>{children}</div>
    </div>
  );
}

export function RunHeader({ model, status, elapsedMs, reportHref }: RunHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4" data-testid="run-header">
      <div>
        <Link href="/jobs" className="mb-2 inline-block text-[12px] leading-[normal] text-muted hover:text-ink">
          ← All jobs
        </Link>
        <h1 className="m-0 text-[18px] font-semibold tracking-[-0.01em]" data-testid="job-name">
          {model.name}
        </h1>
        <div className="mt-3 grid grid-cols-[repeat(auto-fit,minmax(150px,max-content))] gap-x-7 gap-y-2 text-[12.5px]">
          <Meta label="Task">{model.taskName}</Meta>
          <Meta label="Models">{model.models}</Meta>
          <Meta label="Sampling">{model.sampling}</Meta>
          <Meta label="Run" mono>
            <span title={model.harnessRunId ? `harness run ${model.harnessRunId}` : undefined}>{model.runId}</span>
          </Meta>
        </div>
      </div>
      <div className="text-right">
        <div className="font-mono text-[30px] leading-none font-medium tracking-[-0.02em] tabular-nums" data-testid="elapsed">
          {fmtSeconds(elapsedMs)}
        </div>
        <div
          className={clsx('mt-1.5 flex items-center justify-end gap-[7px] text-[12px]', status.tone === 'pass' ? 'text-pass' : status.tone === 'stop' ? 'text-stop' : 'text-ink2')}
          data-testid="job-status"
          data-state={status.dot}
        >
          <StatusDot state={status.dot} size={6} />
          {status.label}
        </div>
        {reportHref && (
          <Link
            href={reportHref}
            data-testid="open-report"
            className="mt-2.5 inline-block rounded bg-ink px-3 py-[7px] text-[12.5px] leading-[normal] font-medium text-white hover:text-white"
          >
            Open report
          </Link>
        )}
      </div>
    </div>
  );
}
