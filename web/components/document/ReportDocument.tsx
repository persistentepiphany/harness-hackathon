'use client';

// Printable A4 run report (prototype DOCUMENTS view): header, verdict, key numbers, structure and
// PAE, stat cards, figures, agreement, interactions, PoseBusters, per-seed table, confidence,
// layers, flagged findings and provenance. Built from the run record only; the report blocks and
// figures come from components/report in their `print` variant. Blocks the harness did not compute
// keep their slot with "not computed". Live records show the PyMOL renders, the report figures and
// the provenance graph the run wrote.

import clsx from 'clsx';
import { useMemo } from 'react';
import {
  AgreementMatrix,
  CalibrationCurve,
  InteractionDiagram,
  MetricsTable,
  PaeHeatmap,
  PoseBustersGrid,
  ProvenanceTable,
  SeedSpread,
  SeedStatsTable,
  StatCards,
  StructureImage,
} from '@/components/report';
import { paeFromStats } from '@/components/report/figures/pae';
import { mockPae } from '@/components/report/figures/pae-mock';
import { StructureViewer } from '@/components/viewer/StructureViewer';
import { useViewerConfig } from '@/components/viewer/config';
import { fmtDateTime } from '@/lib/format';
import { getHarnessApi } from '@/lib/harness-api';
import {
  blockSource,
  docLayers,
  flaggedChecks,
  interactionSummary,
  keyNumbers,
  metaLine,
  recordLine,
  seedAxisLabel,
  seedStatsLine,
  sourceSuffix,
} from '@/lib/selectors/document';
import {
  RESULT_COLOR,
  defaultStructureId,
  metricRows,
  physicsColumns,
  structureCaption,
  structureTargets,
  verdictMeta,
} from '@/lib/selectors/report';
import type { PhysicsRow, RecordRender, Tool, UiRunRecord } from '@/lib/types';
import { BlockBoundary } from './BlockBoundary';
import { DocCaption, DocLabel, DocNotComputed, KeyNumbers } from './DocParts';

export interface ReportDocumentProps {
  record: UiRunRecord;
  /** Tool register (GET /ui/tools); record.tools[].outputs is used first. */
  tools?: Tool[] | null;
  /** Document title (the job name). */
  name: string;
}

const PHYSICS_WORDS: Partial<Record<keyof PhysicsRow, string>> = {
  drift: 'minimisation drift',
  torsions: 'unlikely torsions',
  clashes: 'clashes',
  strain: 'torsion-library strain',
  unsatisfied: 'unsatisfied buried polars',
  pbPassed: 'PoseBusters passed',
  clashscore: 'clashscore',
  rama: 'Ramachandran outliers',
};

/** A list stats block with rows; other shapes count as not computed here. */
function has<T>(v: T[] | null | undefined): v is T[] {
  return Array.isArray(v) && v.length > 0;
}

function structureLabel(record: UiRunRecord, r: RecordRender): string {
  return record.structures?.find((s) => s.id === r.structure)?.label ?? r.structure;
}

