import clsx from 'clsx';
import type { ReactNode } from 'react';

export type StoryState = 'active' | 'done' | 'waiting';

export interface StoryBlockProps {
  step: number;
  title: string;
  /** Right-aligned summary (counts, timing). */
  meta?: ReactNode;
  state: StoryState;
  /** Position among the blocks shown, for the staggered fade when several mount at once. */
  order?: number;
  children: ReactNode;
  'data-testid'?: string;
}

/** One block of the job story: step number, title, summary on the right; fades in when it mounts. */
export function StoryBlock({ step, title, meta, state, order = 0, children, 'data-testid': testId }: StoryBlockProps) {
  return (
    <section
      data-testid={testId}
      data-state={state}
      className="animate-fade-up border-t border-line pt-3.5"
      style={{ animationDelay: `${Math.min(order, 6) * 110}ms`, animationFillMode: 'both' }}
    >
      <div className="mb-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-mono text-[11px] text-faint">{String(step).padStart(2, '0')}</span>
        <h2 className="m-0 text-[13.5px] font-semibold tracking-[-0.005em]">{title}</h2>
        <span aria-hidden className={clsx('inline-block h-1.5 w-1.5 self-center rounded-full', state === 'active' ? 'animate-pulse bg-accent' : state === 'done' ? 'bg-ink2' : 'bg-line')} />
        {meta ? <span className="ml-auto text-right text-[11.5px] text-muted">{meta}</span> : null}
      </div>
      {children}
    </section>
  );
}
