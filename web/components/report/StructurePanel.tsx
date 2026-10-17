'use client';

// Report structure block: structure chips (crystal, medoid, seeds, docking poses, models, overlay),
// the Mol* viewer (PyMOL renders without WebGL), the ensemble table and the stat cards.

import clsx from 'clsx';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { StructureViewer } from '@/components/viewer/StructureViewer';
import { useViewerConfig } from '@/components/viewer/config';
import { getHarnessApi } from '@/lib/harness-api';
import { defaultStructureId, ensembleMembers, reportChipMembers, structureCaption, structureTargets } from '@/lib/selectors/report';
import { EnsembleTable } from './EnsembleTable';
import { StatCards } from './StatCards';
import type { ReportBlockProps } from './types';

export function StructurePanel({ record, tools, className }: ReportBlockProps) {
  const cfg = useViewerConfig();
  const targets = useMemo(() => structureTargets(record, { assetUrl: (p) => getHarnessApi().assetUrl(p), register: tools }), [record, tools]);
  const members = useMemo(() => ensembleMembers(record, targets, tools), [record, targets, tools]);
  const overlay = targets.find((t) => t.kind === 'overlay');
  const chips = reportChipMembers(members);
  const hiddenCount = members.length - chips.length;
  const [picked, setPicked] = useState<{ run: string; id: string } | null>(null);
  const shown = [...chips, ...(overlay ? [overlay] : [])];
  const selected = picked && picked.run === record.id && shown.some((t) => t.id === picked.id) ? picked.id : defaultStructureId(shown);
  const target = shown.find((t) => t.id === selected);
  const select = (id: string) => setPicked({ run: record.id, id });
  const refRenders = record.renders ?? [];

  return (
    <div className={className} data-testid="structure-panel">
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1">
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
                  'rounded-[5px] border px-[9px] py-1 font-mono text-[11.5px] font-medium transition-all duration-150',
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
      <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(330px,1fr)] items-stretch gap-4">
        <StructureViewer
          target={target}
          mode={cfg.mode}
          colorMode={target?.kind === 'overlay' ? 'member' : 'chain'}
          // a chip shows only its own structure's renders (the overlay has none); record renders only without chips
          fallbackRenders={target ? [] : refRenders}
          placeholder={!targets.length ? record.inputs.reference || 'no structures in the record' : undefined}
          className="h-[400px] rounded-card border border-line"
        />
        <EnsembleTable record={record} tools={tools} members={chips} more={hiddenCount} selected={selected} onSelect={select} />
      </div>
      <StatCards record={record} tools={tools} className="mt-4" />
    </div>
  );
}
