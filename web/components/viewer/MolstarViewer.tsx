'use client';

// Mol* viewer (molstar/lib/apps/viewer). Loaded through next/dynamic with ssr:false from
// StructureViewer, so molstar never runs on the server. One Viewer per mount; a change of `loads`
// rebuilds the scene (scene.ts), `colorMode` recolours it and `hidden` toggles members. Scene
// operations run one after another. The render loop pauses off screen, in a hidden tab and when the
// scene has been idle for IDLE_MS.

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
  // G3D (genome) support registers global symbols per plugin and warns on every later viewer
  disabledExtensions: ['g3d'],
} as const;

/** The render loop stops this long after the last interaction or scene operation. */
const IDLE_MS = 1000;
const WAKE_EVENTS = ['pointerdown', 'pointermove', 'wheel', 'keydown', 'touchstart'] as const;

/**
 * Starts and stops the plugin's animation loop: running only while the viewer is on screen, the
 * tab is visible and something happened in the last IDLE_MS (an interaction, a scene operation or
 * a camera transition). Stopping with noDraw leaves the last frame on the canvas.
 */
class RenderLoop {
  private plugin: PluginContext | null = null;
  private onScreen = true;
  private running = true;
  private idle = false;
  private busy = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly el: HTMLElement | null) {}

  attach(plugin: PluginContext): void {
    this.plugin = plugin;
    this.apply();
    this.wake();
  }

  detach(): void {
    this.plugin = null;
    this.running = true;
    this.idle = false;
  }

  apply(): void {
    const p = this.plugin;
    if (!p) return;
    const want = !this.idle && this.onScreen && (typeof document === 'undefined' || document.visibilityState !== 'hidden');
    if (want === this.running) return;
    this.running = want;
    if (this.el) this.el.dataset.running = String(want);
    // the plugin's animation loop drives canvas3d.tick; stopping it with noDraw also pauses canvas3d
    if (want) p.animationLoop.start();
    else p.animationLoop.stop({ noDraw: true });
  }

  setOnScreen(on: boolean): void {
    this.onScreen = on;
    this.apply();
  }

  /** Activity: run the loop now and stop it again IDLE_MS after the last activity. */
  wake(): void {
    if (this.idle) {
      this.idle = false;
      if (this.el) this.el.dataset.idle = 'false';
      this.apply();
    }
    this.schedule(IDLE_MS);
  }

  /** A scene operation starts / ends: the loop stays on while any runs. */
  begin(): void {
    this.busy += 1;
    this.wake();
  }

  end(): void {
    this.busy = Math.max(0, this.busy - 1);
    this.wake();
  }

  dispose(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private schedule(ms: number): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(this.check, ms);
  }

  private readonly check = (): void => {
    this.timer = null;
    const p = this.plugin;
    if (!p) return;
    if (this.busy > 0 || p.canvas3d?.camera.transition.inTransition) {
      this.schedule(IDLE_MS / 2);
      return;
    }
    this.idle = true;
    if (this.el) this.el.dataset.idle = 'true';
    this.apply();
  };
}

const keyOf = (loads: StructureLoad[], flagged: SceneResidue[]) =>
  `${loads.map((l) => `${l.format}:${l.url}:${l.color ?? ''}:${l.polymer === false ? 0 : 1}:${l.align ? 1 : 0}:${l.focus ?? ''}`).join('|')}#${flagged.map((r) => `${r.chain ?? ''}${r.num}`).join(',')}`;

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

  // the render loop runs only while the viewer is on screen, the tab is visible and the scene is
  // not idle (RenderLoop); scene operations count as activity
  const loop = useRef<RenderLoop | null>(null);
  const enqueue = (fn: () => Promise<void>) => {
    const run = async () => {
      const l = loop.current;
      l?.begin();
      try {
        await fn();
      } finally {
        l?.end();
      }
    };
    queue.current = queue.current.then(run, run);
    return queue.current;
  };
  useEffect(() => {
    const node = el.current;
    const l = new RenderLoop(node);
    loop.current = l;
    const onVis = () => l.apply();
    document.addEventListener('visibilitychange', onVis);
    let io: IntersectionObserver | null = null;
    if (node && typeof IntersectionObserver !== 'undefined') {
      io = new IntersectionObserver((entries) => {
        // the latest entry is the current state
        l.setOnScreen(entries[entries.length - 1].isIntersecting);
      });
      io.observe(node);
    }
    // interactions and size changes redraw: restart the loop, then stop it again when idle
    const onWake = () => l.wake();
    for (const ev of WAKE_EVENTS) node?.addEventListener(ev, onWake, { passive: true });
    const ro = node && typeof ResizeObserver !== 'undefined' ? new ResizeObserver(onWake) : null;
    if (node) ro?.observe(node);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      io?.disconnect();
      ro?.disconnect();
      for (const ev of WAKE_EVENTS) node?.removeEventListener(ev, onWake);
      l.dispose();
      if (loop.current === l) loop.current = null;
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
        // no axes / camera helper gizmo in the corner of the viewport
        try {
          v.plugin.canvas3d.setProps({ camera: { helper: { axes: { name: 'off', params: {} } } } });
        } catch {
          /* a viewport decoration; the scene works without it */
        }
        // software GL: every frame costs ~1 s, so no temporal multisampling (it redraws until settled)
        if (isSoftwareGL()) {
          try {
            v.plugin.canvas3d.setProps({ multiSample: { mode: 'off' } });
          } catch {
            /* rendering settings are an optimisation */
          }
        }
        loop.current?.attach(v.plugin);
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
      loop.current?.detach();
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
    void enqueue(async () => {
      const sc = await pending;
      sc?.setHidden(latest.current.hidden);
    });
  }, [hiddenKey]);

  return <div ref={el} className={clsx('harness-molstar', className)} style={{ position: 'absolute', inset: 0 }} data-testid="molstar-canvas" data-running="true" data-idle="false" />;
}
