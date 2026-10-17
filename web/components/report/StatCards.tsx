'use client';

// Site, pose and docking (or sampling) cards under the structure viewer. Absent blocks keep their
// slot with a muted "not computed".

import clsx from 'clsx';
import { blockSource, sourceLabel, statCards } from '@/lib/selectors/report';
import { BlockLabel, KvRow, NotComputed } from './parts';
import type { ReportBlockProps } from './types';

export function StatCards({ record, tools, variant, className }: ReportBlockProps) {
  const print = variant === 'print';
  const cards = statCards(record, tools);
  return (
    <div
      className={clsx('grid', print ? 'grid-cols-3 gap-4' : 'gap-4', className)}
      style={print ? undefined : { gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))' }}
      data-testid="stat-cards"
    >
      {cards.map((card) => (
        <div key={card.id} className={clsx('border-t border-ink', print ? 'pt-1.5' : 'pt-2.5')} data-testid="stat-card" data-card={card.id} data-state={card.computed ? 'computed' : 'not-computed'}>
          <BlockLabel print={print}>{card.title}</BlockLabel>
          {card.rows.map(([k, v]) => (
            <KvRow key={k} k={k} v={v} print={print} muted={!card.computed} title={sourceLabel(blockSource(record, `${card.id}.${k}`))} />
          ))}
          {!card.computed && <NotComputed what={card.id} print={print} />}
        </div>
      ))}
    </div>
  );
}
