'use client';

// Executors from the tool register (GET /ui/tools), grouped by family: co-folding chips solid and
// primary, docking chips dashed and secondary. Unavailable tools are disabled and carry their
// note. The dashed "+ executor" input asks the API to register a tool and shows its answer.

import clsx from 'clsx';
import type { ExecutorChipModel, ExecutorGroupModel } from '@/lib/selectors/run';
import { AddInput, SectionHead } from './parts';

export interface ExecutorChipsProps {
  groups: ExecutorGroupModel[];
  onToggle: (id: string) => void;
  addValue: string;
  onAddValue: (v: string) => void;
  onAdd: (v: string) => void;
  addBusy?: boolean;
  /** API answer to the last "+ executor" request (e.g. 501 not_implemented). */
  addMessage?: { code: string; message: string; status?: number } | null;
}

function ExecutorChip({ c, docking, onToggle }: { c: ExecutorChipModel; docking: boolean; onToggle: (id: string) => void }) {
  const unavailable = !c.available;
  const title = [unavailable ? `not available: ${c.note || 'no reason given'}` : c.note, c.versionTitle].filter(Boolean).join(' · ') || undefined;
  return (
    <button
      type="button"
      aria-pressed={c.selected}
      disabled={c.disabled}
      title={title}
      onClick={() => onToggle(c.id)}
      data-testid="executor-chip"
      data-tool={c.id}
      data-family={docking ? 'docking' : 'co-folding'}
      data-state={c.selected ? 'selected' : unavailable ? 'unavailable' : 'idle'}
      className={clsx(
        'flex items-center gap-2 rounded border leading-[normal] transition-all duration-150',
        docking ? 'border-dashed px-2.5 py-[5px]' : 'px-3 py-[7px]',
        c.selected ? (docking ? 'border-ink2 bg-[#F1F1ED]' : 'border-accent bg-accent-tint') : 'border-line bg-transparent',
        unavailable && 'opacity-45',
        c.disabled ? 'cursor-not-allowed' : 'hover:border-ink',
      )}
    >
      <span className={clsx('font-medium', docking ? 'text-[12px] text-ink2' : 'text-[12.5px] text-ink')}>{c.name}</span>
      {c.version ? <span className={clsx('font-mono text-[10.5px]', docking ? 'text-faint' : 'text-muted')}>{c.version}</span> : null}
    </button>
  );
}

export function ExecutorChips({ groups, onToggle, addValue, onAddValue, onAdd, addBusy, addMessage }: ExecutorChipsProps) {
  const primary = groups.filter((g) => g.family !== 'docking');
  const docking = groups.find((g) => g.family === 'docking');
  return (
    <div data-testid="executor-chips">
      <SectionHead label="Co-folding" hint="registered executors · add any tool with a container" />
      <div className="flex flex-wrap items-center gap-1.5">
        {primary.flatMap((g) => g.chips).map((c) => (
          <ExecutorChip key={c.id} c={c} docking={false} onToggle={onToggle} />
        ))}
      </div>
      <div className="mt-[18px] mb-2 flex items-center gap-3">
        <div className="text-[11px] font-medium tracking-[0.06em] text-faint uppercase">Docking · cross-check</div>
        <div className="flex-1 border-t border-line2" />
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {(docking?.chips ?? []).map((c) => (
          <ExecutorChip key={c.id} c={c} docking onToggle={onToggle} />
        ))}
        <AddInput value={addValue} onChange={onAddValue} onSubmit={onAdd} placeholder="+ executor · image:tag" width={180} small disabled={addBusy} data-testid="add-executor" />
      </div>
      {addMessage && (
        <div className="mt-2 flex items-baseline gap-2 text-[11.5px]" role="status" data-testid="add-executor-message" data-state={addMessage.code}>
          <span className="flex-none font-mono whitespace-nowrap text-stop">
            {addMessage.status ? `${addMessage.status} ` : ''}
            {addMessage.code}
          </span>
          <span className="text-ink2">{addMessage.message}</span>
        </div>
      )}
    </div>
  );
}
