import clsx from 'clsx';
import type { ReactNode } from 'react';

export interface EmptyStateProps {
  /** Defaults to "not computed": the harness has not produced this block. */
  children?: ReactNode;
  className?: string;
  'data-testid'?: string;
}

/** Muted placeholder for a block with no data ("not computed", "no data"). */
export function EmptyState({ children = 'not computed', className, ...rest }: EmptyStateProps) {
  return (
    <div className={clsx('text-[12px] text-muted', className)} data-testid={rest['data-testid'] ?? 'empty-state'}>
      {children}
    </div>
  );
}
