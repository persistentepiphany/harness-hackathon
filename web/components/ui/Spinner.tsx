import clsx from 'clsx';

export interface SpinnerProps {
  /** Diameter in px (prototype uses 9 to 10). */
  size?: number;
  className?: string;
  label?: string;
}

/** Pending ring: line-coloured with an accent top, spin .8s. */
export function Spinner({ size = 10, className, label = 'loading' }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label={label}
      className={clsx('inline-block flex-none animate-spin rounded-full border-[1.5px] border-line border-t-accent', className)}
      style={{ width: size, height: size }}
    />
  );
}
