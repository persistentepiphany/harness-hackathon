'use client';

// Seed spread: RMSD to the medoid against the primary tool's confidence (stats.seeds), with the
// bootstrap CI of the median (stats.pairwise) as a band.

import clsx from 'clsx';
import { fmtNum } from '@/lib/format';
import { blockSource, SEED_RMSD_CUT, seedAxisLabel, seedSpreadPoints, sourceLabel } from '@/lib/selectors/report';
import { NotComputed } from '../parts';
import { FigureCaption, SVG_TEXT, type FigureProps } from './common';

export interface SeedSpreadProps extends FigureProps {
  /** Show the statistics beside the plot (default true). */
  side?: boolean;
}

export function SeedSpread({ record, tools, side = true, caption = true, figNo = 3, variant, className }: SeedSpreadProps) {
  const print = variant === 'print';
  const seeds = record.stats.seeds;
  if (!seeds || !seeds.length) return <NotComputed what="seeds" print={print} className={className} />;
  const { points, cutX, band, axis } = seedSpreadPoints(record);
  const p = record.stats.pairwise;
  const yLabel = seedAxisLabel(record, tools);
  const src = sourceLabel(blockSource(record, 'seeds'));
  const tau = typeof record.stats.kendallTau === 'number' ? record.stats.kendallTau : null;
  return (
    <div className={className} data-testid="figure-seeds" title={src}>
      <div className={clsx('grid items-start gap-6', side ? 'grid-cols-[minmax(0,1fr)_minmax(200px,260px)]' : 'grid-cols-1')}>
        <svg viewBox="0 0 360 170" className="block h-auto w-full" role="img" aria-label={`Seed spread, ${seeds.length} seeds`}>
          <line x1={40} y1={130} x2={350} y2={130} stroke="var(--color-line)" />
          {band && <rect x={band.x} y={124} width={band.w} height={12} fill="var(--color-accent-tint)" data-band={band.kind} />}
          <line x1={cutX} y1={14} x2={cutX} y2={130} stroke="var(--color-warn)" strokeDasharray="3 3" />
          <text x={cutX} y={10} {...SVG_TEXT} fill="var(--color-warn)" textAnchor="middle">
            {fmtNum(SEED_RMSD_CUT, 'Å')}
          </text>
          {points.map((s) => (
            <g key={s.label}>
              <circle cx={s.cx} cy={s.cy} r={5.5} fill={s.fill} stroke="#fff" strokeWidth={1.5} />
              <text x={s.cx} y={s.cy + 15} {...SVG_TEXT} fontSize={8} textAnchor="middle">
                {s.label}
              </text>
            </g>
          ))}
          <text x={40} y={150} {...SVG_TEXT}>
            0
          </text>
          <text x={350} y={150} {...SVG_TEXT} textAnchor="end">
            8 Å RMSD to medoid
          </text>
          <text x={12} y={75} {...SVG_TEXT} textAnchor="middle" transform="rotate(-90 12 75)">
            {yLabel}
          </text>
          {axis?.field === 'score' && (
            <>
              <text x={36} y={22} {...SVG_TEXT} textAnchor="end">
                {fmtNum(axis.max, undefined, 1)}
              </text>
              <text x={36} y={128} {...SVG_TEXT} textAnchor="end">
                {fmtNum(axis.min, undefined, 1)}
              </text>
            </>
          )}
        </svg>
        {side && (
          <div className={clsx('font-mono text-ink2', print ? 'text-[8pt] leading-[1.6]' : 'text-[11.5px] leading-[1.9]')}>
            {p ? (
              <>
                <div>median {fmtNum(p.median, 'Å', 2)}</div>
                {p.iqr && (
                  <div>
                    IQR {fmtNum(p.iqr[0], undefined, 2)}–{fmtNum(p.iqr[1], undefined, 2)}
                  </div>
                )}
                {p.ci95 && (
                  <div>
                    95% CI {fmtNum(p.ci95[0], undefined, 2)}–{fmtNum(p.ci95[1], undefined, 2)}
                  </div>
                )}
                {p.n != null && <div>n = {p.n}</div>}
              </>
            ) : (
              <div>n = {seeds.length}</div>
            )}
            {tau !== null && <div>Kendall τ {fmtNum(tau, undefined, 2)}</div>}
          </div>
        )}
      </div>
      {caption && (
        <FigureCaption no={figNo} print={print}>
          Seed spread, RMSD to the medoid against {yLabel}
          {band?.kind === 'ci95' ? '; shaded band is the bootstrap 95% CI of the median' : band?.kind === 'iqr' ? '; shaded band is the IQR of pairwise RMSD' : ''}.{src ? ` ${src.replace('source: ', 'Source: ')}.` : ''}
        </FigureCaption>
      )}
    </div>
  );
}
