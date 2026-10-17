"use client";

// /reports/[runId]: one verdict line, then two columns. Left (sticky on wide screens): the
// structure viewer with the Inputs / Applicability / Outputs switcher beneath it. Right (scrolls):
// dimension strip, execution, the checks of the selected stage, that stage's calculated blocks
// (outputs: ensemble, stat cards, PoseBusters, per-seed statistics, figures, metrics, scores),
// thresholds, then run details, tools and provenance. Selecting a check or a pose drives the viewer.

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { ErrorState, Spinner } from "@/components/ui";
import { useRunRecord, useTools } from "@/lib/hooks";
import {
  checkFocus,
  defaultLayerIndex,
  defaultStructureId,
  stageItems,
  stageOfLayer,
} from "@/lib/selectors/report";
import type { UiRunRecord } from "@/lib/types";
import { DimensionStrip } from "./DimensionStrip";
import { EnsembleTable } from "./EnsembleTable";
import { ExecutionRow } from "./ExecutionRow";
import { FiguresPanel } from "./FiguresPanel";
import { ToolsList } from "./LayerSidebar";
import { MetricsTable } from "./MetricsTable";
import { BlockLabel } from "./parts";
import { PoseBustersGrid } from "./PoseBustersGrid";
import { ProvenanceTable } from "./ProvenanceTable";
import { ControlsList, PerturbationList, ThresholdsList } from "./ReportLists";
import { ReportPicker } from "./ReportPicker";
import { ScoresSection } from "./ScoresSection";
import { SeedStatsTable } from "./SeedStatsTable";
import {
  StageChecks,
  StageSwitcher,
  type StageSelection,
} from "./StageSwitcher";
import { StatCards } from "./StatCards";
import { StructurePanel } from "./StructurePanel";
import { chipForPose, useStructures } from "./useStructures";
import { RunDetails, VerdictLine } from "./VerdictHeader";

const BTN =
  "rounded border border-line bg-transparent px-2.5 py-[5px] text-[12px] leading-[normal] font-medium text-ink hover:border-ink hover:text-ink";
const BTN_PRIMARY =
  "rounded border-0 bg-ink px-3 py-1.5 text-[12px] leading-[normal] font-medium text-white hover:text-white";

