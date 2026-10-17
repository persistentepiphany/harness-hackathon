'use client';

// /reports/[runId]: verdict header, dimension strip, execution, compact layer sidebar, structure
// block with the stage switcher beneath it and the checks of the selected stage, stat cards,
// PoseBusters, per-seed statistics, figures, metrics, scores, perturbation, thresholds and controls.

import Link from 'next/link';
import { useState } from 'react';
import { ErrorState, Spinner } from '@/components/ui';
import { useRunRecord, useTools } from '@/lib/hooks';
import { defaultLayerIndex, stageItems, stageOfLayer } from '@/lib/selectors/report';
import type { UiRunRecord } from '@/lib/types';
import { DimensionStrip } from './DimensionStrip';
import { ExecutionRow } from './ExecutionRow';
import { FiguresPanel } from './FiguresPanel';
import { LayerSidebar } from './LayerSidebar';
import { MetricsTable } from './MetricsTable';
import { PoseBustersGrid } from './PoseBustersGrid';
import { ReportPicker } from './ReportPicker';
import { ScoresSection } from './ScoresSection';
import { StageChecks, StageSwitcher, type StageSelection } from './StageSwitcher';
import { StatCards } from './StatCards';
import { ControlsList, PerturbationList, ThresholdsList } from './ReportLists';
import { SeedStatsTable } from './SeedStatsTable';
import { StructurePanel } from './StructurePanel';
import { VerdictHeader } from './VerdictHeader';

const BTN = 'rounded border border-line bg-transparent px-3 py-[7px] text-[12.5px] leading-[normal] font-medium text-ink hover:border-ink hover:text-ink';
const BTN_PRIMARY = 'rounded border-0 bg-ink px-3.5 py-2 text-[12.5px] leading-[normal] font-medium text-white hover:text-white';

export function downloadRecord(record: UiRunRecord) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: 'application/json' }));
  a.download = `${record.id}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export function RecordGate({ runId, children }: { runId: string; children: (record: UiRunRecord) => React.ReactNode }) {
  const rec = useRunRecord(runId);
  if (rec.data) return <>{children(rec.data)}</>;
  if (rec.error) return <ErrorState error={rec.error} onRetry={rec.reload} title={`Cannot load run ${runId}`} />;
  return (
    <div className="flex items-center gap-2 text-muted" data-testid="record-loading">
      <Spinner /> loading run record
    </div>
  );
}

function Report({ record }: { record: UiRunRecord }) {
  const tools = useTools().data;
  const [picked, setPicked] = useState<{ run: string; sel: StageSelection } | null>(null);
  const fallback = (): StageSelection => {
    const L = record.layers[defaultLayerIndex(record)];
    return { stage: L ? stageOfLayer(L.i) : 'inputs', layer: null };
  };
  const sel = picked && picked.run === record.id ? picked.sel : fallback();
  const setSel = (v: StageSelection) => setPicked({ run: record.id, sel: v });
  const stage = stageItems(record).find((s) => s.id === sel.stage);
  const selectedIdx = sel.layer === null ? -1 : record.layers.findIndex((l) => l.i === sel.layer);
  const id = encodeURIComponent(record.id);
  return (
    <>
      <VerdictHeader
        record={record}
        tools={tools}
        picker={<ReportPicker runId={record.id} />}
        actions={
          <>
            <Link href={`/reports/${id}/ensemble`} className={BTN} data-testid="open-ensemble">
              Ensemble
            </Link>
            <Link href={`/ensemble?runs=${id}`} className={BTN} data-testid="open-compare">
              Compare
            </Link>
            <Link href={`/documents/${id}`} className={BTN_PRIMARY} data-testid="open-document">
              Document
            </Link>
            <button type="button" className={BTN} onClick={() => downloadRecord(record)} data-testid="download-record">
              JSON
            </button>
          </>
        }
      />
      <DimensionStrip
        record={record}
        tools={tools}
        className="mt-6"
        onSelect={(d) => {
          const first = record.layers.find((l) => l.checks.some((c) => d.checkIds.includes(c.id)));
          if (first) setSel({ stage: stageOfLayer(first.i), layer: null });
        }}
      />
      <ExecutionRow record={record} tools={tools} className="mt-3" />
      <div className="mt-8 grid grid-cols-[210px_minmax(0,1fr)] items-start gap-10">
        <LayerSidebar
          record={record}
          tools={tools}
          selected={selectedIdx}
          inStage={stage?.layerIdx ?? []}
          onSelect={(idx) => {
            const L = record.layers[idx];
            if (L) setSel({ stage: stageOfLayer(L.i), layer: L.i });
          }}
        />
        <div className="flex min-w-0 flex-col gap-10">
          <div className="flex flex-col gap-4">
            <StructurePanel record={record} tools={tools} cards={false} />
            <StageSwitcher record={record} tools={tools} value={sel} onChange={setSel} />
            <StageChecks record={record} tools={tools} value={sel} onChange={setSel} />
          </div>
          <StatCards record={record} tools={tools} />
          <PoseBustersGrid record={record} tools={tools} />
          <SeedStatsTable record={record} tools={tools} />
          <FiguresPanel record={record} tools={tools} />
          <div className="grid gap-10" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))' }}>
            <div className="flex flex-col gap-8">
              <MetricsTable record={record} tools={tools} />
              <ScoresSection record={record} tools={tools} />
            </div>
            <div className="flex flex-col gap-8">
              <PerturbationList record={record} tools={tools} />
              <ThresholdsList record={record} tools={tools} />
              <ControlsList record={record} tools={tools} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export function ReportView({ runId }: { runId: string }) {
  return <RecordGate runId={runId}>{(record) => <Report record={record} />}</RecordGate>;
}
