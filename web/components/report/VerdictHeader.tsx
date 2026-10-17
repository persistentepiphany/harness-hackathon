'use client';

// Verdict scoped to the claim (prototype report header): outcome label (supported, narrowed,
// refused, incomplete, not assessed, or in progress), the claim tested, the run metadata grid and
// the verdict statement. A pre-run record (nothing predicted) reads "Not assessed" with what was
// assessed; it is never styled supported or narrowed.

import clsx from 'clsx';
import type { ReactNode } from 'react';
import { fmtDateTime, isMissing } from '@/lib/format';
import { verdictView } from '@/lib/selectors/report';
import { recordTools } from '@/lib/tools';
import type { ReportBlockProps } from './types';

export interface VerdictHeaderProps extends ReportBlockProps {
  /** Run picker shown above the verdict (report and ensemble pages). */
  picker?: ReactNode;
  /** Buttons on the right. */
  actions?: ReactNode;
  /** Show the run metadata grid (default true). */
  meta?: boolean;
}

function Meta({ label, children, mono }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div>
      <div className="mb-[3px] text-[10.5px] tracking-[.06em] text-muted uppercase">{label}</div>
      <div className={mono ? 'font-mono text-[12px]' : undefined}>{children}</div>
    </div>
  );
}

export function VerdictHeader({ record, tools, picker, actions, meta = true, variant, className }: VerdictHeaderProps) {
  const v = verdictView(record);
  const print = variant === 'print';
  const rt = recordTools(record, tools);
  const { inputs } = record;
  const sampling = isMissing(inputs.seeds) ? '–' : `${inputs.seeds} seeds${isMissing(inputs.samples) ? '' : ` × ${inputs.samples} samples`}`;
  const completed = record.record.finishedAt ?? (record.status && record.status !== 'done' ? undefined : record.createdAt);
  const statement = record.verdict.statement;
  const claim = record.verdict.claim || record.claim;

  return (
    <div className={clsx('flex flex-col gap-3', className)}>
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0 flex-1">
          {picker}
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1" data-testid="verdict" data-state={v.state} data-assessment={v.preRun ? 'pre-run' : 'full'}>
            <span className={clsx('font-semibold', print ? 'text-[15pt]' : 'text-[22px] tracking-[-0.015em]')} style={{ color: v.color }} data-testid="verdict-label">
              {v.label}
            </span>
            <span className={clsx('text-muted', print ? 'text-[8.5pt]' : 'text-[11px] tracking-[.06em] uppercase')}>Claim tested</span>
            <span className={print ? 'text-[11pt]' : 'text-[15px]'} data-testid="verdict-claim">
              “{claim}”
            </span>
          </div>
          {v.preRun && (
            <div className={clsx('mt-1.5 text-ink2', print ? 'text-[9pt]' : 'text-[12.5px]')} data-testid="pre-run-note">
              <span className="font-medium text-ink">Pre-run check · nothing was predicted</span>
              {v.assessed && (
                <>
                  <span className="text-muted"> · assessed: </span>
                  <span data-testid="assessed-claim">{v.assessed}</span>
                </>
              )}
              {v.pending > 0 && <span className="text-muted"> · {v.pending} output checks pending</span>}
            </div>
          )}
          {meta && (
            <div className="mt-4 grid grid-cols-[repeat(2,minmax(150px,max-content))] gap-x-8 gap-y-2.5 text-[12.5px]">
              <Meta label="Task">{record.taskName || record.task}</Meta>
              <Meta label="Models">
                {rt.length
                  ? rt.map((t, i) => {
                      const ran = t.ran === true || t.ranBy === 'harness' || t.ranBy === 'external';
                      return (
                        <span key={t.id} className={ran ? undefined : 'text-muted'} data-testid="model" data-state={ran ? 'exercised' : 'declared'}>
                          {i > 0 && ', '}
                          {t.name}
                          {t.version ? ` ${t.version}` : ''}
                          {t.ranBy === 'external' ? ' (outputs supplied)' : ran ? '' : ' (declared, not run)'}
                        </span>
                      );
                    })
                  : '–'}
              </Meta>
              <Meta label="Inputs" mono>
                {[inputs.target, inputs.partner, inputs.reference].filter((x) => !isMissing(x)).join(' · ') || '–'}
              </Meta>
              <Meta label="Sampling">{sampling}</Meta>
              <Meta label="Run" mono>
                <span title={record.record.runId ? `harness run ${record.record.runId}` : undefined}>{record.id}</span>
              </Meta>
              <Meta label={completed ? 'Completed' : 'Started'}>{fmtDateTime(completed ?? record.record.startedAt ?? record.createdAt)}</Meta>
              {v.scope && (
                <Meta label="Scope" mono>
                  <span data-testid="verdict-scope">{v.scope}</span>
                </Meta>
              )}
            </div>
          )}
        </div>
        {actions && <div className="flex flex-none gap-2">{actions}</div>}
      </div>
      {statement && (
        <p className={clsx('m-0 max-w-[880px] text-ink2', print ? 'text-[9pt]' : 'text-[12.5px]')} data-testid="verdict-statement">
          {statement}
        </p>
      )}
    </div>
  );
}
