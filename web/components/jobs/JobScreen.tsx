'use client';

// Single-job view as a story of stacked blocks that fill in as the run progresses: provenance,
// inputs, preliminary input checks (layers 1–3), pose production (executors, per-seed timings,
// PyMOL thumbnails), output checks (layers 4–5), and the report card once the job is done. Header
// with the live elapsed time and the layer strip on top; executors and the live log alongside.

import { useEffect, useMemo } from 'react';
import { ErrorState, Spinner } from '@/components/ui';
import { DASH, fmtSeconds } from '@/lib/format';
import { useCatalog, useJob, useJobLog, useRunRecord, useTasks, useTools } from '@/lib/hooks';
import {
  assessmentOf,
  checkRows,
  checkTotals,
  engagedLine,
  executionOf,
  executionViews,
  isExecutionActive,
  jobError,
  layerCells,
  layerStrip,
  pendingOutputChecks,
  poseThumbs,
  sourceCounts,
  sourceRows,
  stageTimings,
  verdictMeta,
} from '@/lib/selectors/jobs';
import { currentStep, executorRows, findLigand, findProtein, jobVerdictCounts, runEndLine, runHeaderModel, runStatus } from '@/lib/selectors/run';
import type { Catalog, Job, UiRunRecord } from '@/lib/types';
import { CheckRows } from './CheckRows';
import { ExecutionPanel, StageBar } from './ExecutionPanel';
import { ExecutorList } from './ExecutorList';
import { LayerStrip } from './LayerStrip';
import { LogPanel } from './LogPanel';
import { PoseThumbs } from './PoseThumbs';
import { ReportCard } from './ReportCard';
import { RunHeader } from './RunHeader';
import { SourceRows } from './SourceRows';
import { StoryBlock, type StoryState } from './StoryBlock';
import { useElapsed } from './useElapsed';

/** Resolved inputs: target with its length, partner, ligand, reference, pH, seeds. */
function inputRows(record: UiRunRecord | null | undefined, job: Job, catalog: Catalog | null | undefined): { k: string; v: string; title?: string }[] {
  const inp = record?.inputs ?? {};
  const rows: { k: string; v: string; title?: string }[] = [];
  const prot = (acc: string | null | undefined) => {
    const p = findProtein(catalog, acc);
    return p ? `${p.label} · ${p.accession}${p.length ? ` · ${p.length.toLocaleString('en-US')} aa` : ''}` : (acc ?? DASH);
  };
  if (inp.target) rows.push({ k: 'Target', v: prot(inp.target) });
  if (inp.partner) rows.push({ k: 'Partner', v: prot(inp.partner) });
  if (inp.ligand) {
    const l = findLigand(catalog, inp.ligand);
    rows.push({ k: 'Ligand', v: l ? `${l.names[0]}${l.ccd ? ` · ${l.ccd}` : ''}${l.formula ? ` · ${l.formula}` : ''}` : inp.ligand, title: inp.ligand });
  }
  if (inp.reference) rows.push({ k: 'Reference', v: inp.reference });
  if (inp.ph !== undefined && inp.ph !== null) rows.push({ k: 'pH', v: String(inp.ph) });
  const seeds = inp.seeds ?? (job.seeds || undefined);
  if (seeds) rows.push({ k: 'Seeds', v: `${seeds}${inp.samples ? ` × ${inp.samples} samples` : ''}` });
  if (inp.assembly) rows.push({ k: 'Assembly', v: inp.assembly });
  return rows;
}

