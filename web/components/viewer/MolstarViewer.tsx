'use client';

// Mol* viewer (molstar/lib/apps/viewer). Loaded through next/dynamic with ssr:false from
// StructureViewer, so molstar never runs on the server. One Viewer per mount; a change of `loads`
// rebuilds the scene (scene.ts), `colorMode` recolours it and `hidden` toggles members. Scene
// operations run one after another.

import 'molstar/build/viewer/molstar.css';
import './viewer.css';
import clsx from 'clsx';
import { useEffect, useRef } from 'react';
import type { PluginContext } from 'molstar/lib/mol-plugin/context';
import type { StructureLoad } from '@/lib/selectors/report';
import type { Scene } from './scene';
import { isSoftwareGL } from './config';
import type { ColorMode, SceneResidue } from './scene-types';

export type ViewerStatus = 'creating' | 'loading' | 'ready' | 'error' | 'no-webgl';

export interface MolstarViewerProps {
  loads: StructureLoad[];
  colorMode?: ColorMode;
  /** Member ids (StructureLoad.id) to hide. */
  hidden?: string[];
  /** Residues highlighted in the `flagged` colour mode. */
  flagged?: SceneResidue[];
  onStatus?: (status: ViewerStatus, detail?: string) => void;
  className?: string;
}

interface ViewerLike {
  plugin: PluginContext;
  dispose: () => void;
}

/** Prototype viewerOpts: no panels, no controls, white background. */
const VIEWER_OPTIONS = {
  layoutIsExpanded: false,
  layoutShowControls: false,
  layoutShowSequence: false,
  layoutShowLog: false,
  layoutShowLeftPanel: false,
  viewportShowExpand: false,
  viewportShowSelectionMode: false,
  viewportShowAnimation: false,
  viewportShowSettings: false,
  viewportShowTrajectoryControls: false,
  viewportBackgroundColor: 'white',
  pdbProvider: 'rcsb',
  emdbProvider: 'rcsb',
} as const;

const keyOf = (loads: StructureLoad[], flagged: SceneResidue[]) =>
  `${loads.map((l) => `${l.format}:${l.url}:${l.color ?? ''}:${l.polymer === false ? 0 : 1}:${l.align ? 1 : 0}`).join('|')}#${flagged.map((r) => `${r.chain ?? ''}${r.num}`).join(',')}`;

export default function MolstarViewer({ loads, colorMode = 'chain', hidden, flagged, onStatus, className }: MolstarViewerProps) {
  const el = useRef<HTMLDivElement>(null);
  const scene = useRef<Scene | null>(null);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const ready = useRef<Promise<Scene | null> | null>(null);
  const latest = useRef({ loads, colorMode, hidden: hidden ?? [], flagged: flagged ?? [], onStatus });
  useEffect(() => {
    latest.current = { loads, colorMode, hidden: hidden ?? [], flagged: flagged ?? [], onStatus };
  });
  const status = (s: ViewerStatus, d?: string) => latest.current.onStatus?.(s, d);
  const enqueue = (fn: () => Promise<void>) => {
    queue.current = queue.current.then(fn, fn);
    return queue.current;
  };

  // the render loop runs only while the viewer is on screen and the tab is visible
  const plugin = useRef<PluginContext | null>(null);
  const onScreen = useRef(true);
  const running = useRef(true);
  const applyRunning = () => {
    const p = plugin.current;
    if (!p) return;
    const want = onScreen.current && (typeof document === 'undefined' || document.visibilityState !== 'hidden');
    if (want === running.current) return;
    running.current = want;
    if (el.current) el.current.dataset.running = String(want);
    // the plugin's animation loop drives canvas3d.tick; stopping it with noDraw also pauses canvas3d
    if (want) p.animationLoop.start();
    else p.animationLoop.stop({ noDraw: true });
  };
  useEffect(() => {
    const node = el.current;
    const onVis = () => applyRunning();
    document.addEventListener('visibilitychange', onVis);
    let io: IntersectionObserver | null = null;
    if (node && typeof IntersectionObserver !== 'undefined') {
      io = new IntersectionObserver((entries) => {
        // the latest entry is the current state
        onScreen.current = entries[entries.length - 1].isIntersecting;
        applyRunning();
      });
      io.observe(node);
    }
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      io?.disconnect();
    };
  }, []);

  // create once per mount
  useEffect(() => {
    let cancelled = false;
    let viewer: ViewerLike | null = null;
    status('creating');
    ready.current = (async () => {
      try {
        const { Viewer } = await import('molstar/lib/apps/viewer/app');
        if (cancelled || !el.current) return null;
        const v = (await Viewer.create(el.current, VIEWER_OPTIONS as never)) as unknown as ViewerLike;
        if (cancelled) {
          v.dispose();
          return null;
        }
        if (!v.plugin.canvas3d) {
          v.dispose();
          status('no-webgl');
          return null;
        }
        viewer = v;
        // software GL: every frame costs ~1 s, so no temporal multisampling (it redraws until settled)
        if (isSoftwareGL()) {
          try {
            v.plugin.canvas3d.setProps({ multiSample: { mode: 'off' } });
          } catch {
            /* rendering settings are an optimisation */
          }
        }
        plugin.current = v.plugin;
        applyRunning();
        // scene.ts and its molstar modules load only after the viewer app (see loadDeps there)
        const { createScene } = await import('./scene');
        if (cancelled) return null;
        scene.current = await createScene(v.plugin);
        return scene.current;
      } catch (e) {
        if (!cancelled) status('error', e instanceof Error ? e.message : String(e));
        return null;
      }
    })();
    return () => {
      cancelled = true;
      // Viewer.dispose disposes the plugin, which destroys the WebGL context (WEBGL_lose_context)
      try {
        viewer?.dispose();
      } catch {
        /* already disposed */
      }
      plugin.current = null;
      running.current = true;
      scene.current = null;
      ready.current = null;
    };
  }, []);

  // rebuild the scene when the files change
  const key = keyOf(loads, flagged ?? []);
  useEffect(() => {
    let stale = false;
    const pending = ready.current;
    if (!pending) return;
    void enqueue(async () => {
      const sc = await pending;
      if (!sc || stale) return;
      const { loads: ls, flagged: fl, colorMode: cm, hidden: hd } = latest.current;
      status('loading', ls.map((l) => l.label).join(' + '));
      try {
        await sc.color(cm);
        sc.setHidden(hd);
        await sc.load(ls, fl);
        if (!stale) status('ready');
      } catch (e) {
        if (!stale) status('error', e instanceof Error ? e.message : String(e));
      }
    });
    return () => {
      stale = true;
    };
  }, [key]);

  // recolour
  useEffect(() => {
    const pending = ready.current;
    if (!pending) return;
    void enqueue(async () => {
      const sc = await pending;
      if (sc) await sc.color(latest.current.colorMode);
    });
  }, [colorMode]);

  // visibility
  const hiddenKey = (hidden ?? []).join('|');
  useEffect(() => {
    const pending = ready.current;
    if (!pending) return;
    void pending.then((sc) => sc?.setHidden(latest.current.hidden));
  }, [hiddenKey]);

  return <div ref={el} className={clsx('harness-molstar', className)} style={{ position: 'absolute', inset: 0 }} data-testid="molstar-canvas" data-running="true" />;
}
