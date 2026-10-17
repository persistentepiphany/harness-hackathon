'use client';

// Quick setup decisions: one row per interpreter step with an icon, the decided value and, on hover,
// why. Warnings get their own row style; repeated text is shown once.

import clsx from 'clsx';
import { Button, ErrorState } from '@/components/ui';
import type { ApiError } from '@/lib/api-client';

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

const PATHS: Record<string, string> = {
  request: 'M2 3.5h10M2 7h10M2 10.5h6',
  task: 'M3 12V2.5M3 2.5h7l-1.5 2.5L10 7.5H3',
  executors: 'M4 4h6v6H4zM5.5 1.5v2.5M8.5 1.5v2.5M5.5 10v2.5M8.5 10v2.5M1.5 5.5H4M1.5 8.5H4M10 5.5h2.5M10 8.5h2.5',
  target: 'M7 1.5a5.5 5.5 0 1 0 0 11a5.5 5.5 0 1 0 0-11M7 4.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5',
  partner: 'M5 3a3 3 0 1 0 0 6a3 3 0 1 0 0-6M9 5a3 3 0 1 0 0 6a3 3 0 1 0 0-6',
  ligand: 'M7 1.5l4.8 2.75v5.5L7 12.5l-4.8-2.75v-5.5z',
  series: 'M4.5 2l3 1.7v3.5l-3 1.7l-3-1.7V3.7zM9.5 5.8l3 1.7v3.5l-3 1.7l-3-1.7V7.5z',
  seeds: 'M3 3h2v2H3zM9 3h2v2H9zM6 6h2v2H6zM3 9h2v2H3zM9 9h2v2H9z',
  ph: 'M7 1.5C5 4.5 3.5 6.5 3.5 8.5a3.5 3.5 0 0 0 7 0C10.5 6.5 9 4.5 7 1.5z',
  reference: 'M3.5 1.5h7v11L7 10l-3.5 2.5z',
  claim: 'M7 1.5l4.5 1.8v3.6c0 2.8-2 4.6-4.5 5.6c-2.5-1-4.5-2.8-4.5-5.6V3.3zM5 7l1.5 1.5L9.5 5.5',
  warning: 'M7 1.8l5.5 9.7h-11zM7 5.5v3M7 10v.4',
};

function iconKey(r: DecisionRow): string {
  const k = (r.field ?? r.label).toLowerCase();
  if (k.startsWith('warn')) return 'warning';
  if (k.startsWith('executor') || k === 'tools') return 'executors';
  if (k === 'reference' || k === 'pdb') return 'reference';
  return PATHS[k] ? k : 'task';
}

function StepIcon({ row }: { row: DecisionRow }) {
  const key = iconKey(row);
  if (row.status === 'loading') {
    return <span className="block h-3 w-3 animate-spin rounded-full border-[1.5px] border-line border-t-ink" aria-hidden />;
  }
  const color = row.status === 'error' ? 'var(--color-stop)' : key === 'warning' ? 'var(--color-warn)' : 'var(--color-ink2)';
  return (
    <svg width={13} height={13} viewBox="0 0 14 14" fill="none" stroke={color} strokeWidth={1.3} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={PATHS[key]} />
    </svg>
  );
}

/** "a — a" (a warning repeated as its own reason) reads once; other reasons go to the tooltip. */
function rowText(r: DecisionRow): { value: string; why?: string } {
  const parts = r.value.split(' — ');
  const value = parts[0];
  const why = [parts.slice(1).join(' — '), r.because].filter((x): x is string => !!x && x !== value)[0];
  return { value, why };
}

export function DecisionStream({ rows, done, onStart, onAdjust, starting, error }: DecisionStreamProps) {
  return (
    <div className="flex flex-col" data-testid="decision-stream" data-state={done ? 'done' : 'streaming'}>
      <div className="flex flex-col divide-y divide-line2 border-y border-line2">
        {rows.map((s, i) => {
          const { value, why } = rowText(s);
          const warning = iconKey(s) === 'warning';
          return (
            <div
              key={`${i}-${s.label}`}
              data-testid="decision-row"
              data-field={s.field}
              data-state={s.status}
              title={why}
              className={clsx('grid animate-fade-up grid-cols-[18px_88px_minmax(0,1fr)] items-center gap-2.5 py-[7px]', warning && 'bg-warn/5')}
            >
              <span className="flex justify-center">
                <StepIcon row={s} />
              </span>
              <span className="text-[12px] text-muted capitalize">{warning ? 'Note' : s.label}</span>
              <span
                className={clsx(
                  'min-w-0 truncate text-[13px]',
                  s.status === 'loading' ? 'text-muted' : s.status === 'error' ? 'text-stop' : warning ? 'text-ink2' : 'text-ink',
                )}
              >
                {value}
                {why && !warning && <span className="ml-2 text-[11.5px] text-faint">{why.length > 60 ? `${why.slice(0, 59)}…` : why}</span>}
              </span>
            </div>
          );
        })}
      </div>
      {done && (
        <div className="flex animate-fade-up gap-2.5 pt-3.5 pb-1">
          <Button onClick={onStart} disabled={starting} data-testid="start-run">
            {starting ? 'Starting' : 'Start run'}
          </Button>
          <Button variant="ghost" onClick={onAdjust} data-testid="adjust-manually">
            Adjust manually
          </Button>
        </div>
      )}
      {error && <ErrorState error={error} title="Run not started" className="mt-2" />}
    </div>
  );
}
