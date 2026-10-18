'use client';

// Stage switcher at the top of the check column: Inputs · Applicability · Outputs, each with its
// counts and a dot. The selected stage lists all of its checks below, one flat list.

import clsx from 'clsx';
import { assessmentOf, checkSources, stageItems, type StageId } from '@/lib/selectors/report';
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
    <div className={clsx('grid grid-cols-3 gap-[3px] rounded-card border border-line bg-surface p-[3px]', className)} role="tablist" aria-label="Check stage" data-testid="stage-switcher">
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
            className={clsx('flex min-w-0 flex-col items-start gap-0.5 rounded-[6px] border-0 px-2.5 py-2 text-left transition-colors duration-200 sm:px-3.5', on ? 'bg-ink text-white' : 'bg-transparent text-ink hover:bg-canvas')}
          >
            <span className="flex w-full items-center gap-2">
              {s.running ? (
                <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-accent" />
              ) : (
                <ResultDot result={s.dot} size={7} hollow={s.dot === null || s.dot === 'pending' || s.dot === 'reported' || s.dot === 'skip'} className="top-0" />
              )}
              <span className="truncate text-[13px] font-semibold">{s.label}</span>
            </span>
            <span className={clsx('flex flex-wrap gap-x-2 text-[11.5px] tabular-nums sm:pl-[15px]', on ? 'text-white/75' : 'text-muted')} data-testid="stage-counts">
              {(['pass', 'warn', 'stop', 'pending', 'na'] as const)
                .filter((k) => c[k] > 0)
                .map((k) => (
                  <span key={k} data-count={k}>
                    {c[k]} {k === 'na' ? 'n/a' : k}
                  </span>
                ))}
              {!(c.pass || c.warn || c.stop || c.pending || c.na) && <span>no checks</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** Checks of the selected stage grouped by layer (or of one layer), with pending and not applicable counted apart. */
export interface StageChecksProps extends ReportBlockProps {
  value: StageSelection;
  onChange: (v: StageSelection) => void;
  /** Selected (expanded) check id. */
  selectedCheck?: string | null;
  onSelectCheck?: (id: string | null) => void;
}

export function StageChecks({ record, value, selectedCheck, onSelectCheck, className }: StageChecksProps) {
  const stage = stageItems(record).find((s) => s.id === value.stage);
  const idxs = (stage?.layerIdx ?? []).filter((idx) => value.layer === null || record.layers[idx].i === value.layer);
  const rows = idxs.flatMap((idx) => record.layers[idx].checks.map((c) => ({ c, layer: record.layers[idx].i })));
  const preRun = assessmentOf(record) === 'pre-run';
  return (
    <div className={className} data-testid="check-table" data-stage={value.stage}>
      <SectionTitle note={`${rows.length} checks`} className="mb-1.5">
        {stage?.label ?? 'Checks'}
      </SectionTitle>
      <div className="border-t border-line">
        {rows.map(({ c, layer }) => (
          <CheckRow key={c.id} c={c} layer={layer} preRun={preRun} sources={checkSources(record, c.id)} selected={selectedCheck === c.id} onSelect={onSelectCheck} />
        ))}
      </div>
      {!rows.length && (
        <div className="py-3 text-[12px] text-muted" data-testid="empty-state">
          {preRun && value.stage === 'outputs' ? 'pending · waits for predictions' : 'no checks in this stage'}
        </div>
      )}
    </div>
  );
}
