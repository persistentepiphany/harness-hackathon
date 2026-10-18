import clsx from 'clsx';
import type { VerdictMeta } from '@/lib/selectors/jobs';
import { VERDICT_TEXT } from './tone';

/** Inputs block of the single-job view (prototype `rj.inputsLine1/2`, plus the ligand). */
export function JobInputs({ lines }: { lines: string[] }) {
  return (
    <div data-testid="job-inputs">
      <div className="eyebrow mb-2">Inputs</div>
      <div className="font-mono text-[11.5px] leading-[1.8] text-ink2">
        {lines.map((l, i) => (
          <div key={i} className="truncate" title={l}>
            {l}
          </div>
        ))}
      </div>
    </div>
  );
}

export interface JobVerdictProps {
  meta: VerdictMeta;
  outcome: string | null;
  claim: string;
  counts: { text: string; skip?: string };
  error?: string | null;
}

/** Verdict of a finished job (prototype: label, “claim”, counts). */
export function JobVerdict({ meta, outcome, claim, counts, error }: JobVerdictProps) {
  return (
    <div className="border-t border-line pt-3.5" data-testid="verdict" data-state={outcome ?? 'none'}>
      <div className={clsx('text-[16px] font-semibold', VERDICT_TEXT[meta.tone])}>{meta.label}</div>
      {claim && <div className="mt-[3px] text-[12.5px]">“{claim}”</div>}
      <div className="mt-1.5 font-mono text-[11.5px] text-muted">
        {counts.text}
        {counts.skip && <span className="text-faint">{counts.skip}</span>}
      </div>
      {error && <div className="mt-1.5 text-[12px] break-words text-stop">{error}</div>}
    </div>
  );
}
