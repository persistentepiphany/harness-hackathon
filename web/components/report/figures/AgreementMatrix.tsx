'use client';

// Agreement between methods (stats.agreement); method labels resolve through the record's tools.

import clsx from 'clsx';
import { agreementCellStyle, blockSource, methodName, sourceLabel } from '@/lib/selectors/report';
import { NotComputed } from '../parts';
import { FigureCaption, type FigureProps } from './common';

export function AgreementMatrix({ record, tools, caption = true, figNo = 4, variant, className }: FigureProps) {
  const print = variant === 'print';
  const rows = record.stats.agreement;
  if (!rows || !rows.length) return <NotComputed what="agreement" print={print} record={record} className={className} />;
  const unit = rows[0].cells[0]?.unit ?? '';
  const name = (m: string) => methodName(record, m, tools);
  const cols = print ? `70px repeat(${rows.length},1fr)` : `90px repeat(${rows.length},minmax(0,110px))`;
  return (
    <div className={className} data-testid="figure-agreement" title={sourceLabel(blockSource(record, 'agreement'))}>
      <div className={clsx('grid gap-1 font-mono', print ? 'text-[9pt]' : 'text-[11.5px]')} style={{ gridTemplateColumns: cols }}>
        <div />
        {rows.map((r) => (
          <div key={r.method} className="pb-0.5 text-center text-muted">
            {name(r.method)}
          </div>
        ))}
        {rows.map((r) => (
          <div key={r.method} className="contents">
            <div className="flex items-center text-ink2">{name(r.method)}</div>
            {r.cells.map((c) => {
              const st = agreementCellStyle(c.value);
              return (
                <div key={c.vs} className={clsx('rounded-[4px] text-center', print ? 'py-1' : 'px-1.5 py-2.5')} style={{ background: st.bg, color: st.color }} title={`${name(r.method)} vs ${name(c.vs)}: ${c.value} ${c.unit}`}>
                  <div className={print ? '' : 'text-[13px] font-medium'}>{st.text}</div>
                  {!print && <div className="mt-px text-[10px] opacity-80">{c.weight}</div>}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {caption && (
        <FigureCaption no={figNo} print={print}>
          Agreement between methods, {unit}; cell label is the evidential weight.
        </FigureCaption>
      )}
    </div>
  );
}
