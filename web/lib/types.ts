// Shared shapes for the Harness UI. docs/UI.md is the contract; the Python API returns the same keys
// (camelCase on the wire). Fields marked "UI addition" are optional extensions the prototype views
// read; the live API may omit them, and the UI then shows "not computed".

export type Outcome = 'supported' | 'narrowed' | 'refused' | 'incomplete';
export type Result = 'pass' | 'warn' | 'stop' | 'skip' | 'reported' | 'pending';
export type Gate = 'Stop' | 'Warn' | 'Reported';
export type JobStatus = 'queued' | 'running' | 'done' | 'failed';
export type LayerStatus = 'done' | 'running' | 'pending' | 'not_run';
export type ToolFamily = 'co-folding' | 'docking';
export type HarnessMode = 'live' | 'mock';

export const LAYER_COUNT = 6;

// ---------------------------------------------------------------- health

/** Upstream `GET /health` returns {status: "ok", version, profile}; the mock returns {ok, mode: "mock"}. */
export interface Health {
  status?: string;
  ok?: boolean;
  version?: string;
  profile?: string;
  runs_dir?: string;
  mode?: HarnessMode;
}

// ---------------------------------------------------------------- jobs and logs

export interface JobLayer {
  i: number;
  result: Result | null;
  done: boolean;
}

export interface Job {
  id: string;
  runId: string;
  name: string;
  task: string;
  taskName: string;
  tools: string[];
  seeds: number;
  status: JobStatus;
  /** Layer currently running, 6 when done. */
  layerIdx: number;
  /** 0..1 within layerIdx. */
  progress: number;
  elapsedMs: number;
  createdAt: string;
  /** Six entries, worst result per layer. */
  layers: JobLayer[];
  verdict: Outcome | null;
  /** Live API: the harness's own run id (runs/<id>/record.json runId). */
  harnessRunId?: string;
  /** Live API: checks finished so far and checks listed by the task. */
  checksDone?: number;
  checksTotal?: number;
  /** Live API: report generation status (e.g. "done"). */
  reportStatus?: string;
}

export type LogKind = 'fetch' | 'cache' | 'check' | 'layer' | 'exec' | 'run' | 'artifact' | 'log';

export interface LogLine {
  seq: number;
  ts: string;
  /** Seconds since run start, e.g. "12.4s". */
  t: string;
  /** 0..5, or null for run-level lines. */
  layer: number | null;
  kind: LogKind;
  result?: Result;
  /** Terminal line. */
  text: string;
  /** One plain sentence. */
  plain: string;
}

// ---------------------------------------------------------------- tools and tasks

export type ToolOutputKind =
  | 'confidence'
  | 'interface'
  | 'affinity'
  | 'score'
  | 'rmsd'
  | 'plddt'
  | 'pae'
  | 'other';
export type ToolOutputScope = 'global' | 'interface' | 'ligand' | 'pose' | 'residue';

/** One parsed field an executor reports (docs/EXECUTORS.md "Parsed fields"). */
export interface ToolOutput {
  key: string;
  label: string;
  unit?: string;
  kind: ToolOutputKind;
  scope: ToolOutputScope;
  range?: [number, number];
  higherIsBetter?: boolean;
  /** Shown on its own line below the accent rule, never as pose quality. */
  rankingOnly?: boolean;
  note?: string;
}

export interface DockingParam {
  key: string;
  label: string;
  unit?: string;
  default?: string;
}

export interface ToolRuntime {
  profiles: string[];
  gpu?: string;
  accel?: boolean;
}

export interface Tool {
  id: string;
  name: string;
  family: ToolFamily;
  version: string | null;
  role: string;
  available: boolean;
  note?: string;
  licence?: string;
  repo?: string;
  runtime?: ToolRuntime;
  outputs: ToolOutput[];
  dockingParams?: DockingParam[];
  /** UI addition: entry added by the user through the "+ executor" input. */
  custom?: boolean;
}

export type TaskGroup = 'co-folding' | 'docking';
export type TaskKind = 'monomer' | 'complex' | 'ligand';

