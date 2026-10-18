'use client';

// Run plan (prototype manual setup, right column): name, claim, executors, controls, Start run.

import { ErrorState } from '@/components/ui';
import type { ApiError } from '@/lib/api-client';

export interface RunPlanProps {
  name: string;
  suggestion: string;
  onName: (v: string) => void;
  claim: string;
  tools: string;
  controls: string;
  onStart: () => void;
  starting?: boolean;
  error?: ApiError | null;
}

export function RunPlan({ name, suggestion, onName, claim, tools, controls, onStart, starting, error }: RunPlanProps) {
  return (
    <div className="flex flex-col gap-3 border-t border-line pt-[18px]" data-testid="run-plan">
      <input
        value={name}
        onChange={(e) => onName(e.target.value)}
        placeholder={suggestion}
        aria-label="Run name"
        data-testid="run-name"
        className="w-full rounded-none border-0 border-b border-line bg-transparent px-0 pt-1 pb-2 text-[14px] leading-[normal] font-semibold text-ink placeholder:text-[#757575]"
      />
      <div className="flex flex-col gap-1.5 text-[12.5px]">
        <div className="flex gap-3">
          <span className="w-[72px] flex-none text-muted">Claim</span>
          <span className="text-pretty" data-testid="plan-claim">
            {claim}
          </span>
        </div>
        <div className="flex gap-3">
          <span className="w-[72px] flex-none text-muted">Executors</span>
          <span data-testid="plan-tools">{tools}</span>
        </div>
        <div className="flex gap-3">
          <span className="w-[72px] flex-none text-muted">Controls</span>
          <span className="text-pretty">{controls}</span>
        </div>
      </div>
      <button
        type="button"
        onClick={onStart}
        disabled={starting}
        data-testid="start-run"
        className="mt-1 rounded border-0 bg-ink px-3.5 py-[9px] text-[12.5px] leading-[normal] font-medium text-white transition-opacity duration-200 disabled:opacity-40"
      >
        {starting ? 'Starting' : 'Start run'}
      </button>
      {error && <ErrorState error={error} title="Run not started" />}
    </div>
  );
}
