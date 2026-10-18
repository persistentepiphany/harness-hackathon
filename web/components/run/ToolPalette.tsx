'use client';

// Tools first: every executor grouped co-folding · docking · protein–protein, with what it
// produces and where it runs. Click selects the tool and names it in the request; drag drops it
// into the request box.

import clsx from 'clsx';
import type { DragEvent } from 'react';
import { executorGroups, serializeToken, toolToken, TOKEN_MIME, type PromptToken } from '@/lib/selectors/run';
import type { Task, Tool } from '@/lib/types';
import { SectionHead } from './parts';

export function dragToken(e: DragEvent, token: PromptToken) {
  e.dataTransfer.setData(TOKEN_MIME, serializeToken(token));
  e.dataTransfer.setData('text/plain', token.text);
  e.dataTransfer.effectAllowed = 'copy';
}

export function ToolPalette({ register, selected, task, onPick }: { register: Tool[] | null | undefined; selected: string[]; task?: Task | null; onPick: (tool: Tool) => void }) {
  const groups = executorGroups(register, selected, task);
  if (!groups.length) return null;
  const byId = new Map((register ?? []).map((t) => [t.id, t]));
  return (
    <div data-testid="tool-palette">
      <SectionHead label="Tools" hint="click to use · drag into the request" />
      <div className="flex flex-col gap-2">
        {groups.map((g) => (
          <div key={g.group} className="flex flex-wrap items-center gap-1.5">
            <span className="w-[112px] flex-none text-[11.5px] text-muted">{g.label}</span>
            {g.chips.map((c) => {
              const tool = byId.get(c.id);
              const off = !c.available && !c.selected;
              return (
                <button
                  key={c.id}
                  type="button"
                  draggable={!off}
                  disabled={off}
                  onDragStart={(e) => tool && dragToken(e, toolToken(tool))}
                  onClick={() => tool && onPick(tool)}
                  title={[c.endpoints.length ? `produces ${c.endpoints.join(', ')}` : null, c.run, c.note].filter(Boolean).join(' · ')}
                  data-testid="palette-tool"
                  data-tool={c.id}
                  data-state={c.selected ? 'selected' : off ? 'unavailable' : 'idle'}
                  className={clsx(
                    'flex items-baseline gap-1.5 rounded-[6px] border px-2.5 py-1 text-[12.5px] transition-colors duration-150',
                    c.selected ? 'border-ink bg-ink text-white' : off ? 'cursor-not-allowed border-line text-faint' : 'cursor-grab border-line bg-surface text-ink hover:border-ink',
                  )}
                >
                  <span className="font-medium">{c.name}</span>
                  {c.run && <span className={clsx('text-[11px]', c.selected ? 'text-white/70' : 'text-muted')}>{c.run}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