export interface Task {
  id: string;
  group: TaskGroup;
  kind: TaskKind;
  name: string;
  long: string;
  defaultTools: string[];
  claim: string;
  controls: string[];
  inputs: string[];
  /** Live API: number of the task's checks that are registered. Absent in mock mode. */
  implemented?: number;
  /** Live API: number of checks the task spec lists. Absent in mock mode. */
  checks?: number;
}

// ---------------------------------------------------------------- run settings and interpreter

export interface RunSettings {
  task: string;
  tools: string[];
  target: string;
  partner?: string;
  ligand?: string;
  reference: string;
  ph: number;
  seeds: number;
  name?: string;
}

export type StepField =
  | 'task'
  | 'tools'
  | 'target'
  | 'partner'
  | 'ligand'
  | 'seeds'
  | 'ph'
  | 'reference'
  | 'claim';

export interface Step {
  field: StepField | string;
  value: string | number | string[];
  because: string;
}

export interface InterpretResult {
  settings: RunSettings;
  steps: Step[];
}

/** `GET /ui/examples`: example manifests with task and claim. Extra keys pass through. */
export interface ExampleManifest {
  path: string;
  task?: string;
  claim?: string;
  name?: string;
  [key: string]: unknown;
}

export interface StartRunResult {
  jobId: string;
  runId: string;
}

// ---------------------------------------------------------------- entities and catalog

export interface EntityGroup {
  key: string;
  kind: 'protein' | 'ligand';
  title: string;
  source: string;
  query: string;
  /** Resolver latency in ms (mock: simulated). */
  ms: number;
  rows: [string, string][];
}

export interface CatalogProtein {
  names: string[];
  accession: string;
  entry: string;
  label: string;
  organism: string;
  length: number;
  pdb: string;
  resolution: string;
  holo: number;
  afPlddt: number;
  sites: number;
  domains: string;
  disorder: string;
  cofactors: string;
  custom?: boolean;
}

export interface CatalogLigand {
  names: string[];
  smiles: string;
  ccd: string;
  cid: string;
  chembl: string;
  formula: string;
  mw: number | string;
  inchikey: string;
  activities: number;
  stereo: number;
  pka: string;
  custom?: boolean;
}

export interface Catalog {
  proteins: CatalogProtein[];
  ligands: CatalogLigand[];
}

// ---------------------------------------------------------------- uploads

export interface UploadedFile {
  name: string;
  size: number;
  sha256: string;
  kind: string;
  status: 'ok' | 'error' | 'loading';
  detail: string;
}

export interface UploadResult {
  files: UploadedFile[];
}

// ---------------------------------------------------------------- agent monitor

export type AgentStepKind = 'thought' | 'tool' | 'result' | 'report' | 'conclusion';
export type AgentTaskStatus = 'queued' | 'running' | 'done' | 'failed';

export interface AgentStep {
  seq: number;
  ts: string;
  kind: AgentStepKind;
  text: string;
  ms?: number;
  data?: Record<string, unknown>;
}

export interface AgentOutcome {
  label: string;
  detail?: string;
  runs?: number;
  reports?: number;
}

export interface AgentTask {
  id: string;
  goal: string;
  status: AgentTaskStatus;
  createdAt: string;
  /** 0..1. */
  progress: number;
  /** Steps reported so far. The step stream is the source of truth for the timeline. */
  steps?: AgentStep[];
  outcome: AgentOutcome | null;
  /** UI addition: total planned steps when known (mock), otherwise absent. */
  stepsTotal?: number;
  /** UI addition: elapsed time of the task when known. */
  elapsedMs?: number;
}

// ---------------------------------------------------------------- run record

export interface Measurement {
  name: string;
  value: number | string | boolean | null;
  unit?: string | null;
}

export interface ThresholdDef {
  name: string;
  value: number | string | boolean;
  comparator: string;
  origin: string;
  evidenceLevel: string;
}

export interface UiCheck {
  id: string;
  name: string;
  tool?: string;
  gate: Gate;
  result: Result;
  evidence?: string;
  ms?: number;
  threshold?: { value: string; origin: string; evidenceLevel: string };
  message?: string;
  skipReason?: string;
  measurements?: Measurement[];
  thresholds?: ThresholdDef[];
}

