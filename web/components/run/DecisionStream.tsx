'use client';

// Quick setup decisions (prototype `stream`): one row per interpreter step, spinner then check.

import { Button, ErrorState } from '@/components/ui';
import type { ApiError } from '@/lib/api-client';
import { RingDot } from './parts';

export interface DecisionRow {
  label: string;
  value: string;
  because?: string;
  status: 'loading' | 'ok' | 'error';
  field?: string;
}

export interface DecisionStreamProps {
  rows: DecisionRow[];
  done: boolean;
  onStart: () => void;
  onAdjust: () => void;
  starting?: boolean;
  error?: ApiError | null;
}

export function DecisionStream({ rows, done, onStart, onAdjust, starting, error }: DecisionStreamProps) {
  return (
    <div className="ml-1.5 flex flex-col border-l border-line pl-[18px]" data-testid="decision-stream" data-state={done ? 'done' : 'streaming'}>
      {rows.map((s, i) => (
        <div
          key={`${i}-${s.label}`}
          data-testid="decision-row"
          data-field={s.field}
          data-state={s.status}
          className="grid animate-fade-up grid-cols-[14px_92px_minmax(0,1fr)] items-baseline gap-3 py-[7px]"
        >
          <RingDot state={s.status} size={10} className="relative top-0.5" />
          <span className="text-[12px] text-muted">{s.label}</span>
          <span className={s.status === 'loading' ? 'text-[13.5px] text-muted [overflow-wrap:anywhere]' : s.status === 'error' ? 'text-[13.5px] text-stop [overflow-wrap:anywhere]' : 'text-[13.5px] text-ink [overflow-wrap:anywhere]'}>
            {s.value}
            {s.because ? <>{'  —  '}{s.because}</> : null}
          </span>
        </div>
      ))}
      {done && (
        <div className="flex animate-fade-up gap-2.5 pt-3.5 pb-1 pl-[26px]">
          <Button onClick={onStart} disabled={starting} data-testid="start-run">
            {starting ? 'Starting' : 'Start run'}
          </Button>
          <Button variant="ghost" onClick={onAdjust} data-testid="adjust-manually">
            Adjust manually
          </Button>
        </div>
      )}
      {error && <ErrorState error={error} title="Run not started" className="mt-2 ml-[26px]" />}
    </div>
  );
}
