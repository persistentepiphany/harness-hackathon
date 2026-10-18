// Derivations for the New run view and the single-job view (prototype logic-v2.js renderVals,
// "new run" and "run" blocks; quickSetup/submit/addKey rules). Pure functions over the catalog,
// task list, tool register, interpreter steps, job, record and log lines.

import { DASH, fmtSha } from '../format';
import { familyOf, toolById } from '../tools';
import type {
  Catalog,
  CatalogLigand,
  CatalogProtein,
  EntityGroup,
  Job,
  LogLine,
  RecordSource,
  Result,
  RunSettings,
  Step,
  Task,
  TaskKind,
  Tool,
  ToolFamily,
  UiRunRecord,
} from '../types';
import { jobTools, toolLabel, type CheckTotals, type LayerCell } from './jobs';

// ---------------------------------------------------------------- form

/** The New run form as the inputs hold it (numbers as typed). */
export interface RunForm {
  task: string;
  tools: string[];
  target: string;
  partner: string;
  ligand: string;
  reference: string;
  ph: string;
  seeds: string;
  name: string;
  /** Run the selected executors; null or absent: follow the tools (on when one can be dispatched). */
  execute?: boolean | null;
}

/** The prototype's starting task, the harness's default (`RunSettings.task`). */
export const DEFAULT_TASK = 'ligand_pose';
/** Defaults the prototype applies on submit (`+form.seeds || 5`, `+form.ph || 7.4`). */
export const DEFAULT_SEEDS = 5;
export const DEFAULT_PH = 7.4;
/** Partner the prototype fills when a complex task is picked and none is set. */
export const FALLBACK_PARTNER = 'P04049';

export interface CatalogDefaults {
  target?: string;
  partner?: string;
  ligand?: string;
  reference?: string;
}

/** `GET /ui/catalog` adds `defaults` (configs/catalog.yaml); the mock catalog has none. */
export function catalogDefaults(catalog: Catalog | null | undefined): CatalogDefaults {
  const d = (catalog as (Catalog & { defaults?: CatalogDefaults }) | null | undefined)?.defaults;
  return d && typeof d === 'object' ? d : {};
}

/** Ligand by catalog name, CCD code or SMILES. */
export function findLigand(catalog: Pick<Catalog, 'ligands'> | null | undefined, value: string | null | undefined): CatalogLigand | undefined {
  if (!value) return undefined;
  const v = value.trim();
  const low = v.toLowerCase();
  return catalog?.ligands.find((l) => l.smiles === v || l.names?.some((n) => n === low) || (l.ccd && l.ccd === v.toUpperCase()));
}

export function findProtein(catalog: Pick<Catalog, 'proteins'> | null | undefined, accession: string | null | undefined): CatalogProtein | undefined {
  if (!accession) return undefined;
  const acc = accession.trim().toUpperCase();
  return catalog?.proteins.find((p) => p.accession === acc);
}

/** Starting form: catalog defaults (or its first entries) and the default task's tools that fit its endpoint. */
export function defaultForm(catalog: Catalog | null | undefined, tasks: Task[] | null | undefined, register?: Tool[] | null): RunForm {
  const d = catalogDefaults(catalog);
  const target = d.target ?? catalog?.proteins[0]?.accession ?? '';
  const protein = findProtein(catalog, target);
  const ligand = (d.ligand ? findLigand(catalog, d.ligand) : undefined) ?? catalog?.ligands[0];
  const task = tasks?.find((t) => t.id === DEFAULT_TASK) ?? tasks?.[0];
  return {
    task: task?.id ?? DEFAULT_TASK,
    tools: taskDefaultTools(task, register),
    target,
    partner: '',
    ligand: ligand?.smiles ?? d.ligand ?? '',
    reference: d.reference ?? protein?.pdb ?? '',
    ph: String(DEFAULT_PH),
    seeds: String(DEFAULT_SEEDS),
    name: '',
  };
}

const INPUT_NAMES = ['target', 'partner', 'ligand', 'series', 'reference', 'ph', 'seeds'];

/** The inputs a task takes, when the task list says so (mock: always; live: not yet). */
export function taskInputs(task: Task | null | undefined): string[] | null {
  const inputs = task?.inputs;
  return Array.isArray(inputs) && inputs.some((x) => INPUT_NAMES.includes(x)) ? inputs : null;
}

/** monomer | complex | ligand: from the task, else from its inputs; ligand when unknown. */
export function taskKind(task: Task | null | undefined): TaskKind {
  if (task?.kind === 'monomer' || task?.kind === 'complex' || task?.kind === 'ligand') return task.kind;
  const inputs = taskInputs(task);
  if (inputs?.includes('partner')) return 'complex';
  if (inputs && !inputs.includes('ligand') && !inputs.includes('series')) return 'monomer';
  return 'ligand';
}

export interface InputVisibility {
  partner: boolean;
  ligand: boolean;
  ph: boolean;
  reference: boolean;
}

/** Which inputs the form shows (prototype: partner for complexes, ligand and pH otherwise). */
export function inputVisibility(task: Task | null | undefined): InputVisibility {
  const complex = taskKind(task) === 'complex';
  return { partner: complex, ligand: !complex, ph: !complex, reference: true };
}

