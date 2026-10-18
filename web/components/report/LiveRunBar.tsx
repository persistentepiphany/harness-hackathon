"use client";

// While a run is in progress the report is its live view: current stage, elapsed time, the
// engaged executor and the latest log lines. Checks, structures and renders fill in below as the
// record updates.

import clsx from "clsx";
import { useJobLog } from "@/lib/hooks";
import { executionRows } from "@/lib/selectors/report";
import type { UiRunRecord } from "@/lib/types";

const LAYER_NAMES = [
  "Provenance",
  "Input integrity",
  "Input adequacy",
  "Applicability",
  "Output validity",
  "Output support",
];

/** True while the run has not finished (status `running`, `queued`, or not reported yet). */
export function isLive(record: UiRunRecord): boolean {
  return record.status !== "done" && record.status !== "failed";
}

export function LiveRunBar({
  record,
  className,
}: {
  record: UiRunRecord;
  className?: string;
}) {
  const log = useJobLog(record.id);
  const lines = log.data;
  const last = lines[lines.length - 1];
  const layer =
    [...lines].reverse().find((l) => l.layer !== null)?.layer ?? null;
  const exec = executionRows(record).find(
    (e) =>
      e.phase === "running" || e.phase === "building" || e.phase === "queued",
  );
  const stage = exec
    ? `${exec.name} ${exec.phase === "running" ? "running" : exec.phase}${exec.gpu ? ` on ${exec.gpu}` : ""}${exec.route ? ` · ${exec.route}` : ""}`
    : layer !== null
      ? (LAYER_NAMES[layer] ?? `layer ${layer}`)
      : "starting";
  return (
    <div
      className={clsx(
        "flex flex-col gap-1 rounded-card border border-line bg-surface px-3 py-2",
        className,
      )}
      data-testid="live-run"
      data-state={exec?.phase ?? "checks"}
    >
      <div className="flex items-baseline gap-2 text-[12.5px]">
        <span className="relative top-[-1px] h-[7px] w-[7px] flex-none animate-pulse rounded-full bg-accent" />
        <span className="font-medium text-ink">{stage}</span>
        {last && <span className="text-muted tabular-nums">{last.t}</span>}
        {exec?.seeds.length ? (
          <span className="text-muted tabular-nums">
            seeds {exec.seeds.filter((s) => s.phase === "done").length} of{" "}
            {exec.seeds.length}
          </span>
        ) : null}
      </div>
      <div
        className="flex flex-col text-[11.5px] text-ink2"
        data-testid="live-log"
      >
        {lines.slice(-3).map((l) => (
          <span key={l.seq} className="truncate">
            <span className="mr-2 text-faint tabular-nums">{l.t}</span>
            {l.plain}
          </span>
        ))}
        {!lines.length && (
          <span className="text-muted">waiting for the first events</span>
        )}
      </div>
    </div>
  );
}
