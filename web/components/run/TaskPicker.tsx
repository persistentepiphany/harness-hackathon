'use client';

// Task chips grouped co-folding (solid) and docking (dashed), every task from GET /ui/tasks.

import clsx from 'clsx';
import type { Task } from '@/lib/types';
import { SectionHead } from './parts';

export interface TaskPickerProps {
  cofolding: Task[];
  docking: Task[];
  selected: string;
  hint: string;
  onSelect: (t: Task) => void;
}

function TaskChip({ task, on, dashed, onSelect }: { task: Task; on: boolean; dashed: boolean; onSelect: (t: Task) => void }) {
  const impl = typeof task.implemented === 'number' && typeof task.checks === 'number' ? `checks implemented ${task.implemented}/${task.checks}` : undefined;
  return (
    <button
      type="button"
      aria-pressed={on}
      title={[task.long, impl].filter(Boolean).join(' · ')}
      onClick={() => onSelect(task)}
      data-testid="task-chip"
      data-task={task.id}
      data-group={dashed ? 'docking' : 'co-folding'}
      data-state={on ? 'selected' : 'idle'}
      className={clsx(
        'rounded border font-medium leading-[normal] transition-all duration-150 hover:border-ink',
        dashed ? 'border-dashed px-[11px] py-1.5 text-[12px]' : 'px-3 py-[7px] text-[12.5px]',
        on ? 'border-ink bg-ink text-white' : clsx('border-line bg-transparent', dashed ? 'text-ink2' : 'text-ink'),
      )}
    >
      {task.name}
    </button>
  );
}

export function TaskPicker({ cofolding, docking, selected, hint, onSelect }: TaskPickerProps) {
  return (
    <div data-testid="task-picker">
      <SectionHead label="Task · co-folding" hint={hint} />
      <div className="flex flex-wrap gap-1.5">
        {cofolding.map((t) => (
          <TaskChip key={t.id} task={t} on={selected === t.id} dashed={false} onSelect={onSelect} />
        ))}
      </div>
      {docking.length > 0 && (
        <>
          <div className="mt-4 mb-2 text-[11px] font-medium tracking-[0.06em] text-faint uppercase">Task · docking</div>
          <div className="flex flex-wrap gap-1.5">
            {docking.map((t) => (
              <TaskChip key={t.id} task={t} on={selected === t.id} dashed onSelect={onSelect} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