/** `ABL1 kinase · ligand pose` (prototype `suggestName`). */
export function suggestName(form: Pick<RunForm, 'task' | 'target'>, catalog: Catalog | null | undefined, tasks: Task[] | null | undefined): string {
  const t = tasks?.find((x) => x.id === form.task);
  const p = findProtein(catalog, form.target);
  return `${p ? p.label : form.target} · ${t ? t.name.toLowerCase() : 'run'}`;
}

/** Text the Sources panel resolves (prototype `formText`). */
export function formText(form: Pick<RunForm, 'target' | 'partner' | 'ligand'>, catalog: Catalog | null | undefined, nlText = ''): string {
  const lig = catalog?.ligands.find((l) => l.smiles === form.ligand);
  return [form.target, form.partner, lig ? lig.names[0] : customLigandQuery(form.ligand, catalog), nlText].map((s) => (s ?? '').trim()).filter(Boolean).join(' ');
}

const CCD_CODE = /^[A-Z0-9]{1,5}$/;

/**
 * Lookup text for a ligand that is not in the catalog, in the forms GET /ui/entities resolves:
 * `cid N` for a number, `ccd XXX` for a CCD code, else the raw input (a SMILES or a name).
 */
export function customLigandQuery(value: string | null | undefined, catalog: Catalog | null | undefined): string {
  const v = (value ?? '').trim();
  if (!v) return '';
  if (/^\d{1,12}$/.test(v)) return `cid ${v}`;
  const l = ligandFromInput(v, catalog);
  if (!l) return '';
  if (!l.custom) return l.names[0] ?? v;
  const code = String(l.ccd ?? '');
  return code !== 'NEW' && CCD_CODE.test(code) ? `ccd ${code}` : v;
}

