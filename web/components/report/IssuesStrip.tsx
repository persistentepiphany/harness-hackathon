"use client";

// Issues first: every stop and warning with its value, and what is missing (output checks that
// wait for predictions). Clicking an issue opens its check and focuses the structure.

import clsx from "clsx";
import { checkValue } from "@/lib/format";
import { RESULT_COLOR, verdictView } from "@/lib/selectors/report";
import type { UiCheck, UiRunRecord } from "@/lib/types";

interface Issue {
  check: UiCheck;
  layer: number;
}

const MAX = 4;

function issuesOf(record: UiRunRecord): Issue[] {
  const out: Issue[] = [];
  for (const l of record.layers)
    for (const c of l.checks)
      if (c.result === "stop" || c.result === "warn")
        out.push({ check: c, layer: l.i });
  return out.sort(
    (a, b) =>
      Number(b.check.result === "stop") - Number(a.check.result === "stop"),
  );
}

export function IssuesStrip({
  record,
  onSelect,
  className,
}: {
  record: UiRunRecord;
  onSelect: (checkId: string, layer: number) => void;
  className?: string;
}) {
  const issues = issuesOf(record);
  const pending = verdictView(record).pending;
  if (!issues.length && !pending) return null;
  const shown = issues.slice(0, MAX);
  return (
    <div
      className={clsx("flex flex-wrap items-stretch gap-2", className)}
      data-testid="issues"
    >
      {shown.map(({ check: c, layer }) => (
        <button
          key={c.id}
          type="button"
          onClick={() => onSelect(c.id, layer)}
          className="flex max-w-[360px] min-w-0 items-start gap-2 rounded-[6px] border border-line bg-surface px-2.5 py-1.5 text-left transition-colors duration-200 hover:border-ink"
          data-testid="issue"
          data-state={c.result}
          data-check={c.id}
          title={c.evidence ?? c.message ?? c.name}
        >
          <span
            className="relative top-[5px] h-[7px] w-[7px] flex-none rounded-full"
            style={{ background: RESULT_COLOR[c.result] }}
          />
          <span className="min-w-0">
            <span className="block truncate text-[12px] font-medium text-ink">
              {c.name}
            </span>
            <span className="block truncate text-[11.5px] text-ink2 tabular-nums">
              {checkValue(c)}
            </span>
          </span>
        </button>
      ))}
      {issues.length > MAX && (
        <span
          className="self-center text-[11.5px] text-muted"
          data-testid="issues-more"
        >
          +{issues.length - MAX} more in the check list
        </span>
      )}
      {pending > 0 && (
        <span
          className="flex items-start gap-2 rounded-[6px] border border-dashed border-line px-2.5 py-1.5"
          data-testid="issue-pending"
        >
          <span className="relative top-[5px] h-[7px] w-[7px] flex-none rounded-full border border-muted" />
          <span>
            <span className="block text-[12px] font-medium text-ink">
              {pending} output checks pending
            </span>
            <span className="block text-[11.5px] text-ink2">
              no predictions in this run; run the models to evaluate them
            </span>
          </span>
        </span>
      )}
    </div>
  );
}
