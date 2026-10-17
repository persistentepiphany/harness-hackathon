// Mol* scene for one viewer: loads structures with explicit components (polymer cartoon, ligand
// ball-and-stick, flagged residues), superposes co-folding models on the first structure, and
// switches colour modes and per-member visibility. Imported only by MolstarViewer, which is
// loaded with next/dynamic (ssr: false).

import type { Structure } from 'molstar/lib/mol-model/structure';
import type { PluginContext } from 'molstar/lib/mol-plugin/context';
import type { StateObjectSelector } from 'molstar/lib/mol-state';
import type { StructureLoad } from '@/lib/selectors/report';
import type { ColorMode, SceneResidue } from './scene-types';

export type { ColorMode, SceneResidue } from './scene-types';

/**
 * Mol* modules used by the scene. Loaded with dynamic imports after molstar/lib/apps/viewer/app,
 * never statically: molstar's circular imports must evaluate in the order the viewer app sets up,
 * or the production bundle fails with "Cannot read properties of undefined (reading 'factory')".
 */
async function loadDeps() {
  const [structure, superposition, staticState, reprParams, transforms, builder, script, assets, color] = await Promise.all([
    import('molstar/lib/mol-model/structure'),
    import('molstar/lib/mol-model/structure/structure/util/superposition'),
    import('molstar/lib/mol-plugin/behavior/static/state'),
    import('molstar/lib/mol-plugin-state/helpers/structure-representation-params'),
    import('molstar/lib/mol-plugin-state/transforms'),
    import('molstar/lib/mol-script/language/builder'),
    import('molstar/lib/mol-script/script'),
    import('molstar/lib/mol-util/assets'),
    import('molstar/lib/mol-util/color'),
  ]);
  return {
    Structure: structure.Structure,
    StructureSelection: structure.StructureSelection,
    alignAndSuperpose: superposition.alignAndSuperpose,
    setSubtreeVisibility: staticState.setSubtreeVisibility,
    createStructureColorThemeParams: reprParams.createStructureColorThemeParams,
    StateTransforms: transforms.StateTransforms,
    MS: builder.MolScriptBuilder,
    Script: script.Script,
    Asset: assets.Asset,
    Color: color.Color,
  };
}

type Deps = Awaited<ReturnType<typeof loadDeps>>;

/** Scene for a created viewer plugin (call after the viewer app module has loaded). */
export async function createScene(plugin: PluginContext): Promise<Scene> {
  return new Scene(plugin, await loadDeps());
}

/* eslint-disable @typescript-eslint/no-explicit-any -- molstar state selectors are generic over transformer types */
type Sel = StateObjectSelector<any, any>;

interface Entry {
  load: StructureLoad;
  /** Top node of the member (hidden to hide the member). */
  root: Sel;
  /** Structure the components hang off (superposed copy when aligned). */
  structure: Sel;
  polymer?: Sel;
  ligand?: Sel;
  flagged?: Sel;
}

const FLAG = 0xc4513b;
const MUTED = 0xd8d8d2;
const hexNum = (h: string | undefined, fallback: number) => (h ? parseInt(h.replace('#', ''), 16) : fallback);

function caLoci(d: Deps, s: Structure) {
  const sel = d.Script.getStructureSelection((Q) => Q.struct.generator.atomGroups({ 'atom-test': Q.core.rel.eq([Q.struct.atomProperty.macromolecular.label_atom_id(), 'CA']) }), s);
  return d.StructureSelection.toLociWithSourceUnits(sel);
}

function residuesExpression(d: Deps, rs: SceneResidue[]) {
  const MS = d.MS;
  const P = MS.struct.atomProperty.macromolecular;
  const tests = rs.map((r) =>
    r.chain
      ? MS.core.logic.and([MS.core.rel.eq([P.auth_seq_id(), r.num]), MS.core.rel.eq([P.auth_asym_id(), r.chain])])
      : MS.core.rel.eq([P.auth_seq_id(), r.num]),
  );
  return MS.struct.generator.atomGroups({ 'residue-test': tests.length === 1 ? tests[0] : MS.core.logic.or(tests) });
}

export class Scene {
  private entries: Entry[] = [];
  private mode: ColorMode = 'chain';
  private hidden = new Set<string>();

  constructor(
    private readonly plugin: PluginContext,
    private readonly d: Deps,
  ) {}

