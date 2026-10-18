'use client';

// Dropdown menu: a trigger that shows the current choice, a popover list with optional groups,
// single or multiple selection, disabled items with a reason, and an optional free-text entry.

import clsx from 'clsx';
import { useEffect, useRef, useState } from 'react';

export interface MenuItem {
  id: string;
  label: string;
  /** Muted text after the label (accession, route). */
  sub?: string;
  group?: string;
  disabled?: boolean;
  /** Tooltip; for a disabled item, why it cannot be picked. */
  title?: string;
}

export interface MenuProps {
  label: string;
  items: MenuItem[];
  selected: string[];
  onSelect: (id: string) => void;
  multiple?: boolean;
  placeholder?: string;
  /** Free-text entry at the bottom of the list (accession, SMILES); Enter submits. */
  entry?: { placeholder: string; onSubmit: (value: string) => void };
  className?: string;
  'data-testid'?: string;
}

export function Menu({ label, items, selected, onSelect, multiple, placeholder = 'choose', entry, className, 'data-testid': testId }: MenuProps) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', esc);
    };
  }, [open]);

  const chosen = items.filter((i) => selected.includes(i.id));
  const extra = selected.filter((id) => !items.some((i) => i.id === id));
  const names = [...chosen.map((i) => i.label), ...extra];
  const summary = names.length === 0 ? placeholder : names.length <= 2 ? names.join(', ') : `${names.slice(0, 2).join(', ')} +${names.length - 2}`;
  const groups = [...new Set(items.map((i) => i.group ?? ''))];

  return (
    <div ref={root} className={clsx('relative', className)} data-testid={testId}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label}
        onClick={() => setOpen((o) => !o)}
        className={clsx(
          'flex h-9 w-full items-center justify-between gap-2 rounded border bg-surface px-3 text-left text-[13px] transition-colors duration-150',
          open ? 'border-ink' : 'border-line hover:border-ink',
        )}
      >
        <span className={clsx('min-w-0 truncate', names.length ? 'text-ink' : 'text-muted')}>{summary}</span>
        <svg aria-hidden width="10" height="10" viewBox="0 0 10 10" className={clsx('flex-none text-muted transition-transform', open && 'rotate-180')}>
          <path d="M1.5 3.5 5 7l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
        </svg>
      </button>
      {open && (
        <div role="listbox" aria-multiselectable={multiple || undefined} className="absolute top-[calc(100%+4px)] left-0 z-30 max-h-[340px] w-full min-w-[240px] overflow-y-auto rounded border border-line bg-surface py-1 shadow-lg">
          {groups.map((g) => (
            <div key={g || 'items'}>
              {g && <div className="px-3 pt-2 pb-1 text-[10.5px] font-semibold tracking-[.06em] text-faint uppercase">{g}</div>}
              {items
                .filter((i) => (i.group ?? '') === g)
                .map((i) => {
                  const on = selected.includes(i.id);
                  return (
                    <button
                      key={i.id}
                      type="button"
                      role="option"
                      aria-selected={on}
                      disabled={i.disabled}
                      title={i.title}
                      data-testid="menu-item"
                      data-item={i.id}
                      onClick={() => {
                        onSelect(i.id);
                        if (!multiple) setOpen(false);
                      }}
                      className={clsx(
                        'flex w-full items-center gap-2.5 px-3 py-1.5 text-left text-[13px]',
                        i.disabled ? 'cursor-not-allowed text-faint' : 'text-ink hover:bg-line2',
                      )}
                    >
                      <span className={clsx('flex h-3.5 w-3.5 flex-none items-center justify-center rounded-[3px] border text-[10px]', multiple ? '' : 'rounded-full', on ? 'border-ink bg-ink text-white' : 'border-line')}>
                        {on ? '✓' : ''}
                      </span>
                      <span className="min-w-0 flex-1 truncate">{i.label}</span>
                      {i.sub && <span className="flex-none font-mono text-[11px] text-muted">{i.sub}</span>}
                    </button>
                  );
                })}
            </div>
          ))}
          {entry && (
            <div className="border-t border-line2 px-2 pt-2 pb-1">
              <input
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key !== 'Enter' || !text.trim()) return;
                  entry.onSubmit(text.trim());
                  setText('');
                  if (!multiple) setOpen(false);
                }}
                placeholder={entry.placeholder}
                aria-label={entry.placeholder}
                className="w-full rounded border border-line bg-transparent px-2 py-1.5 font-mono text-[12px] text-ink placeholder:text-[#757575]"
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
