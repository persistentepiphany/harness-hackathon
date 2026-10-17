'use client';

// Interaction fingerprint as a radial SVG around the ligand (stats.interactions), with the list.

import clsx from 'clsx';
import { fmtNum } from '@/lib/format';
import { blockSource, interactionKnownText, interactionNodes, interactionPoseText, ligandLabel, sourceLabel } from '@/lib/selectors/report';
import { NotComputed } from '../parts';
import { FigureCaption, type FigureProps } from './common';

export interface InteractionDiagramProps extends FigureProps {
  /** Show the residue list beside the diagram (default true). */
  list?: boolean;
  /** Show the diagram (default true; false renders the list only, as the printed table). */
  diagram?: boolean;
}

export function InteractionDiagram({ record, list = true, diagram = true, caption = true, figNo = 2, variant, className }: InteractionDiagramProps) {
  const print = variant === 'print';
  const nodes = interactionNodes(record);
  if (!record.stats.interactions) return <NotComputed what="interactions" print={print} className={className} />;
  const summary = interactionKnownText(record);
  const label = ligandLabel(record);
  return (
    <div className={className} data-testid="figure-interactions" title={sourceLabel(blockSource(record, 'interactions'))}>
      <div className={clsx('grid items-start gap-6', diagram && list ? 'grid-cols-[minmax(0,1fr)_minmax(220px,300px)]' : 'grid-cols-1')}>
        {diagram && (
          <svg viewBox="0 0 360 300" className="block h-auto w-full max-w-[420px]" role="img" aria-label={`Interaction diagram, ${nodes.length} residues around ${label}`}>
            {nodes.map((n) => (
              <g key={`${n.residue}-${n.type}`}>
                <line x1={180} y1={150} x2={n.x} y2={n.y} stroke={n.stroke} strokeWidth={1.5} strokeDasharray={n.dash} />
                <circle cx={n.x} cy={n.y} r={17} fill="#fff" stroke={n.stroke} strokeWidth={1.5} />
                <text x={n.x} y={n.y} dy={3.5} fontSize={8.5} textAnchor="middle" fill="var(--color-ink)" fontFamily="var(--font-mono)">
                  {n.residue}
                </text>
                <text x={n.lx} y={n.ly} fontSize={8} textAnchor="middle" fill="var(--color-muted)" fontFamily="var(--font-mono)">
                  {fmtNum(n.distance, 'Å')}
                </text>
              </g>
            ))}
            <rect x={150} y={136} width={60} height={28} rx={6} fill="var(--color-ink)" />
            <text x={180} y={154} fontSize={9} textAnchor="middle" fill="#fff" fontFamily="var(--font-mono)">
              {label}
            </text>
          </svg>
        )}
        {list && (
          <div className={clsx('flex flex-col font-mono', print ? 'gap-px text-[8.5pt]' : 'gap-1 text-[11.5px]')}>
            {nodes.map((n) => (
              <div key={`${n.residue}-${n.type}`} className="grid grid-cols-[54px_minmax(0,1fr)_48px_40px] gap-2 text-ink2" data-testid="interaction-row">
                <span className="text-ink">{n.residue}</span>
                <span style={{ color: n.stroke }}>{n.type}</span>
                <span className="text-right">{fmtNum(n.distance, 'Å')}</span>
                <span className="text-right text-muted">{n.known ? 'known' : 'new'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      {caption && (
        <FigureCaption no={figNo} print={print}>
          Interaction fingerprint (PLIP) of {interactionPoseText(record)}; {summary}.
        </FigureCaption>
      )}
    </div>
  );
}
