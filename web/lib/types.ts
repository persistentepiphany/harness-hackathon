// Shared shapes for the Harness UI. docs/UI.md is the contract; the Python API returns the same keys
// (camelCase on the wire). Fields marked "UI addition" are optional extensions the prototype views
// read; the live API may omit them, and the UI then shows "not computed".

/** `not_assessed`: the claim needs output evidence (layers 4-5) and none ran, e.g. a pre-run check. */
export type Outcome = 'supported' | 'narrowed' | 'refused' | 'incomplete' | 'not_assessed';
/** `pre-run`: no executor outputs in the run (nothing predicted); `full`: predictions were checked. */
export type Assessment = 'pre-run' | 'full';
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
  /** Live API: checks of the layer whose skip leaves the verdict incomplete (tool missing, error). */
  incomplete?: string[];
  /** Live API: output checks of the layer waiting for predictions (result 'pending' when all are). */
  pending?: string[];
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
  /** Live API: pre-run when the run holds no executor outputs. */
  assessment?: Assessment;
  /** Live API: one entry per executor the run dispatched (execution events). */
  execution?: UiExecution[];
}

// ---------------------------------------------------------------- execution (executor progress)

export type ExecutionPhase = 'queued' | 'building' | 'running' | 'done' | 'failed' | 'skipped';
export type ExecutionRoute = 'kit' | 'stock' | 'local';

export interface UiExecutionSeed {
  seed: number;
  phase: ExecutionPhase | string;
  ms?: number | null;
}

/** Aggregated execution events of one executor (events.jsonl data.stage == "execute"). */
export interface UiExecution {
  executor: string;
  name: string;
  phase: ExecutionPhase;
  gpu?: string | null;
  route?: ExecutionRoute | null;
  routeNote?: string | null;
  startedAt?: string | null;
  elapsedMs?: number | null;
  seeds: UiExecutionSeed[];
  message?: string | null;
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
  /** Live API: endpoints the tool can report (configs/models.yaml models[*].endpoints). */
  endpoints?: string[];
  /** Live API: whether the harness can dispatch the executor (RunSettings.execute). */
  dispatchable?: boolean;
  gpu?: string | null;
}

/** `POST /ui/tools` body: an executor entered as `name:version` (the whole input as `image`). */
export interface AddToolSpec {
  name: string;
  version?: string | null;
  image?: string;
}

export type TaskGroup = 'co-folding' | 'docking' | 'protein-protein';
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
  /** Live API: endpoint the claim needs (configs/models.yaml task_endpoints). */
  endpoint?: string | null;
  /** Live API: executor ids (Tool.id) whose endpoints include `endpoint`. */
  compatibleTools?: string[];
  /** Live API: offered in Quick setup and by the interpreter (configs/catalog.yaml). */
  quickSetup?: boolean;
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
  /** Optional model checkpoint for the selected tools (backend accepts it in the manifest). */
  checkpoint?: string;
  /** Optional database snapshot (e.g. MSA database release) recorded in the manifest. */
  databaseSnapshot?: string;
  /** true: run the selected executors (GPU ones on Modal); false or absent: pre-run checks only. */
  execute?: boolean;
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
  /** Live API: problems with the request kept as the user wrote it (e.g. a tool that lacks the endpoint). */
  warnings?: string[];
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
  /** Live API and mock: 'error' when the source returned nothing (see `message`). */
  status?: 'ok' | 'error';
  message?: string;
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
  /** Live API: sample requests that map onto Quick setup tasks (configs/catalog.yaml `prompts`). */
  prompts?: string[];
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
  /** null when the log did not record a duration (live). */
  ms?: number | null;
  data?: Record<string, unknown> | null;
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
  /**
   * Steps reported so far. The live task list returns a count; the mock (and task detail) return
   * the steps. The step stream is the source of truth for the timeline.
   */
  steps?: number | AgentStep[];
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
  /** Live API: name of the measurement the check compared with this threshold, when it differs. */
  measurement?: string;
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

/**
 * Why a check was skipped. `pending_input`: an output check (layers 4-5) waiting for predictions;
 * `not_applicable`: the check does not apply to the run (no MSA for a docking tool, and so on).
 */
export type SkipReason = 'pending_input' | 'not_applicable' | 'not_implemented' | 'tool_missing' | 'error' | string;

export type DimensionId = 'inputs' | 'applicability' | 'geometry' | 'physics' | 'interactions' | 'confidence' | 'support';
export type Certainty = 'calibrated' | 'published' | 'uncalibrated' | 'none';