  /** Replace the scene with `loads`; residues in `flagged` get their own component. */
  async load(loads: StructureLoad[], flagged: SceneResidue[]): Promise<void> {
    const p = this.plugin;
    const d = this.d;
    await p.clear();
    this.entries = [];
    for (let i = 0; i < loads.length; i++) {
      const l = loads[i];
      const data = await p.builders.data.download({ url: d.Asset.Url(l.url), isBinary: false, label: l.label }, { state: { isGhost: true } });
      const traj = await p.builders.structure.parseTrajectory(data, l.format);
      const model = await p.builders.structure.createModel(traj);
      const root: Sel = await p.builders.structure.createStructure(model);
      let structure: Sel = root;
      const ref = this.entries[0];
      if (l.align && ref) {
        try {
          const a = ref.structure.data as Structure | undefined;
          const b = root.data as Structure | undefined;
          if (a && b) {
            const [t] = d.alignAndSuperpose([caLoci(d, a), caLoci(d, b)]);
            if (t) {
              structure = await p
                .build()
                .to(root)
                .apply(d.StateTransforms.Model.TransformStructureConformation, { transform: { name: 'matrix', params: { data: t.bTransform, transpose: false } } })
                .commit();
            }
          }
        } catch {
          /* no common chain to align on: shown in its own frame */
        }
      }
      const e: Entry = { load: l, root, structure };
      if (l.polymer !== false) {
        const poly = await p.builders.structure.tryCreateComponentStatic(structure, 'polymer');
        if (poly) e.polymer = await p.builders.structure.representation.addRepresentation(poly, { type: 'cartoon', color: 'chain-id' });
        if (flagged.length) {
          const comp = await p.builders.structure.tryCreateComponentFromExpression(structure, residuesExpression(d, flagged), `flagged-${i}`, { label: 'flagged residues' });
          if (comp) {
            await p.builders.structure.representation.addRepresentation(comp, { type: 'ball-and-stick', color: 'uniform', colorParams: { value: d.Color(FLAG) } });
            e.flagged = comp;
          }
        }
      }
      const lig = await p.builders.structure.tryCreateComponentStatic(structure, 'ligand');
      if (lig) e.ligand = await p.builders.structure.representation.addRepresentation(lig, { type: 'ball-and-stick', color: 'element-symbol' });
      else if (l.polymer === false) {
        // a ligand-only file (SDF) may not classify as a ligand component: show the whole structure
        e.ligand = await p.builders.structure.representation.addRepresentation(structure, { type: 'ball-and-stick', color: 'element-symbol' });
      }
      this.entries.push(e);
    }
    await this.color(this.mode, true);
    this.applyVisibility();
    // ligand-only members (poses on the reference receptor): frame the poses, not the whole receptor
    const ligandOnly = this.entries.filter((e) => e.load.polymer === false).map((e) => e.structure.data as Structure | undefined).filter((x): x is Structure => !!x);
    if (ligandOnly.length) p.managers.camera.focusLoci(ligandOnly.map((x) => d.Structure.toStructureElementLoci(x)), { extraRadius: 6 });
    else p.managers.camera.reset();
  }

  /** Recolour every member for `mode`. */
  async color(mode: ColorMode, force = false): Promise<void> {
    if (mode === this.mode && !force) return;
    this.mode = mode;
    const p = this.plugin;
    const d = this.d;
    const b = p.build();
    // poses shown as ligands on a receptor: the receptor cartoon is context, drawn muted
    const receptorContext = this.entries.some((e) => e.load.polymer === false);
    for (const e of this.entries) {
      const s = e.structure.data as Structure | undefined;
      const member = d.Color(hexNum(e.load.color, 0x8b8b85));
      const muted = d.Color(MUTED);
      const polymerTheme: [string, any] =
        mode === 'member' ? ['uniform', { value: receptorContext ? muted : member }] : mode === 'flagged' ? ['uniform', { value: muted }] : mode === 'confidence' && e.load.confidence ? ['plddt-confidence', undefined] : ['chain-id', undefined];
      const ligandTheme: [string, any] = mode === 'member' ? ['uniform', { value: member }] : ['element-symbol', undefined];
      for (const [repr, theme] of [
        [e.polymer, polymerTheme],
        [e.ligand, ligandTheme],
      ] as const) {
        if (!repr) continue;
        b.to(repr).update(d.StateTransforms.Representation.StructureRepresentation3D, (old: any) => ({
          ...old,
          colorTheme: d.createStructureColorThemeParams(p, s, old.type?.name, theme[0], theme[1]),
        }));
      }
    }
    await b.commit();
    this.applyVisibility();
  }

  /** Members (StructureLoad.id) to hide. */
  setHidden(ids: Iterable<string>): void {
    const next = new Set(ids);
    if (next.size === this.hidden.size && Array.from(next).every((x) => this.hidden.has(x))) return;
    this.hidden = next;
    this.applyVisibility();
  }

  private applyVisibility(): void {
    const state = this.plugin.state.data;
    const isHidden = (ref: string) => !!state.cells.get(ref)?.state.isHidden;
    for (const e of this.entries) {
      const hide = e.load.id !== undefined && this.hidden.has(e.load.id);
      // touch Mol* state only where visibility changes, so an unchanged scene is never redrawn
      if (isHidden(e.root.ref) !== hide) this.d.setSubtreeVisibility(state, e.root.ref, hide);
      const hideFlag = hide || this.mode !== 'flagged';
      if (e.flagged && isHidden(e.flagged.ref) !== hideFlag) this.d.setSubtreeVisibility(state, e.flagged.ref, hideFlag);
    }
  }
}
/* eslint-enable @typescript-eslint/no-explicit-any */
