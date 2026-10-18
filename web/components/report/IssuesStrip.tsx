"use client";

// Issues first: every stop and warning with its value, and what is missing (output checks that
// wait for predictions). Clicking an issue opens its check and focuses the structure.

import clsx from "clsx";
import { checkValue } from "@/lib/format";
import { referenceOnly, RESULT_COLOR, verdictView } from "@/lib/selectors/report";
import type { UiCheck, UiRunRecord } from "@/lib/types";

interface Issue {
  check: UiCheck;
  layer: number;
}

const MAX = 6;

/** Stops first (P1), then warnings (P2); within a priority, earlier layers first. */
function issuesOf(record: UiRunRecord): Issue[] {
  const out: Issue[] = [];
  for (const l of record.layers)
    for (const c of l.checks)
      if (c.result === "stop" || c.result === "warn")
        out.push({ check: c, layer: l.i });
  return out.sort(
    (a, b) =>
      Number(b.check.result === "stop") - Number(a.check.result === "stop") ||
      a.layer - b.layer,
  );
}

function pendingNote(record: UiRunRecord): string {
  const ex = record.execution ?? [];
  const live = ex.filter((e) => ["queued", "building", "running"].includes(e.phase));
  if (live.length)
    return `${live.map((e) => e.name).join(", ")} running on ${live.some((e) => e.route !== "local") ? "Modal" : "CPU"}; output checks run when predictions arrive`;
  if (ex.some((e) => e.phase === "failed"))
    return "an executor failed; see the execution rows";
  if (!referenceOnly(record)) return "these checks need an input this run does not have";
  return "no model ran in this run; pick tools on New run to evaluate outputs";
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
  const stops = issues.filter((i) => i.check.result === "stop").length;
  return (
    <section
      className={clsx("rounded-card border border-line bg-surface", className)}
      data-testid="issues"
    >
      <div className="flex items-baseline justify-between gap-3 border-b border-line2 px-4 py-2.5">
        <span className="text-[13px] font-semibold text-ink">Issues</span>
        <span className="text-[11.5px] text-muted tabular-nums">
          {stops} stop · {issues.length - stops} warn{pending ? ` · ${pending} pending` : ""}
        </span>
      </div>
      <div className="divide-y divide-line2">
        {shown.map(({ check: c, layer }) => (
          <button
            key={c.id}
            type="button"
            onClick={() => onSelect(c.id, layer)}
            className="grid w-full grid-cols-[76px_minmax(0,1.2fr)_minmax(0,1fr)_32px] items-baseline gap-3 px-4 py-2 text-left transition-colors duration-150 hover:bg-line2"
            data-testid="issue"
            data-state={c.result}
            data-check={c.id}
            title={c.evidence ?? c.message ?? c.name}
          >
            <span
              className="text-[10.5px] font-semibold tracking-[.04em] whitespace-nowrap uppercase"
              style={{ color: RESULT_COLOR[c.result] }}
            >
              {c.result === "stop" ? "P1" : "P2"} {c.result}
            </span>
            <span className="truncate text-[12.5px] text-ink">{c.name}</span>
            <span className="truncate text-[12px] text-ink2 tabular-nums">
              {checkValue(c)}
            </span>
            <span className="text-right font-mono text-[11px] text-muted">
              L{layer}
            </span>
          </button>
        ))}
        {issues.length > MAX && (
          <div className="px-4 py-2 text-[11.5px] text-muted" data-testid="issues-more">
            +{issues.length - MAX} more in the check list
          </div>
        )}
        {pending > 0 && (
          <div
            className="grid grid-cols-[76px_minmax(0,1fr)] items-baseline gap-3 px-4 py-2"
            data-testid="issue-pending"
          >
            <span className="text-[10.5px] font-semibold tracking-[.04em] text-muted uppercase">
              P3
            </span>
            <span className="min-w-0 text-[12px] text-ink2">
              <span className="font-medium text-ink">{pending} output check{pending > 1 ? "s" : ""} pending</span>
              {" · "}
              {pendingNote(record)}
            </span>
          </div>
        )}
      </div>
    </section>
  );
}
