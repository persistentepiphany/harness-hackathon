// Executors of the job (prototype `rj.execution`): one row per executor line or tool; docking
// tools list their parameters from the tool register (values the record reports, else defaults).

import clsx from 'clsx';
import { DASH, THIN } from '@/lib/format';
import type { ExecutorRowModel } from '@/lib/selectors/run';
import { RingDot } from '@/components/run/parts';

export function ExecutorList({ rows }: { rows: ExecutorRowModel[] }) {
  return (
    <div data-testid="executor-list">
      <div className="eyebrow mb-2">Executors</div>
      {rows.length === 0 && <div className="border-t border-line2 py-[7px] text-[12px] text-faint">none declared</div>}
      {rows.map((e) => (
        <div key={e.key} className="grid grid-cols-[12px_minmax(0,1fr)] gap-2.5 border-t border-line2 py-[7px] text-[12.5px]" data-testid="executor-row" data-state={e.state}>
          <RingDot state={e.state === 'loading' ? 'loading' : e.state === 'ok' ? 'ok' : 'idle'} size={8} className="relative top-[5px]" />
          <div className="min-w-0">
            <div className="font-medium">{e.tool}</div>
            <div className={clsx('text-[12px] text-pretty', e.state === 'not_run' ? 'text-muted' : 'text-ink2')}>{e.text}</div>
            {e.params && e.params.length > 0 && (
              <dl className="mt-1.5 grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-0.5 text-[11.5px]" data-testid="docking-params">
                {e.params.map((p) => (
                  <div key={p.key} className="contents">
                    <dt className="truncate text-muted" title={p.key}>
                      {p.label}
                    </dt>
                    <dd className={clsx('m-0 text-right font-mono', p.value === DASH ? 'text-faint' : 'text-ink2')}>
                      {p.value}
                      {p.unit ? `${THIN}${p.unit}` : ''}
                      {p.isDefault && <span className="ml-1 font-sans text-[10.5px] text-faint">default</span>}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
