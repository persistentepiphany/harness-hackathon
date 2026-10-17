'use client';

// Task list of the agent monitor (prototype AGENT view, left column): goal, status, progress bar,
// step count and elapsed time per task.

import clsx from 'clsx';
import { fmtElapsedShort, type TaskCardView } from '@/lib/selectors/agent';
import type { AgentTaskStatus } from '@/lib/types';

const STATUS_TEXT: Record<AgentTaskStatus, string> = {
  done: 'text-pass',
  failed: 'text-stop',
  running: 'text-ink2',
  queued: 'text-ink2',
};
const DOT: Record<AgentTaskStatus, string> = {
  done: 'bg-pass',
  failed: 'bg-stop',
  running: 'bg-accent animate-pulse',
  queued: 'bg-faint',
};
const BAR: Record<AgentTaskStatus, string> = {
  done: 'bg-pass',
  failed: 'bg-stop',
  running: 'bg-accent',
  queued: 'bg-accent',
};

export interface TaskListProps {
  tasks: TaskCardView[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function TaskList({ tasks, selectedId, onSelect }: TaskListProps) {
  return (
    <div className="flex flex-col gap-2.5" data-testid="agent-task-list">
      {tasks.map((t) => {
        const on = t.id === selectedId;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onSelect(t.id)}
            data-testid="agent-task"
            data-task={t.id}
            data-state={t.status}
            data-selected={on ? 'true' : undefined}
            aria-pressed={on}
            className={clsx(
              'flex flex-col gap-2 rounded-card border px-3.5 py-3 text-left leading-[normal] transition-all duration-150 hover:border-ink',
              on ? 'border-ink bg-surface' : 'border-line bg-transparent',
            )}
          >
            <div className="flex w-full items-start justify-between gap-2.5">
              <span className="text-[13px] font-medium text-pretty text-ink">{t.goal}</span>
              <span className={clsx('flex flex-none items-center gap-1.5 font-mono text-[11px]', STATUS_TEXT[t.status])} data-testid="agent-task-status">
                <span className={clsx('h-1.5 w-1.5 rounded-full', DOT[t.status])} />
                {t.statusLabel}
              </span>
            </div>
            <div className="h-[3px] w-full overflow-hidden rounded-[2px] bg-[#ECECE8]">
              <div className={clsx('h-full transition-[width] duration-300', BAR[t.status])} style={{ width: `${t.pct}%` }} />
            </div>
            <div className="flex w-full justify-between font-mono text-[10.5px] text-muted">
              <span data-testid="agent-task-steps">{t.stepLabel}</span>
              <span>{fmtElapsedShort(t.elapsedMs)}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
