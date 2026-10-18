'use client';

// Viewer settings (prototype tweaks `gridViewers` and `viewerMode`, HANDOFF §7). Read from
// NEXT_PUBLIC_GRID_VIEWERS / NEXT_PUBLIC_VIEWER_MODE, overridable per page with ?gridViewers= and
// ?viewerMode=. Defaults on the first render, URL values after mount (no hydration mismatch).

import { useEffect, useState } from 'react';

export type ViewerMode = 'molstar' | 'placeholder';

export interface ViewerConfig {
  /** Mol* viewers on the ensemble grid; the browser limits WebGL contexts (default 6). */
  gridViewers: number;
  /** `placeholder` never creates a Mol* viewer and shows the PyMOL renders instead. */
  mode: ViewerMode;
}

export const DEFAULT_GRID_VIEWERS = 6;

function parseCount(v: string | null | undefined): number | undefined {
  if (v === null || v === undefined || v === '') return undefined;
  const n = Math.floor(Number(v));
  return Number.isFinite(n) && n >= 0 ? n : undefined;
}

function parseMode(v: string | null | undefined): ViewerMode | undefined {
  return v === 'placeholder' || v === 'molstar' ? v : undefined;
}

export function viewerConfig(search?: string): ViewerConfig {
  let params: URLSearchParams | null = null;
  try {
    params = new URLSearchParams(search ?? (typeof window !== 'undefined' ? window.location.search : ''));
  } catch {
    params = null;
  }
  return {
    gridViewers: parseCount(params?.get('gridViewers')) ?? parseCount(process.env.NEXT_PUBLIC_GRID_VIEWERS) ?? DEFAULT_GRID_VIEWERS,
    mode: parseMode(params?.get('viewerMode')) ?? parseMode(process.env.NEXT_PUBLIC_VIEWER_MODE) ?? 'molstar',
  };
}

const SERVER_DEFAULT: ViewerConfig = { gridViewers: DEFAULT_GRID_VIEWERS, mode: 'molstar' };

export function useViewerConfig(): ViewerConfig {
  const [cfg, setCfg] = useState<ViewerConfig>(SERVER_DEFAULT);
  useEffect(() => {
    const next = viewerConfig();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- URL is only readable after mount
    setCfg((c) => (c.gridViewers === next.gridViewers && c.mode === next.mode ? c : next));
  }, []);
  return cfg;
}

let probe: { webgl: boolean; software: boolean } | null = null;

/** One WebGL probe per page: support and whether the renderer is software (SwiftShader, llvmpipe). */
function glProbe(): { webgl: boolean; software: boolean } {
  if (probe) return probe;
  if (typeof document === 'undefined') return { webgl: false, software: false };
  try {
    const c = document.createElement('canvas');
    const gl = (c.getContext('webgl2') || c.getContext('webgl')) as WebGLRenderingContext | null;
    if (!gl) {
      probe = { webgl: false, software: false };
    } else {
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      const renderer = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
      probe = { webgl: true, software: /swiftshader|llvmpipe|softpipe|software/i.test(renderer) };
      // release the probe context: browsers cap live WebGL contexts
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    }
  } catch {
    probe = { webgl: false, software: false };
  }
  return probe;
}

/** Whether the browser can create a WebGL context (cached). False on the server. */
export function hasWebGL(): boolean {
  return glProbe().webgl;
}

/** Whether WebGL runs on a software rasteriser, where every Mol* frame is expensive. */
export function isSoftwareGL(): boolean {
  return glProbe().software;
}
