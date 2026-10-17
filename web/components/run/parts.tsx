import clsx from 'clsx';
import type { ReactNode } from 'react';

export type RingState = 'loading' | 'ok' | 'error' | 'idle';

/**
 * The prototype's status ring (`spinner()` in logic-v2.js): a line-coloured ring with an accent
 * top that spins while loading, a filled pass dot when done. `error` fills stop, `idle` faint.
 */
export function RingDot({ state, size = 8, className }: { state: RingState; size?: number; className?: string }) {
  return (
    <span
      aria-hidden
      data-state={state}
      className={clsx(
        'inline-block flex-none rounded-full border-[1.5px]',
        state === 'loading' && 'animate-spin border-line border-t-accent bg-transparent',
        state === 'ok' && 'border-pass bg-pass',
        state === 'error' && 'border-stop bg-stop',
        state === 'idle' && 'border-faint bg-faint',
        className,
      )}
      style={{ width: size, height: size }}
    />
  );
}

/** Section label row: uppercase eyebrow on the left, faint hint on the right. */
export function SectionHead({ label, hint, className }: { label: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <div className={clsx('mb-2.5 flex items-baseline justify-between gap-3', className)}>
      <div className="eyebrow">{label}</div>
      {hint ? <span className="text-right text-[11px] text-faint">{hint}</span> : null}
    </div>
  );
}

/** Dashed "+ …" input that adds an entry on Enter (prototype `addKey`). */
export function AddInput({
  value,
  onChange,
  onSubmit,
  placeholder,
  width,
  small,
  disabled,
  'data-testid': testId,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: (v: string) => void;
  placeholder: string;
  width: number;
  small?: boolean;
  disabled?: boolean;
  'data-testid'?: string;
}) {
  return (
    <input
      value={value}
      disabled={disabled}
      data-testid={testId}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={(e) => {
        if (e.key !== 'Enter') return;
        const v = value.trim();
        if (v) onSubmit(v);
      }}
      placeholder={placeholder}
      aria-label={placeholder}
      className={clsx(
        'rounded border border-dashed border-[#D7D7D2] bg-transparent font-mono leading-[normal] text-ink placeholder:text-[#757575] disabled:opacity-50',
        small ? 'px-2.5 py-[5px] text-[12px]' : 'px-[11px] py-[7px] text-[12.5px]',
      )}
      style={{ width }}
    />
  );
}
