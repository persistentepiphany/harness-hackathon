'use client';

// Predicted aligned error heatmap (canvas). Data: stats.pae; mock records draw the prototype's
// synthetic pattern. Otherwise "not computed".

import clsx from 'clsx';
import { useEffect, useMemo, useRef } from 'react';
import { NotComputed } from '../parts';
import { FigureCaption, type FigureProps } from './common';
import { paeColor, paeFromStats, type PaeData } from './pae';
import { mockPae } from './pae-mock';

export interface PaeHeatmapProps extends FigureProps {
  /** Canvas size in CSS px (default 240). */
  size?: number;
  /** Text lines beside the heatmap (default true). */
  side?: boolean;
}

function draw(el: HTMLCanvasElement, d: PaeData) {
  const ctx = el.getContext('2d');
  if (!ctx) return;
  const n = d.matrix.length;
  const cell = el.width / n;
  ctx.clearRect(0, 0, el.width, el.height);
  for (let j = 0; j < n; j++) {
    const row = d.matrix[j];
    for (let i = 0; i < row.length; i++) {
      ctx.fillStyle = paeColor(row[i], d.max);
      ctx.fillRect(i * cell, j * cell, cell + 0.5, cell + 0.5);
    }
  }
  if (d.block) {
    const [r0, r1] = d.block.rows;
    const [c0, c1] = d.block.cols;
    ctx.strokeStyle = '#B07E2C';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(c0 * cell + 0.75, r0 * cell + 0.75, (c1 - c0) * cell - 1.5, (r1 - r0) * cell - 1.5);
  }
}

export function PaeHeatmap({ record, size = 240, side = true, caption = true, figNo = 1, variant, className }: PaeHeatmapProps) {
  const print = variant === 'print';
  const data = useMemo(() => paeFromStats(record) ?? (record.source === 'mock' ? mockPae(record) : null), [record]);
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (ref.current && data) draw(ref.current, data);
  }, [data]);
  if (!data) return <NotComputed what="pae" print={print} record={record} className={className} />;
  return (
    <div className={className} data-testid="figure-pae">
      <div className="flex flex-wrap items-start gap-6">
        <canvas ref={ref} width={240} height={240} className="flex-none rounded-[4px]" style={{ width: size, height: size }} />
        {side && (
          <div className={clsx('min-w-[160px] font-mono text-ink2', print ? 'text-[8pt] leading-[1.6]' : 'text-[11.5px] leading-[1.9]')}>
            {(data.lines ?? []).map((l) => (
              <div key={l}>{l}</div>
            ))}
            <div className="mt-2 flex items-center gap-2 text-muted">
              <span>0</span>
              <span className="h-1.5 w-[120px] rounded-[3px]" style={{ background: 'linear-gradient(90deg,#2F6B4F,#B9D7C3,#F6F6F3)' }} />
              <span>{data.max ?? 30} Å</span>
            </div>
          </div>
        )}
      </div>
      {caption && (
        <FigureCaption no={figNo} print={print}>
          Predicted aligned error; the outlined block is the one read for the verdict.
        </FigureCaption>
      )}
    </div>
  );
}
