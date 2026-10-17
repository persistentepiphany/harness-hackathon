'use client';

// Single-job view (prototype `isRun` block): header with live elapsed time, layer strip, live log,
// executors with docking parameters, inputs and the verdict once the job is done.

import { useEffect, useMemo } from 'react';
import { ErrorState, Spinner } from '@/components/ui';
import { useJob, useJobLog, useRunRecord, useTasks, useTools } from '@/lib/hooks';
import { checkTotals, jobError, layerCells, layerStrip, verdictMeta } from '@/lib/selectors/jobs';
import { currentStep, executorRows, inputLines, jobVerdictCounts, runEndLine, runHeaderModel, runStatus } from '@/lib/selectors/run';
import { ExecutorList } from './ExecutorList';
import { JobInputs, JobVerdict } from './JobSide';
import { LayerStrip } from './LayerStrip';
import { LogPanel } from './LogPanel';
import { RunHeader } from './RunHeader';
import { useElapsed } from './useElapsed';

export function JobScreen({ jobId }: { jobId: string | null }) {
  const job = useJob(jobId);
  const runId = job.data ? job.data.runId || job.data.id : null;
  const record = useRunRecord(runId);
  const log = useJobLog(jobId);
  const register = useTools();
  const tasks = useTasks();
  // the run_end line: the clock stops at its time and the job and record are read again at once
  const runEnd = useMemo(() => runEndLine(log.data), [log.data]);
  const elapsed = useElapsed(job.data, runEnd?.ms);

  // a queued live run may not have a record yet: read it again once the job starts or ends
  const status = job.data?.status;
  const reloadRecord = record.reload;
  const reloadJob = job.reload;
  useEffect(() => {
    if (status === 'running' || status === 'done' || status === 'failed') reloadRecord();
  }, [status, reloadRecord]);
  const runEndSeq = runEnd?.seq;
  useEffect(() => {
    if (runEndSeq === undefined) return;
    reloadJob();
    reloadRecord();
  }, [runEndSeq, reloadJob, reloadRecord]);

  // the log stream ended without the run ending (`stale` for a job waiting for a slot, `missing`
  // before events.jsonl exists): open it again while the job is queued or running
  const { ended: logEnded, endReason, restart: restartLog } = log;
  useEffect(() => {
    if (!logEnded || !endReason || endReason === 'run_end') return;
    if (status !== 'queued' && status !== 'running') return;
    const t = setTimeout(restartLog, 2000);
    return () => clearTimeout(t);
  }, [logEnded, endReason, status, restartLog]);

  if (!job.data) {
    return (
      <main className="mx-auto flex w-full max-w-[1160px] animate-fade-up flex-col gap-7 px-6 pt-11 pb-20" data-testid="page-job" data-state={job.error ? 'error' : 'loading'}>
        {job.error ? (
          <ErrorState error={job.error} title={job.error.status === 404 ? `No job ${jobId}` : 'Cannot load the job'} onRetry={job.reload} />
        ) : (
          <div className="flex items-center gap-2 text-muted">
            <Spinner /> loading job
          </div>
        )}
      </main>
    );
  }

  const j = job.data;
  const rec = record.data;
  const cells = layerCells(j, rec);
  const totals = checkTotals(rec);
  const header = runHeaderModel(j, rec, register.data, tasks.data);
  const st = runStatus(j, cells, { total: rec ? totals.total : (j.checksTotal ?? 0) });
  const outcome = j.verdict ?? rec?.verdict.outcome ?? null;
  const done = j.status === 'done';
  const err = jobError(j);
  const showRecordError = record.error && !record.data && j.status !== 'queued';

  return (
    <main className="mx-auto flex w-full max-w-[1160px] animate-fade-up flex-col gap-7 px-6 pt-11 pb-20" data-testid="page-job" data-state={j.status}>
      <RunHeader model={header} status={st} elapsedMs={elapsed} reportHref={done ? `/reports/${encodeURIComponent(runId ?? j.id)}` : null} />
      <LayerStrip layers={layerStrip(cells)} />
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(280px,360px)] items-start gap-8">
        <LogPanel
          lines={log.data}
          header={currentStep(j, log.data)}
          emptyText={j.status === 'queued' ? 'Waiting for a slot.' : log.loading ? 'Connecting to the log.' : 'No log lines yet.'}
          status={log.ended ? 'ended' : log.status}
          error={log.error}
          sources={rec?.sources}
        />
        <div className="flex flex-col gap-[22px]">
          <ExecutorList rows={executorRows(j, rec, register.data)} />
          <JobInputs lines={inputLines(rec, j)} />
          {showRecordError && <ErrorState error={record.error} title="Run record unavailable" onRetry={record.reload} />}
          {done && <JobVerdict meta={verdictMeta(outcome)} outcome={outcome} claim={rec?.claim ?? ''} counts={jobVerdictCounts(j, rec, totals)} />}
          {j.status === 'failed' && (
            <JobVerdict meta={{ label: 'Failed', tone: 'stop' }} outcome="failed" claim={rec?.claim ?? ''} counts={jobVerdictCounts(j, rec, totals)} error={err} />
          )}
        </div>
      </div>
    </main>
  );
}
