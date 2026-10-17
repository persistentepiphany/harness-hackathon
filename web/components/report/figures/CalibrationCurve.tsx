'use client';

// Benchmark calibration: failure rate by confidence band, split by harness verdict (stats.calibration).

import { calibrationPolylines } from '@/lib/selectors/report';
import { NotComputed } from '../parts';
import { FigureCaption, SVG_TEXT, type FigureProps } from './common';

export function CalibrationCurve({ record, caption = true, figNo = 5, variant, className }: FigureProps) {
  const print = variant === 'print';
  const lines = calibrationPolylines(record);
  if (!lines) return <NotComputed what="calibration" print={print} record={record} className={className} />;
  return (
    <div className={className} data-testid="figure-calibration">
      <svg viewBox="0 0 320 170" className="block h-auto w-full" role="img" aria-label="Calibration curve">
        <line x1={40} y1={130} x2={310} y2={130} stroke="var(--color-line)" />
        <line x1={40} y1={10} x2={40} y2={130} stroke="var(--color-line)" />
        <polyline points={lines.flagged} fill="none" stroke="var(--color-stop)" strokeWidth={2} />
        <polyline points={lines.passed} fill="none" stroke="var(--color-pass)" strokeWidth={2} />
        <text x={44} y={18} {...SVG_TEXT} fill="var(--color-stop)">
          flagged
        </text>
        <text x={44} y={30} {...SVG_TEXT} fill="var(--color-pass)">
          passed
        </text>
        <text x={40} y={148} {...SVG_TEXT}>
          0.5
        </text>
        <text x={310} y={148} {...SVG_TEXT} textAnchor="end">
          1.0 confidence
        </text>
        <text x={12} y={75} {...SVG_TEXT} transform="rotate(-90 12 75)">
          failure rate
        </text>
      </svg>
      {caption && (
        <FigureCaption no={figNo} print={print}>
          Benchmark calibration: failure rate against crystal structures by confidence band, split by harness verdict.
        </FigureCaption>
      )}
    </div>
  );
}