/** Tool entry in a record: Tool-compatible, carries `outputs` when the register knows the tool. */
export type RecordTool = Omit<Partial<Tool>, 'id' | 'name' | 'version'> & {
  id: string;
  name: string;
  version: string | null;
  family?: ToolFamily;
  container?: string;
  /** Live API: version declared in the manifest. */
  declaredVersion?: string;
  checkpoint?: string;
  /** Live API: whether the executor ran in this run (false = outputs supplied, not executed). */
  ran?: boolean;
};

export interface RecordSource {
  /** Live API: provenance object id, e.g. "uniprot:P00760:2daae107e8c8". */
  id?: string;
  /** Live API: source client id, e.g. "uniprot". */
  sourceId?: string;
  /** Live API: check ids that used this object. */
  usedBy?: string[];
  source: string;
  supplies?: string;
  accession: string;
  release: string;
  sha256: string;
  retrievedAt: string;
  cached?: boolean;
  ms?: number;
  url?: string;
  sizeBytes?: number;
  version?: string;
}

export type LayerKey =
  | 'provenance'
  | 'integrity'
  | 'adequacy'
  | 'applicability'
  | 'validity'
  | 'support';

export interface RecordLayer {
  i: number;
  key: LayerKey | string;
  name: string;
  question: string;
  durationMs?: number;
  status: LayerStatus;
  counts: Partial<Record<Result, number>>;
  summary?: string[];
  figures?: [string, string][];
  checks: UiCheck[];
}

export interface Verdict {
  claim: string;
  /** null while the run is in progress (live API). */
  outcome: Outcome | null;
  statement: string;
  stops: string[];
  warnings: string[];
  incomplete?: string[];
  /** Live API: layers the verdict covers, e.g. "layers 0,1". */
  scope?: string;
  notApplicable?: string[];
}

// ----- stats blocks (all optional: absent means not computed)

export interface SeedStat {
  seed: number;
  rmsdToMedoid: number;
  cluster: number;
  confidence: number;
}
export interface AgreementCell {
  vs: string;
  value: number;
  unit: string;
  weight: string;
}
export interface AgreementRow {
  method: string;
  cells: AgreementCell[];
}
export interface PerturbationRow {
  name: string;
  construction: string;
  expected: string;
  observed: string;
  ok: boolean;
}
export interface CalibrationPoint {
  x: number;
  passed: number;
  flagged: number;
}
export interface UiMetric {
  name: string;
  value: string;
  read?: string;
  /** Display name of the tool that produced the value. */
  tool?: string;
  /** UI addition: register id of the producing tool, links the metric to a ToolOutput. */
  toolId?: string;
  /** UI addition: ToolOutput.key of the value. */
  key?: string;
  /** Ranking-only score, shown below the accent rule. */
  separate?: boolean;
}
export interface InteractionRow {
  residue: string;
  type: string;
  distance: number;
  known: boolean;
}
export type StructureKind = 'crystal' | 'medoid' | 'seed' | 'docking' | 'model';
export interface EnsembleEntry {
  id: string;
  label: string;
  kind: StructureKind;
  source: string;
  /** UI addition: register id of the producing tool (absent for crystal). */
  toolId?: string;
  rmsdToMedoid: number;
  pocketPlddt: number | null;
  iptm: number | null;
  cnn?: number | null;
  posebusters: number | null;
  cluster: number | null;
  /** UI addition: values keyed by ToolOutput.key of the producing tool. */
  values?: Record<string, number | null>;
}
export interface PairwiseStat {
  median: number;
  iqr: [number, number];
  ci95: [number, number];
  n: number;
}
export interface RocPoint {
  fpr: number;
  tpr: number;
}
export interface PoseBustersTest {
  test: string;
  pass: boolean;
  value: string;
}
export interface PhysicsRow {
  seed: number;
  drift: number;
  torsions: number;
  clashes: number;
  strain: number;
  unsatisfied: number;
  pbPassed: number | null;
  clashscore: number;
  rama: number;
}

