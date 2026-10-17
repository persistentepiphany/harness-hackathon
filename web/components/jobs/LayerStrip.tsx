import clsx from 'clsx';
import type { StripModel } from '@/lib/selectors/jobs';

/** Six layer columns of the single-job view: name, time or %, pass/warn/stop counts (skips muted). */
export function LayerStrip({ layers }: { layers: StripModel[] }) {
  return (
    <div className="grid grid-cols-6 gap-1.5" data-testid="layer-strip">
      {layers.map((l) => (
        <div
          key={l.i}
          data-testid="layer-cell"
          data-layer={l.i}
          data-state={l.state === 'done' ? (l.result ?? 'done') : l.state}
          title={l.title}
          className="border-t-2 pt-2 transition-colors duration-200"
          style={{ borderTopColor: l.bar }}
        >
          <div className={clsx('overflow-hidden text-[12px] text-ellipsis whitespace-nowrap', l.nameTone === 'ink' ? 'text-ink' : 'text-faint')}>{l.name}</div>
          <div className={clsx('mt-[3px] font-mono text-[12px]', l.valueTone === 'ink' ? 'text-ink' : l.valueTone === 'accent' ? 'text-accent' : 'text-faint')}>{l.value}</div>
          <div className="mt-0.5 min-h-[15px] font-mono text-[10.5px] text-muted">
            {l.counts.map((c, k) => (
              <span key={k} className={c.muted ? 'text-faint' : undefined}>
                {c.text}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
