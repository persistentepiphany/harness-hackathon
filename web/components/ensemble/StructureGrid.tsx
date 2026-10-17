'use client';

// Ensemble grid (prototype en.cells): one cell per member (crystal, medoid, seeds, docking poses,
// models). Cells in view with coordinates get live Mol* viewers up to gridViewers (an
// IntersectionObserver frees slots as cells scroll away); other cells show the member's PyMOL
// render, then a placeholder. Footer: key numbers from the tools' outputs; header: tool and gate.

import clsx from 'clsx';
import { useEffect, useRef, useState } from 'react';
import { StructureViewer } from '@/components/viewer/StructureViewer';
import type { ViewerMode } from '@/components/viewer/config';
import type { ColorMode, SceneResidue } from '@/components/viewer/scene-types';
import { KIND_COLOR, memberColumns, type EnsembleMember } from '@/lib/selectors/report';
import { GateDot, MemberFooter } from './MemberNumbers';

export interface StructureGridProps {
  members: EnsembleMember[];
  gridViewers: number;
  mode: ViewerMode;
  colorMode: Exclude<ColorMode, 'member'>;
  flagged: SceneResidue[];
  /** Members the columns are built from (all, before filtering). */
  columnsFrom?: EnsembleMember[];
  selected: string | null;
  onSelect: (id: string) => void;
  className?: string;
}

/** Viewer slots in display order to members with coordinates that are in view, up to `cap`. */
export function assignSlots(members: { id: string; load: unknown[] }[], cap: number, inView?: Set<string>): Set<string> {
  const out = new Set<string>();
  for (const t of members) {
    if (out.size >= cap) break;
    if (t.load.length && (!inView || inView.has(t.id))) out.add(t.id);
  }
  return out;
}

function useInView(ids: string[]) {
  const [inView, setInView] = useState<Set<string>>(() => new Set());
  const nodes = useRef(new Map<string, Element>());
  const observer = useRef<IntersectionObserver | null>(null);
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- no observer: treat every cell as visible
      setInView(new Set(ids));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        setInView((prev) => {
          const next = new Set(prev);
          for (const e of entries) {
            const id = (e.target as HTMLElement).dataset.member;
            if (!id) continue;
            if (e.isIntersecting) next.add(id);
            else next.delete(id);
          }
          return next;
        });
      },
      { rootMargin: '200px 0px' },
    );
    observer.current = io;
    nodes.current.forEach((el) => io.observe(el));
    return () => io.disconnect();
    // ids identity changes every render; the joined key is the dependency
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids.join('|')]);
  const ref = (id: string) => (el: Element | null) => {
    const prev = nodes.current.get(id);
    if (prev && prev !== el) observer.current?.unobserve(prev);
    if (el) {
      nodes.current.set(id, el);
      observer.current?.observe(el);
    } else nodes.current.delete(id);
  };
  return { inView, ref };
}

export function StructureGrid({ members, columnsFrom, gridViewers, mode, colorMode, flagged, selected, onSelect, className }: StructureGridProps) {
  const columns = memberColumns(columnsFrom ?? members);
  const { inView, ref } = useInView(members.map((m) => m.id));
  const slots = assignSlots(members, gridViewers, inView);
  const showRanking = (columnsFrom ?? members).some((m) => m.ranking.length > 0);

  return (
    <div className={clsx('grid gap-3.5', className)} style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(260px,1fr))' }} data-testid="structure-grid">
      {members.map((m) => {
        const confOff = colorMode === 'confidence' && !m.perResidueConfidence && m.load.length > 0;
        return (
          <div
            key={m.id}
            ref={ref(m.id)}
            data-member={m.id}
            className={clsx(
              'animate-fade-up overflow-hidden rounded-card border bg-surface',
              selected === m.id ? 'border-ink' : m.kind === 'medoid' ? 'border-accent' : 'border-line',
            )}
            data-testid="structure-cell"
            data-structure={m.id}
            data-kind={m.kind}
            data-state={selected === m.id ? 'selected' : 'idle'}
          >
            <button
              type="button"
              onClick={() => onSelect(m.id)}
              className="flex w-full items-center justify-between gap-2 border-0 border-b border-line2 bg-transparent px-3 py-2 text-left font-mono text-[11.5px] text-ink hover:bg-canvas"
              title="open with all numbers"
            >
              <span className="flex min-w-0 items-center gap-[7px]">
                <span className="h-1.5 w-1.5 flex-none rounded-full" style={{ background: KIND_COLOR[m.kind] }} />
                <span className="truncate" title={m.structure?.path ?? m.label}>
                  {m.kind === 'medoid' ? `${m.label} · medoid` : m.label}
                </span>
              </span>
              <span className="flex flex-none items-center gap-1.5 text-muted">
                <span className="max-w-[110px] truncate text-[10.5px]">{m.toolName ?? m.entry?.source ?? m.kind}</span>
                <GateDot m={m} />
              </span>
            </button>
            <div className="relative">
              <StructureViewer target={m} mode={mode} slot={slots.has(m.id)} compact colorMode={colorMode} flagged={flagged} className="h-[210px]" data-testid="cell-viewer" />
              {confOff && slots.has(m.id) && (
                <span className="pointer-events-auto absolute top-1.5 left-2 rounded-[4px] bg-white/85 px-1.5 py-[1px] font-mono text-[10px] text-muted" title="no per-residue confidence for this structure; coloured by chain" data-testid="confidence-off">
                  by chain
                </span>
              )}
            </div>
            <MemberFooter m={m} columns={columns} showRanking={showRanking} />
          </div>
        );
      })}
      {!members.length && <div className="text-[12px] text-muted">no structures match</div>}
    </div>
  );
}