export function downloadRecord(record: UiRunRecord) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(
    new Blob([JSON.stringify(record, null, 2)], { type: "application/json" }),
  );
  a.download = `${record.id}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export function RecordGate({
  runId,
  children,
}: {
  runId: string;
  children: (record: UiRunRecord) => React.ReactNode;
}) {
  const rec = useRunRecord(runId);
  if (rec.data) return <>{children(rec.data)}</>;
  if (rec.error)
    return (
      <ErrorState
        error={rec.error}
        onRetry={rec.reload}
        title={`Cannot load run ${runId}`}
      />
    );
  return (
    <div
      className="flex items-center gap-2 text-muted"
      data-testid="record-loading"
    >
      <Spinner /> loading run record
    </div>
  );
}

function Report({ record }: { record: UiRunRecord }) {
  const tools = useTools().data;
  const model = useStructures(record, tools);
  const [picked, setPicked] = useState<{
    run: string;
    sel: StageSelection;
  } | null>(null);
  const [check, setCheck] = useState<{ run: string; id: string | null } | null>(
    null,
  );
  const [pose, setPose] = useState<{ run: string; id: string } | null>(null);
  const right = useRef<HTMLDivElement>(null);
  const fallback = (): StageSelection => {
    const L = record.layers[defaultLayerIndex(record)];
    return { stage: L ? stageOfLayer(L.i) : "inputs", layer: null };
  };
  const sel = picked && picked.run === record.id ? picked.sel : fallback();
  const setSel = (v: StageSelection) => {
    setPicked({ run: record.id, sel: v });
    // keep the switch in view: back to the top of the scrolling column when it is above the fold
    right.current?.scrollTo({ top: 0, behavior: "smooth" });
  };
  const stage = stageItems(record).find((s) => s.id === sel.stage);
  const stageChecks = (stage?.layerIdx ?? []).flatMap((idx) =>
    record.layers[idx].checks.map((c) => c.id),
  );
  const checkId = check && check.run === record.id ? check.id : null;
  const focus = useMemo(
    () => (checkId ? checkFocus(record, checkId) : null),
    [record, checkId],
  );
  const poseFromCheck = chipForPose(model, focus?.pose ?? null);
  const selected =
    poseFromCheck ??
    (pose && pose.run === record.id
      ? pose.id
      : defaultStructureId(model.shown));
  const selectPose = (id: string) => {
    setPose({ run: record.id, id });
    setCheck(null);
  };
  const id = encodeURIComponent(record.id);
  const outputs = sel.stage === "outputs";

  return (
    <>
      <VerdictLine
        record={record}
        tools={tools}
        actions={
          <>
            <Link
              href={`/reports/${id}/ensemble`}
              className={BTN}
              data-testid="open-ensemble"
            >
              Ensemble
            </Link>
            <Link
              href={`/ensemble?runs=${id}`}
              className={BTN}
              data-testid="open-compare"
            >
              Compare
            </Link>
            <Link
              href={`/documents/${id}`}
              className={BTN_PRIMARY}
              data-testid="open-document"
            >
              Document
            </Link>
            <button
              type="button"
              className={BTN}
              onClick={() => downloadRecord(record)}
              data-testid="download-record"
            >
              JSON
            </button>
          </>
        }
      />
      <div className="mt-3 grid min-w-0 gap-6 lg:h-[calc(100vh-128px)] lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-8">
        <aside
          className="flex min-h-0 min-w-0 flex-col"
          data-testid="report-viewer-column"
        >
          <StructurePanel
            record={record}
            tools={tools}
            fill
            selected={selected}
            onSelect={selectPose}
            focus={focus}
            className="h-[380px] lg:h-auto lg:min-h-0 lg:flex-1"
          />
        </aside>
        <div className="flex min-h-0 min-w-0 flex-col gap-4">
          <div
            className="hidden flex-none lg:-mb-2 lg:block lg:h-[30px]"
            aria-hidden
          />
          <StageSwitcher
            record={record}
            tools={tools}
            value={sel}
            onChange={setSel}
            className="flex-none"
          />
          <div
            ref={right}
            className="flex min-w-0 flex-col gap-8 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:pr-2"
            data-testid="report-stage-column"
          >
            <DimensionStrip
              record={record}
              tools={tools}
              onSelect={(d) => {
                const first = record.layers.find((l) =>
                  l.checks.some((c) => d.checkIds.includes(c.id)),
                );
                if (first)
                  setSel({ stage: stageOfLayer(first.i), layer: null });
              }}
            />
            <ExecutionRow record={record} tools={tools} />
            <div key={sel.stage} className="flex animate-stage flex-col gap-8">
              <StageChecks
                record={record}
                tools={tools}
                value={sel}
                onChange={setSel}
                selectedCheck={checkId}
                onSelectCheck={(c) => setCheck({ run: record.id, id: c })}
              />
              {sel.stage === "inputs" && (
                <StatCards record={record} tools={tools} only={["site"]} />
              )}
              {outputs && (
                <>
                  {model.chips.some((m) => m.kind !== "crystal") && (
                    <div>
                      <BlockLabel>Structures</BlockLabel>
                      <EnsembleTable
                        record={record}
                        tools={tools}
                        members={model.chips}
                        more={model.hiddenCount}
                        selected={selected}
                        onSelect={selectPose}
                      />
                    </div>
                  )}
                  <StatCards record={record} tools={tools} />
                  <PoseBustersGrid record={record} tools={tools} />
                  <SeedStatsTable record={record} tools={tools} />
                  <FiguresPanel record={record} tools={tools} />
                  <MetricsTable record={record} tools={tools} />
                  <ScoresSection record={record} tools={tools} />
                  <PerturbationList record={record} tools={tools} />
                  <ControlsList record={record} tools={tools} />
                  <Link
                    href={`/documents/${id}#appendix`}
                    className="self-start font-mono text-[11.5px] text-muted underline decoration-line underline-offset-2 hover:text-ink"
                    data-testid="appendix-link"
                  >
                    every seed and pose → document appendix
                  </Link>
                </>
              )}
              <ThresholdsList
                record={record}
                tools={tools}
                checks={stageChecks}
              />
            </div>
            <div
              className="flex flex-col gap-6 border-t border-line pt-6"
              data-testid="report-details"
            >
              <div>
                <BlockLabel>Details</BlockLabel>
                <ReportPicker runId={record.id} />
                <RunDetails record={record} tools={tools} />
              </div>
              <div>
                <BlockLabel>Tools</BlockLabel>
                <ToolsList record={record} tools={tools} />
              </div>
              <ProvenanceTable record={record} tools={tools} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export function ReportView({ runId }: { runId: string }) {
  return (
    <RecordGate runId={runId}>
      {(record) => <Report record={record} />}
    </RecordGate>
  );
}