function num(v: string | number | null | undefined): number | undefined {
  if (v === null || v === undefined || v === '') return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

/** Settings for `POST /ui/runs`: only the inputs the task shows, prototype defaults for seeds and pH. */
export function settingsFromForm(form: RunForm, catalog: Catalog | null | undefined, tasks: Task[] | null | undefined, register?: Tool[] | null): RunSettings {
  const task = tasks?.find((t) => t.id === form.task);
  const show = inputVisibility(task);
  const s: RunSettings = {
    task: form.task,
    tools: [...form.tools],
    target: form.target.trim(),
    reference: form.reference.trim(),
    ph: num(form.ph) || DEFAULT_PH,
    seeds: num(form.seeds) || DEFAULT_SEEDS,
    name: form.name.trim() || suggestName(form, catalog, tasks),
    execute: effectiveExecute(form, register),
  };
  if (show.partner && form.partner.trim()) s.partner = form.partner.trim();
  if (show.ligand && form.ligand.trim()) s.ligand = form.ligand.trim();
  return s;
}

/** Form after picking a task (prototype `taskOptions[].select`): its default tools that fit its endpoint. */
export function selectTask(form: RunForm, task: Task, catalog: Catalog | null | undefined, register?: Tool[] | null): RunForm {
  const complex = taskKind(task) === 'complex';
  const partner = complex ? form.partner || catalogDefaults(catalog).partner || FALLBACK_PARTNER : form.partner;
  return { ...form, task: task.id, tools: taskDefaultTools(task, register), partner };
}

// ---------------------------------------------------------------- quick setup (interpreter steps)

const STEP_LABELS: Record<string, string> = {
  task: 'Task',
  tools: 'Executors',
  target: 'Target',
  partner: 'Partner',
  ligand: 'Ligand',
  seeds: 'Seeds',
  ph: 'pH',
  reference: 'Reference',
  claim: 'Claim',
};

export function stepLabel(field: string): string {
  return STEP_LABELS[field] ?? field;
}

/** Display name of a tool id: register name, else the id itself. */
export function toolName(id: string, register: Tool[] | null | undefined): string {
  return register?.find((t) => t.id === id)?.name ?? id;
}

/** Step value as the decision row shows it (prototype `fmt`). */
export function fmtStep(step: Step, tasks: Task[] | null | undefined, register: Tool[] | null | undefined): string {
  const v = step.value;
  if (step.field === 'tools') return (Array.isArray(v) ? v : [String(v)]).map((id) => toolName(id, register)).join(' · ');
  if (step.field === 'task') return tasks?.find((t) => t.id === v)?.long ?? String(v);
  if (step.field === 'ligand' && typeof v === 'string' && v.length > 40) return `${v.slice(0, 38)}…`;
  return Array.isArray(v) ? v.join(' · ') : String(v);
}

/** `14 tokens · 9 decisions` for the first row. */
export function requestSummary(text: string, steps: Step[]): string {
  const tokens = text.trim() ? text.trim().split(/\s+/).length : 0;
  return `${tokens} tokens · ${steps.length} decisions`;
}

/** Form after one interpreter step (claim is not a form field). */
export function applyStep(form: RunForm, step: Step): RunForm {
  const v = step.value;
  switch (step.field) {
    case 'tools':
      return { ...form, tools: Array.isArray(v) ? v.map(String) : [String(v)] };
    case 'task':
    case 'target':
    case 'partner':
    case 'ligand':
    case 'reference':
    case 'seeds':
    case 'ph':
      return { ...form, [step.field]: Array.isArray(v) ? v.join(' ') : String(v) };
    default:
      return form;
  }
}

/** Short text of a sample prompt (prototype `samplePrompts[].short`). */
export function shortPrompt(p: string): string {
  return p.split(/[,.?]/)[0] + (p.includes('?') ? '?' : '');
}

// ---------------------------------------------------------------- target and ligand cards

export type TargetOption = Partial<CatalogProtein> & { accession: string; label: string; names: string[] };
export type LigandOption = Partial<CatalogLigand> & { smiles: string; names: string[] };

const UNIPROT_ACC = /^[A-Z][0-9][A-Z0-9]{3}[0-9]$/i;

/** A target typed into "+ accession or name": the catalog entry it names, or a custom chip. */
export function targetFromInput(value: string, catalog: Catalog | null | undefined): TargetOption | null {
  const v = value.trim();
  if (!v) return null;
  const low = v.toLowerCase();
  const hit = catalog?.proteins.find((p) => p.accession === v.toUpperCase() || p.names?.some((n) => low.includes(n)));
  if (hit) return hit;
  const acc = UNIPROT_ACC.test(v) ? v.toUpperCase() : v;
  return { names: [low], accession: acc, label: v, custom: true };
}

/** A ligand typed into "+ SMILES, CCD or name": the catalog entry, or a custom chip. */
export function ligandFromInput(value: string, catalog: Catalog | null | undefined): LigandOption | null {
  const v = value.trim();
  if (!v) return null;
  const low = v.toLowerCase();
  const hit = catalog?.ligands.find((l) => l.names?.some((n) => low.includes(n)) || l.ccd === v.toUpperCase() || l.smiles === v);
  if (hit) return hit;
  return { names: [v.length > 12 ? 'custom ligand' : v], smiles: v, ccd: v.length <= 3 ? v.toUpperCase() : 'NEW', custom: true };
}

const has = (v: unknown): boolean => v !== undefined && v !== null && v !== '';
const str = (v: unknown, fn?: (x: never) => string): string => (has(v) ? (fn ? fn(v as never) : String(v)) : DASH);

export interface DetailRow {
  k: string;
  v: string;
  missing: boolean;
}

const row = (k: string, v: string): DetailRow => ({ k, v, missing: v === DASH });

/** Target detail card rows (prototype `td.rows`); fields the catalog does not carry are an en dash. */
export function targetRows(p: TargetOption, release?: string | null): DetailRow[] {
  const rows = [
    row('Length', str(p.length, (n: number) => `${n.toLocaleString('en-US')} aa`)),
    row('Organism', str(p.organism)),
    row('Domains', str(p.domains)),
    row('Cofactors', str(p.cofactors)),
    row('Holo entries', str(p.holo)),
    row('Reference', has(p.pdb) ? `${p.pdb}${has(p.resolution) ? ` · ${p.resolution}` : ''}` : DASH),
    row('AF pLDDT', str(p.afPlddt)),
    row('Disorder', str(p.disorder)),
    row('Binding sites', has(p.sites) ? `${p.sites} · PDBe-KB` : DASH),
  ];
  // The release comes from the resolved UniProt record; without one the row is left out.
  if (release) rows.push(row('Release', `UniProt ${release}`));
  return rows;
}

/** UniProt release of `accession` from the Sources lookups (row `Release`), if one resolved. */
export function uniprotRelease(groups: EntityGroup[] | null | undefined, accession: string | null | undefined): string | null {
  if (!accession) return null;
  const acc = accession.toUpperCase();
  const g = (groups ?? []).find((x) => x.source === 'UniProt' && x.query.toUpperCase() === acc && (x as { status?: string }).status !== 'error');
  const r = g?.rows?.find(([k]) => k === 'Release');
  return r && r[1] ? r[1] : null;
}

/** Ligand detail card rows (prototype `ld.rows`). */
export function ligandRows(l: LigandOption): DetailRow[] {
  const chembl = has(l.chembl) && l.chembl !== '—' ? `${l.chembl}${has(l.activities) ? ` · ${Number(l.activities).toLocaleString('en-US')} activities` : ''}` : DASH;
  return [
    row('CCD', has(l.ccd) && l.ccd !== 'NEW' ? String(l.ccd) : DASH),
    row('PubChem', has(l.cid) && l.cid !== '—' ? `CID ${l.cid}` : DASH),
    row('ChEMBL', chembl),
    row('InChIKey', str(l.inchikey)),
    row('Stereocentres', str(l.stereo)),
    row('pKa', str(l.pka)),
    row('SMILES', str(l.smiles)),
  ];
}

/** `C29H31N7O · 493.6` header suffix of the ligand card. */
export function ligandFormula(l: LigandOption): string {
  return [l.formula, l.mw].filter(has).join(' · ') || DASH;
}

// ---------------------------------------------------------------- sources panel

export type EntityStatus = 'ok' | 'error';

export interface EntityItem {
  key: string;
  source: string;
  query: string;
  ms: number | null;
  status: EntityStatus;
  message?: string;
  rows: { k: string; v: string }[];
}

export interface EntityGroupView {
  title: string;
  kind: 'protein' | 'ligand';
  items: EntityItem[];
}

/** Lookup results grouped by entity (prototype `entityGroups`). The live API adds status/message. */
export function groupEntities(groups: EntityGroup[] | null | undefined): EntityGroupView[] {
  const out: EntityGroupView[] = [];
  for (const g of groups ?? []) {
    let view = out.find((x) => x.title === g.title);
    if (!view) {
      view = { title: g.title, kind: g.kind, items: [] };
      out.push(view);
    }
    const extra = g as EntityGroup & { status?: string; message?: string };
    view.items.push({
      key: g.key,
      source: g.source,
      query: g.query,
      ms: typeof g.ms === 'number' && Number.isFinite(g.ms) ? g.ms : null,
      status: extra.status === 'error' ? 'error' : 'ok',
      message: extra.message,
      rows: (g.rows ?? []).map(([k, v]) => ({ k, v })),
    });
  }
  return out;
}

// ---------------------------------------------------------------- executors and plan

export interface ExecutorChipModel {
  id: string;
  name: string;
  version: string;
  versionTitle?: string;
  family: ToolFamily | null;
  /** co-folding | docking | ppi (protein–protein docking). */
  group: ToolGroup;
  selected: boolean;
  available: boolean;
  /** Unavailable tools cannot be added; a selected one (task default, interpreter) can be removed. */
  disabled: boolean;
  note: string;
  /** Endpoints the tool reports (`pose · structure`), empty when the register does not say. */
  endpoints: string[];
  /** `A100 · Modal`, `CPU · local`, `checks only`; null when the register does not say. */
  run: string | null;
  dispatchable: boolean | null;
  /** The task's endpoint is not among the tool's endpoints. */
  fit: ToolFit;
}

export interface ExecutorGroupModel {
  family: ToolFamily | null;
  group: ToolGroup;
  label: string;
  chips: ExecutorChipModel[];
}

/** Register tools grouped co-folding, docking, PPI docking, with selection, availability and endpoint fit. */
export function executorGroups(register: Tool[] | null | undefined, selected: string[], task?: Task | null): ExecutorGroupModel[] {
  const out: ExecutorGroupModel[] = [];
  for (const t of register ?? []) {
    const on = selected.includes(t.id);
    const long = !!t.version && /^[0-9a-f]{20,}$/i.test(t.version);
    const group = toolGroup(t);
    let g = out.find((x) => x.group === group);
    if (!g) {
      g = { family: group === 'co-folding' ? 'co-folding' : group === 'docking' || group === 'ppi' ? 'docking' : null, group, label: TOOL_GROUP_LABELS[group], chips: [] };
      out.push(g);
    }
    g.chips.push({
      id: t.id,
      name: t.name,
      version: t.version ? (long ? fmtSha(t.version) : t.version) : '',
      versionTitle: long ? (t.version ?? undefined) : undefined,
      family: familyOf(t),
      group,
      selected: on,
      available: t.available !== false,
      disabled: t.available === false && !on,
      note: t.note ?? '',
      endpoints: (t.endpoints ?? []).map(endpointLabel),
      run: toolRunLabel(t),
      dispatchable: typeof t.dispatchable === 'boolean' ? t.dispatchable : null,
      fit: toolFit(t, task),
    });
  }
  return GROUP_ORDER.map((k) => out.find((g) => g.group === k)).filter((g): g is ExecutorGroupModel => !!g);
}

export function toggleTool(tools: string[], id: string): string[] {
  return tools.includes(id) ? tools.filter((x) => x !== id) : [...tools, id];
}

/** `Boltz-2 · Gnina`, or `none` (prototype `planTools`). Unknown ids show as the id. */
export function planTools(ids: string[], register: Tool[] | null | undefined): string {
  return ids.length ? ids.map((id) => toolName(id, register)).join(' · ') : 'none';
}

export interface TaskGroups {
  cofolding: Task[];
  docking: Task[];
}

/** Tasks by group (prototype `taskOptionsCofold` / `taskOptionsDock`); an unknown group goes first. */
export function taskGroups(tasks: Task[] | null | undefined): TaskGroups {
  const list = tasks ?? [];
  return { cofolding: list.filter((t) => t.group !== 'docking'), docking: list.filter((t) => t.group === 'docking') };
}

/** `permitted claim: …` plus `checks implemented 13/38` when the live API reports it. */
export function taskHint(task: Task | null | undefined): string {
  if (!task) return '';
  const impl = typeof task.implemented === 'number' && typeof task.checks === 'number' ? ` · checks implemented ${task.implemented}/${task.checks}` : '';
  return `permitted claim: ${task.claim}${impl}`;
}

// ---------------------------------------------------------------- single job view

export interface RunHeaderModel {
  name: string;
  taskName: string;
  models: string;
  sampling: string;
  runId: string;
  harnessRunId?: string;
}

export function runHeaderModel(job: Job, record: UiRunRecord | null | undefined, register: Tool[] | null | undefined, tasks?: Task[] | null): RunHeaderModel {
  const tools = jobTools(job, record, register);
  const seeds = record?.inputs?.seeds ?? (job.seeds || undefined);
  const samples = record?.inputs?.samples;
  return {
    name: job.name || job.id,
    taskName: record?.taskName || tasks?.find((t) => t.id === job.task)?.long || job.taskName || job.task || DASH,
    models: tools.length ? tools.map(toolLabel).join(' · ') : DASH,
    sampling: seeds ? `${seeds} seeds${samples ? ` × ${samples} samples` : ''}` : DASH,
    runId: job.id,
    harnessRunId: job.harnessRunId && job.harnessRunId !== job.id ? job.harnessRunId : undefined,
  };
}

export type StatusTone = 'pass' | 'ink2' | 'stop';

export interface RunStatusModel {
  label: string;
  tone: StatusTone;
  dot: 'running' | 'done' | 'queued' | 'failed';
}

/** Status line under the elapsed time (prototype `rj.statusLabel`). */
export function runStatus(job: Job, cells: LayerCell[], totals: Pick<CheckTotals, 'total'>): RunStatusModel {
  if (job.status === 'done') return { label: `complete · ${totals.total} checks`, tone: 'pass', dot: 'done' };
  if (job.status === 'running') {
    const cur = cells[Math.min(job.layerIdx, cells.length - 1)];
    return { label: `${(cur?.name ?? '').toLowerCase()} · ${Math.round(job.progress * 100)}%`, tone: 'ink2', dot: 'running' };
  }
  if (job.status === 'failed') return { label: 'failed', tone: 'stop', dot: 'failed' };
  return { label: 'queued', tone: 'ink2', dot: 'queued' };
}

/** Log header text (prototype `rj.currentStep`). */
export function currentStep(job: Job, lines: LogLine[]): string {
  if (job.status === 'running') return lines.length ? lines[lines.length - 1].text.slice(0, 60) : 'starting';
  if (job.status === 'done') return `finished · ${(job.elapsedMs / 1000).toFixed(1)} s`;
  return job.status;
}

export interface LogStats {
  pass: number;
  warn: number;
  stop: number;
  skip: number;
  /** Sources fetched: fetch/cache log lines, else record.sources fetched over the network; null when neither exists. */
  fetched: number | null;
  /** Sources served from the content cache (record.sources), when the count comes from the record. */
  cached: number | null;
  checks: number;
}

/**
 * Footer counts of the log (prototype `evPass` … `evChecks`). The harness log has no fetch/cache
 * lines, so the fetched count then comes from the run record's sources.
 */
export function logStats(lines: LogLine[], sources?: Pick<RecordSource, 'cached'>[] | null): LogStats {
  const s: LogStats = { pass: 0, warn: 0, stop: 0, skip: 0, fetched: null, cached: null, checks: 0 };
  let fetchLines = 0;
  for (const l of lines) {
    if (l.kind === 'fetch' || l.kind === 'cache') fetchLines += 1;
    if (l.kind !== 'check') continue;
    s.checks += 1;
    if (l.result === 'pass' || l.result === 'warn' || l.result === 'stop' || l.result === 'skip') s[l.result] += 1;
  }
  if (fetchLines) s.fetched = fetchLines;
  else if (sources && sources.length) {
    s.fetched = sources.filter((x) => x.cached === false).length;
    s.cached = sources.filter((x) => x.cached === true).length;
  }
  return s;
}

/** The harness's `run end` log line with its time in ms (`t` is seconds since run start), if it streamed. */
export function runEndLine(lines: LogLine[]): { seq: number; ms: number | null } | null {
  for (let i = lines.length - 1; i >= 0; i--) {
    const l = lines[i];
    if (l.kind === 'run' && /^run\s+end\b/.test(l.text)) {
      const s = Number.parseFloat(l.t);
      return { seq: l.seq, ms: Number.isFinite(s) ? Math.round(s * 1000) : null };
    }
  }
  return null;
}

/** Verdict counts of the job page: from the record, else the job's check total, else an en dash. */
export function jobVerdictCounts(job: Pick<Job, 'checksTotal'>, record: UiRunRecord | null | undefined, totals: CheckTotals): { text: string; skip?: string } {
  if (record) return verdictCounts(totals);
  return { text: typeof job.checksTotal === 'number' ? `${job.checksTotal} checks` : DASH };
}

export type LogMode = 'plain' | 'terminal';

export interface LogLineView {
  text: string;
  /** CSS colour of the dot; null draws no dot (the prototype has none for reported lines). */
  dot: string | null;
  color: string | undefined;
  weight: 400 | 500;
}

const LOG_COLORS: Record<LogMode, Partial<Record<Result | 'fetch' | 'cache' | 'exec', string>>> = {
  terminal: {
    pass: 'var(--color-terminal-pass)',
    warn: 'var(--color-terminal-warn)',
    stop: 'var(--color-terminal-stop)',
    skip: '#6B6B66',
    fetch: '#C9C9C3',
    cache: 'var(--color-muted)',
    exec: '#C9C9C3',
  },
  plain: {
    pass: 'var(--color-pass)',
    warn: 'var(--color-warn)',
    stop: 'var(--color-stop)',
    skip: 'var(--color-faint)',
    fetch: 'var(--color-ink)',
    cache: 'var(--color-ink2)',
    exec: 'var(--color-ink)',
  },
};

/** Text, dot and colour of a log line in Plain or Terminal mode (prototype `logLines`). */
export function logLineView(l: LogLine, mode: LogMode): LogLineView {
  const term = mode === 'terminal';
  const C = LOG_COLORS[mode];
  let dot: string | null;
  if (l.result) dot = C[l.result] ?? null;
  else if (l.kind === 'fetch') dot = 'var(--color-accent)';
  else if (l.kind === 'exec') dot = 'var(--color-docking)';
  else dot = term ? 'var(--color-ink2)' : '#D7D7D2';
  let color: string | undefined;
  if (term) {
    color = l.kind === 'layer' ? '#fff' : l.result ? C[l.result] : C[l.kind as 'fetch' | 'cache' | 'exec'];
  } else {
    color = l.kind === 'layer' ? 'var(--color-ink)' : l.result === 'stop' ? 'var(--color-stop)' : l.result === 'warn' ? 'var(--color-accent-deep)' : 'var(--color-ink2)';
  }
  return { text: (term ? l.text : l.plain) || l.text || l.plain || '', dot, color, weight: l.kind === 'layer' ? 500 : 400 };
}

export interface DockingParamView {
  key: string;
  label: string;
  value: string;
  unit?: string;
  /** Value is the register default, not one the record reports. */
  isDefault: boolean;
}

export interface ExecutorRowModel {
  key: string;
  tool: string;
  text: string;
  state: 'loading' | 'ok' | 'not_run';
  params?: DockingParamView[];
}

/** Docking parameters of a tool: values the record reports, else the register's defaults. */
export function dockingParams(record: UiRunRecord | null | undefined, toolId: string, register: Tool[] | null | undefined): DockingParamView[] {
  const tool = toolById(record, toolId, register);
  const card = record?.docking && (record.docking.toolId === tool.id || record.docking.tool === tool.name) ? record.docking : null;
  return (tool.dockingParams ?? []).map((p) => {
    const reported = card?.params?.find((x) => x.key === p.key)?.value;
    const value = reported ?? p.default;
    return { key: p.key, label: p.label, value: value ?? DASH, unit: value !== undefined ? p.unit : undefined, isDefault: reported === undefined && value !== undefined };
  });
}

/** Executor rows (prototype `rj.execution`), from the record's execution lines or its tools. */
export function executorRows(job: Job, record: UiRunRecord | null | undefined, register: Tool[] | null | undefined): ExecutorRowModel[] {
  const queued = job.status === 'queued';
  const tools = jobTools(job, record, register).map((t) => toolById(record, t.id, register));
  const paramsFor = (id: string | undefined) => {
    if (!id) return undefined;
    const t = toolById(record, id, register);
    return familyOf(t) === 'docking' && t.dockingParams?.length ? dockingParams(record, id, register) : undefined;
  };
  if (record?.executionLines?.length) {
    return record.executionLines.map((e, i) => {
      const t = tools.find((x) => x.name === e.tool || x.id === e.tool);
      return { key: `${e.tool}-${i}`, tool: e.tool, text: e.plain || e.text, state: queued ? 'loading' : 'ok', params: paramsFor(t?.id) };
    });
  }
  return tools.map((t) => {
    const notRun = t.ran === false;
    const parts = [notRun ? 'not run (checks only)' : t.version ? `version ${t.version}` : ''];
    if (t.checkpoint) parts.push(`checkpoint ${t.checkpoint}`);
    return {
      key: t.id,
      tool: toolLabel({ name: t.name, version: t.version ?? null }),
      text: parts.filter(Boolean).join(' · ') || DASH,
      state: queued ? 'loading' : notRun ? 'not_run' : 'ok',
      params: paramsFor(t.id),
    };
  });
}

/** Two or three mono lines of inputs (prototype `inputsLine1`/`inputsLine2`, plus the ligand). */
export function inputLines(record: UiRunRecord | null | undefined, job: Pick<Job, 'seeds'>): string[] {
  const inp = record?.inputs ?? {};
  const first = [inp.target ? `${inp.target}${inp.partner ? ` + ${inp.partner}` : ''}` : '', inp.reference ?? '', inp.ph !== undefined && inp.ph !== null ? `pH ${inp.ph}` : ''].filter(Boolean);
  const seeds = inp.seeds ?? (job.seeds || undefined);
  const second = [seeds ? `${seeds} seeds${inp.samples ? ` × ${inp.samples} samples` : ''}` : '', inp.assembly ?? ''].filter(Boolean);
  const out = [first.join(' · ') || DASH];
  if (second.length) out.push(second.join(' · '));
  if (inp.ligand) out.push(inp.ligand);
  return out;
}

/** `20 pass · 1 warn · 1 stop` plus muted skip (prototype `rj.verdictCounts`). */
export function verdictCounts(t: CheckTotals): { text: string; skip?: string } {
  return { text: `${t.pass} pass · ${t.warn} warn · ${t.stop} stop`, skip: t.skip ? ` · ${t.skip} skip` : undefined };
}


// ---------------------------------------------------------------- endpoints, fit and execution (new run)

/** Readable endpoint names (configs/models.yaml endpoints and task_endpoints). */
const ENDPOINT_LABELS: Record<string, string> = {
  pose: 'pose',
  structure: 'structure',
  interface: 'interface',
  affinity_series: 'affinity series',
  score_within_run: 'score within run',
};

export function endpointLabel(e: string): string {
  return ENDPOINT_LABELS[e] ?? e.replace(/_/g, ' ');
}

export type ToolGroup = 'co-folding' | 'docking' | 'ppi';
export const TOOL_GROUP_LABELS: Record<ToolGroup, string> = { 'co-folding': 'Co-folding', docking: 'Docking', ppi: 'PPI docking' };
const GROUP_ORDER: ToolGroup[] = ['co-folding', 'docking', 'ppi'];

/**
 * co-folding | docking | ppi. A docking tool is PPI docking when its endpoints are protein–protein
 * only (interface, no pose) or its role says so. Unknown families count as co-folding (prototype).
 */
export function toolGroup(t: Pick<Tool, 'family' | 'role'> & { endpoints?: string[] }): ToolGroup {
  if (familyOf(t) !== 'docking') return 'co-folding';
  const e = t.endpoints ?? [];
  if ((e.includes('interface') && !e.includes('pose')) || /protein.protein/i.test(t.role ?? '')) return 'ppi';
  return 'docking';
}

export interface ToolFit {
  ok: boolean;
  /** false when neither the task nor the tool says which endpoints apply (then ok). */
  known: boolean;
  endpoint: string | null;
  /** `cannot produce pose for ligand pose`, null when the tool fits. */
  reason: string | null;
}

/**
 * Whether `tool` can report the endpoint the task's claim needs: from Task.compatibleTools when the
 * API lists them, else from Tool.endpoints. Unknown on either side counts as a fit (no warning).
 */
export function toolFit(tool: { id: string; endpoints?: string[] } | null | undefined, task: Task | null | undefined): ToolFit {
  const endpoint = task?.endpoint ?? null;
  if (!task || !endpoint || !tool) return { ok: true, known: false, endpoint, reason: null };
  let ok: boolean | null = null;
  if (Array.isArray(task.compatibleTools) && task.compatibleTools.length) ok = task.compatibleTools.includes(tool.id);
  else if (Array.isArray(tool.endpoints)) ok = tool.endpoints.includes(endpoint);
  if (ok === null) return { ok: true, known: false, endpoint, reason: null };
  return { ok, known: true, endpoint, reason: ok ? null : `cannot produce ${endpointLabel(endpoint)} for ${task.name.toLowerCase()}` };
}

/**
 * The task's default tools that fit its endpoint. When none fits, the first available register
 * tool that does (none: an empty list; the plan then asks for a tool).
 */
export function taskDefaultTools(task: Task | null | undefined, register?: Tool[] | null): string[] {
  const defaults = task?.defaultTools ?? [];
  const find = (id: string) => register?.find((t) => t.id === id) ?? { id };
  const fit = defaults.filter((id) => toolFit(find(id), task).ok);
  if (fit.length || !defaults.length) return [...fit];
  const alt = (register ?? []).find((t) => t.available !== false && toolFit(t, task).ok && toolFit(t, task).known);
  return alt ? [alt.id] : [];
}

/** `A100 · Modal`, `CPU · local`, `checks only`; null when the register says nothing. */
export function toolRunLabel(t: Pick<Tool, 'dispatchable' | 'gpu' | 'available'>): string | null {
  if (t.dispatchable === false) return 'checks only';
  if (t.dispatchable !== true) return null;
  return t.gpu ? `${t.gpu} · Modal` : 'CPU · local';
}

/** True when some selected tool can be dispatched (Tool.dispatchable). */
export function canExecute(ids: string[], register: Tool[] | null | undefined): boolean {
  return ids.some((id) => register?.find((t) => t.id === id)?.dispatchable === true);
}

/** RunSettings.execute: the user's choice, else on when a selected tool can be dispatched. */
export function effectiveExecute(form: Pick<RunForm, 'tools' | 'execute'>, register: Tool[] | null | undefined): boolean {
  return typeof form.execute === 'boolean' ? form.execute : canExecute(form.tools, register);
}

/** Inputs the task needs that the form lacks (`series` is met by a ligand or an uploaded series file). */
export function missingInputs(form: Pick<RunForm, 'target' | 'partner' | 'ligand'>, task: Task | null | undefined, opts: { seriesFile?: boolean } = {}): string[] {
  const inputs = taskInputs(task);
  const kind = taskKind(task);
  const need = inputs ?? (kind === 'complex' ? ['target', 'partner'] : kind === 'ligand' ? ['target', 'ligand'] : ['target']);
  const out: string[] = [];
  if (need.includes('target') && !form.target.trim()) out.push('target');
  if (need.includes('partner') && !form.partner.trim()) out.push('partner');
  if (need.includes('ligand') && !form.ligand.trim()) out.push('ligand');
  if (need.includes('series') && !form.ligand.trim() && !opts.seriesFile) out.push('series');
  return out;
}

export interface PlanToolRow {
  id: string;
  name: string;
  available: boolean;
  note: string;
  /** `A100 · Modal`, `CPU · local`, `checks only`, or null when unknown. */
  run: string | null;
  dispatchable: boolean | null;
  fit: ToolFit;
}

export type PlanWarningKind = 'endpoint' | 'input' | 'unavailable' | 'execute' | 'tools';

export interface PlanWarning {
  kind: PlanWarningKind;
  text: string;
}

export interface RunPlanModel {
  tools: PlanToolRow[];
  warnings: PlanWarning[];
  /** RunSettings.execute for this form. */
  execute: boolean;
  /** Some selected tool can be dispatched. */
  canExecute: boolean;
  /** `Start run` (executors run) or `Check inputs` (pre-run check). */
  startLabel: string;
  /** One line under the switch. */
  mode: string;
}

/** The run plan: tools with route and fit, the warnings the run carries, the execute switch. */
export function runPlanModel(form: RunForm, task: Task | null | undefined, register: Tool[] | null | undefined, opts: { seriesFile?: boolean; extraWarnings?: string[] } = {}): RunPlanModel {
  const tools: PlanToolRow[] = form.tools.map((id) => {
    const t = register?.find((x) => x.id === id);
    return {
      id,
      name: t?.name ?? id,
      available: t?.available !== false,
      note: t?.note ?? '',
      run: t ? toolRunLabel(t) : null,
      dispatchable: typeof t?.dispatchable === 'boolean' ? t.dispatchable : null,
      fit: toolFit(t ?? { id }, task),
    };
  });
  const warnings: PlanWarning[] = [];
  if (!tools.length) warnings.push({ kind: 'tools', text: 'no executor selected' });
  for (const t of tools) if (!t.fit.ok && t.fit.reason) warnings.push({ kind: 'endpoint', text: `${t.name} ${t.fit.reason}` });
  for (const t of tools) if (!t.available) warnings.push({ kind: 'unavailable', text: `${t.name} not available${t.note ? `: ${t.note}` : ''}` });
  for (const m of missingInputs(form, task, opts)) warnings.push({ kind: 'input', text: `missing input: ${m}` });
  for (const w of opts.extraWarnings ?? []) if (!warnings.some((x) => x.text === w)) warnings.push({ kind: 'endpoint', text: w });
  const can = canExecute(form.tools, register);
  const execute = effectiveExecute(form, register);
  if (execute && !can && tools.length) warnings.push({ kind: 'execute', text: 'no selected executor can be dispatched: the run checks inputs only' });
  const runs = execute && can;
  return {
    tools,
    warnings,
    execute,
    canExecute: can,
    startLabel: runs ? 'Start run' : 'Check inputs',
    mode: runs ? 'Executors run, then layers 4–5 check their outputs.' : 'Pre-run check: layers 0–3 only. Output checks wait for predictions.',
  };
}

// ---------------------------------------------------------------- prompt tokens (click or drag into the request)

export type PromptTokenKind = 'tool' | 'target' | 'ligand';

export interface PromptToken {
  kind: PromptTokenKind;
  /** Tool id, UniProt accession or ligand SMILES. */
  id: string;
  /** Text inserted into the request (`Boltz-2`, `ABL1 kinase P00519`, `imatinib`). */
  text: string;
}

/** dataTransfer type of a dragged chip. */
export const TOKEN_MIME = 'application/x-dock-harness-token';

export function toolToken(t: Pick<Tool, 'id' | 'name'>): PromptToken {
  return { kind: 'tool', id: t.id, text: t.name };
}

export function targetToken(p: TargetOption): PromptToken {
  const label = (p.label ?? '').trim();
  const text = !label || label.toUpperCase() === p.accession.toUpperCase() ? p.accession : `${label} ${p.accession}`;
  return { kind: 'target', id: p.accession, text };
}

export function ligandToken(l: LigandOption): PromptToken {
  const name = l.names?.[0] ?? '';
  const text = l.custom ? (l.smiles.length <= 40 ? l.smiles : name || l.smiles.slice(0, 40)) : name || l.smiles;
  return { kind: 'ligand', id: l.smiles, text };
}

export function serializeToken(t: PromptToken): string {
  return JSON.stringify(t);
}

export function parseToken(raw: string | null | undefined): PromptToken | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as Partial<PromptToken>;
    if ((v.kind === 'tool' || v.kind === 'target' || v.kind === 'ligand') && typeof v.id === 'string' && typeof v.text === 'string') return { kind: v.kind, id: v.id, text: v.text };
  } catch {
    /* not a token */
  }
  return null;
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Whether `token` appears in `text` as a whole phrase (case-insensitive). */
export function hasToken(text: string, token: string): boolean {
  if (!token.trim()) return false;
  return new RegExp(`(^|[^\\w-])${escapeRe(token)}(?=$|[^\\w-])`, 'i').test(text);
}

