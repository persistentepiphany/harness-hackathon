'use client';

// Selected task: goal, id and counts, the outcome once the task has finished, then the streamed
// step timeline (useAgentSteps: replay, then tail until the task finishes).

import clsx from 'clsx';
import { ErrorState } from '@/components/ui';
import type { StreamResult } from '@/lib/hooks';
import { fmtElapsedLong, fmtSteps, pendingLabel, stepCounts, stepViews, type TaskCardView } from '@/lib/selectors/agent';
import type { AgentStep, AgentTask } from '@/lib/types';
import { StepTimeline } from './StepTimeline';

export interface TaskDetailProps {
  task: AgentTask;
  card: TaskCardView;
  steps: AgentStep[];
  stream: StreamResult<AgentStep>;
}

export function TaskDetail({ task, card, steps, stream }: TaskDetailProps) {
  const views = stepViews(steps, task.createdAt);
  const counts = stepCounts(steps);
  const finished = task.status === 'done' || task.status === 'failed';
  const active = !finished && !stream.ended;
  const pending = active ? pendingLabel(steps[steps.length - 1], task.status) : null;
  const outcome = task.outcome;
  const streamNote =
    stream.status === 'reconnecting' ? 'stream reconnecting' : stream.status === 'failed' ? 'stream closed' : stream.loading ? 'connecting' : null;

  return (
    <div className="flex min-w-0 flex-col gap-6" data-testid="agent-task-detail" data-task={task.id} data-state={task.status}>
      <div>
        <div className="text-[16px] font-semibold tracking-[-0.01em] text-pretty" data-testid="agent-task-goal">
          {task.goal}
        </div>
        <div className="mt-2 flex flex-wrap gap-4 font-mono text-[11.5px] text-muted">
          <span>{task.id}</span>
          <span data-testid="agent-task-stepcount">{fmtSteps(views.length, card.stepsTotal)}</span>
          <span>{counts.toolCalls} tool calls</span>
          <span>{counts.reports} reports read</span>
          <span>{fmtElapsedLong(card.elapsedMs)}</span>
          {streamNote && (
            <span className={clsx(stream.status === 'failed' ? 'text-stop' : 'text-faint')} data-testid="agent-stream-note">
              {streamNote}
            </span>
          )}
        </div>
      </div>

      {finished && (
        <div className="flex flex-wrap items-baseline gap-3.5 border-t border-ink pt-3" data-testid="agent-outcome" data-state={task.status}>
          <span className={clsx('text-[14px] font-semibold', task.status === 'failed' ? 'text-stop' : 'text-pass')}>
            {outcome?.label || (task.status === 'failed' ? 'Failed' : 'Done')}
          </span>
          {outcome?.detail && <span className="font-mono text-[12px] text-ink2">{outcome.detail}</span>}
        </div>
      )}

      {stream.error && stream.status === 'failed' && <ErrorState error={stream.error} title="Step stream closed" />}

      {views.length === 0 && !pending ? (
        <div className="text-[12px] text-muted" data-testid="agent-no-steps">
          No steps reported.
        </div>
      ) : (
        <StepTimeline taskId={task.id} steps={views} pending={pending} streamState={stream.status} />
      )}
    </div>
  );
}
