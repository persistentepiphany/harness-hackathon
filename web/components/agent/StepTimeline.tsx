'use client';

// Step timeline of one agent task (prototype AGENT view, right column). Kinds: thought (hollow
// grey dot), tool and result (square, blue and grey, mono text), report (accent), conclusion (ink,
// weight 500). Each row shows its offset from the task start and the duration the agent reported;
// run ids the step refers to link to the job and its report. New steps scroll into view while the
// viewer is at the bottom of the page.

import clsx from 'clsx';
import Link from 'next/link';
import { useEffect, useRef } from 'react';
import type { StepView } from '@/lib/selectors/agent';
import type { AgentStepKind } from '@/lib/types';

interface KindStyle {
  label: string;
  marker: string;
  text: string;
}

const KIND: Record<AgentStepKind, KindStyle> = {
  thought: { label: 'text-muted', marker: 'rounded-full border-muted bg-transparent', text: 'font-sans text-[13px] text-ink2' },
  tool: { label: 'text-docking', marker: 'rounded-[2px] border-docking bg-docking', text: 'font-mono text-[12px] text-ink' },
  result: { label: 'text-ink2', marker: 'rounded-[2px] border-ink2 bg-ink2', text: 'font-mono text-[12px] text-ink' },
  report: { label: 'text-accent', marker: 'rounded-full border-accent bg-accent', text: 'font-mono text-[12px] text-ink' },
  conclusion: { label: 'text-ink', marker: 'rounded-full border-ink bg-ink', text: 'font-sans text-[14px] font-medium text-ink' },
};

/** Distance from the bottom of the page within which new steps are followed. */
const FOLLOW_PX = 160;

export interface StepTimelineProps {
  taskId: string;
  steps: StepView[];
  /** Label of the pending row; null hides it (task finished or stream ended). */
  pending: string | null;
  /** Stream status, exposed as data-state for tests and agent harnesses. */
  streamState?: string;
}

export function StepTimeline({ taskId, steps, pending, streamState }: StepTimelineProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const prev = useRef<{ task: string | null; n: number }>({ task: null, n: 0 });

  useEffect(() => {
    const measure = () => {
      const doc = document.documentElement;
      nearBottom.current = window.innerHeight + window.scrollY >= doc.scrollHeight - FOLLOW_PX;
    };
    measure();
    window.addEventListener('scroll', measure, { passive: true });
    window.addEventListener('resize', measure);
    return () => {
      window.removeEventListener('scroll', measure);
      window.removeEventListener('resize', measure);
    };
  }, []);

  const count = steps.length;
  useEffect(() => {
    const last = prev.current;
    prev.current = { task: taskId, n: count };
    // switching tasks or the first replay never scrolls; growth of the followed task does
    if (last.task !== taskId || count <= last.n || !nearBottom.current) return;
    endRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [taskId, count]);

  return (
    <div className="ml-1.5 flex flex-col border-l border-line" data-testid="agent-timeline" data-state={streamState}>
      {steps.map((s) => {
        const k = KIND[s.kind];
        return (
          <div
            key={s.seq}
            className="-ml-1.5 grid animate-fade-up grid-cols-[24px_60px_minmax(0,1fr)] items-baseline gap-x-3 py-[9px]"
            data-testid="agent-step"
            data-state={s.kind}
            data-seq={s.seq}
          >
            <span className={clsx('relative top-[2px] h-[11px] w-[11px] justify-self-start border-[1.5px]', k.marker)} aria-hidden />
            <span className="font-mono text-[10.5px] text-muted" title={s.offsetMs === null ? undefined : `${s.offsetMs} ms after the task started`}>
              {s.offsetLabel}
            </span>
            <div className="min-w-0">
              <div className={clsx('mb-0.5 text-[10.5px] tracking-[.06em] uppercase', k.label)}>
                {s.kind}
                {s.msLabel && (
                  <span className="ml-2 font-mono tracking-normal text-faint normal-case" data-testid="agent-step-ms">
                    {s.msLabel}
                  </span>
                )}
              </div>
              <div className={clsx('leading-[1.55] text-pretty [overflow-wrap:anywhere]', k.text)}>{s.text}</div>
              {s.links.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-[10.5px] text-muted">
                  {s.links.map((l) => (
                    <span key={l.id} className="flex items-baseline gap-2" data-testid="agent-step-run" data-run={l.id}>
                      <span>{l.id}</span>
                      <Link href={l.jobHref} className="text-docking underline decoration-line underline-offset-2" data-testid="agent-step-job-link">
                        job
                      </Link>
                      <Link href={l.reportHref} className="text-docking underline decoration-line underline-offset-2" data-testid="agent-step-report-link">
                        report
                      </Link>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
      {pending && (
        <div className="-ml-1.5 grid grid-cols-[24px_60px_minmax(0,1fr)] items-baseline gap-x-3 py-[9px]" data-testid="agent-pending">
          <span className="relative top-[2px] h-[11px] w-[11px] animate-spin justify-self-start rounded-full border-[1.5px] border-line border-t-accent" aria-hidden />
          <span />
          <span className="text-[12px] text-faint">{pending}</span>
        </div>
      )}
      <div ref={endRef} className="h-px" aria-hidden />
    </div>
  );
}
