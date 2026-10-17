import clsx from 'clsx';
import type { SegmentModel } from '@/lib/selectors/jobs';

/** Six-segment layer progress of a job card (prototype `j.segs`); colour = worst result of the layer. */
export function LayerProgress({ segments }: { segments: SegmentModel[] }) {
  return (
    <div className="mt-0.5 grid grid-cols-6 gap-[3px]" data-testid="layer-progress">
      {segments.map((s) => (
        <div
          key={s.i}
          title={s.title ? `${s.name} · ${s.title}` : s.name}
          data-testid="layer-cell"
          data-layer={s.i}
          data-state={s.state === 'done' ? (s.result ?? 'done') : s.state}
          data-incomplete={s.incomplete.length ? 'true' : undefined}
        >
          <div className="h-[3px] overflow-hidden rounded-[2px] bg-[#ECECE8]">
            <div className="h-full transition-[width] duration-[120ms] ease-linear" style={{ width: `${s.pct}%`, background: s.color }} />
          </div>
          <div className={clsx('mt-[5px] flex justify-between gap-1.5 text-[10.5px]', s.active ? 'text-ink2' : 'text-[#C9C9C3]')}>
            <span className="overflow-hidden text-ellipsis whitespace-nowrap">{s.name}</span>
            <span className={clsx('flex-none font-mono', s.countsMuted && 'text-faint')}>{s.counts}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
