'use client';

// /reports/[runId]/ensemble: header; summary strip (per numeric output); view, colour, sort and
// filter controls; the selected member opened large; the multi-structure grid or the overlay.

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useViewerConfig } from '@/components/viewer/config';
import type { ColorMode } from '@/components/viewer/scene-types';
import { RecordGate } from '@/components/report/ReportView';
import { ReportPicker } from '@/components/report/ReportPicker';
import { getHarnessApi } from '@/lib/harness-api';
import { useTools } from '@/lib/hooks';
import {
  ensembleMembers,
  flaggedResidues,
  pbFailed,
  sortMembers,
  structureTargets,
  type EnsembleMember,
  type MemberSort,
} from '@/lib/selectors/report';
import { familyOf, recordTools } from '@/lib/tools';
import type { UiRunRecord } from '@/lib/types';
import { MemberDetail } from './MemberDetail';
import { OverlayView } from './OverlayView';
import { Segmented, ToggleChip } from './Segmented';
import { StructureGrid } from './StructureGrid';
import { SummaryStats } from './SummaryStats';

function caption(members: EnsembleMember[], primary: string | null, hasStats: boolean): string {
  const kinds = new Set(members.map((m) => m.kind));
  const parts: string[] = [];
  if (kinds.has('crystal')) parts.push('experimental reference');
  if (kinds.has('medoid') || kinds.has('seed')) parts.push(`${primary ? `${primary} ` : ''}seeds (medoid first)`);
  if (kinds.has('docking')) parts.push('docking poses');
  if (kinds.has('model')) parts.push('models');
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}` : (parts[0] ?? 'none');
  return `All sampled structures: ${list}${hasStats ? ', each with its RMSD to the medoid' : ''}.`;
}

type View = 'grid' | 'overlay';
type GridColor = Exclude<ColorMode, 'member'>;

function Ensemble({ record }: { record: UiRunRecord }) {
  const tools = useTools().data;
  const cfg = useViewerConfig();
  const rt = recordTools(record, tools);
  const primary = rt.find((t) => familyOf(t) === 'co-folding')?.name ?? null;
  const members = useMemo(() => ensembleMembers(record, structureTargets(record, { assetUrl: (p) => getHarnessApi().assetUrl(p), register: tools }), tools), [record, tools]);
  const flagged = useMemo(() => flaggedResidues(record), [record]);

  const [view, setView] = useState<View>('grid');
  const [color, setColor] = useState<GridColor>('chain');
  const [sort, setSort] = useState<MemberSort>('record');
  const [pbOnly, setPbOnly] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const anyConfidence = members.some((m) => m.perResidueConfidence);
  const anyPb = members.some((m) => m.pb !== null && m.pb.total !== null);
  const anyCluster = members.some((m) => m.cluster !== null);
  const anyRmsd = members.some((m) => m.rmsd !== null && m.kind !== 'crystal');
  const anyConf = members.some((m) => m.confidence !== null);
  const shown = useMemo(() => sortMembers(pbOnly ? members.filter(pbFailed) : members, sort), [members, pbOnly, sort]);
  const sel = members.find((m) => m.id === selected) ?? null;
  const withCoords = members.filter((m) => m.load.length).length;

  return (
    <>
      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0 flex-1">
          <ReportPicker runId={record.id} suffix="/ensemble" />
          <h1 className="m-0 text-[18px] font-semibold tracking-[-0.01em]">
            Ensemble
            <span className="ml-2 font-mono text-[13px] font-normal text-muted" data-testid="ensemble-summary">
              {members.length} {members.length === 1 ? 'structure' : 'structures'} · {rt.map((t) => t.name).join(' + ') || '–'} · {record.inputs.reference ?? '–'}
            </span>
          </h1>
        </div>
        <Link href={`/reports/${encodeURIComponent(record.id)}`} className="flex-none rounded border border-line bg-transparent px-3 py-[7px] text-[12.5px] leading-[normal] font-medium text-ink hover:border-ink hover:text-ink">
          Report
        </Link>
      </div>

      <SummaryStats record={record} tools={tools} figNo={6} />

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2" data-testid="ensemble-controls">
        <Segmented<View>
          label="view"
          testId="view-mode"
          value={view}
          onChange={setView}
          options={[
            { value: 'grid', label: 'grid' },
            { value: 'overlay', label: 'overlay', disabled: withCoords < 1, title: withCoords < 1 ? 'no structures with coordinates in the record' : `superpose ${withCoords} structures on the reference receptor` },
          ]}
        />
        <Segmented<GridColor>
          label="colour"
          testId="color-mode"
          value={color}
          onChange={setColor}
          options={[
            { value: 'chain', label: 'by chain', disabled: view === 'overlay', title: view === 'overlay' ? 'the overlay colours each structure' : undefined },
            { value: 'confidence', label: 'by confidence', disabled: view === 'overlay' || !anyConfidence, title: anyConfidence ? 'pLDDT on the B-factor column' : 'no structure in the record carries per-residue confidence (co-folding pLDDT)' },
            {
              value: 'flagged',
              label: 'flagged',
              disabled: view === 'overlay' || !flagged.length,
              title: flagged.length ? `residues named in warned or stopped findings: ${flagged.map((r) => `${r.name}${r.num}${r.chain ?? ''}`).join(', ')}` : 'no residues named in warned or stopped findings',
            },
          ]}
        />
        <Segmented<MemberSort>
          label="sort"
          testId="sort-mode"
          value={sort}
          onChange={setSort}
          options={[
            { value: 'record', label: 'record' },
            { value: 'confidence', label: 'confidence', disabled: !anyConf, title: anyConf ? undefined : 'no confidence output in the record' },
            { value: 'rmsd', label: 'RMSD', disabled: !anyRmsd, title: anyRmsd ? 'RMSD to the medoid' : 'RMSD to the medoid not computed' },
            { value: 'cluster', label: 'cluster', disabled: !anyCluster, title: anyCluster ? undefined : 'clusters not computed' },
          ]}
        />
        <ToggleChip on={pbOnly} onChange={setPbOnly} disabled={!anyPb} title={anyPb ? 'structures with fewer PoseBusters passes than tests' : 'PoseBusters not computed per structure'} testId="filter-pb">
          PoseBusters failures only
        </ToggleChip>
      </div>

      {sel && <MemberDetail m={sel} mode={cfg.mode} colorMode={view === 'overlay' ? 'chain' : color} flagged={flagged} onClose={() => setSelected(null)} />}

      {view === 'grid' ? (
        <StructureGrid
          members={shown}
          gridViewers={Math.max(0, cfg.gridViewers - (sel ? 1 : 0))}
          mode={cfg.mode}
          colorMode={color}
          flagged={flagged}
          columnsFrom={members}
          selected={selected}
          onSelect={(id) => setSelected((s) => (s === id ? null : id))}
        />
      ) : (
        <OverlayView members={shown} mode={cfg.mode} />
      )}
      <div className="text-[11px] text-muted">
        Fig. 7 · {view === 'overlay' ? `Overlay of ${withCoords} structures on the reference receptor; docking poses show the ligand only, co-folding models are superposed on the first chain by Cα.` : caption(members, primary, !!record.stats.ensemble)}
      </div>
    </>
  );
}

export function EnsembleView({ runId }: { runId: string }) {
  return <RecordGate runId={runId}>{(record) => <Ensemble record={record} />}</RecordGate>;
}
