// Report and ensemble derivations (prototype logic-v2.js renderVals() `rp` and `en`), as pure
// functions of the UI record and the tool register. Components render these; they never name an
// executor or a metric. Missing stats blocks stay missing (null), so the UI can show "not computed".

import { DASH, fmtNum, fmtQuantityParts, isMissing, quantityOf, type Quantity } from '../format';
import { familyOf, labelFor, outputFor, recordTools, toolById, type ResolvedTool } from '../tools';
import type {
  Assessment,
  Certainty,
  DimensionId,
  EnsembleEntry,
  Outcome,
  PhysicsRow,
  RecordLayer,
  RecordRender,
  RecordStructure,
  Result,
  StatsSource,
  StructureKind,
  Tool,
  ToolFamily,
  ToolOutput,
  UiCheck,
  UiMetric,
  UiDimension,
  UiExecution,
  UiGlossary,
  UiRunRecord,
  UiToolVersion,
} from '../types';

type Register = Tool[] | null | undefined;

// ---------------------------------------------------------------- palette (prototype P, T, KIND)

export const RESULT_COLOR: Record<Result, string> = {
  pass: 'var(--color-pass)',
  warn: 'var(--color-warn)',
  stop: 'var(--color-stop)',
  reported: 'var(--color-reported)',
  skip: 'var(--color-faint)',
  pending: 'var(--color-faint)',
};

export const RESULT_TINT: Record<'pass' | 'warn' | 'stop' | 'reported', string> = {
  pass: 'var(--color-pass-tint)',
  warn: 'var(--color-warn-tint)',
  stop: 'var(--color-stop-tint)',
  reported: 'var(--color-line2)',
};

export const KIND_COLOR: Record<StructureKind, string> = {
  crystal: 'var(--color-ink)',
  medoid: 'var(--color-accent)',
  seed: 'var(--color-seed)',
  docking: 'var(--color-docking)',
  model: 'var(--color-model)',
};

/** Interaction type → stroke colour and dash (prototype INTER). Unknown types are muted, solid. */
export function interactionStyle(type: string): { stroke: string; dash: string } {
  const stroke =
    type === 'H-bond'
      ? 'var(--color-pass)'
      : type === 'Salt bridge'
        ? 'var(--color-accent)'
        : type === 'π stacking'
          ? 'var(--color-docking)'
          : 'var(--color-muted)';
  const dash = type === 'Hydrophobic' ? '3 3' : type === 'H-bond' ? '5 3' : '0';
  return { stroke, dash };
}

// ---------------------------------------------------------------- verdict

export interface VerdictMeta {
  label: string;
  color: string;
  /** data-state for the verdict element. */
  state: Outcome | 'pending';
}

export function verdictMeta(outcome: Outcome | null | undefined): VerdictMeta {
  switch (outcome) {
    case 'refused':
      return { label: 'Refused', color: 'var(--color-stop)', state: 'refused' };
    case 'narrowed':
      return { label: 'Narrowed', color: 'var(--color-accent-deep)', state: 'narrowed' };
    case 'supported':
      return { label: 'Supported', color: 'var(--color-pass)', state: 'supported' };
    case 'incomplete':
      return { label: 'Incomplete', color: 'var(--color-ink2)', state: 'incomplete' };
    case 'not_assessed':
      return { label: 'Not assessed', color: 'var(--color-ink2)', state: 'not_assessed' };
    default:
      return { label: 'In progress', color: 'var(--color-muted)', state: 'pending' };
  }
}

// ---------------------------------------------------------------- checks and layers

/** A check listed by the task but not registered in the harness. */
export function isNotImplemented(c: Pick<UiCheck, 'result' | 'skipReason'>): boolean {
  return c.result === 'skip' && c.skipReason === 'unknown_check';
}

/** Worst result of a list: stop > warn > pass > reported > pending > skip; null when empty. */
export function worstResult(checks: Pick<UiCheck, 'result'>[]): Result | null {
  const order: Result[] = ['stop', 'warn', 'pass', 'reported', 'pending', 'skip'];
  for (const r of order) if (checks.some((c) => c.result === r)) return r;
  return null;
}

export interface LayerNavItem {
  i: number;
  name: string;
  summary: string;
  dot: Result | null;
  status: RecordLayer['status'];
  total: number;
  notImplemented: number;
}

export function layerNav(record: Pick<UiRunRecord, 'layers'>): LayerNavItem[] {
  return record.layers.map((l) => ({
    i: l.i,
    name: l.name,
    summary: (l.summary ?? []).join(' · '),
    dot: worstResult(l.checks),
    status: l.status,
    total: l.checks.length,
    notImplemented: l.checks.filter(isNotImplemented).length,
  }));
}

const evaluated = (c: UiCheck) => c.result !== 'skip' && c.result !== 'pending';

/**
 * Layer shown first: the first layer with a stop when refused; otherwise layer 4 (output
 * validity, as the prototype) when it has evaluated checks; otherwise the last layer with an
 * evaluated check; otherwise 0.
 */
export function defaultLayerIndex(record: Pick<UiRunRecord, 'layers' | 'verdict'>): number {
  const ls = record.layers;
  if (!ls.length) return 0;
  const firstStop = ls.findIndex((l) => l.checks.some((c) => c.result === 'stop'));
  if (record.verdict.outcome === 'refused' && firstStop >= 0) return firstStop;
  const four = ls.findIndex((l) => l.i === 4);
  if (four >= 0 && ls[four].checks.some(evaluated)) return four;
  for (let k = ls.length - 1; k >= 0; k--) if (ls[k].checks.some(evaluated)) return k;
  return 0;
}

/** Sum of layer durations; null when no layer reports one. */
export function totalDurationMs(record: Pick<UiRunRecord, 'layers'>): number | null {
  const ds = record.layers.map((l) => l.durationMs).filter((d): d is number => typeof d === 'number');
  return ds.length ? ds.reduce((a, b) => a + b, 0) : null;
}

/** ISO time in ms; fractional seconds beyond milliseconds are dropped first. */
function parseIso(t: string | null | undefined): number | null {
  if (!t) return null;
  const v = Date.parse(t.replace(/(\.\d{3})\d+/, '$1'));
  return Number.isFinite(v) ? v : null;
}

/**
 * Wall time of the run (record.finishedAt − record.startedAt, as the job page), falling back to
 * the sum of layer durations when the record has no timestamps.
 */
export function runDurationMs(record: Pick<UiRunRecord, 'layers' | 'record'>): number | null {
  const a = parseIso(record.record?.startedAt);
  const b = parseIso(record.record?.finishedAt);
  if (a !== null && b !== null && b >= a) return b - a;
  return totalDurationMs(record);
}

// ---------------------------------------------------------------- task shape

/** True when the record has a ligand (prototype `lig`, ligand-pose style tasks). */
export function hasLigand(record: Pick<UiRunRecord, 'inputs'>): boolean {
  return !isMissing(record.inputs.ligand);
}

// ---------------------------------------------------------------- structures

export interface StructureLoad {
  url: string;
  format: RecordStructure['format'];
  label: string;
  /** Member id (overlay legend and visibility). */
  id?: string;
  /** Member colour in the overlay, CSS hex. */
  color?: string;
  /** Show the polymer; false shows the ligand only (docking poses on the reference receptor). */
  polymer?: boolean;
  /** Superpose onto the first structure of the scene by its first polymer chain. */
  align?: boolean;
  /** The B-factor column carries per-residue confidence (co-folding output). */
  confidence?: boolean;
  /** Frame the camera on the ligand instead of the whole structure (single docking pose). */
  focus?: 'ligand';
}

export interface StructureTarget {
  /** Chip id; `medoid` for the medoid entry, `overlay` for the overlay. */
  id: string;
  label: string;
  kind: StructureKind | 'overlay';
  /** Where the structure comes from (RCSB, a tool name, a file path). */
  source: string;
  /** Files to load into Mol*; empty when the record carries no coordinates for it. */
  load: StructureLoad[];
  /** PyMOL renders of the structure (live records), one per file. */
  renders: RecordRender[];
  /** The record structure entry, when there is one. */
  structure?: RecordStructure;
  /** The stats row, when stats.ensemble has one. */
  entry?: EnsembleEntry;
  /** Register id and display name of the producing tool, when known. */
  toolId?: string;
  toolName?: string;
  /** The pose's ligand as its own file (stats.ensemble[].ligand), used by the overlay. */
  ligandLoad?: StructureLoad;
}

export interface StructureTargetOptions {
  /** Browser URL for a native API path (HarnessApi.assetUrl). */
  assetUrl: (pathOrUrl: string) => string;
  /** Tool register (families and outputs of tools missing from record.tools). */
  register?: Register;
}

const PDB_ID = /^[0-9][A-Za-z0-9]{3}$/;

/**
 * Mock records carry no coordinates. As in the prototype, the crystal reference is loaded from
 * RCSB in mock mode only; live records load their own files and never fall back to the network.
 */
function mockReferenceLoad(record: UiRunRecord): StructureLoad[] {
  const ref = record.inputs.reference;
  if (record.source !== 'mock' || !ref || !PDB_ID.test(ref)) return [];
  return [{ url: `https://files.rcsb.org/download/${ref.toUpperCase()}.cif`, format: 'mmcif', label: `RCSB ${ref}` }];
}

function matchStructure(structures: RecordStructure[], entry: EnsembleEntry): RecordStructure | undefined {
  const ref = entry.structureId;
  return (
    structures.find((s) => s.id === entry.id || (ref !== undefined && s.id === ref)) ??
    (entry.kind === 'crystal' ? structures.find((s) => s.kind === 'crystal') : undefined)
  );
}

/**
 * Intermediate files are not ensemble members: artifactKind `file` (protonated receptors, fixed
 * inputs) and check-derived files under <run>/derived/.
 */
const isMemberStructure = (s: RecordStructure) => s.artifactKind !== 'file' && !/(^|\/)derived\//.test(s.path ?? s.id);

/** The record tool whose id is a segment of the structure path, e.g. predictions/00_x/<tool>/seed0. */
function toolOfStructure(record: UiRunRecord, s: RecordStructure): string | undefined {
  const segs = (s.path ?? s.id).split('/');
  return record.tools.find((t) => segs.includes(t.id))?.id;
}

/** Labels that collide get the first path segment where their paths differ as a prefix. */
function disambiguate(targets: StructureTarget[]): void {
  const byLabel = new Map<string, StructureTarget[]>();
  for (const t of targets) byLabel.set(t.label, [...(byLabel.get(t.label) ?? []), t]);
  for (const group of Array.from(byLabel.values())) {
    if (group.length < 2) continue;
    const paths = group.map((t) => (t.structure?.path ?? t.id).split('/'));
    let k = 0;
    while (k < Math.min(...paths.map((p) => p.length)) && paths.every((p) => p[k] === paths[0][k])) k++;
    group.forEach((t, i) => {
      if (paths[i][k] && !t.label.includes(paths[i][k])) t.label = `${paths[i][k]} ${t.label}`;
    });
  }
}

/** `3PTB mmCIF` → `3PTB`: crystal chips show the entry id. */
function crystalLabel(label: string, reference?: string): string {
  if (reference && label.startsWith(reference)) return reference;
  const m = label.match(/^(\S+) (mmCIF|CIF|PDB|BinaryCIF)$/i);
  return m ? m[1] : label;
}

/**
 * Crystal structures other than the declared reference (comparators that exposure checks fetched
 * into artifacts/sources/) are not ensemble members; stats.py `_crystal_rows` keeps the same set.
 */
