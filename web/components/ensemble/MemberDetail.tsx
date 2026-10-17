'use client';

// A selected member opened large: Mol* viewer (renders without WebGL) and the full numbers table.

import { StructureViewer } from '@/components/viewer/StructureViewer';
import type { ViewerMode } from '@/components/viewer/config';
import type { ColorMode, SceneResidue } from '@/components/viewer/scene-types';
import { KIND_COLOR, type EnsembleMember } from '@/lib/selectors/report';
import { GateDot, MemberTable } from './MemberNumbers';

export function MemberDetail({ m, mode, colorMode, flagged, onClose }: { m: EnsembleMember; mode: ViewerMode; colorMode: ColorMode; flagged: SceneResidue[]; onClose: () => void }) {
  return (
    <div className="animate-fade-up" data-testid="member-detail" data-structure={m.id}>
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 font-mono text-[12px]">
          <span className="h-2 w-2 flex-none rounded-full" style={{ background: KIND_COLOR[m.kind] }} />
          <span className="truncate font-medium">{m.kind === 'medoid' ? `${m.label} · medoid` : m.label}</span>
          <span className="text-muted">{m.toolName ?? m.source}</span>
          <GateDot m={m} />
        </div>
        <button type="button" onClick={onClose} className="rounded border border-line px-3 py-[5px] text-[12px] font-medium text-ink2 hover:border-ink hover:text-ink" data-testid="member-close">
          Close
        </button>
      </div>
      <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(330px,1fr)] items-start gap-4">
        <StructureViewer target={m} mode={mode} colorMode={colorMode === 'member' ? 'chain' : colorMode} flagged={flagged} className="h-[400px] rounded-card border border-line" data-testid="detail-viewer" />
        <MemberTable m={m} />
      </div>
    </div>
  );
}