/** Checks grouped by what they test (configs/catalog.yaml `dimensions`). */
export interface UiDimension {
  id: DimensionId;
  label: string;
  result: 'pass' | 'warn' | 'stop' | 'pending' | 'na';
  checks: number;
  passed: number;
  warned: number;
  stopped: number;
  pending: number;
  /** Weakest evidence level among the thresholds of the non-skip checks. */
  certainty: Certainty;
  checkIds: string[];
}

export interface UiToolVersion {
  name: string;
  version: string | null;
  /** true when some non-skip finding ran with the tool (an executor: its outputs ran); false when only declared. */
  exercised: boolean;
  checks: string[];
  /** `library` (check dependency) or `executor`. */
  kind?: 'library' | 'executor';
  /** Executor id, for kind `executor`. */
  id?: string;
}

/** `GET /ui/glossary`: score keys from configs/executors.yaml and check measurements the UI shows. */
export interface UiGlossaryScore {
  key: string;
  label: string;
  unit?: string | null;
  kind: string;
  producedBy: string[];
  what: string;
  inputs: string[];
  higherIsBetter?: boolean | null;
}

export interface UiGlossary {
  scores: UiGlossaryScore[];
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
  /** Live API: whether the executor's outputs are in this run. */
  ran?: boolean;
  /** Live API: "harness" when this run executed it, "external" when its outputs were supplied, null when not run. */
  ranBy?: 'harness' | 'external' | null;
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
  /** Live API: layers the verdict covers, e.g. "layers 0-3" (evaluated layers only). */
  scope?: string;
  notApplicable?: string[];
  /** Live API: output checks (layers 4-5) waiting for predictions. */
  pending?: string[];
  /** Live API: what was evaluated, e.g. "Inputs fit to run" for a pre-run check; null for a full run. */
  assessedClaim?: string | null;
  /** Live API: the engine's own outcome before scoping (e.g. 'supported' for a pre-run). */
  engineOutcome?: Outcome | null;
}

// ----- stats blocks (all optional: absent means not computed)