function isReferenceOrPrediction(s: RecordStructure, reference: string | null | undefined): boolean {
  if (s.kind !== 'crystal' || !reference) return true;
  const base = (s.path ?? s.id).split('/').pop() ?? '';
  return base.split('.')[0].toUpperCase() === reference.toUpperCase();
}

const uniqueRenders = (rs: RecordRender[]) => rs.filter((r, i) => rs.findIndex((x) => x.png === r.png) === i);
/** Render ids are structure ids with separators replaced (`predictions_00_x_seed0_mode0_complex`). */
const normId = (id: string) => id.replace(/[^A-Za-z0-9]+/g, '_');

/**
 * Structure chips in prototype order: crystal, medoid, seeds, docking poses and models, then
 * `overlay` when there are two or more structures. Built from stats.ensemble (mock) and
 * record.structures (live), merged by id.
 */
export function structureTargets(record: UiRunRecord, opts: StructureTargetOptions): StructureTarget[] {
  const structures = (record.structures ?? []).filter(isMemberStructure).filter((s) => isReferenceOrPrediction(s, record.inputs.reference));
  const renders = record.renders ?? [];
  const ensemble = record.stats.ensemble ?? [];
  const used = new Set<string>();
  const loadOf = (s: RecordStructure | undefined): StructureLoad[] =>
    s ? [{ url: opts.assetUrl(s.url), format: s.format, label: s.label }] : [];
  const rendersOf = (s: RecordStructure | undefined, e?: EnsembleEntry) => {
    // renders[].structure is the structure id, or an id derived from its path or label: try in that order
    const tries = [s?.id, s?.path, s?.label, e?.pose, e?.label].filter((v): v is string => !!v);
    let own: RecordRender[] = [];
    for (const t of tries) {
      own = renders.filter((r) => r.structure === t || normId(r.structure) === normId(t));
      if (own.length) break;
    }
    if (!own.length && s) {
      // render ids built from part of the path (`00_x_seed0_mode0` for predictions/00_x/x/seed0/mode0/complex): longest contained id wins
      const sid = normId(s.path ?? s.id);
      const contained = renders.filter((r) => normId(r.structure).length >= 8 && sid.includes(normId(r.structure)));
      const best = Math.max(0, ...contained.map((r) => normId(r.structure).length));
      own = contained.filter((r) => normId(r.structure).length === best);
    }
    const png = e?.render;
    const fromEntry: RecordRender[] = png && !own.some((r) => r.png === png) ? (renders.filter((r) => r.png === png).length ? renders.filter((r) => r.png === png) : [{ structure: s?.id ?? e?.id ?? '', png, pse: '', view: 'overview' }]) : [];
    return uniqueRenders([...own, ...fromEntry]);
  };
  const nameOf = (id: string | undefined) => (id ? toolById(record, id, opts.register).name : undefined);

  const fromEnsemble: StructureTarget[] = ensemble.map((e) => {
    const s = matchStructure(structures, e);
    if (s) used.add(s.id);
    const load = s ? loadOf(s) : e.kind === 'crystal' ? mockReferenceLoad(record) : [];
    const toolId = e.toolId ?? (s ? toolOfStructure(record, s) : undefined);
    const lig = e.ligand;
    const ligandLoad: StructureLoad | undefined =
      lig?.url && (lig.format === 'sdf' || lig.format === 'pdb' || lig.format === 'mmcif') ? { url: opts.assetUrl(lig.url), format: lig.format, label: `${e.label} ligand` } : undefined;
    const label = e.kind === 'crystal' ? crystalLabel(e.label, record.inputs.reference) : e.label;
    return { id: e.kind === 'medoid' ? 'medoid' : e.id, label, kind: e.kind, source: e.source, load, renders: rendersOf(s, e), structure: s, entry: e, toolId, toolName: nameOf(toolId), ligandLoad };
  });
  const fromStructures: StructureTarget[] = structures
    .filter((s) => !used.has(s.id))
    .map((s) => {
      const toolId = s.kind === 'crystal' ? undefined : toolOfStructure(record, s);
      const docking = toolId !== undefined && familyOf(toolById(record, toolId, opts.register)) === 'docking';
      // the tool is shown beside the label, so a leading `<tool>/` is dropped from it
      const label = toolId && s.label.startsWith(`${toolId}/`) ? s.label.slice(toolId.length + 1) : s.label;
      return {
        id: s.id,
        label: s.kind === 'crystal' ? crystalLabel(s.label, record.inputs.reference) : label,
        kind: s.kind === 'model' && docking ? 'docking' : s.kind,
        source: nameOf(toolId) ?? s.path ?? s.label,
        load: loadOf(s),
        renders: rendersOf(s),
        structure: s,
        toolId,
        toolName: nameOf(toolId),
      };
    });

  const rank: Record<StructureKind, number> = { crystal: 0, medoid: 1, seed: 2, docking: 3, model: 3 };
  const all = [...fromEnsemble, ...fromStructures].sort((a, b) => rank[a.kind as StructureKind] - rank[b.kind as StructureKind]);
  disambiguate(all);
  // the overlay superposes predictions on the reference: at least one predicted member
  if (all.length >= 2 && all.some((t) => t.kind !== 'crystal')) {
    const members = ensembleMembers(record, all, opts.register);
    all.push({ id: 'overlay', label: 'overlay', kind: 'overlay', source: 'overlay', load: overlayLoads(members), renders: [] });
  }
  return all;
}

// ---------------------------------------------------------------- ensemble members

export interface MemberValue {
  key: string;
  label: string;
  unit?: string;
  value: number;
  kind: ToolOutput['kind'];
  rankingOnly: boolean;
}

export interface EnsembleMember extends StructureTarget {
  kind: StructureKind;
  /** Primary confidence: first output with a value, kinds confidence and plddt first, then interface and score. */
  confidence: MemberValue | null;
  rmsd: number | null;
  /** RMSD to the crystal reference (control poses), when the record has it. */
  rmsdToReference: number | null;
  cluster: number | null;
  /** Pocket (or interface) pLDDT computed by the harness. */
  plddt: number | null;
  pb: { passed: number; total: number | null } | null;
  /** rankingOnly outputs (affinity, docking score): their own muted line, never pose quality. */
  ranking: MemberValue[];
  /** Every output of the member's tool with a value, with units. */
  outputs: MemberValue[];
  /** Worst gate the record attributes to this member; null when the record has none per member. */
  gate: Result | null;
  /** Co-folding model whose B-factor column carries per-residue confidence. */
  perResidueConfidence: boolean;
  /** Overlay colour (CSS hex): crystal ink, medoid accent, then a muted palette from the tokens. */
  color: string;
  /** Family of the producing tool, when known. */
  family: ToolFamily | null;
}

const HEX = { ink: '#1A1A18', accent: '#B07E2C' };
const PALETTE = ['#5B7FA6', '#8B6FB5', '#C9A86A', '#3B8A58', '#C4513B', '#8E6420', '#C28A1A', '#8B8B85'];

