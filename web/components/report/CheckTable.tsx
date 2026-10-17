'use client';

// Checks of one layer (prototype "Checks for selected layer"): result dot, name, evidence with
// `measured cmp threshold`, id · tool · gate · ms, result. Not-implemented checks are muted.

import clsx from 'clsx';
import { fmtMs, measuredVsThreshold, pairMeasurement, thresholdText } from '@/lib/format';
import { assessmentOf, defaultLayerIndex, isNotApplicable, isNotImplemented, isPendingInput, RESULT_COLOR } from '@/lib/selectors/report';
import type { UiCheck } from '@/lib/types';
import { ResultDot, SectionTitle } from './parts';
import type { ReportBlockProps } from './types';

export interface CheckTableProps extends ReportBlockProps {
  /** Index into record.layers (default: the layer the report opens on). */
  layer?: number;
  /** Explicit check list instead of a layer (e.g. warned or stopped checks). */
  checks?: UiCheck[];
  /** Title over the table (default: the layer name; null hides it). */
  title?: string | null;
}

function thresholdTitle(c: UiCheck): string | undefined {
  const pair = pairMeasurement(c);
  if (pair) return `threshold origin: ${pair.t.origin} · evidence level ${pair.t.evidenceLevel}`;
  if (c.threshold) return `threshold ${c.threshold.value} · ${c.threshold.origin} · ${c.threshold.evidenceLevel}`;
  return undefined;
}

/** Result word of a row: skips read `pending` (waiting for predictions) or `n/a` (not applicable). */
export function checkResultText(c: UiCheck, layer?: number, preRun?: boolean): string {
  if (isPendingInput(c, layer, preRun)) return 'pending';
  if (isNotApplicable(c)) return 'n/a';
  return c.result;
}

export function CheckRow({ c, print, layer, preRun }: { c: UiCheck; print?: boolean; layer?: number; preRun?: boolean }) {
  const ni = isNotImplemented(c);
  const pendingInput = isPendingInput(c, layer, preRun);
  const resultText = checkResultText(c, layer, preRun);
  const cmp = measuredVsThreshold(c);
  const thr = cmp ? null : thresholdText(c);
  const color = ni ? 'var(--color-faint)' : RESULT_COLOR[c.result];
  const meta = [c.tool, c.gate].filter(Boolean).join(' · ');
  return (
    <div
      data-testid="check-row"
      data-check={c.id}
      data-state={c.result}
      data-skip={c.result === 'skip' ? (pendingInput ? 'pending_input' : (c.skipReason ?? 'skip')) : undefined}
      data-implemented={ni ? 'false' : 'true'}
      className={clsx(
        'grid animate-fade-up items-baseline border-b border-line2',
        print ? 'grid-cols-[10px_minmax(0,1.2fr)_minmax(0,1fr)_44px] gap-2 py-1 text-[9pt]' : 'grid-cols-[12px_minmax(0,1.2fr)_minmax(0,1fr)_150px_56px] gap-3.5 py-2.5',
      )}
    >
      <ResultDot result={c.result} size={8} hollow={ni || c.result === 'reported' || c.result === 'pending'} />
      <span className={clsx(print ? '' : 'text-[13px]', (ni || c.result === 'skip') && 'text-muted', ni && 'text-faint')}>{c.name}</span>
      <span className={clsx('font-mono text-pretty', print ? 'text-[8pt]' : 'text-[11.5px]', ni ? 'text-faint' : 'text-ink2')}>
        {ni ? 'not implemented' : pendingInput ? 'waits for predictions' : (c.evidence ?? c.message ?? (c.result === 'pending' ? 'running' : '–'))}
        {cmp && (
          <span className="block text-muted" title={thresholdTitle(c)} data-testid="check-cmp">
            {cmp}
          </span>
        )}
        {thr && !ni && (
          <span className="block text-muted" title={thresholdTitle(c)}>
            {thr}
          </span>
        )}
      </span>
      {!print && (
        <span className="min-w-0 font-mono text-[10.5px] text-muted">
          <span className="block truncate" title={c.id}>
            {c.id}
          </span>
          <span className="block truncate" title={meta}>
            {[meta, c.ms === undefined ? null : fmtMs(c.ms)].filter(Boolean).join(' · ')}
          </span>
        </span>
      )}
      <span className={clsx('text-right font-semibold tracking-[.04em] uppercase', print ? 'text-[7.5pt]' : 'text-[11px]')} style={{ color }} data-testid="check-result">
        {resultText}
      </span>
    </div>
  );
}

export function CheckTable({ record, layer, checks, title, variant, className }: CheckTableProps) {
  const idx = layer ?? defaultLayerIndex(record);
  const L = record.layers[idx];
  const list = checks ?? L?.checks ?? [];
  const print = variant === 'print';
  const heading = title === undefined ? L?.name : title;
  return (
    <div className={className} data-testid="check-table" data-layer={checks ? undefined : L?.i}>
      {heading !== null && heading !== undefined && (
        <SectionTitle note={checks ? `${list.length} checks` : fmtMs(L?.durationMs)} className="mb-1.5">
          {heading}
        </SectionTitle>
      )}
      <div className={clsx('border-t', print ? 'border-ink' : 'border-line')}>
        {list.map((c) => (
          <CheckRow key={c.id} c={c} print={print} layer={checks ? undefined : L?.i} preRun={assessmentOf(record) === 'pre-run'} />
        ))}
        {list.length === 0 && (
          <div className="py-3 text-[12px] text-muted" data-testid="empty-state">
            {L?.status === 'not_run' ? 'layer not run' : L?.status === 'pending' ? 'pending' : 'no checks'}
          </div>
        )}
      </div>
    </div>
  );
}