export interface SeedStat {
  seed: number;
  rmsdToMedoid: number;
  cluster: number;
  /** Absent when the per-pose value is not a confidence output (then it is `score`). */
  confidence?: number;
  /** Live API: pose id, sample index, producing tool and site distance (Å). */
  pose?: string;
  sample?: number;
  toolId?: string;
  siteDistance?: number;
  /** Live API: ToolOutput.key of `confidence`. */
  confidenceKey?: string;
  /** Live API: ranking-only per-pose value (e.g. a docking score) and its ToolOutput.key. */
  score?: number;
  scoreKey?: string;
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
  /** Live API: check id that reported the value. */
  check?: string;
  note?: string;
  /** Live API: numeric value, unit and kind of the output, whether the register declares the key. */
  number?: number;
  unit?: string;
  kind?: ToolOutputKind;
  declared?: boolean;
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
  /** Live API: RecordStructure.id of the member's structure file. */
  structureId?: string;
  /** Live API: native API path of the member's PNG render (pass through HarnessApi.assetUrl()). */
  render?: string;
  /** Live API: ligand SDF of a docking pose. */
  ligand?: { url?: string; format?: string; path?: string };
  /** Live API: PoseBusters tests run (`posebusters` is the number passed). */
  posebustersTotal?: number;
  /** Live API: whether the register declares a per-residue confidence output for the tool. */
  perResidueConfidence?: boolean;
  perResidueConfidenceKey?: string;
  perResidueConfidenceRange?: [number, number];
  /** Live API: role in the manifest, e.g. "primary", "control:redocking". */
  role?: string;
  pose?: string;
  /** Live API: RMSD to the experimental reference (Å). */
  rmsdToReference?: number;
  seed?: number;
  sample?: number;
  /** Live API: docking mode index (`sample` named by the parser). */
  mode?: number;
  siteDistance?: number;
  globalPlddt?: number;
}
export interface PairwiseStat {
  median: number;
  iqr?: [number, number];
  /** Absent in live records (the clustering check reports median and IQR). */
  ci95?: [number, number];
  n?: number;
  unit?: string;
  poses?: number;
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
/** Mock rows carry every field; live rows carry only the fields a check reported. */
export interface PhysicsRow {
  seed?: number;
  drift?: number;
  torsions?: number;
  clashes?: number;
  strain?: number;
  unsatisfied?: number;
  pbPassed?: number | null;
  clashscore?: number;
  rama?: number;
  /** Live API fields. */
  pose?: string;
  sample?: number;
  torsionsScanned?: number;
  maxTorsionExcess?: number;
  buriedPolar?: number;
  buriedCharged?: number;
  pbTotal?: number;
  pbFailed?: string[];
  converged?: boolean;
}

/** Where a stats block came from (stats.provenance[key] or the block's own `source`). */
export interface StatsSource {
  check?: string | null;
  checks?: string[];
  tool?: string | null;
  version?: string | null;
  field?: string;
  unit?: string | null;
  n?: number;
  [key: string]: unknown;
}

/** Why a stats block is absent: `na` = cannot exist for these tools, `pending` = not computed yet. */
export interface StatsStatus {
  status: 'na' | 'pending';
  reason: string;
}

export interface UiPae {
  /** Live API: present instead of the matrix when the block is not applicable or not computed. */
  status?: 'na' | 'pending' | 'ok';
  reason?: string;
  path?: string;
  url?: string;
  format?: string;
  pose?: string;
  matrix?: number[][];
  tokens?: number;
  binned?: number;
  lines?: string[];
  block?: { rows: [number, number]; cols: [number, number] };
  max?: number;
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
  /** Live API: pose the interaction fingerprint was taken from (representative pose id). */
  interactionsPose?: string;
  /**
   * Live API: PAE of the top-ranked pose (l5.confidence.local evidence.pae): the saved .npy file
   * and its matrix in Å (rounded to 0.01; above 512 tokens, means of `binned` x `binned` blocks).
   */
  pae?: UiPae;
  /** Live API: source of each block, keyed by block name (or `block.field`). */
  provenance?: Record<string, StatsSource>;
  /** Live API: why `agreement` is absent (e.g. na with one executor). */
  agreementStatus?: StatsStatus;
  /** Live API: status of absent blocks keyed by block name (pae, agreement, seeds, ...). */
  status?: Record<string, StatsStatus>;
  [key: string]: unknown;
}

export interface RecordThreshold {
  name: string;
  value: string;
  origin: string;
  level: string;
}

/** Prototype (mock) executor line. Live records carry UiExecution entries instead. */
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

/** One output check result on one pose (from the check's `evidence.poses[]` rows). */
export interface UiPoseCheck {
  id: string;
  name: string;
  /** `reported`: the check gave values for the pose but no per-pose pass/fail. */
  result: Result;
  /** Failed sub-tests (e.g. PoseBusters test names). */
  failed?: string[];
}

export interface UiPoseScore {
  key: string;
  label: string;
  value: number;
  unit?: string | null;
}

/** `png` and `pse` are native API paths: pass them through HarnessApi.assetUrl(). */
export interface RecordRender {
  structure: string;
  png: string;
  pse: string;
  view: string;
  caption?: string;
  alt?: string;
  /** Live API, renders of predicted poses: producing executor, seed, rank (docking mode or sample). */
  executor?: string;
  seed?: number | null;
  rank?: number | null;
  pose?: string | null;
  /** First output of the executor (configs/executors.yaml order) that the pose reports. */
  score?: UiPoseScore | null;
  /** Output checks already reported for the pose; empty while they are pending. */
  checks?: UiPoseCheck[];
}

/** Live API: l0.sources.resolved counts and the receptor chains present (l1.receptor.chains). */
export interface UiSourceSummary {
  check: string;
  identifiers?: number;
  records?: number;
  failed?: number;
  cacheHits?: number;
  chains?: string[];
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
  /** UI addition (prototype): executor lines for the job view (mock records). */
  executionLines?: ExecutionLine[];
  /** Live API: per-executor execution progress, from execution events. */
  execution?: UiExecution[];
  /** Live API: pre-run when the run holds no executor outputs (no predictions to check). */
  assessment?: Assessment;
  /** Live API: layers with at least one non-skip result. */
  evaluatedLayers?: number[];
  dimensions?: UiDimension[];
  toolVersions?: UiToolVersion[];
  /** Live API: output checks per pose (also on each render as `checks`). */
  poseChecks?: { pose: string; checks: UiPoseCheck[] }[];
  sourceSummary?: UiSourceSummary;
  /** UI addition (prototype): docking stat card. */
  docking?: DockingCard | null;
  /** Live API: report, graph and figure files. */
  report?: RecordReport;
  /** Live API: files read or written by the run. */
  artifacts?: RecordArtifact[];
  source: 'pah' | 'mock';
}