export interface UiStats {
  seeds?: SeedStat[];
  agreement?: AgreementRow[];
  perturbation?: PerturbationRow[];
  calibration?: CalibrationPoint[];
  metrics?: UiMetric[];
  interactions?: InteractionRow[];
  ensemble?: EnsembleEntry[];
  pairwise?: PairwiseStat;
  roc?: RocPoint[] | null;
  posebusters?: PoseBustersTest[];
  physics?: PhysicsRow[];
  site?: [string, string][];
  pose?: [string, string][];
  auc?: number | null;
  enrichment?: string | null;
  sitePlacement?: string;
  poseAccuracy?: string;
  [key: string]: unknown;
}

export interface RecordThreshold {
  name: string;
  value: string;
  origin: string;
  level: string;
}

export interface ExecutionLine {
  tool: string;
  text: string;
  plain: string;
}

export interface DockingCard {
  tool: string;
  /** UI addition: register id of the docking tool. */
  toolId?: string;
  rows: [string, string][];
  /** UI addition: parameter values keyed by Tool.dockingParams[].key. */
  params?: { key: string; label: string; value: string; unit?: string }[];
}

/** `url` is a native API path (/runs/{id}/files/...): pass it through HarnessApi.assetUrl(). */
export interface RecordStructure {
  id: string;
  label: string;
  kind: StructureKind;
  url: string;
  format: 'mmcif' | 'pdb' | 'sdf';
  artifactKind?: string;
  path?: string;
  sha256?: string;
}

/** `png` and `pse` are native API paths: pass them through HarnessApi.assetUrl(). */
export interface RecordRender {
  structure: string;
  png: string;
  pse: string;
  view: string;
  caption?: string;
  alt?: string;
}

export interface RecordFigure {
  id: string;
  url: string;
  caption?: string;
  alt?: string;
  /** CSV with the plotted numbers. */
  data?: string;
}

/** Live API: report generation result (paths are native API paths). */
export interface RecordReport {
  status: string;
  reports?: Record<string, string>;
  graph?: Record<string, string>;
  figures?: RecordFigure[];
  renderErrors?: unknown[];
  limitations?: string[];
}

/** Live API: one file the run read or wrote, with provenance. */
export interface RecordArtifact {
  path: string;
  kind: string;
  label?: string;
  sha256?: string;
  sizeBytes?: number;
  /** Native API path, or null for inputs outside runs/<id>/. */
  url: string | null;
  derivedFrom?: string[];
}

export interface RecordMeta {
  hardware?: string;
  scheduler?: string;
  containers?: string[];
  seeds?: number[];
  pahVersion?: string;
  toolVersions?: Record<string, string>;
  /** Prototype fields. */
  acceleratedMode?: string;
  notebook?: string;
  /** Live API fields. */
  runId?: string;
  startedAt?: string;
  finishedAt?: string;
  layersSelected?: number[];
  profile?: string;
}

export interface UiRunRecord {
  id: string;
  createdAt: string;
  /** Live API: run status (e.g. "running", "done"). */
  status?: string;
  task: string;
  taskName: string;
  claim: string;
  tools: RecordTool[];
  inputs: {
    target?: string;
    partner?: string | null;
    ligand?: string | null;
    reference?: string;
    ph?: number;
    seeds?: number;
    samples?: number;
    assembly?: string;
  };
  sources: RecordSource[];
  layers: RecordLayer[];
  verdict: Verdict;
  /** Only keys the harness computed; absent means not computed. */
  stats: UiStats;
  narrative: string[];
  controls: { name: string; status: string; note?: string; check?: string }[];
  outputs: string[];
  record: RecordMeta;
  structures?: RecordStructure[];
  renders?: RecordRender[];
  /** UI addition (prototype): threshold table. */
  thresholds?: RecordThreshold[];
  /** UI addition (prototype): executor lines for the job view. */
  execution?: ExecutionLine[];
  /** UI addition (prototype): docking stat card. */
  docking?: DockingCard | null;
  /** Live API: report, graph and figure files. */
  report?: RecordReport;
  /** Live API: files read or written by the run. */
  artifacts?: RecordArtifact[];
  source: 'pah' | 'mock';
}
