'use client';

// Prototype report sidebar: layer nav (name, summary, worst-result dot), the selected layer's key
// figures and check list (not-implemented checks muted), then run totals and tool versions.

import clsx from 'clsx';
import { countSegments, fmtFraction, fmtMs, SEP, tallyResults } from '@/lib/format';
import { isNotImplemented, layerNav, totalDurationMs } from '@/lib/selectors/report';
import { recordTools } from '@/lib/tools';
import type { Result } from '@/lib/types';
import { ResultDot } from './parts';
import type { ReportBlockProps } from './types';

export interface LayerSidebarProps extends ReportBlockProps {
  selected: number;
  onSelect: (index: number) => void;
}

function Counts({ counts }: { counts: Partial<Record<Result, number>> }) {
  return (
    <span className="font-mono text-[10.5px]">
      {countSegments(counts).map((s, k) => (
        <span key={s.result} className={s.muted ? 'text-faint' : 'text-ink2'} data-count={s.result}>
          {k > 0 && <span className="text-faint">{SEP}</span>}
          {s.text}
        </span>
      ))}
    </span>
  );
}

export function LayerSidebar({ record, tools, selected, onSelect, className }: LayerSidebarProps) {
  const nav = layerNav(record);
  const L = record.layers[selected];
  const all = record.layers.flatMap((l) => l.checks);
  const total = totalDurationMs(record);
  const rt = recordTools(record, tools);
  const versions = [
    ...rt.map((t) => `${t.name}${t.version ? ` ${t.version}` : ''}`),
    ...(record.record.pahVersion ? [`pah ${record.record.pahVersion}`] : []),
    ...Object.entries(record.record.toolVersions ?? {}).map(([k, v]) => `${k} ${v}`),
  ];
  const notImpl = L ? L.checks.filter(isNotImplemented).length : 0;

  return (
    <div className={clsx('sticky top-[68px] flex flex-col gap-6', className)} data-testid="layer-sidebar">
      <div>
        <div className="eyebrow mb-2">Layers</div>
        {nav.map((l, idx) => {
          const on = idx === selected;
          return (
            <button
              key={l.i}
              type="button"
              onClick={() => onSelect(idx)}
              data-testid="layer-cell"
              data-layer={l.i}
              data-state={l.status === 'done' ? (l.dot ?? 'empty') : l.status}
              aria-pressed={on}
              className={clsx(
                'block w-full border-0 border-l-2 bg-transparent py-2 pr-0 pl-3 text-left transition-colors duration-150',
                on ? 'border-ink' : 'border-line hover:border-faint',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={clsx('text-[13px]', on ? 'font-semibold text-ink' : 'font-medium text-ink2')}>{l.name}</span>
                {l.status === 'running' ? (
                  <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-accent" />
                ) : l.status === 'not_run' || l.status === 'pending' ? (
                  <span className="h-[7px] w-[7px] rounded-full border-[1.5px] border-faint" title={l.status === 'not_run' ? 'layer not run' : 'pending'} />
                ) : (
                  <ResultDot result={l.dot} size={7} hollow={l.dot === null || l.dot === 'reported'} className="top-0" />
                )}
              </div>
              <div className="mt-[3px] font-mono text-[11px] leading-[1.5] text-muted">
                {l.summary || (l.status === 'not_run' ? 'not run' : l.status === 'pending' ? 'pending' : '')}
              </div>
            </button>
          );
        })}
      </div>

      {L && (
        <div className="border-t border-line pt-3.5" data-testid="layer-detail" data-layer={L.i}>
          <div className="mb-2 flex items-baseline justify-between">
            <div className="eyebrow">{L.name}</div>
            <span className="font-mono text-[10.5px] text-muted">{fmtMs(L.durationMs)}</span>
          </div>
          {(L.figures ?? []).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2.5 border-b border-line3 py-1 text-[12px]">
              <span className="text-ink2">{k}</span>
              <span className="text-right font-mono text-[11.5px] text-ink">{v}</span>
            </div>
          ))}
          {L.checks.length > 0 && (
            <div className="mt-2 flex flex-wrap items-baseline justify-between gap-x-2">
              <Counts counts={Object.keys(L.counts ?? {}).length ? L.counts : tallyResults(L.checks)} />
              {notImpl > 0 && (
                <span className="font-mono text-[10.5px] text-muted" title="checks registered in the harness / checks listed by the task">
                  implemented {fmtFraction(L.checks.length - notImpl, L.checks.length)}
                </span>
              )}
            </div>
          )}
          <div className="mt-3 flex flex-col gap-[3px]">
            {L.checks.map((c) => {
              const ni = isNotImplemented(c);
              return (
                <div
                  key={c.id}
                  className={clsx('grid grid-cols-[8px_minmax(0,1fr)] items-baseline gap-2 text-[11.5px]', ni ? 'text-faint' : 'text-ink2')}
                  data-testid="side-check"
                  data-check={c.id}
                  data-state={c.result}
                  title={ni ? `${c.id}: not implemented` : c.id}
                >
                  <ResultDot result={c.result} hollow={ni || c.result === 'reported' || c.result === 'pending'} />
                  <span className="truncate">
                    {c.name}
                    {ni && <span className="font-mono text-[10.5px]"> · not implemented</span>}
                  </span>
                </div>
              );
            })}
            {L.checks.length === 0 && <div className="text-[11.5px] text-muted">{L.status === 'not_run' ? 'layer not run' : 'no checks'}</div>}
          </div>
        </div>
      )}

      <div className="pl-3.5 font-mono text-[11px] leading-[1.7] text-muted">
        {all.length} checks · {total === null ? '–' : `${(total / 1000).toFixed(1)} s`}
        {versions.map((line) => (
          <div key={line}>{line}</div>
        ))}
      </div>
    </div>
  );
}
