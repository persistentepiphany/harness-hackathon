'use client';

// Summary strip above the ensemble grid (prototype en.summary): per numeric output one strip plot
// of all members, the median tick and the medoid ring, then median, IQR, n, mean, sd, min, max.
// Rows come from the record's stats and its tools' outputs.

import clsx from 'clsx';
import { fmtNum } from '@/lib/format';
import { blockSource, sourceLabel, summaryRows } from '@/lib/selectors/report';
import type { Tool, UiRunRecord } from '@/lib/types';

/** stats.provenance key of each summary row (tool outputs: ensemble.values). */
const SOURCE_KEY: Record<string, string> = {
  rmsd: 'ensemble.rmsdToMedoid',
  plddt: 'ensemble.pocketPlddt',
  posebusters: 'ensemble.posebusters',
  drift: 'physics.drift',
  strain: 'physics.strain',
  clashscore: 'physics.clashscore',
};

const COLS = 'grid-cols-[minmax(150px,1.3fr)_minmax(160px,2fr)_repeat(3,minmax(0,0.8fr))_repeat(4,minmax(0,0.7fr))]';

export function SummaryStats({ record, tools, className, figNo = 7 }: { record: UiRunRecord; tools?: Tool[] | null; className?: string; figNo?: number }) {
  const rows = summaryRows(record, tools);
  // counts (PoseBusters passed) without fixed decimals; their mean and sd keep two
  const f = (m: { integer: boolean }, v: number) => (m.integer && Number.isInteger(v) ? fmtNum(v) : fmtNum(v, undefined, 2));
  return (
    <div className={className} data-testid="summary-stats" data-state={rows.length ? 'computed' : 'not-computed'}>
      <div className="mb-2 text-[14px] font-semibold">Summary statistics</div>
      <div className="border-t border-line font-mono text-[11.5px]">
        <div className={clsx('grid gap-2.5 border-b border-line2 py-[7px] text-[10.5px] text-muted', COLS)}>
          <span>metric</span>
          <span>distribution</span>
          <span className="text-right">median</span>
          <span className="text-right">IQR</span>
          <span className="text-right">n</span>
          <span className="text-right">mean</span>
          <span className="text-right">sd</span>
          <span className="text-right">min</span>
          <span className="text-right">max</span>
        </div>
        {rows.map((m) => (
          <div key={m.id} className={clsx('grid items-center gap-2.5 border-b border-line3 py-2', COLS)} data-testid="summary-row" data-metric={m.id}>
            <span className="truncate text-ink" title={[m.tool ? `${m.name} · ${m.tool}` : m.name, sourceLabel(blockSource(record, SOURCE_KEY[m.id] ?? 'ensemble.values'))].filter(Boolean).join(' · ')}>
              {m.name}
              {m.unit && <span className="text-muted"> {m.unit}</span>}
              {m.tool && <span className="text-[10.5px] text-muted"> · {m.tool}</span>}
            </span>
            <svg viewBox="0 0 200 16" className="block h-4 w-full" aria-hidden>
              <line x1={4} y1={8} x2={196} y2={8} stroke="var(--color-line)" />
              {m.points.map((p, i) => (
                <circle key={i} cx={p.x} cy={8} r={4} fill={p.fill} fillOpacity={0.85} />
              ))}
              {m.medoidX !== undefined && <circle cx={m.medoidX} cy={8} r={6} fill="none" stroke="var(--color-accent)" strokeWidth={1.5} data-testid="summary-medoid" />}
              <line x1={m.medianX} y1={1} x2={m.medianX} y2={15} stroke="var(--color-ink)" strokeWidth={1.5} />
            </svg>
            <span className="text-right font-medium">{f(m, m.stats.median)}</span>
            <span className="text-right text-ink2">
              {f(m, m.stats.q1)}–{f(m, m.stats.q3)}
            </span>
            <span className="text-right text-ink2">{m.stats.n}</span>
            <span className="text-right">{f(m, m.stats.mean)}</span>
            <span className="text-right">{f(m, m.stats.sd)}</span>
            <span className="text-right text-muted">{f(m, m.stats.min)}</span>
            <span className="text-right text-muted">{f(m, m.stats.max)}</span>
          </div>
        ))}
        {!rows.length && (
          <div className="py-2 font-sans text-[12px] text-muted" data-testid="not-computed">
            not computed
          </div>
        )}
      </div>
      <div className="mt-2.5 text-[11px] text-muted">
        Fig. {figNo} · Distribution across seeds and poses; vertical mark is the median, the ring is the medoid. Medoid is the representative, never a mean structure.
      </div>
    </div>
  );
}
