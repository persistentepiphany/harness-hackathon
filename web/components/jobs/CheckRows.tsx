import clsx from 'clsx';
import { StatusDot } from '@/components/ui';
import type { CheckRowView } from '@/lib/selectors/jobs';

/** Compact check rows: result dot, name (category and standing when the record has them), value vs threshold, gate. */
export function CheckRows({ rows, label }: { rows: CheckRowView[]; label?: string }) {
  if (!rows.length) return null;
  return (
    <div className="flex flex-col" data-testid="story-checks" data-group={label}>
      {label && <div className="mt-1 mb-1 text-[10.5px] tracking-[0.06em] text-muted uppercase">{label}</div>}
      {rows.map((r) => (
        <div
          key={r.id}
          data-testid="story-check"
          data-state={r.result}
          data-check={r.id}
          title={[r.id, r.origin ? `threshold origin: ${r.origin}` : ''].filter(Boolean).join(' · ')}
          className="grid animate-fade-in grid-cols-[10px_minmax(0,1fr)_minmax(0,auto)_44px] items-baseline gap-x-2.5 border-t border-line2 py-[5px] text-[12px] max-sm:grid-cols-[10px_minmax(0,1fr)_44px]"
        >
          <StatusDot state={r.result} size={6} />
          <span className="min-w-0">
            <span className={clsx(r.result === 'stop' ? 'text-stop' : r.result === 'skip' ? 'text-muted' : 'text-ink')}>{r.name}</span>
            {(r.category || r.standing) && (
              <span className="ml-2 font-mono text-[10.5px] text-faint">{[r.category, r.standing].filter(Boolean).join(' · ')}</span>
            )}
          </span>
          <span className="max-w-[260px] truncate text-right font-mono text-[11px] text-ink2 max-sm:order-4 max-sm:col-span-2 max-sm:col-start-2 max-sm:max-w-none max-sm:text-left" title={r.value}>
            {r.value}
          </span>
          <span className="text-right text-[10.5px] text-faint">{r.gate}</span>
        </div>
      ))}
    </div>
  );
}