export function JobScreen({ jobId }: { jobId: string | null }) {
  const job = useJob(jobId);
  const runId = job.data ? job.data.runId || job.data.id : null;
  const record = useRunRecord(runId);
  const log = useJobLog(jobId);
  const register = useTools();
  const tasks = useTasks();
  const catalog = useCatalog();
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
  // the record carries renders and per-pose checks: read it again when an artifact line streams
  const artifacts = useMemo(() => log.data.filter((l) => l.kind === 'artifact').length, [log.data]);
  useEffect(() => {
    if (artifacts) reloadRecord();
  }, [artifacts, reloadRecord]);

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
      <main className="mx-auto flex w-full max-w-[1160px] animate-fade-up flex-col gap-7 px-4 pt-11 pb-20 sm:px-6" data-testid="page-job" data-state={job.error ? 'error' : 'loading'}>
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
  const failed = j.status === 'failed';
  const finished = done || failed;
  const err = jobError(j);
  const showRecordError = record.error && !record.data && j.status !== 'queued';
  const reportHref = done ? `/reports/${encodeURIComponent(runId ?? j.id)}` : null;

  // ---- story data
  const fetchLines = log.data.filter((l) => l.kind === 'fetch' || l.kind === 'cache').length || null;
  const layer0Started = finished || cells[0].state !== 'pending';
  const sources = sourceRows(rec?.sources, fetchLines, layer0Started && (finished || cells[0].state === 'done' || fetchLines !== null));
  const inputs = inputRows(rec, j, catalog.data);
  const preChecks = checkRows(rec, 1, 3);
  const outChecks = checkRows(rec, 4, 5).filter((c) => !(c.result === 'skip' && /pending input/.test(c.value)));
  const pending = pendingOutputChecks(rec);
  const execs = executionOf(j, rec);
  const execActive = isExecutionActive(execs);
  const views = executionViews(execs);
  const engaged = engagedLine(execs);
  const stages = stageTimings(j, rec, execs);
  const thumbs = poseThumbs(rec);
  const preRun = assessmentOf(j, rec) === 'pre-run';
  const pastInputs = finished || j.layerIdx >= 4;
  const layerState = (from: number, to: number): StoryState => (cells.slice(from, to + 1).some((c) => c.state === 'running') ? 'active' : cells.slice(from, to + 1).every((c) => c.state === 'done' || c.state === 'not_run') ? 'done' : 'waiting');

  type Block = { key: string; show: boolean; node: (order: number) => React.ReactNode };
  const blocks: Block[] = [
    {
      key: 'provenance',
      show: sources.length > 0,
      node: (o) => (
        <StoryBlock key="provenance" step={1} order={o} title="Provenance" state={layerState(0, 0)} meta={sourceCounts(rec, sources)} data-testid="story-provenance">
          <SourceRows rows={sources} />
        </StoryBlock>
      ),
    },
    {
      key: 'inputs',
      show: inputs.length > 0 && (finished || cells[0].state === 'done' || sources.length > 0),
      node: (o) => (
        <StoryBlock key="inputs" step={2} order={o} title="Inputs" state={cells[0].state === 'done' || finished ? 'done' : 'active'} data-testid="job-inputs">
          <dl className="m-0 grid grid-cols-[88px_minmax(0,1fr)] gap-x-3 gap-y-[3px] text-[12px]">
            {inputs.map((r) => (
              <div key={r.k} className="contents">
                <dt className="text-muted">{r.k}</dt>
                <dd className="m-0 truncate font-mono text-[11.5px] text-ink2" title={r.title ?? r.v}>
                  {r.v}
                </dd>
              </div>
            ))}
          </dl>
        </StoryBlock>
      ),
    },
    {
      key: 'input-checks',
      show: preChecks.length > 0,
      node: (o) => (
        <StoryBlock key="input-checks" step={3} order={o} title="Input checks" state={layerState(1, 3)} meta={`${preChecks.length} checks · layers 1–3`} data-testid="story-input-checks">
          <CheckRows rows={preChecks.filter((c) => c.layer <= 2)} label="Inputs" />
          <CheckRows rows={preChecks.filter((c) => c.layer === 3)} label="Applicability" />
        </StoryBlock>
      ),
    },
    {
      key: 'poses',
      show: execs.length > 0 || thumbs.length > 0 || pastInputs,
      node: (o) => (
        <StoryBlock
          key="poses"
          step={4}
          order={o}
          title="Pose production"
          state={execActive ? 'active' : preRun || !execs.length ? (pastInputs ? 'done' : 'waiting') : 'done'}
          meta={thumbs.length ? `${thumbs.length} pose${thumbs.length === 1 ? '' : 's'} rendered` : undefined}
          data-testid="story-poses"
        >
          {preRun ? (
            <div className="text-[12.5px] text-ink2" data-testid="pre-run-note">
              Pre-run check: no executor ran. {pending ? `${pending} output checks wait for predictions.` : ''}
            </div>
          ) : execs.length ? (
            <ExecutionPanel engaged={engaged} executions={views} />
          ) : (
            <div className="text-[12.5px] text-muted">No execution reported: the run checks outputs supplied with the manifest, if any.</div>
          )}
          <PoseThumbs thumbs={thumbs} progress={rec?.renderProgress} />
          <div className="mt-3">
            <StageBar stages={stages} />
          </div>
        </StoryBlock>
      ),
    },
    {
      key: 'output-checks',
      show: outChecks.length > 0 || (pastInputs && !execActive && (preRun || finished)),
      node: (o) => (
        <StoryBlock key="output-checks" step={5} order={o} title="Output checks" state={preRun ? 'done' : layerState(4, 5)} meta={outChecks.length ? `${outChecks.length} checks · layers 4–5` : pending ? `${pending} pending` : undefined} data-testid="story-output-checks">
          {outChecks.length ? (
            <CheckRows rows={outChecks} />
          ) : (
            <div className="text-[12.5px] text-muted">{pending ? `${pending} checks wait for predictions (pending input).` : 'Layers 4–5 did not run.'}</div>
          )}
        </StoryBlock>
      ),
    },
    {
      key: 'report',
      show: finished,
      node: (o) => {
        const meta = failed ? { label: 'Failed', tone: 'stop' as const } : verdictMeta(outcome);
        const counts = jobVerdictCounts(j, rec, totals);
        const assessed = rec?.verdict.assessedClaim;
        const numbers = [
          { k: 'Assessment', v: preRun ? 'pre-run' : (assessmentOf(j, rec) ?? DASH) },
          { k: 'Layers evaluated', v: rec?.evaluatedLayers?.length ? rec.evaluatedLayers.join(', ') : DASH },
          { k: 'Executors', v: engaged && !engaged.active ? engaged.text.replace(/ ran · .*$/, '') : preRun ? 'not run' : DASH },
          { k: 'Poses rendered', v: String(thumbs.length) },
          { k: 'Total time', v: fmtSeconds(j.elapsedMs) },
        ];
        if (pending) numbers.push({ k: 'Pending checks', v: String(pending) });
        return (
          <StoryBlock key="report" step={6} order={o} title="Report" state="done" data-testid="story-report">
            <ReportCard
              meta={meta}
              outcome={failed ? 'failed' : outcome}
              claimLabel={assessed ? 'Assessed:' : 'Claim tested:'}
              claim={assessed ?? rec?.claim ?? ''}
              statement={rec?.verdict.statement}
              counts={counts}
              numbers={numbers}
              href={reportHref}
              error={failed ? err : null}
            />
          </StoryBlock>
        );
      },
    },
  ];
  // while running, a block shows only after the one before it (the story fills in order)
  const visible: Block[] = [];
  for (const b of blocks) {
    if (!b.show) {
      if (!finished) break;
      continue;
    }
    visible.push(b);
  }

  return (
    <main className="mx-auto flex w-full max-w-[1160px] animate-fade-up flex-col gap-7 px-4 pt-11 pb-20 sm:px-6" data-testid="page-job" data-state={j.status}>
      <RunHeader model={header} status={st} elapsedMs={elapsed} reportHref={reportHref} />
      <LayerStrip layers={layerStrip(cells)} />
      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
        <div className="flex min-w-0 flex-col gap-5" data-testid="job-story">
          {j.status === 'queued' && !visible.length && <div className="text-[12.5px] text-muted">Queued. The story starts when the run gets a slot.</div>}
          {visible.map((b, i) => b.node(i))}
          {showRecordError && <ErrorState error={record.error} title="Run record unavailable" onRetry={record.reload} />}
        </div>
        <div className="flex min-w-0 flex-col gap-[22px] lg:sticky lg:top-[68px]">
          <ExecutorList rows={executorRows(j, rec, register.data)} />
          <LogPanel
            lines={log.data}
            header={currentStep(j, log.data)}
            emptyText={j.status === 'queued' ? 'Waiting for a slot.' : log.loading ? 'Connecting to the log.' : 'No log lines yet.'}
            status={log.ended ? 'ended' : log.status}
            error={log.error}
            sources={rec?.sources}
          />
        </div>
      </div>
    </main>
  );
}