function mixWhite(hex: string, t: number): string {
  const n = parseInt(hex.slice(1), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((x) => Math.round(x + (255 - x) * t));
  return `#${c.map((x) => x.toString(16).padStart(2, '0')).join('')}`;
}

/** Member colour: palette entry i, lightened by 25% for every pass through the palette (max 3). */
export function paletteColor(i: number): string {
  return mixWhite(PALETTE[i % PALETTE.length], Math.min(3, Math.floor(i / PALETTE.length)) * 0.25);
}

const CONF_ORDER: ToolOutput['kind'][] = ['confidence', 'plddt', 'interface', 'score'];
const RESULTS: Result[] = ['pass', 'warn', 'stop', 'skip', 'reported', 'pending'];

function memberGate(e: EnsembleEntry | undefined): Result | null {
  if (!e) return null;
  const x = e as EnsembleEntry & { result?: unknown; gate?: unknown; worst?: unknown };
  for (const v of [x.result, x.gate, x.worst]) if (typeof v === 'string' && (RESULTS as string[]).includes(v)) return v as Result;
  return null;
}

/** Ensemble members (structure targets without the overlay) with their numbers from the tools' outputs. */
export function ensembleMembers(record: UiRunRecord, targets: StructureTarget[], register?: Register): EnsembleMember[] {
  const pbTotal = poseBustersTotal(record);
  const metrics = record.stats.metrics ?? [];
  const ref = record.inputs.reference;
  const refCrystal = targets.find((t) => t.kind === 'crystal' && (!ref || t.label === ref)) ?? targets.find((t) => t.kind === 'crystal');
  let k = 0;
  return targets
    .filter((t): t is StructureTarget & { kind: StructureKind } => t.kind !== 'overlay')
    .map((t) => {
      const e = t.entry;
      const tool = t.toolId ? toolById(record, t.toolId, register) : null;
      const outputs: MemberValue[] = [];
      for (const [key, v] of Object.entries(e?.values ?? {})) {
        if (typeof v !== 'number' || !Number.isFinite(v)) continue;
        const o = tool ? outputFor(tool, key) : undefined;
        // an output missing from the register is ranking-only when the record's metric for it is `separate`
        const separate = !!metrics.find((m) => m.key === key && (!m.toolId || m.toolId === t.toolId))?.separate;
        outputs.push({ key, label: o?.label ?? key, unit: o?.unit, value: v, kind: o?.kind ?? 'other', rankingOnly: o ? !!o.rankingOnly : separate });
      }
      const quality = outputs.filter((o) => !o.rankingOnly);
      let confidence: MemberValue | null = null;
      for (const kind of CONF_ORDER) {
        confidence = quality.find((o) => o.kind === kind) ?? null;
        if (confidence) break;
      }
      const family = tool ? familyOf(tool) : null;
      const residueConf = typeof e?.perResidueConfidence === 'boolean' ? e.perResidueConfidence : !!tool?.outputs.some((o) => o.kind === 'plddt' && o.scope === 'residue');
      const color = t === refCrystal ? HEX.ink : t.kind === 'medoid' ? HEX.accent : paletteColor(k++);
      const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
      return {
        ...t,
        confidence,
        rmsd: e ? (e.kind === 'medoid' ? 0 : num(e.rmsdToMedoid)) : null,
        rmsdToReference: num(e?.rmsdToReference),
        cluster: num(e?.cluster),
        plddt: num(e?.pocketPlddt),
        pb: num(e?.posebusters) !== null ? { passed: e!.posebusters as number, total: num(e?.posebustersTotal) ?? pbTotal } : null,
        ranking: outputs.filter((o) => o.rankingOnly),
        outputs,
        gate: memberGate(e),
        perResidueConfidence: (typeof e?.perResidueConfidence === 'boolean' || family === 'co-folding') && residueConf && t.kind !== 'crystal' && t.load.length > 0,
        color,
        family,
      };
    });
}

/**
 * Overlay scene: every member with coordinates in its colour. Docking poses show the ligand only
 * when a crystal receptor is in the scene; co-folding models are superposed on the first structure.
 */
export function overlayLoads(members: EnsembleMember[]): StructureLoad[] {
  const withCoords = members.filter((m) => m.load.length);
  const hasCrystal = withCoords.some((m) => m.kind === 'crystal');
  return withCoords.flatMap((m) => {
    const ligandOnly = hasCrystal && m.kind !== 'crystal' && (m.kind === 'docking' || m.family === 'docking');
    // a separate ligand file (stats.ensemble[].ligand) is lighter than the complex with its polymer hidden
    return (ligandOnly && m.ligandLoad ? [m.ligandLoad] : m.load).map((l) => ({
      ...l,
      id: m.id,
      color: m.color,
      polymer: !ligandOnly,
      align: m.kind !== 'crystal' && m.family === 'co-folding',
      confidence: m.perResidueConfidence,
    }));
  });
}

/** A member whose PoseBusters passes are fewer than the tests in the record. */
export function pbFailed(m: Pick<EnsembleMember, 'pb'>): boolean {
  return !!m.pb && m.pb.total !== null && m.pb.passed < m.pb.total;
}

export type MemberSort = 'record' | 'confidence' | 'rmsd' | 'cluster';

/** Sorted copy; the crystal reference stays first, missing values last. */
export function sortMembers(ms: EnsembleMember[], by: MemberSort): EnsembleMember[] {
  if (by === 'record') return ms.slice();
  const val = (m: EnsembleMember): number | null => (by === 'confidence' ? (m.confidence ? -m.confidence.value : null) : by === 'rmsd' ? m.rmsd : m.cluster);
  return ms
    .map((m, i) => ({ m, i }))
    .sort((a, b) => {
      if (a.m.kind === 'crystal' || b.m.kind === 'crystal') return a.m.kind === 'crystal' ? (b.m.kind === 'crystal' ? a.i - b.i : -1) : 1;
      const va = val(a.m);
      const vb = val(b.m);
      if (va === null || vb === null) return va === null ? (vb === null ? a.i - b.i : 1) : -1;
      if (va !== vb) return va - vb;
      if (by === 'cluster' && a.m.rmsd !== null && b.m.rmsd !== null && a.m.rmsd !== b.m.rmsd) return a.m.rmsd - b.m.rmsd;
      return a.i - b.i;
    })
    .map((x) => x.m);
}

// ---------------------------------------------------------------- flagged residues

export interface FlaggedResidue {
  name: string;
  num: number;
  chain?: string;
  /** Check whose evidence names the residue. */
  check: string;
  result: Result;
}

const AMINO = new Set(['ALA', 'ARG', 'ASN', 'ASP', 'CYS', 'GLN', 'GLU', 'GLY', 'HIS', 'ILE', 'LEU', 'LYS', 'MET', 'PHE', 'PRO', 'SER', 'THR', 'TRP', 'TYR', 'VAL', 'HID', 'HIE', 'HIP', 'ASH', 'GLH', 'LYN', 'CYX', 'MSE', 'SEP', 'TPO', 'PTR']);
const RESIDUE_RE = /\b([A-Za-z]{3})-?(\d{1,4})([A-Z])?\b/g;

/** Residues named in the evidence of warned or stopped checks (`HIS57A`, `Glu286`), deduplicated. */
export function flaggedResidues(record: Pick<UiRunRecord, 'layers'>): FlaggedResidue[] {
  const out: FlaggedResidue[] = [];
  const seen = new Set<string>();
  for (const l of record.layers) {
    for (const c of l.checks) {
      if (c.result !== 'warn' && c.result !== 'stop') continue;
      for (const m of (c.evidence ?? c.message ?? '').matchAll(RESIDUE_RE)) {
        const name = m[1].toUpperCase();
        if (!AMINO.has(name)) continue;
        const r: FlaggedResidue = { name, num: Number(m[2]), chain: m[3], check: c.id, result: c.result };
        const key = `${r.chain ?? ''}:${r.num}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(r);
      }
    }
  }
  return out;
}

/** Chip selected first: medoid, else the first structure with coordinates, else the first chip. */
export function defaultStructureId(targets: StructureTarget[]): string | null {
  if (!targets.length) return null;
  return (targets.find((t) => t.id === 'medoid') ?? targets.find((t) => t.load.length && t.kind !== 'overlay') ?? targets[0]).id;
}

/** Caption above the viewer (prototype structCaption). */
export function structureCaption(record: UiRunRecord, target: StructureTarget | undefined, targets: StructureTarget[]): string {
  if (!target) return '';
  const ref = record.inputs.reference ?? '';
  if (target.kind === 'overlay') {
    // predicted members only (the reference is named first), counting those with coordinates
    const predicted = targets.filter((t) => t.kind !== 'overlay' && t.kind !== 'crystal');
    const n = predicted.filter((t) => t.load.length > 0).length;
    const count = n === predicted.length ? `${n} structures` : `${n} of ${predicted.length} structures with coordinates`;
    return `${ref ? `${ref} + ` : ''}predicted · ${count}`;
  }
  if (target.structure) {
    const s = target.structure;
    return [s.label, s.kind, s.sha256 ? `sha256 ${s.sha256.slice(0, 12)}` : null].filter(Boolean).join(' · ');
  }
  if (target.kind === 'crystal') return `RCSB ${target.label} · experimental`;
  if (target.entry) {
    const e = target.entry;
    const name = e.label.startsWith(e.source) ? e.label : `${e.source} ${e.label}`;
    return `${name} · RMSD to medoid ${fmtNum(e.rmsdToMedoid, 'Å', 1)}`;
  }
  return target.label;
}

// ---------------------------------------------------------------- ensemble columns

export interface ScoreKey {
  toolId: string;
  toolName: string;
  key: string;
  label: string;
  unit?: string;
}

export interface ScoreColumn {
  /** Short header (first word of long labels), full labels in `title`. */
  header: string;
  title: string;
  keys: ScoreKey[];
}

/**
 * The overlay legend's value with its metric named: `ipTM 0.9`, `CNN score 0.79`, `RMSD 0.9 Å`
 * (to the medoid, crystal reference); an en dash when the member has neither.
 */
export function memberValueText(m: Pick<EnsembleMember, 'confidence' | 'rmsd' | 'kind'>): string {
  if (m.confidence) return `${shortLabel(m.confidence.label)} ${fmtNum(m.confidence.value, m.confidence.unit)}`;
  if (m.rmsd !== null && m.kind !== 'medoid') return `RMSD ${fmtNum(m.rmsd, 'Å', 1)}`;
  return DASH;
}

function shortLabel(label: string): string {
  return label.length > 10 && label.includes(' ') ? label.split(' ')[0] : label;
}

/**
 * The tool-output column of the ensemble table: one key per tool whose output values appear in
 * stats.ensemble[].values (in record tool order). The prototype shows them merged in one column,
 * since each structure comes from one tool. null when no entry carries tool values.
 */
export function ensembleScoreColumn(record: UiRunRecord, register?: Register): ScoreColumn | null {
  const ensemble = record.stats.ensemble ?? [];
  const metrics = record.stats.metrics ?? [];
  const keys: ScoreKey[] = [];
  const tools = recordTools(record, register);
  const ids = [...tools.map((t) => t.id), ...ensemble.map((e) => e.toolId).filter((x): x is string => !!x)];
  for (const id of Array.from(new Set(ids))) {
    const tool = toolById(record, id, register);
    const seen = new Set<string>();
    const found: (ScoreKey & { rank: number })[] = [];
    for (const e of ensemble) {
      if (e.toolId !== id || !e.values) continue;
      for (const k of Object.keys(e.values)) {
        if (seen.has(k)) continue;
        seen.add(k);
        const o = outputFor(tool, k);
        // pose quality only: ranking-only scores and RMSDs relative to the tool's own best mode stay out
        const ranking = o ? !!o.rankingOnly : !!metrics.find((m) => m.key === k)?.separate;
        const rank = o ? CONF_ORDER.indexOf(o.kind) : -1;
        if (ranking || rank < 0) continue;
        found.push({ toolId: id, toolName: tool.name, key: k, label: o?.label ?? k, unit: o?.unit, rank });
      }
    }
    // one key per tool: the most confidence-like output
    found.sort((a, b) => a.rank - b.rank);
    if (found[0]) keys.push({ toolId: found[0].toolId, toolName: found[0].toolName, key: found[0].key, label: found[0].label, unit: found[0].unit });
  }
  if (!keys.length) return null;
  const labels = Array.from(new Set(keys.map((k) => k.label)));
  return {
    header: labels.map(shortLabel).join('/'),
    title: keys.map((k) => `${k.toolName}: ${k.label}${k.unit ? ` (${k.unit})` : ''}`).join(' · '),
    keys,
  };
}

/** Value of the score column for one entry (first key of its tool that has a value). */
export function ensembleScore(entry: EnsembleEntry, col: ScoreColumn | null): number | null {
  if (!col || !entry.values) return null;
  for (const k of col.keys) {
    if (k.toolId !== entry.toolId) continue;
    const v = entry.values[k.key];
    if (typeof v === 'number' && Number.isFinite(v)) return v;
  }
  return null;
}

// ---------------------------------------------------------------- member columns

export interface MemberColumn {
  id: string;
  header: string;
  title: string;
  /** Ranking-only scores: muted, never styled as pose quality. */
  ranking: boolean;
  /** Numeric value of a member, or null. */
  value: (m: EnsembleMember) => number | null;
  /** Display text of a value. */
  text: (m: EnsembleMember) => string;
  /** Values above the display reference are shown in warn (RMSD to the medoid). */
  warn?: (m: EnsembleMember) => boolean;
}

const MAX_MEMBER_COLUMNS = 5;

/**
 * Table and cell columns built from the fields and tool outputs present in at least one member:
 * RMSD to the medoid, pocket pLDDT, the quality output (one key per tool, merged as in the
 * prototype), the ranking-only output (merged the same way), PoseBusters, then other outputs, up
 * to five numeric columns.
 */
export function memberColumns(members: EnsembleMember[]): MemberColumn[] {
  const fmt = (v: number | null, unit?: string, digits?: number) => (v === null ? DASH : fmtNum(v, unit, digits));
  const cols: MemberColumn[] = [];
  if (members.some((m) => m.kind !== 'medoid' && m.kind !== 'crystal' && m.rmsd !== null) || members.some((m) => m.kind === 'crystal' && m.rmsd !== null)) {
    cols.push({
      id: 'rmsd',
      header: 'RMSD',
      title: 'RMSD to the medoid (Å)',
      ranking: false,
      value: (m) => (m.kind === 'medoid' ? null : m.rmsd),
      text: (m) => (m.kind === 'medoid' ? DASH : fmt(m.rmsd, undefined, 1)),
      warn: (m) => m.kind !== 'medoid' && m.rmsd !== null && m.rmsd > SEED_RMSD_CUT,
    });
  }
  // members outside the clustered set (redocking controls) have no RMSD to the medoid, only to the reference
  if (members.some((m) => m.kind !== 'crystal' && m.rmsdToReference !== null)) {
    cols.push({
      id: 'ref',
      header: 'to ref.',
      title: 'RMSD to the crystal reference (Å)',
      ranking: false,
      value: (m) => (m.kind === 'crystal' ? null : m.rmsdToReference),
      text: (m) => (m.kind === 'crystal' ? DASH : fmt(m.rmsdToReference, undefined, 1)),
    });
  }
  if (members.some((m) => m.plddt !== null)) {
    cols.push({ id: 'plddt', header: 'pLDDT', title: 'pocket pLDDT', ranking: false, value: (m) => m.plddt, text: (m) => fmt(m.plddt) });
  }
  // one key per tool and role, in tool order of first appearance
  const pick = (pred: (o: MemberValue) => boolean, order: (o: MemberValue) => number) => {
    const byTool = new Map<string, MemberValue>();
    for (const m of members) {
      if (!m.toolId) continue;
      const cands = m.outputs.filter(pred).sort((a, b) => order(a) - order(b));
      if (cands[0] && !byTool.has(m.toolId)) byTool.set(m.toolId, cands[0]);
    }
    return byTool;
  };
  const merged = (id: string, byTool: Map<string, MemberValue>, ranking: boolean): MemberColumn | null => {
    if (!byTool.size) return null;
    const labels = Array.from(new Set(Array.from(byTool.values()).map((o) => o.label)));
    const get = (m: EnsembleMember) => {
      const o = m.toolId ? byTool.get(m.toolId) : undefined;
      return o ? (m.outputs.find((x) => x.key === o.key) ?? null) : null;
    };
    return {
      id,
      header: labels.map(shortLabel).join('/'),
      title: `${Array.from(byTool.entries())
        .map(([tool, o]) => `${members.find((m) => m.toolId === tool)?.toolName ?? tool}: ${o.label}${o.unit ? ` (${o.unit})` : ''}`)
        .join(' · ')}${ranking ? ' · ranking only' : ''}`,
      ranking,
      value: (m) => get(m)?.value ?? null,
      text: (m) => {
        const o = get(m);
        return o ? fmtNum(o.value) : DASH;
      },
    };
  };
  const quality = pick((o) => !o.rankingOnly && CONF_ORDER.includes(o.kind), (o) => CONF_ORDER.indexOf(o.kind));
  const ranking = pick((o) => o.rankingOnly, () => 0);
  const q = merged('quality', quality, false);
  if (q) cols.push(q);
  const r = merged('ranking', ranking, true);
  if (members.some((m) => m.pb !== null)) {
    cols.push({
      id: 'pb',
      header: 'PB',
      title: 'PoseBusters tests passed',
      ranking: false,
      value: (m) => m.pb?.passed ?? null,
      text: (m) => (m.pb ? (m.pb.total ? `${m.pb.passed}/${m.pb.total}` : String(m.pb.passed)) : DASH),
    });
  }
  // remaining outputs (e.g. RMSD bounds relative to the tool's best mode)
  const used = new Set([...Array.from(quality.values()), ...Array.from(ranking.values())].map((o) => o.key));
  const others: MemberValue[] = [];
  for (const m of members) for (const o of m.outputs) if (!used.has(o.key) && !others.some((x) => x.key === o.key)) others.push(o);
  const room = MAX_MEMBER_COLUMNS - (r ? 1 : 0);
  for (const o of others) {
    if (cols.length >= room) break;
    const header = shortLabel(o.label);
    cols.push({
      id: `out:${o.key}`,
      // a short header that repeats another column's falls back to the output key
      header: cols.some((c) => c.header === header) || others.some((x) => x !== o && shortLabel(x.label) === header) ? o.key : header,
      title: `${o.label}${o.unit ? ` (${o.unit})` : ''}`,
      ranking: false,
      value: (m) => m.outputs.find((x) => x.key === o.key)?.value ?? null,
      text: (m) => {
        const v = m.outputs.find((x) => x.key === o.key)?.value;
        return v === undefined ? DASH : fmtNum(v, o.unit);
      },
    });
  }
  // ranking-only scores last, on the right
  if (r) cols.push(r);
  return cols.slice(0, MAX_MEMBER_COLUMNS);
}

/** Members shown as report chips when the ensemble is large. */
export const REPORT_CHIP_LIMIT = 10;

/**
 * Report chip row: every member when there are at most REPORT_CHIP_LIMIT (prototype); otherwise
 * the crystal, the medoid, one representative per other cluster, then members with numbers by
 * confidence (else RMSD to the medoid), up to five representatives. The rest is reached through
 * the ensemble page.
 */
export function reportChipMembers(members: EnsembleMember[]): EnsembleMember[] {
  if (members.length <= REPORT_CHIP_LIMIT) return members;
  const out: EnsembleMember[] = members.filter((m) => m.kind === 'crystal' || m.kind === 'medoid');
  const medoid = members.find((m) => m.kind === 'medoid');
  const rank = (a: EnsembleMember, b: EnsembleMember) => {
    if (a.confidence && b.confidence) return b.confidence.value - a.confidence.value;
    if (a.confidence || b.confidence) return a.confidence ? -1 : 1;
    if (a.rmsd !== null && b.rmsd !== null) return a.rmsd - b.rmsd;
    return a.rmsd !== null ? -1 : b.rmsd !== null ? 1 : 0;
  };
  const rest = members.filter((m) => !out.includes(m));
  const reps: EnsembleMember[] = [];
  const clusters = Array.from(new Set(rest.map((m) => m.cluster).filter((c): c is number => c !== null && c !== medoid?.cluster)));
  for (const c of clusters) {
    const best = rest.filter((m) => m.cluster === c).sort(rank)[0];
    if (best && reps.length < 5) reps.push(best);
  }
  const numbered = rest.filter((m) => !reps.includes(m) && (m.confidence !== null || m.rmsd !== null || m.outputs.length > 0)).sort(rank);
  for (const m of numbered) if (reps.length < 5) reps.push(m);
  const order = new Map(members.map((m, i) => [m.id, i]));
  return [...out, ...reps.sort((a, b) => (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0))];
}

/** Number of PoseBusters tests in the record (denominator of `n/N`), or null. */
export function poseBustersTotal(record: UiRunRecord): number | null {
  const n = record.stats.posebusters?.length;
  return n ? n : null;
}

export function fmtPoseBusters(n: number | null | undefined, total: number | null): string {
  if (isMissing(n)) return DASH;
  return total ? `${n}/${total}` : String(n);
}

/** RMSD to the medoid; the medoid itself shows an en dash. */
export function rmsdCell(e: EnsembleEntry): { text: string; warn: boolean } {
  if (e.kind === 'medoid') return { text: DASH, warn: false };
  return { text: fmtNum(e.rmsdToMedoid, undefined, 1), warn: e.rmsdToMedoid > SEED_RMSD_CUT };
}

/** "4/5 seeds": structures in the medoid's cluster among the predicted ones. */
export function medoidClusterPopulation(record: UiRunRecord): string | null {
  const ens = record.stats.ensemble;
  if (!ens) return null;
  const medoid = ens.find((e) => e.kind === 'medoid');
  const seeds = ens.filter((e) => e.kind === 'medoid' || e.kind === 'seed');
  if (!medoid || medoid.cluster === null || !seeds.length) return null;
  const n = seeds.filter((e) => e.cluster === medoid.cluster).length;
  return `${n}/${seeds.length} seeds`;
}

/** `0.8 Å · IQR 0.8–0.9` (prototype pairwise line), or null when not computed. */
export function pairwiseLine(record: UiRunRecord): string | null {
  const p = record.stats.pairwise;
  if (!p) return null;
  const d = Math.abs(p.median) < 0.1 ? 3 : 1;
  const med = fmtNum(p.median, 'Å', d);
  return p.iqr ? `${med} · IQR ${fmtNum(p.iqr[0], undefined, d)}–${fmtNum(p.iqr[1], undefined, d)}` : med;
}

// ---------------------------------------------------------------- summary statistics

export interface Describe {
  n: number;
  median: number;
  mean: number;
  /** Sample standard deviation (n − 1), 0 for a single value. */
  sd: number;
  min: number;
  max: number;
  /** Quartiles by linear interpolation (IQR = q1–q3). */
  q1: number;
  q3: number;
}

function quantile(sorted: number[], p: number): number {
  const pos = (sorted.length - 1) * p;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

export function describe(values: (number | null | undefined)[]): Describe | null {
  const a = values.filter((x): x is number => typeof x === 'number' && Number.isFinite(x)).sort((x, y) => x - y);
  if (!a.length) return null;
  const n = a.length;
  const mean = a.reduce((s, x) => s + x, 0) / n;
  const median = quantile(a, 0.5);
  const sd = Math.sqrt(a.reduce((s, x) => s + (x - mean) ** 2, 0) / Math.max(1, n - 1));
  return { n, median, mean, sd, min: a[0], max: a[n - 1], q1: quantile(a, 0.25), q3: quantile(a, 0.75) };
}

export interface StripPoint {
  x: number;
  fill: string;
}

export interface SummaryRow {
  id: string;
  name: string;
  unit?: string;
  /** Tool display name when the row is a tool output. */
  tool?: string;
  stats: Describe;
  points: StripPoint[];
  medianX: number;
  /** Position of the medoid's value, when the medoid has one. */
  medoidX?: number;
  medoidValue?: number;
  /** Every value of the row is an integer (counts): shown without fixed decimals. */
  integer: boolean;
}

/** Strip plot positions on a 200-wide axis with 4 px padding (prototype metricRow). */
export function stripPositions(values: (number | null | undefined)[], fills: string[], st: Describe): { points: StripPoint[]; medianX: number } {
  const span = st.max - st.min || 1;
  const pos = (v: number) => +(4 + ((v - st.min) / span) * 192).toFixed(2);
  const points: StripPoint[] = [];
  values.forEach((v, i) => {
    if (typeof v === 'number' && Number.isFinite(v)) points.push({ x: pos(v), fill: fills[i] ?? 'var(--color-muted)' });
  });
  return { points, medianX: pos(st.median) };
}

function summaryRow(
  id: string,
  name: string,
  values: (number | null | undefined)[],
  fills: string[],
  extra: { unit?: string; tool?: string; medoid?: number | null } = {},
): SummaryRow | null {
  const st = describe(values);
  if (!st) return null;
  const { medoid, ...rest } = extra;
  const integer = values.every((v) => typeof v !== 'number' || !Number.isFinite(v) || Number.isInteger(v));
  const row: SummaryRow = { id, name, ...rest, stats: st, ...stripPositions(values, fills, st), integer };
  if (typeof medoid === 'number' && Number.isFinite(medoid)) {
    row.medoidValue = medoid;
    row.medoidX = stripPositions([medoid], ['x'], st).points[0]?.x;
  }
  return row;
}

/**
 * Summary statistics of the ensemble page: RMSD to medoid, pocket pLDDT, the co-folding tools'
 * outputs, PoseBusters passed, the other tools' outputs, then per-seed physics. Rows with no
 * values are left out; an empty list means not computed.
 */
export function summaryRows(record: UiRunRecord, register?: Register): SummaryRow[] {
  const S = record.stats;
  const ens = S.ensemble ?? [];
  const fills = ens.map((e) => KIND_COLOR[e.kind]);
  const lig = hasLigand(record);
  const rows: (SummaryRow | null)[] = [];
  // predicted members only: the crystal reference's RMSD to the medoid is not part of the pose distribution
  const nonMedoid = ens.filter((e) => e.kind !== 'medoid' && e.kind !== 'crystal');
  rows.push(summaryRow('rmsd', 'RMSD to medoid', nonMedoid.map((e) => e.rmsdToMedoid), nonMedoid.map((e) => KIND_COLOR[e.kind]), { unit: 'Å' }));
  const medoid = ens.find((e) => e.kind === 'medoid');
  rows.push(summaryRow('plddt', lig ? 'Pocket pLDDT' : 'Interface pLDDT', ens.map((e) => e.pocketPlddt), fills, { medoid: medoid?.pocketPlddt }));
  const col = ensembleScoreColumn(record, register);
  const outputRow = (k: ScoreKey) =>
    summaryRow(
      `${k.toolId}:${k.key}`,
      k.label,
      ens.map((e) => (e.toolId === k.toolId ? (e.values?.[k.key] ?? null) : null)),
      fills,
      { unit: k.unit, tool: k.toolName, medoid: medoid?.toolId === k.toolId ? (medoid.values?.[k.key] ?? null) : null },
    );
  const keys = col?.keys ?? [];
  const isCofold = (k: ScoreKey) => familyOf(toolById(record, k.toolId, register)) === 'co-folding';
  keys.filter(isCofold).forEach((k) => rows.push(outputRow(k)));
  const pbTotal = poseBustersTotal(record);
  rows.push(summaryRow('posebusters', 'PoseBusters passed', ens.map((e) => e.posebusters), fills, { unit: pbTotal ? `/${pbTotal}` : undefined, medoid: medoid?.posebusters }));
  keys.filter((k) => !isCofold(k)).forEach((k) => rows.push(outputRow(k)));
  const phys = S.physics ?? [];
  const seedFills = phys.map(() => KIND_COLOR.seed);
  const mp = medoid ? (phys.find((p) => !!p.pose && p.pose === medoid.pose) ?? phys.find((p) => medoid.label === `s${p.seed}` || medoid.id === `seed_${p.seed}`)) : undefined;
  rows.push(summaryRow('drift', 'Minimisation drift', phys.map((p) => p.drift), seedFills, { unit: 'Å', medoid: mp?.drift }));
  rows.push(summaryRow('strain', 'Torsion strain', phys.map((p) => p.strain), seedFills, { unit: 'kcal/mol', medoid: mp?.strain }));
  rows.push(summaryRow('clashscore', 'Clashscore', phys.map((p) => p.clashscore), seedFills, { medoid: mp?.clashscore }));
  return rows.filter((r): r is SummaryRow => r !== null);
}

// ---------------------------------------------------------------- per-seed physics

export interface PhysicsColumn {
  key: keyof PhysicsRow;
  label: string;
  /** Number rule of the column (lib/format.ts QUANTITY_RULES). */
  quantity: Quantity;
  /** Unit shown muted in the header. */
  unit?: string;
}

/** Per-seed columns of the prototype, keeping those at least one row carries. */
export function physicsColumns(record: UiRunRecord): PhysicsColumn[] {
  const rows = record.stats.physics ?? [];
  const present = (c: PhysicsColumn) => !rows.length || rows.some((p) => typeof p[c.key] === 'number');
  return prototypePhysicsColumns(record).filter(present);
}

function prototypePhysicsColumns(record: UiRunRecord): PhysicsColumn[] {
  const drift: PhysicsColumn = { key: 'drift', label: 'drift', quantity: 'rmsd', unit: 'Å' };
  const clashes: PhysicsColumn = { key: 'clashes', label: 'clashes', quantity: 'count' };
  const strain: PhysicsColumn = { key: 'strain', label: 'strain', quantity: 'energy' };
  const unsat: PhysicsColumn = { key: 'unsatisfied', label: 'unsat.', quantity: 'count' };
  const clashscore: PhysicsColumn = { key: 'clashscore', label: 'clashscore', quantity: 'plddt' };
  return hasLigand(record)
    ? [drift, { key: 'torsions', label: 'torsions', quantity: 'count' }, clashes, strain, unsat, { key: 'pbPassed', label: 'PB', quantity: 'count' }, clashscore]
    : [drift, clashes, strain, unsat, clashscore, { key: 'rama', label: 'rama', quantity: 'count' }];
}

/** Value of a per-seed cell with its column's decimals (no unit: the header carries it). */
export function fmtPhysics(v: number | null | undefined, quantity?: Quantity): string {
  if (isMissing(v)) return DASH;
  if (quantity) return fmtQuantityParts(v, quantity).value;
  return Number.isInteger(v) ? fmtNum(v) : fmtNum(v, undefined, Math.abs(v) < 10 ? 2 : 1);
}

export interface PhysicsTable {
  columns: PhysicsColumn[];
  /** `key` is the pose id (or the row index): seeds repeat when a seed has several samples. */
  rows: { key: string; seed: string; flagged: boolean; cells: string[] }[];
  median: string[];
}

/** Per-seed statistics with a median row; null when stats.physics is absent or empty. */
export function physicsTable(record: UiRunRecord): PhysicsTable | null {
  const phys = record.stats.physics;
  if (!phys || !phys.length) return null;
  const columns = physicsColumns(record);
  const lig = hasLigand(record);
  const pbTotal = poseBustersTotal(record);
  const num = (p: PhysicsRow, k: keyof PhysicsRow) => (typeof p[k] === 'number' ? (p[k] as number) : null);
  return {
    columns,
    rows: phys.map((p, i) => {
      const total = (p as PhysicsRow & { pbTotal?: number }).pbTotal ?? pbTotal;
      return {
        key: p.pose ?? `row-${i}`,
        seed: poseLabel(p),
        flagged: lig ? typeof p.pbPassed === 'number' && typeof total === 'number' && p.pbPassed < total : typeof p.drift === 'number' && p.drift > DRIFT_FLAG_A,
        cells: columns.map((c) => fmtPhysics(num(p, c.key), c.quantity)),
      };
    }),
    median: columns.map((c) => {
      const st = describe(phys.map((p) => num(p, c.key)));
      // a median of counts can fall between two integers: keep one decimal then
      return st ? (c.quantity === 'count' && !Number.isInteger(st.median) ? fmtNum(st.median, undefined, 1) : fmtPhysics(st.median, c.quantity)) : DASH;
    }),
  };
}

// ---------------------------------------------------------------- figure geometry

/** Prototype display references (seed spread cut line, physics row flag). Not verdict thresholds. */
export const SEED_RMSD_CUT = 2;
export const DRIFT_FLAG_A = 2;
const SEED_X_MAX = 8;

export interface SeedAxis {
  /** `confidence` (0.5..1, prototype) or the seed's tool `score` (data range). */
  field: 'confidence' | 'score';
  key?: string;
  min: number;
  max: number;
}

/** y axis of the seed spread: confidence when the seeds carry it, else their tool score. */
export function seedAxis(record: UiRunRecord): SeedAxis | null {
  const seeds = record.stats.seeds ?? [];
  if (seeds.some((s) => typeof s.confidence === 'number')) return { field: 'confidence', min: 0.5, max: 1 };
  const scores = seeds.map((s) => s.score).filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
  if (!scores.length) return null;
  let min = Math.min(...scores);
  let max = Math.max(...scores);
  if (max - min < 1e-9) {
    min -= 0.5;
    max += 0.5;
  }
  const pad = (max - min) * 0.1;
  return { field: 'score', key: seeds.find((s) => s.scoreKey)?.scoreKey, min: min - pad, max: max + pad };
}

/** Seed spread: RMSD to medoid (x, 0..8 Å) against the seed axis (y), viewBox 360×170. */
/**
 * Row label of a per-pose row: `s<seed>`, `s<seed>.<sample>` when a seed has several samples,
 * the pose id when the seed is missing.
 */
export function poseLabel(row: { seed?: number; sample?: number; pose?: string }): string {
  if (typeof row.seed !== 'number') return row.pose ?? DASH;
  return typeof row.sample === 'number' && row.sample > 0 ? `s${row.seed}.${row.sample}` : `s${row.seed}`;
}

/**
 * True when stats.pairwise holds pairwise RMSD between poses (live: l5.sampling.clusters, n is a
 * pair count); the mock block summarises RMSD to the medoid over n seeds.
 */
export function pairwiseIsPairs(record: UiRunRecord): boolean {
  const p = record.stats.pairwise;
  if (!p) return false;
  const field = record.stats.provenance?.pairwise?.field ?? '';
  return typeof p.poses === 'number' || /pairwise/.test(String(field));
}

/** Seed-spread point labels drawn as text: points with an earlier point within 26×12 units keep only the tooltip. */
const LABEL_DX = 26;
const LABEL_DY = 12;

export function seedSpreadPoints(record: UiRunRecord) {
  const seeds = record.stats.seeds ?? [];
  const axis = seedAxis(record);
  const x = (v: number) => +(40 + (Math.min(SEED_X_MAX, Math.max(0, v)) / SEED_X_MAX) * 310).toFixed(2);
  const y = (c: number) => (axis ? +(128 - ((c - axis.min) / (axis.max - axis.min)) * 108).toFixed(2) : 128);
  const p = record.stats.pairwise;
  const placed = seeds
    .filter((s) => typeof s.rmsdToMedoid === 'number')
    .map((s, i) => {
      const v = axis?.field === 'score' ? s.score : s.confidence;
      return {
        key: s.pose ?? `seed-${i}`,
        cx: x(s.rmsdToMedoid),
        cy: typeof v === 'number' && Number.isFinite(v) ? y(v) : 128,
        fill: s.rmsdToMedoid < SEED_RMSD_CUT ? 'var(--color-pass)' : 'var(--color-warn)',
        label: poseLabel(s),
      };
    });
  const points = placed.map((pt, i) => ({ ...pt, showLabel: !placed.slice(0, i).some((q) => Math.abs(q.cx - pt.cx) < LABEL_DX && Math.abs(q.cy - pt.cy) < LABEL_DY) }));
  return {
    axis,
    points,
    cutX: x(SEED_RMSD_CUT),
    // the bootstrap CI of the median when the record has it, otherwise the IQR; never invented
    band: p?.ci95
      ? { kind: 'ci95' as const, x: x(p.ci95[0]), w: Math.max(2, +(x(p.ci95[1]) - x(p.ci95[0])).toFixed(2)) }
      : p?.iqr
        ? { kind: 'iqr' as const, x: x(p.iqr[0]), w: Math.max(2, +(x(p.iqr[1]) - x(p.iqr[0])).toFixed(2)) }
        : null,
  };
}

/** Calibration polylines, viewBox 320×170 (x: confidence 0.5..1, y: failure rate 0..1). */
export function calibrationPolylines(record: UiRunRecord): { passed: string; flagged: string } | null {
  const c = record.stats.calibration;
  if (!c || !c.length) return null;
  const pts = (key: 'passed' | 'flagged') => c.map((p) => `${+(40 + ((p.x - 0.5) / 0.5) * 270).toFixed(2)},${+(130 - p[key] * 115).toFixed(2)}`).join(' ');
  return { passed: pts('passed'), flagged: pts('flagged') };
}

export function rocPolyline(record: UiRunRecord): string | null {
  const roc = record.stats.roc;
  if (!roc || !roc.length) return null;
  return roc.map((p) => `${+(40 + p.fpr * 270).toFixed(2)},${+(130 - p.tpr * 120).toFixed(2)}`).join(' ');
}

/** Interaction nodes on a circle around the ligand, viewBox 360×300 (prototype `inter`). */
/**
 * `2/3 also in the reference complex` for live records (stats.interactions[].known is read from
 * the declared reference complex), `7/9 seen in known complexes` for mock records.
 */
export function interactionKnownText(record: UiRunRecord): string | null {
  const it = record.stats.interactions;
  if (!it) return null;
  const known = it.filter((i) => i.known).length;
  const live = !!record.stats.provenance?.['interactions.known'];
  return `${known}/${it.length} ${live ? 'also in the reference complex' : 'seen in known complexes'}`;
}

/** `pose vina/seed0/mode0` when the record names the fingerprinted pose, else `the medoid pose`. */
export function interactionPoseText(record: UiRunRecord): string {
  const pose = record.stats.interactionsPose;
  return typeof pose === 'string' && pose ? `pose ${pose}` : 'the medoid pose';
}

export function interactionNodes(record: UiRunRecord) {
  const list = record.stats.interactions ?? [];
  const R = 112;
  return list.map((it, i) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / list.length;
    return {
      ...it,
      ...interactionStyle(it.type),
      x: +(180 + R * Math.cos(a)).toFixed(1),
      y: +(150 + R * Math.sin(a)).toFixed(1),
      lx: +(180 + (R + 30) * Math.cos(a)).toFixed(1),
      ly: +(150 + (R + 30) * Math.sin(a) + 3).toFixed(1),
    };
  });
}

/** Centre label of the interaction diagram: the ligand's CCD code, or the partner. */
export function ligandLabel(record: UiRunRecord): string {
  if (hasLigand(record)) {
    const ccd = record.sources.find((s) => /ccd/i.test(s.source) || s.sourceId === 'ccd' || s.sourceId === 'pdb_ccd');
    return ccd?.accession ?? 'ligand';
  }
  return record.inputs.partner ?? 'partner';
}

/** Agreement cell colours: tint by value on an 8 Å scale; the diagonal (0) is neutral. */
export function agreementCellStyle(value: number): { bg: string; color: string; text: string } {
  if (value === 0) return { bg: 'var(--color-canvas)', color: 'var(--color-faint)', text: DASH };
  const t = Math.min(1, value / 8);
  if (t < 0.25) return { bg: RESULT_TINT.pass, color: 'var(--color-pass)', text: fmtNum(value, undefined, 1) };
  if (t < 0.6) return { bg: RESULT_TINT.warn, color: 'var(--color-accent-deep)', text: fmtNum(value, undefined, 1) };
  return { bg: RESULT_TINT.stop, color: 'var(--color-stop)', text: fmtNum(value, undefined, 1) };
}

/** Display name of an agreement method: the record tool's name when the method is a tool id. */
export function methodName(record: UiRunRecord, method: string, register?: Register): string {
  const inRecord = record.tools.some((t) => t.id === method) || register?.some((t) => t.id === method);
  return inRecord ? toolById(record, method, register).name : method;
}

/**
 * y-axis label of the seed spread: the seeds' confidenceKey or scoreKey through the tool's output
 * label (with unit; a ranking-only score says so), else the first co-folding confidence output.
 */
export function seedAxisLabel(record: UiRunRecord, register?: Register): string {
  const axis = seedAxis(record);
  const seeds = record.stats.seeds ?? [];
  const toolId = seeds.find((s) => s.toolId)?.toolId;
  const tool = toolId ? toolById(record, toolId, register) : null;
  if (axis?.field === 'confidence') {
    const key = seeds.find((s) => s.confidenceKey)?.confidenceKey;
    return key && tool ? labelFor(tool, key) : seedConfidenceLabel(record, register);
  }
  if (axis?.field === 'score') {
    const o = tool && axis.key ? outputFor(tool, axis.key) : undefined;
    const label = tool && axis.key ? labelFor(tool, axis.key) : (axis.key ?? 'score');
    const ranking = o ? !!o.rankingOnly : !!record.stats.metrics?.find((m) => m.key === axis.key)?.separate;
    return `${label}${o?.unit ? ` (${o.unit})` : ''}${ranking ? ', ranking only' : ''}`;
  }
  return seedConfidenceLabel(record, register);
}

/** Axis label for seed confidence: the first co-folding tool's interface (or confidence) output. */
export function seedConfidenceLabel(record: UiRunRecord, register?: Register): string {
  const tools = recordTools(record, register).filter((t) => familyOf(t) === 'co-folding');
  for (const kind of ['interface', 'confidence'] as const) {
    for (const t of tools) {
      const o = t.outputs.find((x) => x.kind === kind && x.scope !== 'residue');
      if (o) return o.label;
    }
  }
  return 'confidence';
}

/** The ranking-only output the ROC figure reads: first co-folding rankingOnly affinity output. */
export function rankingOutputName(record: UiRunRecord, register?: Register): string | null {
  for (const t of recordTools(record, register)) {
    const o = t.outputs.find((x) => x.rankingOnly && x.kind === 'affinity');
    if (o) return o.label.startsWith(t.name) ? o.label : `${t.name} ${o.label.toLowerCase()}`;
  }
  return null;
}

// ---------------------------------------------------------------- metrics

export interface MetricRow {
  id: string;
  name: string;
  tool?: string;
  value: string | null;
  unit?: string;
  read?: string;
  rankingOnly: boolean;
  /** Check that produced the value (live records). */
  check?: string;
}

export interface MetricRows {
  /** True when stats.metrics was present (values computed). */
  computed: boolean;
  rows: MetricRow[];
  ranking: MetricRow[];
}

function rankingOf(m: UiMetric, tools: ResolvedTool[]): boolean {
  if (m.toolId && m.key) {
    const t = tools.find((x) => x.id === m.toolId);
    const o = t ? outputFor(t, m.key) : undefined;
    if (o) return !!o.rankingOnly;
  }
  return !!m.separate;
}

/**
 * Confidence and interface metrics. With stats.metrics: its rows, ranking-only ones (from the
 * tool output's `rankingOnly`, else `separate`) moved below the accent rule. Without: the outputs
 * of the record's tools with no values, so the rows still come from the tools.
 */
export function metricRows(record: UiRunRecord, register?: Register): MetricRows {
  const tools = recordTools(record, register);
  const metrics = record.stats.metrics;
  if (metrics) {
    const all = metrics.map((m, i): MetricRow => {
      const tool = m.toolId ? tools.find((t) => t.id === m.toolId) : undefined;
      const label = m.key && tool ? outputFor(tool, m.key)?.label : undefined;
      return { id: `${i}:${m.name}`, name: label && m.name === m.key ? label : m.name, tool: tool?.name ?? m.tool, value: m.value, read: m.read ?? m.note, rankingOnly: rankingOf(m, tools), check: m.check };
    });
    return { computed: true, rows: all.filter((r) => !r.rankingOnly), ranking: all.filter((r) => r.rankingOnly) };
  }
  const rows: MetricRow[] = [];
  const ranking: MetricRow[] = [];
  for (const t of tools) {
    for (const o of t.outputs) {
      if (o.scope === 'residue') continue;
      const row: MetricRow = { id: `${t.id}:${o.key}`, name: o.label, tool: t.name, value: null, unit: o.unit, read: o.note, rankingOnly: !!o.rankingOnly };
      (row.rankingOnly ? ranking : rows).push(row);
    }
  }
  return { computed: false, rows, ranking };
}

// ---------------------------------------------------------------- stat cards

export interface StatCard {
  id: 'site' | 'pose' | 'docking' | 'sampling';
  title: string;
  rows: [string, string][];
  /** False when the block is absent from the record (shown as "not computed"). */
  computed: boolean;
}

/**
 * Site, pose, and docking (record.docking, or the record's docking tool from the register) or
 * sampling cards. Absent blocks come back with computed=false and no rows.
 */
export function statCards(record: UiRunRecord, register?: Register): StatCard[] {
  const S = record.stats;
  const lig = hasLigand(record);
  const cards: StatCard[] = [
    { id: 'site', title: lig ? 'Binding site' : 'Interface', rows: S.site ?? [], computed: !!S.site },
    { id: 'pose', title: lig ? 'Pose' : 'Complex', rows: S.pose ?? [], computed: !!S.pose },
  ];
  if (record.docking) {
    cards.push({ id: 'docking', title: `Docking · ${record.docking.tool}`, rows: record.docking.rows, computed: true });
    return cards;
  }
  const dock = recordTools(record, register).find((t) => familyOf(t) === 'docking');
  if (dock) {
    cards.push({ id: 'docking', title: `Docking · ${dock.name}`, rows: (dock.dockingParams ?? []).map((p) => [p.label, DASH] as [string, string]), computed: false });
    return cards;
  }
  const sampling: [string, string][] = [];
  if (S.sitePlacement) sampling.push(['site placement', S.sitePlacement]);
  if (S.poseAccuracy) sampling.push(['pose accuracy', S.poseAccuracy]);
  if (S.pairwise) sampling.push(['pairwise RMSD', `${fmtNum(S.pairwise.median, 'Å', 1)} median`]);
  cards.push({ id: 'sampling', title: 'Sampling', rows: sampling, computed: sampling.length > 0 });
  return cards;
}

// ---------------------------------------------------------------- threshold rows

/** Threshold evidence level colour: borrowed/suspected/uncalibrated in accent-deep, else pass. */
export function thresholdLevelColor(level: string): string {
  return /borrowed|suspected|uncalibrated/i.test(level) ? 'var(--color-accent-deep)' : 'var(--color-pass)';
}

export interface ThresholdRow {
  id: string;
  name: string;
  value: string;
  origin: string;
  level: string;
  check?: string;
}

/**
 * Thresholds with origin: record.thresholds (prototype) or, for live records, every threshold the
 * evaluated checks carry (`<comparator> <value>`, origin, evidence level), one row per check and name.
 */
export function thresholdRows(record: UiRunRecord): ThresholdRow[] {
  if (record.thresholds?.length) {
    return record.thresholds.map((t, i) => ({ id: `${i}:${t.name}`, name: t.name, value: t.value, origin: t.origin, level: t.level }));
  }
  const rows: ThresholdRow[] = [];
  for (const l of record.layers) {
    for (const c of l.checks) {
      for (const t of c.thresholds ?? []) {
        const v = typeof t.value === 'boolean' ? String(t.value) : fmtNum(t.value);
        rows.push({ id: `${c.id}:${t.name}`, name: `${c.id} · ${t.name}`, value: `${t.comparator} ${v}`, origin: t.origin, level: t.evidenceLevel, check: c.id });
      }
    }
  }
  return rows;
}

// ---------------------------------------------------------------- block provenance

export type BlockSource = StatsSource;

/**
 * Where a stats block (or one of its rows, `site.pocket residues`) came from: stats.provenance[key]
 * or the block's own `source`. null when the record does not say (mock records).
 */
export function blockSource(record: UiRunRecord, key: string): BlockSource | null {
  const prov = record.stats.provenance;
  const own = record.stats[key] as { source?: BlockSource } | undefined;
  const s = prov?.[key] ?? (own && typeof own === 'object' && !Array.isArray(own) ? own.source : undefined);
  return s && typeof s === 'object' ? s : null;
}

/** `l4.posebusters · posebusters 0.6.5` for a title attribute; undefined when unknown. */
export function sourceLabel(src: BlockSource | null | undefined): string | undefined {
  if (!src) return undefined;
  const checks = src.check ? [src.check] : (src.checks ?? []);
  const tool = src.tool ? `${src.tool}${src.version ? ` ${src.version}` : ''}` : null;
  const parts = [checks.join(', '), tool].filter(Boolean);
  return parts.length ? `source: ${parts.join(' · ')}` : undefined;
}

// ---------------------------------------------------------------- assessment (what the run evaluated)

/** A structure an executor produced (not a source or reference file). */
function isPrediction(s: Pick<RecordStructure, 'kind' | 'artifactKind'>): boolean {
  if (s.artifactKind) return s.artifactKind !== 'source_structure' && s.kind !== 'crystal';
  return s.kind !== 'crystal';
}

/** The record holds executor outputs: a predicted structure, a predicted ensemble member or a tool that ran. */
export function hasPredictions(record: Pick<UiRunRecord, 'structures' | 'stats' | 'tools'>): boolean {
  if ((record.structures ?? []).some(isPrediction)) return true;
  if ((record.stats.ensemble ?? []).some((e) => e.kind !== 'crystal')) return true;
  return record.tools.some((t) => t.ran === true);
}

/**
 * `pre-run` when nothing was predicted. The record's own `assessment` wins; a live record without
 * it is pre-run when it holds no executor outputs. Mock records without it are full runs.
 */
export function assessmentOf(record: Pick<UiRunRecord, 'assessment' | 'source' | 'structures' | 'stats' | 'tools' | 'status'>): Assessment {
  if (record.assessment) return record.assessment;
  return record.source === 'pah' && (!record.status || record.status === 'done') && !hasPredictions(record) ? 'pre-run' : 'full';
}

/** Only reference (source) structures and no predictions: the viewer shows an input, not a result. */
export function referenceOnly(record: UiRunRecord): boolean {
  const s = record.structures ?? [];
  return s.length > 0 && !s.some(isPrediction) && !hasPredictions(record);
}

/**
 * Output check waiting for predictions: skipReason `pending_input`; in a pre-run record without
 * that reason, any skipped output check (layers 4-5), since those checks need predictions.
 */
export function isPendingInput(c: Pick<UiCheck, 'result' | 'skipReason'>, layer?: number, preRun?: boolean): boolean {
  if (c.result !== 'skip') return false;
  if (c.skipReason === 'pending_input') return true;
  return !!preRun && layer !== undefined && layer >= 4 && c.skipReason !== 'unknown_check' && c.skipReason !== 'not_implemented';
}

export function isNotApplicable(c: Pick<UiCheck, 'result' | 'skipReason'>): boolean {
  return c.result === 'skip' && c.skipReason === 'not_applicable';
}

/** Layer numbers as ranges: `0–3`, `0, 2, 4–5`. */
export function fmtLayerSet(layers: number[]): string {
  const xs = [...new Set(layers)].sort((a, b) => a - b);
  const out: string[] = [];
  for (let i = 0; i < xs.length; ) {
    let j = i;
    while (j + 1 < xs.length && xs[j + 1] === xs[j] + 1) j++;
    out.push(j > i ? `${xs[i]}–${xs[j]}` : String(xs[i]));
    i = j + 1;
  }
  return out.join(', ');
}

/** Layers with at least one non-skip result (the record's evaluatedLayers when present). */
export function evaluatedLayers(record: Pick<UiRunRecord, 'layers' | 'evaluatedLayers'>): number[] {
  if (record.evaluatedLayers) return record.evaluatedLayers;
  return record.layers.filter((l) => l.checks.some((c) => c.result !== 'skip' && c.result !== 'pending')).map((l) => l.i);
}

export interface VerdictView extends VerdictMeta {
  preRun: boolean;
  /** `Inputs fit to run` for a pre-run check; null for a full run. */
  assessed: string | null;
  /** `layers 0–3 evaluated · 4–5 pending`. */
  scope: string | null;
  /** Output checks waiting for predictions. */
  pending: number;
}

/**
 * Verdict as shown: a pre-run record is never shown supported or narrowed (nothing was
 * predicted); it reads "Not assessed" unless its inputs stopped (refused).
 */
export function verdictView(record: UiRunRecord): VerdictView {
  const preRun = assessmentOf(record) === 'pre-run';
  const o = record.verdict.outcome;
  const shown = preRun && o !== 'refused' && o !== null ? 'not_assessed' : o;
  const pending = record.verdict.pending?.length ?? record.layers.reduce((n, l) => n + l.checks.filter((c) => isPendingInput(c, l.i, preRun)).length, 0);
  const evald = evaluatedLayers(record);
  const pendLayers = record.layers.filter((l) => l.checks.some((c) => isPendingInput(c, l.i, preRun))).map((l) => l.i);
  const scope = evald.length
    ? [`layers ${fmtLayerSet(evald)} evaluated`, pendLayers.length ? `${fmtLayerSet(pendLayers)} pending` : null].filter(Boolean).join(' · ')
    : (record.verdict.scope ?? null);
  const assessed = record.verdict.assessedClaim ?? (preRun ? 'Inputs fit to run' : null);
  return { ...verdictMeta(shown), preRun, assessed, scope, pending };
}

// ---------------------------------------------------------------- stages (Inputs · Applicability · Outputs)

export type StageId = 'inputs' | 'applicability' | 'outputs';

export const STAGES: { id: StageId; label: string; range: string; layers: number[] }[] = [
  { id: 'inputs', label: 'Inputs', range: 'L0–L2', layers: [0, 1, 2] },
  { id: 'applicability', label: 'Applicability', range: 'L3', layers: [3] },
  { id: 'outputs', label: 'Outputs', range: 'L4–L5', layers: [4, 5] },
];

export interface CheckBreakdown {
  total: number;
  pass: number;
  warn: number;
  stop: number;
  reported: number;
  /** Waiting for predictions (skipReason pending_input) or still running. */
  pending: number;
  /** Skipped as not applicable. */
  na: number;
  /** Other skips (tool missing, error, not implemented). */
  skipped: number;
}

export function checkBreakdown(checks: { c: UiCheck; layer: number }[], preRun: boolean): CheckBreakdown {
  const b: CheckBreakdown = { total: checks.length, pass: 0, warn: 0, stop: 0, reported: 0, pending: 0, na: 0, skipped: 0 };
  for (const { c, layer } of checks) {
    if (c.result === 'pass' || c.result === 'warn' || c.result === 'stop' || c.result === 'reported') b[c.result]++;
    else if (c.result === 'pending' || isPendingInput(c, layer, preRun)) b.pending++;
    else if (isNotApplicable(c)) b.na++;
    else b.skipped++;
  }
  return b;
}

/** `3 pass · 1 warn · 2 pending · 4 not applicable` (zero counts left out; `no checks` when empty). */
export function breakdownText(b: CheckBreakdown, opts: { short?: boolean } = {}): string {
  const na = opts.short ? 'n/a' : 'not applicable';
  const parts: [number, string][] = [
    [b.pass, 'pass'],
    [b.warn, 'warn'],
    [b.stop, 'stop'],
    [b.reported, 'reported'],
    [b.pending, 'pending'],
    [b.na, na],
    [b.skipped, 'skipped'],
  ];
  const s = parts.filter(([n]) => n > 0).map(([n, w]) => `${n} ${w}`);
  return s.length ? s.join(' · ') : 'no checks';
}

/** Dot of a set of checks: worst evaluated result; `pending` when only pending checks remain; null when none apply. */
export function breakdownDot(b: CheckBreakdown): Result | null {
  if (b.stop) return 'stop';
  if (b.warn) return 'warn';
  if (b.pass) return 'pass';
  if (b.reported) return 'reported';
  if (b.pending) return 'pending';
  return b.skipped ? 'skip' : null;
}

export interface StageItem {
  id: StageId;
  label: string;
  range: string;
  /** Indices into record.layers. */
  layerIdx: number[];
  counts: CheckBreakdown;
  dot: Result | null;
  running: boolean;
}

export function stageItems(record: UiRunRecord): StageItem[] {
  const preRun = assessmentOf(record) === 'pre-run';
  return STAGES.map((s) => {
    const layerIdx = record.layers.map((l, idx) => ({ l, idx })).filter(({ l }) => s.layers.includes(l.i)).map(({ idx }) => idx);
    const checks = layerIdx.flatMap((idx) => record.layers[idx].checks.map((c) => ({ c, layer: record.layers[idx].i })));
    const counts = checkBreakdown(checks, preRun);
    return { id: s.id, label: s.label, range: s.range, layerIdx, counts, dot: breakdownDot(counts), running: layerIdx.some((idx) => record.layers[idx].status === 'running') };
  });
}

/** Stage holding a layer number. */
export function stageOfLayer(i: number): StageId {
  return STAGES.find((s) => s.layers.includes(i))?.id ?? 'outputs';
}

/** Per-layer counts with pending and not applicable kept apart. */
export function layerBreakdown(record: UiRunRecord, idx: number): CheckBreakdown {
  const l = record.layers[idx];
  const preRun = assessmentOf(record) === 'pre-run';
  return checkBreakdown((l?.checks ?? []).map((c) => ({ c, layer: l.i })), preRun);
}

// ---------------------------------------------------------------- dimensions

const DIM_LABEL: Record<DimensionId, string> = {
  inputs: 'Inputs',
  applicability: 'Applicability',
  geometry: 'Geometry',
  physics: 'Physics',
  interactions: 'Interactions',
  confidence: 'Confidence',
  support: 'Support',
};
export const DIMENSION_ORDER: DimensionId[] = ['inputs', 'applicability', 'geometry', 'physics', 'interactions', 'confidence', 'support'];

/** Fallback grouping by check id when the record carries no dimensions (configs/catalog.yaml is the source). */
function dimensionOfCheck(id: string, layer: number): DimensionId {
  if (layer <= 2) return 'inputs';
  if (layer === 3) return 'applicability';
  if (/^l4\.interactions\./.test(id)) return 'interactions';
  if (/^l4\.(minimisation|physics|energy|strain|clash)/.test(id)) return 'physics';
  if (layer === 4) return 'geometry';
  if (/^l5\.confidence\./.test(id)) return 'confidence';
  return 'support';
}

const CERTAINTY_RANK: Record<Certainty, number> = { none: 3, calibrated: 2, published: 1, uncalibrated: 0 };

/** Evidence level of a threshold as a certainty class. */
export function certaintyOf(level: string | null | undefined): Certainty {
  const l = (level ?? '').toLowerCase();
  if (!l) return 'none';
  if (l === 'calibrated') return 'calibrated';
  if (l === 'published' || l === 'reproduced' || l === 'literature') return 'published';
  return 'uncalibrated';
}

/** Weakest certainty of a list (uncalibrated < published < calibrated; `none` only when nothing has a level). */
export function weakestCertainty(levels: Certainty[]): Certainty {
  const real = levels.filter((l) => l !== 'none');
  if (!real.length) return 'none';
  return real.reduce((a, b) => (CERTAINTY_RANK[b] < CERTAINTY_RANK[a] ? b : a));
}

function deriveDimensions(record: UiRunRecord): UiDimension[] {
  const preRun = assessmentOf(record) === 'pre-run';
  const groups = new Map<DimensionId, { c: UiCheck; layer: number }[]>();
  for (const l of record.layers) for (const c of l.checks) {
    const d = dimensionOfCheck(c.id, l.i);
    groups.set(d, [...(groups.get(d) ?? []), { c, layer: l.i }]);
  }
  return DIMENSION_ORDER.filter((id) => groups.has(id)).map((id) => {
    const list = groups.get(id)!;
    const b = checkBreakdown(list, preRun);
    const levels = list
      .filter(({ c }) => c.result !== 'skip' && c.result !== 'pending')
      .flatMap(({ c }) => (c.thresholds?.length ? c.thresholds.map((t) => certaintyOf(t.evidenceLevel)) : c.threshold ? [certaintyOf(c.threshold.evidenceLevel)] : []));
    const result: UiDimension['result'] = b.stop ? 'stop' : b.warn ? 'warn' : b.pass || b.reported ? 'pass' : b.pending ? 'pending' : 'na';
    return { id, label: DIM_LABEL[id], result, checks: b.total, passed: b.pass, warned: b.warn, stopped: b.stop, pending: b.pending, certainty: weakestCertainty(levels), checkIds: list.map(({ c }) => c.id) };
  });
}

/** The record's dimensions in the fixed order, or the same grouping derived from its checks. */
export function dimensionsOf(record: UiRunRecord): UiDimension[] {
  const ds = record.dimensions?.length ? record.dimensions : deriveDimensions(record);
  return [...ds].sort((a, b) => DIMENSION_ORDER.indexOf(a.id) - DIMENSION_ORDER.indexOf(b.id));
}

export const CERTAINTY_TEXT: Record<Certainty, string> = {
  calibrated: 'calibrated',
  published: 'published',
  uncalibrated: 'uncalibrated',
  none: 'no threshold',
};

// ---------------------------------------------------------------- tools: exercised vs declared

export interface ToolRow {
  name: string;
  version: string | null;
  exercised: boolean;
  /** `executor` for record.tools, `check` for the libraries the checks use. */
  role: 'executor' | 'check';
  /** `outputs supplied`, `declared, not run`, or the number of checks that ran with it. */
  note: string;
  checks: string[];
}

const toolKey = (s: string) => s.trim().split(/\s+/)[0].toLowerCase();

/** Executors (ran or declared) and check libraries (exercised by a non-skip finding, or only declared). */
export function toolRows(record: UiRunRecord, register?: Register): ToolRow[] {
  const exec: ToolRow[] = recordTools(record, register).map((t) => {
    const exercised = t.ran === true || t.ranBy === 'harness' || t.ranBy === 'external';
    return {
      name: t.name,
      version: t.version,
      exercised,
      role: 'executor',
      note: t.ranBy === 'external' ? 'outputs supplied' : exercised ? 'ran' : 'declared, not run',
      checks: [],
    };
  });
  let libs: UiToolVersion[] = record.toolVersions ?? [];
  if (!record.toolVersions) {
    const all = record.layers.flatMap((l) => l.checks);
    libs = Object.entries(record.record.toolVersions ?? {}).map(([name, version]) => {
      const used = all.filter((c) => (c.tool ?? '').split('·').some((x) => x.trim() && toolKey(x) === name.toLowerCase()));
      return { name, version, exercised: used.some((c) => c.result !== 'skip' && c.result !== 'pending'), checks: used.map((c) => c.id) };
    });
  }
  const check: ToolRow[] = libs.map((t) => ({
    name: t.name,
    version: t.version,
    exercised: t.exercised,
    role: 'check',
    note: t.exercised ? `${t.checks.length} check${t.checks.length === 1 ? '' : 's'}` : 'declared, not run',
    checks: t.checks,
  }));
  return [...exec, ...check];
}

// ---------------------------------------------------------------- block availability (computed, not applicable, pending)

export type BlockState = 'computed' | 'not_applicable' | 'pending' | 'not_computed';

/** Checks whose evidence fills a stats block. */
const BLOCK_CHECKS: Record<string, string[]> = {
  pae: ['l5.confidence.local'],
  agreement: ['l5.agreement.cross_family'],
  interactions: ['l4.interactions.fingerprint'],
  seeds: ['l5.sampling.seeds', 'l5.sampling.clusters'],
  posebusters: ['l4.posebusters'],
  physics: ['l4.minimisation_drift', 'l4.torsion_strain', 'l4.posebusters'],
  calibration: [],
  metrics: ['l5.confidence.local'],
};

export interface BlockAvailability {
  state: BlockState;
  /** Why the block is empty: the skip evidence of its check, or what is missing. */
  reason: string | null;
  check?: string;
}

/**
 * Why a stats block is empty. `not_applicable` when its checks were skipped as not applicable
 * (or, for PAE, when no tool of the run declares a PAE output); `pending` when its checks wait for
 * predictions; `not_computed` when the block should exist and does not.
 */
export function blockAvailability(record: UiRunRecord, block: string, computed: boolean, register?: Register): BlockAvailability {
  if (computed) return { state: 'computed', reason: null };
  const preRun = assessmentOf(record) === 'pre-run';
  const ids = BLOCK_CHECKS[block] ?? [];
  const found = record.layers.flatMap((l) => l.checks.filter((c) => ids.includes(c.id)).map((c) => ({ c, layer: l.i })));
  const pend = found.find(({ c, layer }) => isPendingInput(c, layer, preRun));
  if (pend || (preRun && block !== 'calibration')) {
    return { state: 'pending', reason: 'waits for predictions', check: pend?.c.id };
  }
  if (block === 'pae') {
    const tools = recordTools(record, register);
    if (tools.length && !tools.some((t) => t.outputs.some((o) => o.kind === 'pae'))) {
      return { state: 'not_applicable', reason: `${tools.map((t) => t.name).join(', ')} report${tools.length === 1 ? 's' : ''} no predicted aligned error` };
    }
  }
  const na = found.find(({ c }) => isNotApplicable(c));
  if (na && found.every(({ c }) => c.result === 'skip')) return { state: 'not_applicable', reason: na.c.evidence ?? na.c.message ?? null, check: na.c.id };
  return { state: 'not_computed', reason: null };
}

// ---------------------------------------------------------------- scores and their glossary

export interface ScoreEntry {
  key: string;
  label: string;
  unit: string | null;
  quantity: Quantity;
  producedBy: string[];
  what: string;
  inputs: string[];
  higherIsBetter: boolean | null;
  rankingOnly: boolean;
}

/** Keys of the scores this record shows (metrics, ensemble values, per-seed columns, PoseBusters). */
export function presentScoreKeys(record: UiRunRecord): string[] {
  const S = record.stats;
  const keys: string[] = [];
  const add = (k: string | undefined | null) => {
    if (k && !keys.includes(k)) keys.push(k);
  };
  for (const m of S.metrics ?? []) add(m.key ?? m.name);
  for (const e of S.ensemble ?? []) for (const k of Object.keys(e.values ?? {})) add(k);
  for (const s of S.seeds ?? []) {
    add(s.confidenceKey);
    add(s.scoreKey);
  }
  if ((S.ensemble ?? []).some((e) => typeof e.rmsdToMedoid === 'number' && e.kind !== 'crystal')) add('rmsdToMedoid');
  if ((S.ensemble ?? []).some((e) => typeof e.siteDistance === 'number')) add('siteDistance');
  if ((S.ensemble ?? []).some((e) => typeof e.rmsdToReference === 'number')) add('rmsdToReference');
  for (const c of physicsColumns(record)) if ((S.physics ?? []).some((p) => typeof p[c.key] === 'number')) add(c.key);
  if (S.posebusters?.length) add('posebusters');
  return keys;
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

/** Looks a score up by key, then by label, in the glossary, then in the record's tool outputs. */
export function scoreLookup(record: UiRunRecord, register?: Register, glossary?: UiGlossary | null): (key: string, label?: string) => ScoreEntry | null {
  const tools = recordTools(record, register);
  const gl = glossary?.scores ?? [];
  return (key, label) => {
    const g = gl.find((x) => x.key === key) ?? (label ? gl.find((x) => norm(x.label) === norm(label)) : undefined) ?? gl.find((x) => norm(x.key) === norm(key));
    const t = tools.find((x) => outputFor(x, key));
    const o = t ? outputFor(t, key) : undefined;
    if (g) {
      return {
        key: g.key,
        label: g.label,
        unit: g.unit ?? o?.unit ?? null,
        quantity: quantityOf({ kind: g.kind, unit: g.unit ?? o?.unit, key: g.key, range: o?.range }),
        producedBy: g.producedBy,
        what: g.what,
        inputs: g.inputs,
        higherIsBetter: g.higherIsBetter ?? o?.higherIsBetter ?? null,
        rankingOnly: !!o?.rankingOnly,
      };
    }
    if (o && t) {
      return {
        key,
        label: o.label,
        unit: o.unit ?? null,
        quantity: quantityOf(o),
        producedBy: [t.name],
        what: o.note ?? `${o.label} reported by ${t.name}`,
        inputs: [],
        higherIsBetter: o.higherIsBetter ?? null,
        rankingOnly: !!o.rankingOnly,
      };
    }
    return null;
  };
}

/** Scores present in the record, with producer and inputs (glossary, else the tool output description). */
export function scoreEntries(record: UiRunRecord, register?: Register, glossary?: UiGlossary | null): ScoreEntry[] {
  const look = scoreLookup(record, register, glossary);
  const labels = new Map((record.stats.metrics ?? []).map((m) => [m.key ?? m.name, m.name]));
  const out: ScoreEntry[] = [];
  for (const k of presentScoreKeys(record)) {
    const e = look(k, labels.get(k));
    if (e && !out.some((x) => x.key === e.key)) out.push(e);
  }
  return out;
}

// ---------------------------------------------------------------- execution

/** Execution entries of the record (UiExecution only; prototype executor lines are left out). */
export function executionRows(record: Pick<UiRunRecord, 'execution'>): UiExecution[] {
  return (record.execution ?? []).filter((e) => !!e && typeof e === 'object' && 'executor' in e && 'phase' in e);
}

// ---------------------------------------------------------------- run summary (compare view)

export interface SummaryScore {
  /** Grouping key across runs: `confidence:<label>`, `ranking:<label>`, `rmsd`, `pb`. */
  id: string;
  label: string;
  unit: string | null;
  quantity: Quantity;
  /** Median over the run's predicted members; for `pb`, the pass rate 0..1. */
  value: number;
  n: number;
  rankingOnly: boolean;
}

export interface RunSummary {
  runId: string;
  target: string;
  tools: string[];
  family: ToolFamily | null;
  verdict: VerdictView;
  scores: SummaryScore[];
}

/** Medians of the run's predicted members: each confidence and ranking output, RMSD to medoid, PoseBusters pass rate. Only scores the run has. */
export function runSummary(record: UiRunRecord, members: EnsembleMember[], register?: Register): RunSummary {
  const pred = members.filter((m) => m.kind !== 'crystal');
  const scores: SummaryScore[] = [];
  const byKey = new Map<string, { o: MemberValue; values: number[] }>();
  for (const m of pred) {
    for (const o of m.outputs) {
      if (o.kind === 'rmsd') continue;
      const g = byKey.get(o.key) ?? { o, values: [] };
      g.values.push(o.value);
      byKey.set(o.key, g);
    }
  }
  for (const [key, { o, values }] of byKey) {
    const st = describe(values);
    if (!st) continue;
    scores.push({ id: `${o.rankingOnly ? 'ranking' : 'confidence'}:${o.label}`, label: `median ${o.label}`, unit: o.unit ?? null, quantity: quantityOf({ kind: o.kind, unit: o.unit, key }), value: st.median, n: st.n, rankingOnly: o.rankingOnly });
  }
  scores.sort((a, b) => Number(a.rankingOnly) - Number(b.rankingOnly));
  const rm = describe(pred.filter((m) => m.kind !== 'medoid').map((m) => m.rmsd));
  if (rm) scores.push({ id: 'rmsd', label: 'median RMSD to medoid', unit: 'Å', quantity: 'rmsd', value: rm.median, n: rm.n, rankingOnly: false });
  const pb = pred.filter((m) => m.pb && m.pb.total);
  if (pb.length) {
    const passed = pb.filter((m) => m.pb!.passed === m.pb!.total).length;
    scores.push({ id: 'pb', label: 'PoseBusters all passed', unit: '%', quantity: 'percent', value: (100 * passed) / pb.length, n: pb.length, rankingOnly: false });
  }
  const tools = recordTools(record, register);
  return {
    runId: record.id,
    target: [record.inputs.target, record.inputs.ligand ?? record.inputs.partner].filter((x) => !isMissing(x)).join(' · ') || record.inputs.reference || record.taskName,
    tools: tools.map((t) => t.name),
    family: tools.map((t) => familyOf(t)).find((f) => f) ?? null,
    verdict: verdictView(record),
    scores,
  };
}

/** Median of each score across runs (only runs that have it), in first-seen order. */
export function overallMedians(summaries: RunSummary[]): (SummaryScore & { runs: number })[] {
  const groups = new Map<string, { s: SummaryScore; values: number[] }>();
  for (const r of summaries) {
    for (const s of r.scores) {
      const g = groups.get(s.id) ?? { s, values: [] };
      g.values.push(s.value);
      groups.set(s.id, g);
    }
  }
  return [...groups.values()].map(({ s, values }) => ({ ...s, value: describe(values)!.median, n: values.length, runs: values.length }));
}
