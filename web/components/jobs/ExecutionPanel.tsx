import clsx from 'clsx';
import type { ExecutionView, PhaseStepState, StageView } from '@/lib/selectors/jobs';

const STEP_TONE: Record<PhaseStepState, string> = {
  done: 'bg-ink2',
  active: 'animate-pulse bg-accent',
  todo: 'bg-line',
  failed: 'bg-stop',
};

/** One executor: name and where it runs, queued → building → running → done, elapsed, per-seed bars. */
function ExecutorTimeline({ e }: { e: ExecutionView }) {
  const skipped = e.phase === 'skipped';
  return (
    <div className="border-t border-line2 py-2" data-testid="execution-timeline" data-executor={e.key} data-state={e.phase}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[12.5px]">
        <span className="font-medium">{e.name}</span>
        <span className="font-mono text-[11px] text-muted" title={e.routeNote ?? undefined}>
          {skipped ? 'not dispatched' : e.where}
        </span>
        <span className="ml-auto font-mono text-[11.5px] text-ink2 tabular-nums" data-testid="execution-elapsed">
          {skipped ? '' : e.elapsed}
        </span>
      </div>
      {!skipped && (
        <div className="mt-1.5 grid grid-cols-4 gap-1" aria-label={`${e.name}: ${e.phase}`}>
          {e.steps.map((s) => (
            <div key={s.phase} data-state={s.state}>
              <div className={clsx('h-[3px] rounded-full transition-colors duration-300', STEP_TONE[s.state])} />
              <div className={clsx('mt-1 text-[10.5px]', s.state === 'active' ? 'text-accent-deep' : s.state === 'todo' ? 'text-faint' : 'text-muted')}>{s.phase}</div>
            </div>
          ))}
        </div>
      )}
      {e.seeds.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-x-2 gap-y-1.5" data-testid="seed-bars">
          {e.seeds.map((s) => (
            <div key={s.seed} className="w-[58px]" data-testid="seed-bar" data-state={s.phase} title={`seed ${s.seed}: ${s.phase}${s.ms !== null ? ` · ${s.label}` : ''}`}>
              <div className="h-[5px] overflow-hidden rounded-[2px] bg-line2">
                <div
                  className={clsx('h-full rounded-[2px] transition-[width] duration-300 ease-out', s.phase === 'running' ? 'animate-pulse bg-accent' : s.phase === 'done' ? 'bg-ink2' : s.phase === 'failed' ? 'bg-stop' : 'bg-transparent')}
                  style={{ width: s.phase === 'queued' ? '0%' : `${Math.round(s.frac * 100)}%` }}
                />
              </div>
              <div className="mt-[3px] flex justify-between font-mono text-[10px] text-muted tabular-nums">
                <span>s{s.seed}</span>
                <span className={s.phase === 'running' ? 'text-accent-deep' : undefined}>{s.phase === 'queued' ? '' : s.label}</span>
              </div>
            </div>
          ))}
        </div>
      )}
      {(skipped || e.phase === 'failed') && e.message && <div className={clsx('mt-1 text-[11.5px]', e.phase === 'failed' ? 'text-stop' : 'text-muted')}>{e.message}</div>}
    </div>
  );
}

/** Stage timings: pre-run layers, execute, output layers, report (widths by time, active stage in accent). */
export function StageBar({ stages }: { stages: StageView[] }) {
  const total = stages.reduce((a, s) => a + (s.ms ?? 0), 0);
  return (
    <div data-testid="stage-bar">
      <div className="flex h-[6px] gap-[3px]">
        {stages.map((s) => {
          const w = total > 0 && s.ms ? Math.max(6, (s.ms / total) * 100) : s.state === 'skipped' ? 4 : 10;
          return (
            <div
              key={s.key}
              data-testid="stage"
              data-stage={s.key}
              data-state={s.state}
              className={clsx(
                'rounded-[2px] transition-[flex-grow] duration-500 ease-out',
                s.state === 'active' ? 'animate-pulse bg-accent' : s.state === 'done' ? 'bg-ink2' : s.state === 'skipped' ? 'bg-[repeating-linear-gradient(90deg,var(--color-line)_0_3px,transparent_3px_6px)]' : 'bg-line',
              )}
              style={{ flexGrow: w, flexBasis: 0 }}
            />
          );
        })}
      </div>
      <div className="mt-1.5 grid grid-cols-4 gap-2 text-[11px]">
        {stages.map((s) => (
          <div key={s.key} className="min-w-0">
            <div className={clsx('truncate', s.state === 'active' ? 'text-accent-deep' : 'text-muted')}>{s.label}</div>
            <div className={clsx('font-mono tabular-nums', s.state === 'skipped' || s.state === 'todo' ? 'text-faint' : 'text-ink2')}>{s.text}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export interface ExecutionPanelProps {
  engaged: { text: string; active: boolean } | null;
  executions: ExecutionView[];
}

/** Engaged tool line and one timeline per executor. */
export function ExecutionPanel({ engaged, executions }: ExecutionPanelProps) {
  return (
    <div data-testid="execution-panel">
      {engaged && (
        <div className="mb-1.5 flex items-center gap-2 text-[12.5px]" data-testid="engaged" data-state={engaged.active ? 'active' : 'idle'}>
          <span aria-hidden className={clsx('inline-block h-[7px] w-[7px] rounded-full', engaged.active ? 'animate-pulse bg-accent' : 'bg-ink2')} />
          <span className={engaged.active ? 'text-ink' : 'text-ink2'}>{engaged.text}</span>
        </div>
      )}
      {executions.map((e) => (
        <ExecutorTimeline key={e.key} e={e} />
      ))}
    </div>
  );
}
