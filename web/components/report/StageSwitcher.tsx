'use client';

// Stage switcher beneath the viewer: Inputs (L0-L2) · Applicability (L3) · Outputs (L4-L5), each
// with its counts and a dot. The selected stage (or one layer of it) filters the check list below.

import clsx from 'clsx';
import { fmtMs } from '@/lib/format';
import { assessmentOf, breakdownText, layerBreakdown, stageItems, type StageId } from '@/lib/selectors/report';
import { CheckRow } from './CheckTable';
import { ResultDot, SectionTitle } from './parts';
import type { ReportBlockProps } from './types';

export interface StageSelection {
  stage: StageId;
  /** One layer number of the stage, or null for all of them. */
  layer: number | null;
}

export function StageSwitcher({ record, value, onChange, className }: ReportBlockProps & { value: StageSelection; onChange: (v: StageSelection) => void }) {
  const items = stageItems(record);
  return (
    <div className={clsx('grid grid-cols-3 rounded-card border border-line bg-surface p-[3px]', className)} role="tablist" aria-label="Check stage" data-testid="stage-switcher">
      {items.map((s) => {
        const on = s.id === value.stage;
        const c = s.counts;
        return (
          <button
            key={s.id}
            type="button"
            role="tab"
            aria-selected={on}
            onClick={() => onChange({ stage: s.id, layer: null })}
            data-testid="stage-tab"
            data-stage={s.id}
            data-state={s.dot ?? 'empty'}
            className={clsx('flex min-w-0 flex-col items-start gap-0.5 rounded-[6px] border-0 px-3.5 py-2 text-left transition-colors duration-150', on ? 'bg-ink text-white' : 'bg-transparent text-ink hover:bg-canvas')}
          >
            <span className="flex w-full items-center gap-2">
              {s.running ? (
                <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-accent" />
              ) : (
                <ResultDot result={s.dot} size={7} hollow={s.dot === null || s.dot === 'pending' || s.dot === 'reported' || s.dot === 'skip'} className="top-0" />
              )}
              <span className="text-[13px] font-semibold">{s.label}</span>
              <span className={clsx('font-mono text-[10.5px]', on ? 'text-white/60' : 'text-muted')}>{s.range}</span>
            </span>
            <span className={clsx('flex flex-wrap gap-x-2 pl-[15px] font-mono text-[10.5px] tabular-nums', on ? 'text-white/75' : 'text-ink2')} data-testid="stage-counts">
              <span data-count="pass" className={c.pass ? undefined : 'opacity-50'}>
                {c.pass} pass
              </span>
              <span data-count="warn" className={c.warn ? undefined : 'opacity-50'}>
                {c.warn} warn
              </span>
              <span data-count="stop" className={c.stop ? undefined : 'opacity-50'}>
                {c.stop} stop
              </span>
              <span data-count="pending" className={c.pending ? undefined : 'opacity-50'}>
                {c.pending} pending
              </span>
              {c.na > 0 && <span data-count="na">{c.na} n/a</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** Checks of the selected stage grouped by layer (or of one layer), with pending and not applicable counted apart. */
export function StageChecks({ record, value, onChange, className }: ReportBlockProps & { value: StageSelection; onChange: (v: StageSelection) => void }) {
  const stage = stageItems(record).find((s) => s.id === value.stage);
  const idxs = (stage?.layerIdx ?? []).filter((idx) => value.layer === null || record.layers[idx].i === value.layer);
  const total = idxs.reduce((n, idx) => n + record.layers[idx].checks.length, 0);
  const preRun = assessmentOf(record) === 'pre-run';
  return (
    <div className={className} data-testid="check-table" data-stage={value.stage} data-layer={value.layer ?? undefined}>
      <SectionTitle note={`${total} checks`} className="mb-1.5">
        <span className="flex flex-wrap items-baseline gap-x-3">
          <span>{stage?.label ?? 'Checks'}</span>
          {(stage?.layerIdx.length ?? 0) > 1 && (
            <span className="flex gap-1 text-[11.5px] font-normal" data-testid="stage-layer-filter">
              <button type="button" onClick={() => onChange({ stage: value.stage, layer: null })} aria-pressed={value.layer === null} className={clsx('rounded-[4px] border px-1.5 py-px', value.layer === null ? 'border-ink text-ink' : 'border-line text-muted hover:border-ink hover:text-ink')}>
                all
              </button>
              {stage?.layerIdx.map((idx) => {
                const L = record.layers[idx];
                const on = value.layer === L.i;
                return (
                  <button key={L.i} type="button" onClick={() => onChange({ stage: value.stage, layer: L.i })} aria-pressed={on} data-testid="stage-layer" data-layer={L.i} className={clsx('rounded-[4px] border px-1.5 py-px', on ? 'border-ink text-ink' : 'border-line text-muted hover:border-ink hover:text-ink')}>
                    L{L.i} {L.name}
                  </button>
                );
              })}
            </span>
          )}
        </span>
      </SectionTitle>
      {idxs.map((idx) => {
        const L = record.layers[idx];
        const b = layerBreakdown(record, idx);
        return (
          <div key={L.i} className="mb-4 last:mb-0" data-testid="stage-layer-group" data-layer={L.i}>
            <div className="flex items-baseline justify-between gap-3 border-b border-line pt-1 pb-1.5">
              <span className="text-[12.5px] font-medium">
                <span className="font-mono text-[11px] text-muted">L{L.i}</span> {L.name}
                {L.question && <span className="ml-2 text-[11.5px] font-normal text-muted">{L.question}</span>}
              </span>
              <span className="flex-none font-mono text-[10.5px] text-muted tabular-nums" data-testid="layer-breakdown">
                {breakdownText(b)}
                {L.durationMs !== undefined && ` · ${fmtMs(L.durationMs)}`}
              </span>
            </div>
            {(L.figures ?? []).length > 0 && (
              <div className="flex flex-wrap gap-x-5 gap-y-0.5 border-b border-line2 py-1.5 text-[11.5px]" data-testid="layer-figures">
                {(L.figures ?? []).map(([k, v]) => (
                  <span key={k}>
                    <span className="text-muted">{k}</span> <span className="font-mono tabular-nums">{v}</span>
                  </span>
                ))}
              </div>
            )}
            {L.checks.map((c) => (
              <CheckRow key={c.id} c={c} layer={L.i} preRun={preRun} />
            ))}
            {L.checks.length === 0 && (
              <div className="py-3 text-[12px] text-muted" data-testid="empty-state">
                {L.status === 'not_run' ? 'layer not run' : L.status === 'pending' ? 'pending' : 'no checks'}
              </div>
            )}
          </div>
        );
      })}
      {!idxs.length && (
        <div className="border-t border-line py-3 text-[12px] text-muted" data-testid="empty-state">
          no layers of this stage in the record
        </div>
      )}
    </div>
  );
}
