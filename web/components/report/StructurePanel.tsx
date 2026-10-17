'use client';

// Report structure block: structure chips (crystal, medoid, seeds, docking poses, models, overlay)
// above the Mol* viewer (PyMOL renders without WebGL). A run with only reference (input)
// structures is labelled as such. A selected check highlights its residues, or frames the ligand
// of the pose it names. `fill` stretches the viewer to the parent height (sticky report column).

import clsx from 'clsx';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { StructureViewer } from '@/components/viewer/StructureViewer';
import { useViewerConfig } from '@/components/viewer/config';
import { defaultStructureId, referenceOnly, RESULT_COLOR, structureCaption, type CheckFocus } from '@/lib/selectors/report';
import { StatCards } from './StatCards';
import type { ReportBlockProps } from './types';
import { useStructures } from './useStructures';

export interface StructurePanelProps extends ReportBlockProps {
  /** Show the stat cards under the viewer (default false). */
  cards?: boolean;
  /** Controlled structure selection (chip id); uncontrolled when absent. */
  selected?: string | null;
  onSelect?: (id: string) => void;
  /** Focus of the selected check (residues to highlight, ligand to frame). */
  focus?: CheckFocus | null;
  /** Viewer fills the parent height (flex column). */
  fill?: boolean;
}

export function StructurePanel({ record, tools, className, cards = false, selected: controlled, onSelect, focus, fill }: StructurePanelProps) {
  const cfg = useViewerConfig();
  const model = useStructures(record, tools);
  const { targets, shown, hiddenCount } = model;
  const [picked, setPicked] = useState<{ run: string; id: string } | null>(null);
  const own = controlled !== undefined ? controlled : picked && picked.run === record.id ? picked.id : null;
  const selected = own && shown.some((t) => t.id === own) ? own : defaultStructureId(shown);
  const target = shown.find((t) => t.id === selected);
  const select = (id: string) => {
    setPicked({ run: record.id, id });
    onSelect?.(id);
  };
  const refRenders = record.renders ?? [];
  const refOnly = referenceOnly(record);
  const residues = useMemo(() => focus?.residues ?? [], [focus]);
  const flagged = useMemo(() => residues.map((r) => ({ num: r.num, chain: r.chain })), [residues]);
  // ligand checks frame the ligand of the shown pose (no residues to colour)
  const loads = useMemo(() => (focus?.ligand && !flagged.length && target && target.kind !== 'overlay' && target.kind !== 'crystal' ? target.load.map((l) => ({ ...l, focus: 'ligand' as const })) : undefined), [focus, flagged.length, target]);

  return (
    <div className={clsx(fill && 'flex min-h-0 flex-col', className)} data-testid="structure-panel" data-state={refOnly ? 'reference-only' : 'predictions'}>
      <div className="mb-2 flex min-h-[30px] min-w-0 flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
        <div className="flex min-w-0 flex-wrap items-center gap-1">
          {refOnly && (
            <span className="mr-2 text-[12px] font-medium text-ink" data-testid="reference-label">
              Reference structure (input) · not a prediction
            </span>
          )}
          {shown.map((t) => {
            const on = t.id === selected;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => select(t.id)}
                aria-pressed={on}
                data-testid="structure-chip"
                data-structure={t.id}
                data-kind={t.kind}
                data-state={on ? 'selected' : t.load.length ? 'idle' : 'no-coordinates'}
                title={t.load.length ? t.load.slice(0, 3).map((l) => l.label).join(' + ') + (t.load.length > 3 ? ` + ${t.load.length - 3} more` : '') : 'no coordinates in the record'}
                className={clsx(
                  'rounded-[5px] border px-[9px] py-1 font-mono text-[11.5px] font-medium transition-colors duration-200',
                  on ? 'border-ink bg-ink text-white' : 'border-line bg-transparent text-ink2 hover:border-ink',
                )}
              >
                {t.kind === 'medoid' ? 'medoid' : t.label}
              </button>
            );
          })}
          {hiddenCount > 0 && (
            <Link href={`/reports/${encodeURIComponent(record.id)}/ensemble`} className="px-1.5 font-mono text-[11.5px] text-muted hover:text-ink" data-testid="structure-more">
              +{hiddenCount} more → Ensemble
            </Link>
          )}
        </div>
        <span className="min-w-0 truncate font-mono text-[11px] text-muted" data-testid="structure-caption">
          {structureCaption(record, target, targets)}
        </span>
      </div>
      <div className={clsx('relative', fill && 'min-h-0 flex-1')}>
        <StructureViewer
          target={target}
          mode={cfg.mode}
          colorMode={flagged.length ? 'flagged' : target?.kind === 'overlay' ? 'member' : 'chain'}
          flagged={flagged.length ? flagged : undefined}
          loads={loads}
          // a chip shows only its own structure's renders (the overlay has none); record renders only without chips
          fallbackRenders={target ? [] : refRenders}
          placeholder={!targets.length ? record.inputs.reference || 'no structures in the record' : undefined}
          className={clsx('rounded-card border border-line', fill ? 'h-full min-h-[280px]' : 'h-[400px]')}
        />
        <div
          className={clsx('pointer-events-none absolute top-2.5 left-3 max-w-[80%] rounded-[6px] border border-line bg-white/95 px-2.5 py-1.5 text-[12px] text-ink2 shadow-sm transition-opacity duration-200', focus ? 'opacity-100' : 'opacity-0')}
          data-testid="viewer-highlight"
          data-check={focus?.check}
          aria-hidden={!focus}
        >
          {focus && (
            <>
              <div className="flex items-baseline gap-2">
                <span className="font-medium text-ink">{focus.name ?? focus.check}</span>
                {focus.result && <span className="text-[10.5px] font-semibold tracking-[.04em] uppercase" style={{ color: RESULT_COLOR[focus.result as keyof typeof RESULT_COLOR] }}>{focus.result}</span>}
              </div>
              {focus.value && <div className="tabular-nums">{focus.value}</div>}
              <div className="text-[11px] text-muted">
                {residues.length ? `highlighted: ${residues.map((r) => `${r.name}${r.num}${r.chain ?? ''}`).join(', ')}` : focus.ligand && loads ? 'ligand framed' : 'no residues named by this check'}
              </div>
            </>
          )}
        </div>
      </div>
      {cards && <StatCards record={record} tools={tools} className="mt-4" />}
    </div>
  );
}
