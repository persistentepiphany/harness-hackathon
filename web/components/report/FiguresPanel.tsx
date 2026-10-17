'use client';

// Visual analysis tabs (prototype vizTabs): PAE, interactions, seeds, agreement, calibration and
// ROC from stats; in live records also the report figures (report.figures, SVG) and the
// provenance graph (report.graph.svg). A tab without data shows "not computed".

import clsx from 'clsx';
import { useState } from 'react';
import { getHarnessApi } from '@/lib/harness-api';
import type { RecordFigure } from '@/lib/types';
import { AgreementMatrix } from './figures/AgreementMatrix';
import { CalibrationCurve } from './figures/CalibrationCurve';
import { FigureCaption } from './figures/common';
import { InteractionDiagram } from './figures/InteractionDiagram';
import { paeFromStats } from './figures/pae';
import { PaeHeatmap } from './figures/PaeHeatmap';
import { RocCurve } from './figures/RocCurve';
import { SeedSpread } from './figures/SeedSpread';
import type { ReportBlockProps } from './types';

interface Tab {
  id: string;
  label: string;
  has: boolean;
}

const humanize = (id: string) => id.replace(/[_-]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

function RunFigure({ fig, no }: { fig: RecordFigure; no: number }) {
  const api = getHarnessApi();
  return (
    <figure className="m-0" data-testid="report-figure" data-figure={fig.id}>
      {/* eslint-disable-next-line @next/next/no-img-element -- SVG written by the harness, served through the API proxy */}
      <img src={api.assetUrl(fig.url)} alt={fig.alt ?? fig.caption ?? fig.id} className="block h-auto max-w-full" style={{ maxHeight: 420 }} />
      <FigureCaption no={no}>
        {fig.caption ?? humanize(fig.id)}
        {fig.data && (
          <>
            {' · '}
            <a href={api.assetUrl(fig.data)} className="font-mono underline decoration-line underline-offset-2">
              data
            </a>
          </>
        )}
      </FigureCaption>
    </figure>
  );
}

function GraphFigure({ graph, no }: { graph: Record<string, string>; no: number }) {
  const api = getHarnessApi();
  const svg = graph.svg;
  return (
    <figure className="m-0" data-testid="provenance-graph">
      <div className="max-h-[560px] overflow-auto rounded-card border border-line bg-surface p-2">
        {/* eslint-disable-next-line @next/next/no-img-element -- graph.svg written by the harness */}
        <img src={api.assetUrl(svg)} alt="Provenance graph of sources, files, tools, checks, findings and the verdict" className="block h-auto max-w-none" />
      </div>
      <FigureCaption no={no}>
        Provenance graph: sources, files, tools, checks, findings and the verdict, with checksums.{' '}
        {(['svg', 'json', 'mmd'] as const)
          .filter((k) => graph[k])
          .map((k, i) => (
            <span key={k}>
              {i > 0 && ' · '}
              <a href={api.assetUrl(graph[k])} target="_blank" rel="noreferrer" className="font-mono underline decoration-line underline-offset-2">
                graph.{k}
              </a>
            </span>
          ))}
      </FigureCaption>
    </figure>
  );
}

export function FiguresPanel({ record, tools, className }: ReportBlockProps) {
  const S = record.stats;
  const figs = record.report?.figures ?? [];
  const graph = record.report?.graph;
  const tabs: Tab[] = [
    { id: 'pae', label: 'PAE', has: !!paeFromStats(record) || record.source === 'mock' },
    { id: 'inter', label: 'Interactions', has: !!S.interactions },
    { id: 'seeds', label: 'Seeds', has: !!S.seeds?.length },
    { id: 'agree', label: 'Agreement', has: !!S.agreement?.length },
    { id: 'calib', label: S.roc ? 'Calibration · ROC' : 'Calibration', has: !!S.calibration?.length },
    ...figs.map((f) => ({ id: `fig:${f.id}`, label: humanize(f.id), has: true })),
    ...(graph?.svg ? [{ id: 'graph', label: 'Provenance graph', has: true }] : []),
  ];
  const [picked, setPicked] = useState<string | null>(null);
  const tab = picked && tabs.some((t) => t.id === picked) ? picked : (tabs.find((t) => t.has)?.id ?? 'pae');

  return (
    <div className={className} data-testid="figures">
      <div className="mb-[18px] flex flex-wrap gap-x-[18px] border-b border-line">
        {tabs.map((t) => {
          const on = t.id === tab;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setPicked(t.id)}
              aria-pressed={on}
              data-testid="figure-tab"
              data-tab={t.id}
              data-state={on ? 'active' : t.has ? 'idle' : 'not-computed'}
              className={clsx('-mb-px border-0 border-b-[1.5px] bg-transparent px-0 pt-0 pb-[9px] text-[12.5px] font-medium', on ? 'border-ink text-ink' : 'border-transparent text-muted hover:text-ink')}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      {tab === 'pae' && <PaeHeatmap record={record} tools={tools} />}
      {tab === 'inter' && <InteractionDiagram record={record} tools={tools} />}
      {tab === 'seeds' && <SeedSpread record={record} tools={tools} />}
      {tab === 'agree' && <AgreementMatrix record={record} tools={tools} />}
      {tab === 'calib' &&
        (S.calibration?.length ? (
          <div>
            <div className="grid grid-cols-2 gap-6">
              <CalibrationCurve record={record} tools={tools} caption={false} />
              {S.roc && <RocCurve record={record} tools={tools} caption={false} />}
            </div>
            <FigureCaption no={5}>
              Benchmark calibration: failure rate against crystal structures by confidence band, split by harness verdict
              {S.roc ? '; right, ROC of the ranking score against inactives' : ''}.
            </FigureCaption>
          </div>
        ) : (
          <CalibrationCurve record={record} tools={tools} />
        ))}
      {figs.map((f, i) => tab === `fig:${f.id}` && <RunFigure key={f.id} fig={f} no={6 + i} />)}
      {tab === 'graph' && graph && <GraphFigure graph={graph} no={6 + figs.length} />}
    </div>
  );
}
