import clsx from 'clsx';
import { DASH, fmtNum, isMissing } from '@/lib/format';

export interface MonoNumProps {
  value: number | string | null | undefined;
  unit?: string | null;
  digits?: number;
  className?: string;
  title?: string;
  'data-testid'?: string;
}

/** A number in Geist Mono with its unit after a thin space; missing values are a muted en dash. */
export function MonoNum({ value, unit, digits, className, title, ...rest }: MonoNumProps) {
  const missing = isMissing(value);
  return (
    <span
      className={clsx('font-mono tabular-nums', missing && 'text-faint', className)}
      title={title ?? (missing ? 'not computed' : undefined)}
      data-testid={rest['data-testid']}
      data-missing={missing ? 'true' : undefined}
    >
      {missing ? DASH : fmtNum(value, unit, digits)}
    </span>
  );
}