function StructureFigure({ record }: { record: UiRunRecord }) {
  const cfg = useViewerConfig();
  const targets = useMemo(() => structureTargets(record, { assetUrl: (p) => getHarnessApi().assetUrl(p) }), [record]);
  const target = targets.find((t) => t.id === defaultStructureId(targets));
  const renders = record.renders ?? [];
  const overview = renders.find((r) => r.view === 'overview') ?? renders[0];
  const pocket = overview ? renders.find((r) => r !== overview && r.structure === overview.structure) : undefined;
  // same data PaeHeatmap draws: stats.pae, or the prototype pattern for mock records
  const pae = useMemo(() => paeFromStats(record) ?? (record.source === 'mock' ? mockPae(record) : null), [record]);
  const paeShown = !!pae;
  const overlay = overview ? `${structureLabel(record, overview)} · ${overview.view}` : structureCaption(record, target, targets);

  const left = overview
    ? `PyMOL render of ${structureLabel(record, overview)}, ${overview.view} (left)`
    : target?.kind === 'medoid'
      ? 'Medoid structure (left)'
      : target
        ? `${target.label} (left)`
        : 'No structure in the record (left)';
  const right = paeShown
    ? 'predicted aligned error with the read block outlined (right)'
    : pocket
      ? `${pocket.view} view of the same structure (right); predicted aligned error not computed`
      : 'predicted aligned error not computed';

  return (
    <div className="break-inside-avoid" data-testid="doc-structure">
      <div className="grid grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] gap-4">
        <div className="relative h-[300px] overflow-hidden rounded-[4px] border border-line bg-canvas print:h-[210px]">
          {overview ? (
            <StructureImage record={record} variant="print" caption={false} view={overview.view} structure={overview.structure} height={298} className="h-full [&>div]:!h-full [&>div]:rounded-none [&>div]:border-0" />
          ) : (
            <StructureViewer target={target} mode={cfg.mode} placeholder={record.inputs.reference || 'no structure in the record'} className="absolute inset-0" />
          )}
          {overlay && (
            <div className="pointer-events-none absolute bottom-2 left-2.5 rounded-[3px] bg-white/85 px-1.5 py-0.5 font-mono text-[8pt] text-ink2" data-testid="doc-structure-caption">
              {overlay}
            </div>
          )}
        </div>
        <div className="flex min-w-0 flex-col gap-2">
          {paeShown ? (
            <>
              <PaeHeatmap record={record} variant="print" caption={false} side={false} size={240} />
              {pae?.lines?.length ? (
                <div className="font-mono text-[8pt] leading-[1.6] text-ink2" data-testid="doc-pae-lines">
                  {pae.lines.map((l) => (
                    <div key={l}>{l}</div>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <>
              {pocket && (
                <StructureImage record={record} variant="print" caption={false} view={pocket.view} structure={pocket.structure} height={240} className="print:[&>div]:!h-[165px]" />
              )}
              <DocNotComputed label="Predicted aligned error" block="pae" />
            </>
          )}
        </div>
      </div>
      <DocCaption>
        Fig. 1 · {left}; {right}.{overview?.pse ? ` PyMOL session ${overview.pse.split('/').pop()}.` : ''}
      </DocCaption>
    </div>
  );
}

function LayersTable({ record }: { record: UiRunRecord }) {
  const rows = docLayers(record);
  return (
    <div>
      <DocLabel>Layers</DocLabel>
      <div className="border-t border-ink">
        {rows.map((l) => (
          <div
            key={l.i}
            className="grid grid-cols-[100px_minmax(0,1fr)_70px] items-baseline gap-2 border-b border-line py-1 text-[9pt] break-inside-avoid"
            data-testid="doc-layer"
            data-layer={l.i}
            data-state={l.worst ?? l.status}
          >
            <span>{l.name}</span>
            <span className={clsx('font-mono text-[8pt]', l.status === 'not_run' ? 'text-faint' : 'text-ink2')}>{l.summary}</span>
            <span className="text-right font-mono text-[8pt]" style={{ color: l.worst ? RESULT_COLOR[l.worst] : 'var(--color-faint)' }} title={l.countsLong}>
              {l.countsShort}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Warned or stopped checks. Under the layers on screen; full width with evidence beside the name in print. */
function FlaggedList({ record, className }: { record: UiRunRecord; className?: string }) {
  const flagged = flaggedChecks(record);
  return (
    <div className={className} data-testid="doc-flagged">
      <DocLabel>Warned or stopped</DocLabel>
      {flagged.length === 0 && <div className="text-[8.5pt] text-muted">none</div>}
      {flagged.map((c) => (
        <div
          key={c.id}
          className="grid grid-cols-[38px_minmax(0,1fr)] gap-2 border-b border-line2 py-[3px] text-[9pt] break-inside-avoid"
          data-testid="check-row"
          data-check={c.id}
          data-state={c.result}
        >
          <span className="pt-0.5 text-[7.5pt] font-semibold tracking-[.04em] uppercase" style={{ color: RESULT_COLOR[c.result] }}>
            {c.result}
          </span>
          <div className="min-w-0 print:grid print:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] print:gap-3">
            <div>{c.name}</div>
            {c.evidence && <div className="font-mono text-[8pt] break-words text-ink2">{c.evidence}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ReportDocument({ record, tools, name }: ReportDocumentProps) {
  const v = verdictMeta(record.verdict.outcome);
  const S = record.stats;
  const api = getHarnessApi();
  // figures the harness wrote (report.figures, then the provenance graph), numbered after Fig. 3;
  // slots keep their number when not computed
  const runId = record.record.runId ?? record.id;
  const harnessFigures: { id: string; url: string; alt: string; caption: string }[] = [
    ...(record.report?.figures ?? []).map((f) => ({ id: f.id, url: f.url, alt: f.alt ?? f.caption ?? f.id, caption: f.caption ?? f.id })),
    ...(record.report?.graph?.svg
      ? [{ id: 'provenance-graph', url: record.report.graph.svg, alt: `Provenance graph of run ${runId}`, caption: `Provenance graph of run ${runId} (graph.svg).` }]
      : []),
  ];
  const figAgreement = 4 + harnessFigures.length;
  const agreementUnit = has(S.agreement) ? S.agreement[0]?.cells?.[0]?.unit : undefined;
  const interactions = interactionSummary(record);
  const physicsWords = physicsColumns(record).map((c) => PHYSICS_WORDS[c.key] ?? c.label);
  const metrics = metricRows(record, tools);

  return (
    <article
      data-print="page"
      data-testid="report-document"
      data-run={record.id}
      className="mx-auto flex min-h-[1123px] w-[794px] flex-col gap-[26px] border border-line bg-surface px-16 py-[60px] text-[10.5pt] leading-[1.5] text-ink print:mx-0 print:gap-5 print:p-0"
    >
      <header className="flex items-end justify-between border-b border-ink pb-3">
        <div>
          <div className="text-[8.5pt] tracking-[.08em] text-muted uppercase">Prediction assurance · run report</div>
          <div className="mt-0.5 text-[17pt] font-semibold tracking-[-0.01em]" data-testid="doc-title">
            {name}
          </div>
        </div>
        <div className="text-right font-mono text-[8.5pt] text-ink2">
          {record.id}
          <br />
          {fmtDateTime(record.createdAt)}
        </div>
      </header>

      <div className="break-inside-avoid">
        <div className="flex flex-wrap items-baseline gap-3" title={record.verdict.statement || undefined}>
          <span className="text-[15pt] font-semibold" style={{ color: v.color }} data-testid="verdict" data-state={v.state}>
            {v.label}
          </span>
          <span className="text-[11pt]">“{record.verdict.claim || record.claim}”</span>
          <span className="ml-auto font-mono text-[8.5pt] text-muted">{metaLine(record, tools)}</span>
        </div>
      </div>

      <KeyNumbers items={keyNumbers(record, tools)} />

      <BlockBoundary name="Fig. 1 · Structure">
        <StructureFigure record={record} />
      </BlockBoundary>

      <BlockBoundary name="Stat cards">
        <StatCards record={record} tools={tools} variant="print" className="break-inside-avoid" />
      </BlockBoundary>

      <div className="grid grid-cols-2 gap-5">
        <div className="break-inside-avoid" data-testid="doc-fig-seeds">
          {has(S.seeds) ? (
            <BlockBoundary name="Fig. 2 · Seed spread">
              <SeedSpread record={record} tools={tools} variant="print" side={false} caption={false} />
              <DocCaption>
                Fig. 2 · Seed spread, RMSD to medoid vs {seedAxisLabel(record, tools)}
                {seedStatsLine(record) ? ` · ${seedStatsLine(record)}` : ''}
                {sourceSuffix(blockSource(record, 'seeds'))}
              </DocCaption>
            </BlockBoundary>
          ) : (
            <DocNotComputed label="Fig. 2 · Seed spread" block="seeds" />
          )}
        </div>
        <div className="break-inside-avoid" data-testid="doc-fig-calibration">
          {has(S.calibration) ? (
            <BlockBoundary name="Fig. 3 · Benchmark calibration">
              <CalibrationCurve record={record} tools={tools} variant="print" caption={false} />
              <DocCaption>
                Fig. 3 · Benchmark calibration: failure rate against crystal structures by confidence band.{sourceSuffix(blockSource(record, 'calibration'))}
              </DocCaption>
            </BlockBoundary>
          ) : (
            <DocNotComputed label="Fig. 3 · Benchmark calibration" block="calibration" />
          )}
        </div>
      </div>

      {harnessFigures.length > 0 && (
        <div className="grid grid-cols-2 items-start gap-5" data-testid="doc-report-figures">
          {harnessFigures.map((f, i) => (
            <figure key={f.id} className="m-0 break-inside-avoid" data-testid="doc-report-figure" data-figure={f.id}>
              {/* eslint-disable-next-line @next/next/no-img-element -- run files are served by the API proxy */}
              <img src={api.assetUrl(f.url)} alt={f.alt} className="block h-auto max-h-[260px] w-full object-contain print:max-h-[190px]" />
              <DocCaption>
                Fig. {4 + i} · {f.caption}
              </DocCaption>
            </figure>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-5">
        <div className="break-inside-avoid" data-testid="doc-fig-agreement">
          {has(S.agreement) ? (
            <BlockBoundary name={`Fig. ${figAgreement} · Agreement between methods`}>
              <AgreementMatrix record={record} tools={tools} variant="print" caption={false} />
              <DocCaption>
                Fig. {figAgreement} · Agreement between methods{agreementUnit ? ` (${agreementUnit})` : ''}.{sourceSuffix(blockSource(record, 'agreement'))}
              </DocCaption>
            </BlockBoundary>
          ) : (
            <DocNotComputed label={`Fig. ${figAgreement} · Agreement between methods`} block="agreement" />
          )}
        </div>
        <div className="break-inside-avoid" data-testid="doc-table-interactions">
          {has(S.interactions) ? (
            <BlockBoundary name="Table 1 · Interaction fingerprint">
              <InteractionDiagram record={record} tools={tools} variant="print" diagram={false} caption={false} />
              <DocCaption>
                Table 1 · Interaction fingerprint of the medoid pose · {interactions}.{sourceSuffix(blockSource(record, 'interactions'))}
              </DocCaption>
            </BlockBoundary>
          ) : (
            <DocNotComputed label="Table 1 · Interaction fingerprint" block="interactions" />
          )}
        </div>
      </div>

      {Array.isArray(S.posebusters) && S.posebusters.length === 0 ? null : has(S.posebusters) ? (
        <BlockBoundary name="PoseBusters">
          <PoseBustersGrid record={record} tools={tools} variant="print" className="break-inside-avoid" />
          {blockSource(record, 'posebusters') ? <DocCaption>PoseBusters{sourceSuffix(blockSource(record, 'posebusters'))}</DocCaption> : null}
        </BlockBoundary>
      ) : (
        <DocNotComputed label="PoseBusters" block="posebusters" />
      )}

      {has(S.physics) ? (
        <div className="break-inside-avoid">
          <BlockBoundary name="Per-seed statistics">
            <SeedStatsTable record={record} tools={tools} variant="print" />
            <DocCaption>
              Table 2 · Physical checks per seed: {physicsWords.join(', ')}; median in the last row.{sourceSuffix(blockSource(record, 'physics'))}
            </DocCaption>
          </BlockBoundary>
        </div>
      ) : (
        <DocNotComputed label="Table 2 · Per-seed statistics" block="physics" />
      )}

      <div className="grid grid-cols-2 gap-x-5 gap-y-3.5">
        {metrics.computed ? (
          <BlockBoundary name="Confidence">
            <MetricsTable record={record} tools={tools} variant="print" className="row-span-2 print:row-span-1" />
          </BlockBoundary>
        ) : (
          <div className="row-span-2 print:row-span-1" data-testid="doc-metrics">
            <DocLabel>Confidence</DocLabel>
            <DocNotComputed label={metrics.rows.length + metrics.ranking.length ? `${[...metrics.rows, ...metrics.ranking].map((m) => m.name).join(', ')}` : 'Metrics'} block="metrics" />
          </div>
        )}
        <LayersTable record={record} />
        <FlaggedList record={record} className="col-start-2 print:col-span-2 print:col-start-1" />
      </div>

      <div>
        <BlockBoundary name="Provenance">
          <ProvenanceTable record={record} tools={tools} variant="print" className="break-inside-avoid" />
        </BlockBoundary>
        <div className="mt-2 font-mono text-[8pt] break-words text-muted" data-testid="doc-record-line">
          {recordLine(record)}
        </div>
      </div>
    </article>
  );
}
