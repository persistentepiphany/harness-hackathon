'use client';

// Checks of one layer (prototype "Checks for selected layer"): result dot, name, evidence with
// `measured cmp threshold`, id · tool · gate · ms, result. Not-implemented checks are muted.

import clsx from 'clsx';
import { checkValue, fmtMs, fmtNum, fmtSha, measuredVsThreshold, pairMeasurement, thresholdText } from '@/lib/format';
import { assessmentOf, defaultLayerIndex, isNotApplicable, isNotImplemented, isPendingInput, RESULT_COLOR, thresholdLevelColor } from '@/lib/selectors/report';
import type { RecordSource, UiCheck } from '@/lib/types';
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

export interface CheckRowProps {
  c: UiCheck;
  print?: boolean;
  layer?: number;
  preRun?: boolean;
  /** Sources the check used (record.sources[].usedBy), shown when the row is expanded. */
  sources?: RecordSource[];
  /** Selected rows are expanded and drive the viewer focus. */
  selected?: boolean;
  onSelect?: (id: string | null) => void;
}

function CheckDetails({ c, sources }: { c: UiCheck; sources: RecordSource[] }) {
  return (
    <div className="col-span-full mt-2 grid animate-fade-in gap-x-6 gap-y-2 rounded-[6px] bg-canvas px-3 py-2.5 text-[11.5px] sm:grid-cols-2" data-testid="check-details" onClick={(ev) => ev.stopPropagation()}>
      <div className="col-span-full font-mono text-[10.5px] text-muted" data-testid="check-meta">
        {[c.id, c.tool, c.gate, c.ms === undefined ? null : fmtMs(c.ms)].filter(Boolean).join(' · ')}
      </div>
      {c.evidence && <div className="col-span-full font-mono text-[11px] text-ink2 break-words">{c.evidence}</div>}
      <div className="min-w-0">
        <div className="eyebrow mb-1 !text-[10px]">Sources used</div>
        {sources.length ? (
          sources.map((s) => (
            <div key={s.id ?? `${s.source}:${s.accession}`} className="flex min-w-0 flex-wrap items-baseline gap-x-2 font-mono text-[11px]" data-testid="check-source" title={s.sha256}>
              <span className="text-ink">{s.accession}</span>
              <span className="truncate text-muted">{s.source}</span>
              <span className="text-ink2">{s.release || '–'}</span>
              <span className="text-faint">{fmtSha(s.sha256)}</span>
            </div>
          ))
        ) : (
          <div className="text-muted">no source objects recorded for this check</div>
        )}
      </div>
      <div className="min-w-0">
        <div className="eyebrow mb-1 !text-[10px]">Thresholds · origin</div>
        {(c.thresholds ?? []).length ? (
          (c.thresholds ?? []).map((t) => (
            <div key={t.name} className="font-mono text-[11px] break-words" data-testid="check-threshold">
              <span className="text-ink">
                {t.name} {t.comparator} {String(t.value)}
              </span>
              <span className="text-muted"> · {t.origin}</span>
              <span style={{ color: thresholdLevelColor(t.evidenceLevel) }}> · {t.evidenceLevel}</span>
            </div>
          ))
        ) : (
          <div className="text-muted">no threshold</div>
        )}
        {(c.measurements ?? []).length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-x-3 font-mono text-[11px] text-ink2" data-testid="check-measurements">
            {(c.measurements ?? []).map((m) => (
              <span key={m.name}>
                <span className="text-muted">{m.name}</span> {typeof m.value === 'number' ? fmtNum(m.value) : String(m.value)}
                {m.unit ? <span className="num-unit">{m.unit}</span> : null}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** First clause of the evidence text; the full text is in the row title and the expanded details. */
function shortEvidence(text: string): string {
  const first = text.split(' · ')[0];
  return first.length > 90 ? `${first.slice(0, 89)}…` : first;
}

export function CheckRow({ c, print, layer, preRun, sources = [], selected, onSelect }: CheckRowProps) {
  const ni = isNotImplemented(c);
  const pendingInput = isPendingInput(c, layer, preRun);
  const resultText = checkResultText(c, layer, preRun);
  const cmp = measuredVsThreshold(c);
  const thr = cmp ? null : thresholdText(c);
  const color = ni ? 'var(--color-faint)' : RESULT_COLOR[c.result];
  const meta = [c.tool, c.gate].filter(Boolean).join(' · ');
  const evidence = ni ? 'not implemented' : pendingInput ? 'waits for predictions' : (c.evidence ?? c.message ?? (c.result === 'pending' ? 'running' : '–'));
  const common = {
    'data-testid': 'check-row',
    'data-check': c.id,
    'data-layer': layer,
    'data-state': c.result,
    'data-skip': c.result === 'skip' ? (pendingInput ? 'pending_input' : (c.skipReason ?? 'skip')) : undefined,
    'data-implemented': ni ? 'false' : 'true',
  };
  if (print) {
    return (
      <div {...common} className="grid grid-cols-[10px_minmax(0,1.2fr)_minmax(0,1fr)_44px] items-baseline gap-2 border-b border-line2 py-1 text-[9pt] break-inside-avoid">
        <ResultDot result={c.result} size={8} hollow={ni || c.result === 'reported' || c.result === 'pending'} />
        <span className={clsx((ni || c.result === 'skip') && 'text-muted')}>{c.name}</span>
        <span className="font-mono text-[8pt] text-pretty text-ink2">
          {evidence}
          {cmp && <span className="block text-muted">{cmp}</span>}
        </span>
        <span className="text-right text-[7.5pt] font-semibold tracking-[.04em] uppercase" style={{ color }}>
          {resultText}
        </span>
      </div>
    );
  }
  const interactive = !!onSelect;
  return (
    <div
      {...common}
      data-selected={selected ? 'true' : undefined}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-expanded={interactive ? !!selected : undefined}
      onClick={interactive ? () => onSelect(selected ? null : c.id) : undefined}
      onKeyDown={
        interactive
          ? (ev) => {
              if (ev.key !== 'Enter' && ev.key !== ' ') return;
              ev.preventDefault();
              onSelect(selected ? null : c.id);
            }
          : undefined
      }
      className={clsx(
        'grid grid-cols-[12px_minmax(0,1fr)_52px] items-baseline gap-x-3 border-b border-line2 py-2.5 transition-colors duration-200 md:grid-cols-[12px_minmax(0,1fr)_minmax(0,1.15fr)_52px]',
        interactive && 'cursor-pointer hover:bg-surface',
        selected && 'bg-surface',
      )}
    >
      <ResultDot result={c.result} size={8} hollow={ni || c.result === 'reported' || c.result === 'pending'} />
      <span className="min-w-0">
        <span className={clsx('block text-[13px]', (ni || c.result === 'skip') && 'text-muted', ni && 'text-faint')} title={`${c.id}${meta ? ` · ${meta}` : ''}`}>
          {c.name}
        </span>
      </span>
      <span className={clsx('col-start-2 row-start-2 min-w-0 truncate text-[12.5px] tabular-nums md:col-start-3 md:row-start-1', ni ? 'text-faint' : 'text-ink2')} title={evidence}>
        {cmp ? (
          <span title={thresholdTitle(c)} data-testid="check-cmp">
            {cmp}
          </span>
        ) : ni || pendingInput ? (
          evidence
        ) : (
          shortEvidence(checkValue(c) || evidence)
        )}
        {!cmp && thr && !ni && !pendingInput && <span className="ml-2 text-muted" title={thresholdTitle(c)}>{thr}</span>}
      </span>
      <span className="col-start-3 row-start-1 text-right text-[11px] font-semibold tracking-[.04em] uppercase md:col-start-4" style={{ color }} data-testid="check-result">
        {resultText}
      </span>
      {selected && <CheckDetails c={c} sources={sources} />}
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