/**
 * Insert `token` at `at` (default: the end) with one space on each side; unchanged when the text
 * already names it. Returns the text and the caret after the token.
 */
export function insertToken(text: string, token: string, at?: number | null): { text: string; caret: number } {
  if (!token.trim() || hasToken(text, token)) return { text, caret: at ?? text.length };
  const pos = at === null || at === undefined || at < 0 || at > text.length ? text.length : at;
  const before = text.slice(0, pos);
  const after = text.slice(pos);
  const lead = before && !/\s$/.test(before) ? ' ' : '';
  const trail = after && !/^[\s,.?!]/.test(after) ? ' ' : '';
  const out = `${before}${lead}${token}${trail}${after}`;
  return { text: out, caret: before.length + lead.length + token.length + trail.length };
}

/** Remove a whole-phrase `token` from `text`, tidying the spaces it leaves. */
export function removeToken(text: string, token: string): string {
  if (!token.trim()) return text;
  const re = new RegExp(`(^|[^\\w-])${escapeRe(token)}(?=$|[^\\w-])`, 'i');
  if (!re.test(text)) return text;
  return text
    .replace(re, '$1')
    .replace(/\s+(,|\.)/g, '$1')
    .replace(/ {2,}/g, ' ')
    .replace(/\b(and|with|,)\s+(and|with)\b/gi, '$2')
    .replace(/\s+(and|with)\s*$/i, '')
    .trim();
}

/** Replace the token `prev` (when present) by `next`, else insert `next`. */
export function replaceToken(text: string, prev: string | null | undefined, next: string, at?: number | null): { text: string; caret: number } {
  if (prev && prev !== next && hasToken(text, prev) && !hasToken(text, next)) {
    const re = new RegExp(`(^|[^\\w-])${escapeRe(prev)}(?=$|[^\\w-])`, 'i');
    const m = re.exec(text);
    const out = text.replace(re, `$1${next}`);
    const caret = m ? m.index + m[1].length + next.length : out.length;
    return { text: out, caret };
  }
  return insertToken(text, next, at);
}
