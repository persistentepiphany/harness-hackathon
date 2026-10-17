'use client';

// ROC of the ranking-only score against inactives (stats.roc, stats.auc, stats.enrichment).

import { fmtNum } from '@/lib/format';
import { rankingOutputName, rocPolyline } from '@/lib/selectors/report';
import { NotComputed } from '../parts';
import { FigureCaption, SVG_TEXT, type FigureProps } from './common';

export function RocCurve({ record, tools, caption = true, figNo = 5, variant, className }: FigureProps) {
  const print = variant === 'print';
  const pts = rocPolyline(record);
  if (!pts) return <NotComputed what="roc" print={print} className={className} />;
  const { auc, enrichment } = record.stats;
  const label = [auc === null || auc === undefined ? null : `AUC ${fmtNum(auc, undefined, 2)}`, enrichment].filter(Boolean).join(' · ');
  const ranking = rankingOutputName(record, tools);
  return (
    <div className={className} data-testid="figure-roc">
      <svg viewBox="0 0 320 170" className="block h-auto w-full" role="img" aria-label="ROC curve">
        <line x1={40} y1={130} x2={310} y2={130} stroke="var(--color-line)" />
        <line x1={40} y1={10} x2={40} y2={130} stroke="var(--color-line)" />
        <line x1={40} y1={130} x2={310} y2={10} stroke="var(--color-line)" strokeDasharray="3 3" />
        <polyline points={pts} fill="none" stroke="var(--color-accent)" strokeWidth={2} />
        <text x={44} y={18} {...SVG_TEXT} fill="var(--color-accent)">
          {label}
        </text>
        <text x={40} y={148} {...SVG_TEXT}>
          FPR
        </text>
        <text x={12} y={75} {...SVG_TEXT} transform="rotate(-90 12 75)">
          TPR
        </text>
      </svg>
      {caption && (
        <FigureCaption no={figNo} print={print}>
          ROC{ranking ? ` of ${ranking} ranking` : ''} against inactives.
        </FigureCaption>
      )}
    </div>
  );
}
