import clsx from 'clsx';
import type { HTMLAttributes } from 'react';

/** Section label: 11px uppercase, tracking .06em, muted. */
export function Eyebrow({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx('eyebrow', className)} {...rest} />;
}
