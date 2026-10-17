import clsx from 'clsx';
import type { ButtonHTMLAttributes } from 'react';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary = ink fill (Start run, Quick setup); secondary = outlined (Manual setup); ghost = text only. */
  variant?: 'primary' | 'secondary' | 'ghost';
}

/** Prototype buttons: 6px radius, 12.5px medium text. */
export function Button({ variant = 'primary', className, type = 'button', ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={clsx(
        'rounded text-[12.5px] leading-[normal] font-medium transition-opacity duration-200 disabled:cursor-not-allowed disabled:opacity-40',
        variant === 'primary' && 'border-0 bg-ink px-3.5 py-2 text-white',
        variant === 'secondary' && 'border border-line bg-transparent px-3 py-[7px] text-ink2 hover:border-ink hover:text-ink',
        variant === 'ghost' && 'border-0 bg-transparent px-1.5 py-2 text-muted hover:text-ink',
        className,
      )}
      {...rest}
    />
  );
}
