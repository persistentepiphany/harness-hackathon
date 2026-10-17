'use client';

// Report structure block: structure chips (crystal, medoid, seeds, docking poses, models, overlay),
// the Mol* viewer (PyMOL renders without WebGL), the ensemble table and the stat cards. A run with
// only reference (input) structures shows them as inputs, without pose statistics. A selected
// check with residues highlights them in the viewer.

import clsx from 'clsx';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { StructureViewer } from '@/components/viewer/StructureViewer';
import { useViewerConfig } from '@/components/viewer/config';
import { getHarnessApi } from '@/lib/harness-api';
import { defaultStructureId, ensembleMembers, referenceOnly, reportChipMembers, structureCaption, structureTargets, type FlaggedResidue } from '@/lib/selectors/report';
import { EnsembleTable } from './EnsembleTable';
import { StatCards } from './StatCards';
import type { ReportBlockProps } from './types';

export interface StructurePanelProps extends ReportBlockProps {
  /** Show the stat cards under the viewer (default true). */
  cards?: boolean;
  /** Controlled structure selection (chip id); uncontrolled when absent. */
  selected?: string | null;
  onSelect?: (id: string) => void;
  /** Residues to highlight (the selected check's), with the check id for the caption. */
  highlight?: { check: string; residues: FlaggedResidue[] } | null;
}

export function StructurePanel({ record, tools, className, cards = true, selected: controlled, onSelect, highlight }: StructurePanelProps) {
  const cfg = useViewerConfig();
  const targets = useMemo(() => structureTargets(record, { assetUrl: (p) => getHarnessApi().assetUrl(p), register: tools }), [record, tools]);
  const members = useMemo(() => ensembleMembers(record, targets, tools), [record, targets, tools]);
  const overlay = targets.find((t) => t.kind === 'overlay');
  const chips = reportChipMembers(members);
  const hiddenCount = members.length - chips.length;
  const [picked, setPicked] = useState<{ run: string; id: string } | null>(null);
  const shown = [...chips, ...(overlay ? [overlay] : [])];
  const own = controlled !== undefined ? controlled : picked && picked.run === record.id ? picked.id : null;
  const selected = own && shown.some((t) => t.id === own) ? own : defaultStructureId(shown);
  const target = shown.find((t) => t.id === selected);
  const select = (id: string) => {
    setPicked({ run: record.id, id });
    onSelect?.(id);
  };
  const refRenders = record.renders ?? [];
  const refOnly = referenceOnly(record);
  const residues = useMemo(() => highlight?.residues ?? [], [highlight]);
  const flagged = useMemo(() => residues.map((r) => ({ num: r.num, chain: r.chain })), [residues]);

  return (
    <div className={className} data-testid="structure-panel" data-state={refOnly ? 'reference-only' : 'predictions'}>
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1">
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
        <span className="font-mono text-[11px] text-muted" data-testid="structure-caption">
          {structureCaption(record, target, targets)}
        </span>
      </div>
      <div className={clsx('grid items-stretch gap-4', refOnly ? 'grid-cols-[minmax(0,1fr)]' : 'grid-cols-[minmax(0,1.2fr)_minmax(330px,1fr)]')}>
        <div className="relative">
          <StructureViewer
            target={target}
            mode={cfg.mode}
            colorMode={flagged.length ? 'flagged' : target?.kind === 'overlay' ? 'member' : 'chain'}
            flagged={flagged.length ? flagged : undefined}
            // a chip shows only its own structure's renders (the overlay has none); record renders only without chips
            fallbackRenders={target ? [] : refRenders}
            placeholder={!targets.length ? record.inputs.reference || 'no structures in the record' : undefined}
            className={clsx('rounded-card border border-line', refOnly ? 'h-[360px]' : 'h-[400px]')}
          />
          {highlight && (
            <div className="pointer-events-none absolute top-2.5 left-3 max-w-[70%] animate-fade-in rounded-[4px] bg-white/90 px-2 py-[3px] font-mono text-[10.5px] text-ink2" data-testid="viewer-highlight" data-check={highlight.check}>
              {highlight.check}
              {residues.length ? ` · ${residues.map((r) => `${r.name}${r.num}${r.chain ?? ''}`).join(', ')}` : ' · no residues named in the record'}
            </div>
          )}
        </div>
        {!refOnly && <EnsembleTable record={record} tools={tools} members={chips} more={hiddenCount} selected={selected} onSelect={select} />}
      </div>
      {refOnly && (
        <div className="mt-1.5 font-mono text-[11px] text-muted" data-testid="reference-note">
          {(() => {
            const n = targets.filter((t) => t.kind === 'crystal').length;
            return `${n} reference structure${n === 1 ? '' : 's'} from the inputs · pose statistics need predictions`;
          })()}
        </div>
      )}
      {cards && <StatCards record={record} tools={tools} className="mt-4" />}
    </div>
  );
}
