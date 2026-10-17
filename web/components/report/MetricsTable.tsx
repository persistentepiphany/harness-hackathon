'use client';

// Confidence and interface metrics. Rows come from stats.metrics, or from the outputs of the
// record's tools when nothing was computed; ranking-only scores sit below the accent rule.

import clsx from 'clsx';
import { DASH } from '@/lib/format';
import { metricRows, type MetricRow } from '@/lib/selectors/report';
import { BlockLabel, NotComputed } from './parts';
import type { ReportBlockProps } from './types';

function Row({ m, print, ranking }: { m: MetricRow; print: boolean; ranking: boolean }) {
  const missing = m.value === null;
  return (
    <div
      className={clsx(
        'grid items-baseline border-b',
        ranking ? 'border-accent' : 'border-line2',
        print ? 'grid-cols-[minmax(0,1fr)_auto] gap-2 py-0.5 text-[9pt]' : 'grid-cols-[minmax(0,1fr)_110px] gap-3 py-1.5 text-[12.5px]',
      )}
      data-testid="metric-row"
      data-ranking={ranking ? 'true' : 'false'}
      title={[m.read, m.check ? `source: ${m.check}` : null].filter(Boolean).join(' · ') || undefined}
    >
      <span>
        {m.name}
        {m.tool && <span className={clsx('text-muted', print ? 'text-[7.5pt]' : 'text-[11px]')}> {m.tool}</span>}
      </span>
      <span className={clsx('text-right font-mono', print && 'text-[8.5pt]', missing ? 'text-faint' : ranking ? 'text-accent-deep' : 'text-ink')}>
        {missing ? DASH : m.value}
        {missing && m.unit ? <span className="text-faint">{` ${m.unit}`}</span> : null}
      </span>
    </div>
  );
}

export function MetricsTable({ record, tools, variant, className }: ReportBlockProps) {
  const print = variant === 'print';
  const { computed, rows, ranking } = metricRows(record, tools);
  return (
    <div className={className} data-testid="metrics-table" data-state={computed ? 'computed' : 'not-computed'}>
      <BlockLabel print={print}>{print ? 'Confidence' : 'Confidence · interface metrics'}</BlockLabel>
      {!computed && <NotComputed what="metrics" print={print} className="!pt-0" />}
      <div className={clsx('border-t', print ? 'border-ink' : 'border-line')}>
        {rows.map((m) => (
          <Row key={m.id} m={m} print={print} ranking={false} />
        ))}
        {ranking.length > 0 && <div className="h-0 border-t border-accent" data-testid="accent-rule" />}
        {ranking.map((m) => (
          <Row key={m.id} m={m} print={print} ranking />
        ))}
      </div>
      {!print && ranking.length > 0 && <div className="mt-2 text-[11px] text-muted">Values below the rule are ranking scores, read on their own line.</div>}
    </div>
  );
}
