import clsx from 'clsx';
import type { HTMLAttributes } from 'react';

/** Tabular container: bg-surface, 1px line border, 8px radius. Only for tabular data (HANDOFF §3). */
export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx('rounded-card border border-line bg-surface', className)} {...rest} />;
}
