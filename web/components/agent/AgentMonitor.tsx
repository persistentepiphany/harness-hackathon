'use client';

// Autonomous agent monitor (prototype AGENT view): read-only. The task list polls
// (useAgentTasks), so tasks an agent starts appear without a reload; the selected task's steps
// stream live (useAgentSteps). The selection is kept in ?task= so a view can be shared.

import { useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { EmptyState, ErrorState, Spinner } from '@/components/ui';
import { harnessMode } from '@/lib/config';
import { useAgentSteps, useAgentTasks } from '@/lib/hooks';
import { INITIAL_FOLLOW, agentSummary, defaultTaskId, isActive, nextFollow, taskCard, type FollowState } from '@/lib/selectors/agent';
import type { AgentTask } from '@/lib/types';
import { TaskDetail } from './TaskDetail';
import { TaskList } from './TaskList';

function useNow(enabled: boolean, everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!enabled) return;
    const t = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(t);
  }, [enabled, everyMs]);
  return now;
}

export function AgentMonitor() {
  const live = harnessMode() === 'live';
  const tasks = useAgentTasks();
  const list = useMemo(() => tasks.data ?? [], [tasks.data]);
  const urlTask = useSearchParams().get('task');
  const [picked, setPicked] = useState<string | null>(null);

  // without a pick: the task selected at first load stays, tasks that start later are followed
  const [follow, setFollow] = useState<{ data: AgentTask[] | undefined; state: FollowState }>({ data: undefined, state: INITIAL_FOLLOW });
  if (tasks.data && tasks.data !== follow.data) setFollow({ data: tasks.data, state: nextFollow(follow.state, tasks.data) });
  const autoId = follow.state.auto;

  const valid = (id: string | null) => !!id && list.some((t) => t.id === id);
  const selectedId = valid(picked) ? picked : valid(urlTask) ? urlTask : valid(autoId) ? autoId : defaultTaskId(list);
  const selected = list.find((t) => t.id === selectedId) ?? null;
  const stream = useAgentSteps(selectedId);
  const anyActive = list.some(isActive);
  const now = useNow(live && anyActive);

  const { reload } = tasks;

  // the stream ends when the task finishes: re-read the list for its status and outcome
  useEffect(() => {
    if (stream.ended && selected && isActive(selected)) reload();
  }, [stream.ended, selected, reload]);

  const select = (id: string) => {
    setPicked(id);
    // keep the pick in the URL so the view can be shared (Next syncs useSearchParams)
    const params = new URLSearchParams(window.location.search);
    params.set('task', id);
    window.history.replaceState(window.history.state, '', `${window.location.pathname}?${params}`);
  };

  const cards = list.map((t) => taskCard(t, { live, nowMs: now, steps: t.id === selectedId ? stream.data : undefined }));
  const selectedCard = cards.find((c) => c.id === selectedId) ?? null;

  return (
    <main
      className="mx-auto grid w-full max-w-[1200px] animate-fade-up grid-cols-[minmax(260px,340px)_minmax(0,1fr)] items-start gap-10 px-6 pt-11 pb-20"
      data-testid="page-agent"
      data-state={tasks.loading ? 'loading' : tasks.error && !tasks.data ? 'error' : 'ready'}
    >
      <div className="sticky top-[68px] flex flex-col gap-2.5">
        <h1 className="m-0 mb-1.5 text-[18px] font-semibold tracking-[-0.01em]">
          Agent{' '}
          {tasks.data && (
            <span className="ml-2 text-[13px] font-normal text-muted" data-testid="agent-summary">
              {agentSummary(list)}
            </span>
          )}
        </h1>
        {tasks.loading && !tasks.data && (
          <div className="flex items-center gap-2 text-muted" data-testid="agent-loading">
            <Spinner /> loading tasks
          </div>
        )}
        {tasks.error && <ErrorState error={tasks.error} onRetry={reload} title="Cannot list agent tasks" />}
        {tasks.data && list.length === 0 && (
          <EmptyState data-testid="agent-empty">
            No agent tasks. An agent reports its steps with <span className="font-mono">pah agent-log start</span>,{' '}
            <span className="font-mono">POST /ui/agent/tasks</span> or the MCP tool <span className="font-mono">agent_start</span>.
          </EmptyState>
        )}
        <TaskList tasks={cards} selectedId={selectedId} onSelect={select} />
      </div>
      {selected && selectedCard ? (
        <TaskDetail key={selected.id} task={selected} card={selectedCard} steps={stream.data} stream={stream} />
      ) : (
        <div />
      )}
    </main>
  );
}
