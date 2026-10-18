'use client';

// Structure panel body: Mol* when WebGL works and the target has coordinates, otherwise the PyMOL
// renders of the structure, otherwise a muted placeholder. Status (loading, error, fallback reason)
// sits bottom-left as in the prototype. data-state: molstar-loading | molstar-ready | molstar-error |
// render | placeholder.

import clsx from 'clsx';
import dynamic from 'next/dynamic';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { StructureLoad, StructureTarget } from '@/lib/selectors/report';
import type { RecordRender } from '@/lib/types';
import { hasWebGL, type ViewerMode } from './config';
import type { ViewerStatus } from './MolstarViewer';
import type { ColorMode, SceneResidue } from './scene-types';
import { RenderImage } from './RenderImage';

const MolstarViewer = dynamic(() => import('./MolstarViewer'), { ssr: false });

export interface StructureViewerProps {
  target: StructureTarget | undefined;
  mode?: ViewerMode;
  /** False when the grid has no free viewer slot for this cell. */
  slot?: boolean;
  /** Renders to show when the target has none of its own (e.g. the run's reference renders). */
  fallbackRenders?: RecordRender[];
  /** Placeholder text when nothing can be shown. */
  placeholder?: string;
  compact?: boolean;
  /** Mol* colour mode (default by chain). */
  colorMode?: ColorMode;
  /** Member ids hidden in a multi-structure scene. */
  hidden?: string[];
  /** Residues highlighted in the flagged mode. */
  flagged?: SceneResidue[];
  /** Override for the files to load (default target.load). */
  loads?: StructureLoad[];
  className?: string;
  'data-testid'?: string;
}

function Status({ children, busy, compact }: { children: React.ReactNode; busy?: boolean; compact?: boolean }) {
  return (
    <div
      className={clsx(
        'pointer-events-none absolute flex items-center gap-[7px] rounded-[4px] bg-white/85 font-mono text-muted',
        compact ? 'bottom-1.5 left-2 px-1.5 py-[2px] text-[10px]' : 'bottom-2.5 left-3 px-2 py-[3px] text-[11px]',
      )}
      data-testid="viewer-status"
    >
      {busy && <span className="inline-block h-2 w-2 animate-spin rounded-full border-[1.5px] border-line border-t-accent" />}
      {children}
    </div>
  );
}

export function StructureViewer({ target, mode = 'molstar', slot = true, fallbackRenders, placeholder, compact, colorMode, hidden, flagged, loads: loadsOverride, className, ...rest }: StructureViewerProps) {
  const [status, setStatus] = useState<{ s: ViewerStatus; d?: string; key: string } | null>(null);
  const [gl, setGl] = useState<boolean | null>(null);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- WebGL can only be probed in the browser
    setGl(hasWebGL());
  }, []);

  const loads = loadsOverride ?? target?.load ?? [];
  const key = loads.map((l) => l.url).join('|');
  const keyRef = useRef(key);
  useEffect(() => {
    keyRef.current = key;
  });
  const onStatus = useCallback((s: ViewerStatus, d?: string) => {
    setStatus((prev) => (prev && prev.s === s && prev.d === d && prev.key === keyRef.current ? prev : { s, d, key: keyRef.current }));
  }, []);
  const renders = target?.renders.length ? target.renders : (fallbackRenders ?? []);
  const current = status && status.key === key ? status : null;
  const noWebgl = gl === false || current?.s === 'no-webgl';
  const useMolstar = mode === 'molstar' && slot && loads.length > 0 && gl === true && !noWebgl;

  let state: string;
  let body: React.ReactNode;
  if (useMolstar) {
    state = current?.s === 'ready' ? 'molstar-ready' : current?.s === 'error' ? 'molstar-error' : 'molstar-loading';
    body = (
      <>
        <MolstarViewer loads={loads} colorMode={colorMode} hidden={hidden} flagged={flagged} onStatus={onStatus} />
        {current?.s === 'error' ? (
          <Status compact={compact}>
            <span className="text-stop">load failed</span>
            <span className="max-w-[260px] truncate" title={current.d}>
              {current.d}
            </span>
          </Status>
        ) : current?.s !== 'ready' ? (
          <Status busy compact={compact}>
            {current?.s === 'loading' && current.d ? (loads.length > 3 ? `loading ${loads.length} structures` : current.d) : 'starting Mol*'}
          </Status>
        ) : null}
      </>
    );
  } else if (gl === null && mode === 'molstar' && slot && loads.length > 0) {
    state = 'molstar-loading';
    body = null;
  } else if (renders.length) {
    state = 'render';
    const reason = !loads.length ? 'no coordinates in record' : !slot ? 'viewer slots full' : mode === 'placeholder' ? 'placeholder mode' : 'WebGL unavailable';
    body = (
      <>
        <RenderImage renders={renders} bare={compact} />
        <Status compact={compact}>PyMOL render · {reason}</Status>
      </>
    );
  } else {
    state = 'placeholder';
    const text = !slot && loads.length
      ? 'viewer slots full · raise gridViewers'
      : placeholder ?? (loads.length ? `${target?.label ?? ''}${mode === 'placeholder' ? '' : ' · WebGL unavailable'}` : `no coordinates for ${target?.label ?? 'this structure'} in the record`);
    body = (
      <div className={clsx('absolute inset-0 grid place-items-center px-4 text-center text-faint', compact ? 'font-mono text-[11px]' : 'text-[12px]')}>
        {text}
      </div>
    );
  }

  return (
    <div className={clsx('relative overflow-hidden bg-surface', className)} data-testid={rest['data-testid'] ?? 'structure-viewer'} data-state={state} data-structure={target?.id}>
      {body}
    </div>
  );
}
