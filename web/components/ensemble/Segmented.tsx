'use client';

// Segmented toggle in the structure-chip style (mono 11.5px, selected = ink fill).

import clsx from 'clsx';

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  disabled?: boolean;
  title?: string;
}

export function Segmented<T extends string>({ label, value, options, onChange, testId }: { label?: string; value: T; options: SegmentOption<T>[]; onChange: (v: T) => void; testId?: string }) {
  return (
    <div className="flex items-center gap-2" data-testid={testId} data-state={value}>
      {label && <span className="font-mono text-[10.5px] text-muted">{label}</span>}
      <div className="inline-flex overflow-hidden rounded-[5px] border border-line">
        {options.map((o, i) => {
          const on = o.value === value;
          return (
            <button
              key={o.value}
              type="button"
              disabled={o.disabled}
              title={o.title}
              aria-pressed={on}
              data-value={o.value}
              onClick={() => onChange(o.value)}
              className={clsx(
                'px-[9px] py-1 font-mono text-[11.5px] font-medium transition-colors duration-150',
                i > 0 && 'border-l border-line',
                on ? 'bg-ink text-white' : o.disabled ? 'cursor-not-allowed bg-transparent text-faint' : 'bg-transparent text-ink2 hover:text-ink',
              )}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Toggle chip (filter). */
export function ToggleChip({ on, onChange, children, disabled, title, testId }: { on: boolean; onChange: (v: boolean) => void; children: React.ReactNode; disabled?: boolean; title?: string; testId?: string }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      disabled={disabled}
      title={title}
      data-testid={testId}
      data-state={on ? 'on' : 'off'}
      onClick={() => onChange(!on)}
      className={clsx(
        'rounded-[5px] border px-[9px] py-1 font-mono text-[11.5px] font-medium transition-colors duration-150',
        on ? 'border-ink bg-ink text-white' : disabled ? 'cursor-not-allowed border-line bg-transparent text-faint' : 'border-line bg-transparent text-ink2 hover:border-ink',
      )}
    >
      {children}
    </button>
  );
}
