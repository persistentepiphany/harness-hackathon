import clsx from 'clsx';
import Link from 'next/link';
import type { ReactNode } from 'react';
import type { VerdictMeta } from '@/lib/selectors/jobs';
import { VERDICT_TEXT } from './tone';

export interface ReportCardProps {
  meta: VerdictMeta;
  outcome: string | null;
  claimLabel: string;
  claim: string;
  counts: { text: string; skip?: string };
  numbers: { k: string; v: string }[];
  href: string | null;
  statement?: string;
  error?: string | null;
  children?: ReactNode;
}

/** Final block of the job story: verdict, the claim tested, key numbers, link into the report. */
export function ReportCard({ meta, outcome, claimLabel, claim, counts, numbers, href, statement, error }: ReportCardProps) {
  return (
    <div className="rounded border border-line bg-surface px-4 py-3.5" data-testid="verdict" data-state={outcome ?? 'none'}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className={clsx('text-[16px] font-semibold', VERDICT_TEXT[meta.tone])}>{meta.label}</div>
        {href && (
          <Link href={href} data-testid="story-open-report" className="text-[12.5px] font-medium text-ink hover:text-accent-deep">
            Open report →
          </Link>
        )}
      </div>
      {claim && (
        <div className="mt-1 text-[12.5px]">
          <span className="text-muted">{claimLabel} </span>“{claim}”
        </div>
      )}
      {statement && <div className="mt-1 text-[12px] text-pretty text-ink2">{statement}</div>}
      <div className="mt-1.5 font-mono text-[11.5px] text-muted">
        {counts.text}
        {counts.skip && <span className="text-faint">{counts.skip}</span>}
      </div>
      {numbers.length > 0 && (
        <dl className="mt-2.5 grid grid-cols-[repeat(auto-fit,minmax(120px,1fr))] gap-x-4 gap-y-1.5 border-t border-line2 pt-2.5 text-[12px]" data-testid="report-numbers">
          {numbers.map((n) => (
            <div key={n.k} className="min-w-0">
              <dt className="text-[10.5px] tracking-[0.06em] text-muted uppercase">{n.k}</dt>
              <dd className="m-0 truncate font-mono text-[12px]" title={n.v}>
                {n.v}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {error && <div className="mt-1.5 text-[12px] break-words text-stop">{error}</div>}
    </div>
  );
}
