'use client';

// Perturbation, thresholds (with origin) and controls lists of the report's bottom grid, plus the
// output file chips.

import clsx from 'clsx';
import { useState } from 'react';
import { getHarnessApi } from '@/lib/harness-api';
import { thresholdLevelColor, thresholdRows } from '@/lib/selectors/report';
import { BlockLabel, NotComputed } from './parts';
import type { ReportBlockProps } from './types';

export function PerturbationList({ record, className }: ReportBlockProps) {
  const p = record.stats.perturbation;
  if (p && p.length === 0) return null;
  return (
    <div className={className} data-testid="perturbation" data-state={p ? 'computed' : 'not-computed'}>
      <BlockLabel>Perturbation</BlockLabel>
      <div className="border-t border-line">
        {p ? (
          p.map((row) => (
            <div key={row.name} className="grid grid-cols-[10px_minmax(0,1fr)_minmax(0,1fr)] items-baseline gap-2.5 border-b border-line2 py-1.5 text-[12.5px]" title={`${row.construction} · expected: ${row.expected}`}>
              <span className={clsx('relative top-px h-[7px] w-[7px] rounded-full', row.ok ? 'bg-pass' : 'bg-warn')} />
              <span>{row.name}</span>
              <span className={clsx('text-right font-mono text-[11.5px]', row.ok ? 'text-ink2' : 'text-accent-deep')}>{row.observed}</span>
            </div>
          ))
        ) : (
          <NotComputed what="perturbation" />
        )}
      </div>
    </div>
  );
}

export function ThresholdsList({ record, className }: ReportBlockProps) {
  const rows = thresholdRows(record);
  return (
    <div className={className} data-testid="thresholds">
      <BlockLabel>Thresholds · origin</BlockLabel>
      <div className="border-t border-line">
        {rows.map((t) => (
          <div key={t.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-2.5 border-b border-line2 py-1.5 text-[12.5px]" data-testid="threshold-row" data-check={t.check}>
            <span className="min-w-0">
              <span className={t.check ? 'font-mono text-[11.5px] break-all' : undefined}>{t.name}</span>
              <div className="font-mono text-[11px] text-muted">
                {t.value} · {t.origin}
              </div>
            </span>
            <span className="font-mono text-[11px]" style={{ color: thresholdLevelColor(t.level) }}>
              {t.level}
            </span>
          </div>
        ))}
        {!rows.length && <div className="py-2 text-[12px] text-muted">no thresholds evaluated</div>}
      </div>
    </div>
  );
}

const CONTROL_DOT: Record<string, string> = { sound: 'bg-pass', incomplete: 'bg-stop', failed: 'bg-stop' };

/** Output chips shown before "+n more". */
const OUTPUTS_SHOWN = 12;

export function ControlsList({ record, className }: ReportBlockProps) {
  const api = getHarnessApi();
  const live = record.source === 'pah';
  const [allOutputs, setAllOutputs] = useState(false);
  const outputs = allOutputs ? record.outputs : record.outputs.slice(0, OUTPUTS_SHOWN);
  return (
    <div className={className} data-testid="controls">
      <BlockLabel>Controls</BlockLabel>
      <div className="border-t border-line">
        {record.controls.map((c) => (
          <div key={`${c.name}:${c.check ?? ''}`} className="grid grid-cols-[10px_minmax(0,1fr)_auto] items-baseline gap-2.5 border-b border-line2 py-1.5 text-[12.5px]" data-testid="control-row" data-state={c.status}>
            <span className={clsx('relative top-px h-[7px] w-[7px] rounded-full', CONTROL_DOT[c.status] ?? 'border-[1.5px] border-faint')} />
            <span>
              {c.name}
              {c.status !== 'sound' && <span className="font-mono text-[11px] text-muted"> · {c.status}</span>}
            </span>
            <span className="text-right font-mono text-[11px] text-muted">{c.note}</span>
          </div>
        ))}
        {!record.controls.length && <div className="py-2 text-[12px] text-muted">no controls declared</div>}
      </div>
      {(record.outputs.length > 0 || record.report?.reports?.html) && (
        <div className="mt-3 flex flex-wrap gap-1.5" data-testid="outputs">
          {record.report?.reports?.html && (
            <a href={api.assetUrl(record.report.reports.html)} target="_blank" rel="noreferrer" className="rounded-[4px] border border-ink px-[7px] py-0.5 text-[11px] font-medium text-ink hover:text-accent" data-testid="html-report">
              HTML report
            </a>
          )}
          {outputs.map((o) =>
            live ? (
              <a key={o} href={api.fileUrl(record.id, o)} target="_blank" rel="noreferrer" className="rounded-[4px] border border-line px-[7px] py-0.5 font-mono text-[11px] text-ink2 hover:border-ink hover:text-ink">
                {o}
              </a>
            ) : (
              <span key={o} className="rounded-[4px] border border-line px-[7px] py-0.5 font-mono text-[11px] text-ink2">
                {o}
              </span>
            ),
          )}
          {record.outputs.length > OUTPUTS_SHOWN && (
            <button type="button" onClick={() => setAllOutputs((v) => !v)} className="rounded-[4px] border border-dashed border-line px-[7px] py-0.5 font-mono text-[11px] text-muted hover:border-ink hover:text-ink" data-testid="outputs-more">
              {allOutputs ? 'fewer' : `+${record.outputs.length - OUTPUTS_SHOWN} more`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
