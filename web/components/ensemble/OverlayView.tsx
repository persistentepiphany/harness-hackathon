'use client';

// Overlay: one large Mol* viewer with every member on the reference receptor, each in its own
// colour (crystal ink, medoid accent, then the muted palette). Docking poses show the ligand only;
// co-folding models are superposed on the first chain. The legend toggles visibility; hovering a
// row isolates that member.

import clsx from 'clsx';
import { useMemo, useState } from 'react';
import { StructureViewer } from '@/components/viewer/StructureViewer';
import type { ViewerMode } from '@/components/viewer/config';
import { DASH, fmtNum } from '@/lib/format';
import { overlayLoads, type EnsembleMember } from '@/lib/selectors/report';
import { GateDot } from './MemberNumbers';

export function OverlayView({ members, mode, className }: { members: EnsembleMember[]; mode: ViewerMode; className?: string }) {
  const loads = useMemo(() => overlayLoads(members), [members]);
  const [off, setOff] = useState<Set<string>>(() => new Set());
  const [hover, setHover] = useState<string | null>(null);
  const withCoords = useMemo(() => members.filter((m) => m.load.length), [members]);
  const hidden = useMemo(() => (hover ? withCoords.filter((m) => m.id !== hover).map((m) => m.id) : Array.from(off)), [hover, off, withCoords]);
  const toggle = (id: string) =>
    setOff((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  const target = withCoords.length ? { ...withCoords[0], id: 'overlay', label: 'overlay', load: loads, renders: [] } : undefined;

  return (
    <div className={clsx('grid grid-cols-[minmax(0,1fr)_280px] items-start gap-4', className)} data-testid="overlay-view">
      <StructureViewer
        target={target}
        loads={loads}
        mode={mode}
        colorMode="member"
        hidden={hidden}
        placeholder="no structures with coordinates in the record"
        className="h-[560px] rounded-card border border-line"
        data-testid="overlay-viewer"
      />
      <div className="max-h-[560px] overflow-auto rounded-card border border-line bg-surface font-mono text-[11.5px]" data-testid="overlay-legend" onMouseLeave={() => setHover(null)}>
        <div className="sticky top-0 flex items-center justify-between border-b border-line2 bg-surface px-3 py-2 text-[10.5px] text-muted">
          <span>
            {withCoords.length} of {members.length} with coordinates
          </span>
          <span className="flex gap-2">
            <button type="button" className="text-muted hover:text-ink" onClick={() => setOff(new Set())}>
              all
            </button>
            <button type="button" className="text-muted hover:text-ink" onClick={() => setOff(new Set(withCoords.map((m) => m.id)))}>
              none
            </button>
          </span>
        </div>
        {members.map((m) => {
          const has = m.load.length > 0;
          const on = has && !off.has(m.id);
          return (
            <label
              key={m.id}
              className={clsx('grid cursor-pointer grid-cols-[14px_10px_minmax(0,1fr)_auto_8px] items-center gap-2 border-b border-line3 px-3 py-1.5', hover === m.id && 'bg-canvas', !has && 'cursor-default text-faint')}
              onMouseEnter={() => has && setHover(m.id)}
              data-testid="overlay-member"
              data-structure={m.id}
              data-state={!has ? 'no-coordinates' : on ? 'visible' : 'hidden'}
              title={has ? 'hover to isolate' : 'no coordinates in the record'}
            >
              <input type="checkbox" checked={on} disabled={!has} onChange={() => toggle(m.id)} className="h-3 w-3 accent-[var(--color-ink)]" />
              <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: has ? m.color : 'transparent', border: has ? undefined : '1px solid var(--color-line)' }} />
              <span className="truncate">{m.kind === 'medoid' ? `${m.label} · medoid` : m.label}</span>
              <span className="text-right text-[10.5px] text-muted" title={m.confidence ? m.confidence.label : undefined}>
                {m.confidence ? fmtNum(m.confidence.value, m.confidence.unit) : m.rmsd !== null && m.kind !== 'medoid' ? fmtNum(m.rmsd, 'Å', 1) : DASH}
              </span>
              <GateDot m={m} />
            </label>
          );
        })}
      </div>
    </div>
  );
}
