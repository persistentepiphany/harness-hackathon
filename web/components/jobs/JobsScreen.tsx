'use client';

// Jobs overview (prototype `isJobs` block): summary line, New run, one card per job, newest first.

import Link from 'next/link';
import { EmptyState, ErrorState, Spinner } from '@/components/ui';
import { duplicateLabels } from '@/lib/format';
import { useJobs, useTasks, useTools } from '@/lib/hooks';
import { jobsSummary } from '@/lib/selectors/jobs';
import { JobCard } from './JobCard';

export function JobsScreen() {
  const jobs = useJobs();
  const tasks = useTasks();
  const tools = useTools();
  const list = jobs.data ?? [];
  // runs with the same name carry a short run id after the name
  const dups = duplicateLabels(list, (j) => j.name || j.id);
  return (
    <main className="mx-auto flex w-full max-w-[1000px] animate-fade-up flex-col gap-2.5 px-6 pt-11 pb-20" data-testid="page-jobs">
      <div className="mb-3 flex items-baseline justify-between">
        <h1 className="m-0 text-[18px] font-semibold tracking-[-0.01em]">
          Jobs{' '}
          {jobs.data && (
            <span className="ml-2 text-[13px] font-normal text-muted" data-testid="jobs-summary">
              {jobsSummary(list)}
            </span>
          )}
        </h1>
        <Link
          href="/runs/new"
          className="rounded border border-line bg-transparent px-[11px] py-1.5 text-[12.5px] leading-[normal] font-medium text-ink2 hover:border-ink hover:text-ink"
        >
          New run
        </Link>
      </div>
      {jobs.error && <ErrorState error={jobs.error} title="Cannot list jobs" onRetry={jobs.reload} />}
      {jobs.loading && !jobs.data && (
        <div className="flex items-center gap-2 text-muted" data-testid="jobs-loading">
          <Spinner /> loading jobs
        </div>
      )}
      {jobs.data && list.length === 0 && <EmptyState data-testid="no-jobs">No jobs yet.</EmptyState>}
      {list.map((j, i) => (
        <JobCard key={j.id} job={j} index={i} total={list.length} tasks={tasks.data} register={tools.data} showRunId={dups.has(j.name || j.id)} />
      ))}
    </main>
  );
}
