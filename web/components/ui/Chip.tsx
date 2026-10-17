import clsx from 'clsx';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

export interface ChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  selected?: boolean;
  /** Secondary mono label after the main label (accession, CCD code). */
  sub?: ReactNode;
  /** Dashed border, the prototype's marker for docking / secondary elements. */
  dashed?: boolean;
  children: ReactNode;
}

/** Selectable chip. Selected = bg-ink text-white (HANDOFF §3). */
export function Chip({ selected, sub, dashed, className, children, disabled, ...rest }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      disabled={disabled}
      data-selected={selected ? 'true' : undefined}
      className={clsx(
        'flex items-baseline gap-2 rounded border px-3 py-[7px] text-[12.5px] leading-[normal] font-medium transition-all duration-150',
        selected ? 'border-ink bg-ink text-white' : 'border-line bg-transparent text-ink hover:border-ink',
        dashed && !selected && 'border-dashed',
        disabled && 'cursor-not-allowed opacity-45 hover:border-line',
        className,
      )}
      {...rest}
    >
      <span>{children}</span>
      {sub !== undefined && sub !== null && (
        <span className={clsx('font-mono text-[10.5px]', selected ? 'text-faint' : 'text-muted')}>{sub}</span>
      )}
    </button>
  );
}
