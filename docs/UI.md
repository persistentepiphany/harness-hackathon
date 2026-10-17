# Web UI and HTTP API contract

The web UI in `web/` is a Next.js App Router + Tailwind port of
`web/design/prototype/Harness v2.dc.html`. The prototype is the visual reference: the port must look
the same at 1440x900. `web/design/prototype/HANDOFF.md` maps prototype views to routes and components,
and `web/design/prototype/data/run-record.schema.json` is the record the views render from. This file
fixes the parts the prototype leaves open: the HTTP API that `pah serve` exposes, how the harness's own
run record becomes the UI record, and how live and mock data are switched.

## Processes and ports

| Process | Command | Port |
| --- | --- | --- |
| HTTP API | `.venv/bin/pah serve --port 8000` (upstream FastAPI app + `/ui` routes, `pah[api]` extra) | 8000 |
| Web UI | `cd web && npm run dev` or `npm run build && npm start` | 3000 |

The browser only talks to the Next.js origin. Next.js proxies `/api/harness/:path*` to
`${HARNESS_API_URL}/:path*` (default `http://127.0.0.1:8000`), so SSE and file downloads work without
CORS. The API also allows CORS from `http://localhost:3000` for direct use.

| Variable | Where | Meaning |
| --- | --- | --- |
| `NEXT_PUBLIC_HARNESS_MODE` | web | `live` (default when `HARNESS_API_URL` is set) or `mock` |
| `HARNESS_API_URL` | web server | Base URL of `pah serve` |
| `NEXT_DIST_DIR` | web | Build directory, so parallel dev servers do not share `.next` |
| `PAH_PROFILE` | API | Profile name for `runs_dir` and `cache_dir` (default `local`) |

`mock` mode serves the prototype's data and simulator (`web/lib/mock/`), ported from
`data/runs.js` and `logic-v2.js`. It exists for demos, video recording and a Vercel deployment with no
backend. Every view must render in both modes from the same components; only `lib/harness-api.ts`
knows which mode is active.

## Endpoints

The API is the harness's own FastAPI app, `pah.interfaces.api:create_app(profile, allow_origins)`,
started with `pah serve`. Its native routes stay as they are (`POST /runs` with a manifest,
`GET /runs/{id}` job view, `GET /runs/{id}/events` raw event SSE, `GET /runs/{id}/report`,
`GET /runs/{id}/findings`, `GET /runs/{id}/files/{rel}`, `POST /batches`, `/tasks`, `/checks`,
`/schemas/{name}`, `/health`). The UI routes live in `pah.webui` and are mounted on the same app
under the `/ui` prefix with `app.include_router(pah.webui.ui_router(profile, jobs))`, so they share
the upstream `JobStore` and run pipeline (`pah.service.run_manifest`: checks, reports, PyMOL renders,
provenance graph). The UI reads from disk (`runs/<id>/`), so runs started by the CLI, the MCP
server, a batch or an agent appear and stream the same way as runs started from the UI.

All responses are JSON unless marked SSE. UI route errors are `{"error": {"code", "message"}}`.
The web client calls `/api/harness/ui/...`; files go through the native
`/api/harness/runs/{id}/files/{rel}`.

| Method and path | Returns | Notes |
| --- | --- | --- |
| `GET /health` | upstream health | Native route |
| `GET /ui/jobs` | `Job[]`, newest first | One per directory in `runs_dir` with `events.jsonl` (batches and `agent-*` excluded) |
| `GET /ui/jobs/{id}` | `Job` | |
| `GET /ui/jobs/{id}/log` | SSE of `LogLine` | Replays the file, then tails it until `run_end`; `?format=json` returns `LogLine[]` |
| `GET /ui/runs/{id}/record` | `UiRunRecord` | Built from `record.json`, or from `events.jsonl` while the run is still going |
| `GET /runs/{id}/files/{rel}` | file bytes | Native route; only paths inside `runs/<id>/` |
| `POST /ui/runs` | `{jobId, runId}` (202) | Body `RunSettings`; built into a manifest, started through the upstream `JobStore` |
| `POST /ui/interpret` | `{settings: RunSettings, steps: Step[]}` | Rule-based port of `interpretRun()`; `steps[i] = {field, value, because}` |
| `GET /ui/entities?q=` | `EntityGroup[]` | Same shape as `lookupEntities()`, resolved through `pah.sources` clients |
| `GET /ui/catalog` | `{proteins[], ligands[]}` | From `configs/catalog.yaml` |
| `GET /ui/tools` | `Tool[]` | Executors from `configs/executors.yaml` with outputs and availability |
| `GET /ui/tasks` | `Task[]` | Task specs with `implemented/checks` counts, mapped to UI task ids |
| `GET /ui/examples` | example manifests | `examples/**/manifest.yaml` with task and claim |
| `POST /ui/uploads` | `{files: [{name, size, sha256, kind, status, detail}]}` | Multipart; stored under `runs/uploads/` |
| `GET /ui/agent/tasks` | `AgentTask[]` | From `runs/agent-*/task.json` + `steps.jsonl` |
| `POST /ui/agent/tasks` | `AgentTask` (201) | Body `{goal}` |
| `POST /ui/agent/tasks/{id}/steps` | `AgentStep` (201) | Body `{kind, text, ms?, data?}` |
| `POST /ui/agent/tasks/{id}/finish` | `AgentTask` | Body `{status: "done" or "failed", outcome}` |
| `GET /ui/agent/tasks/{id}/steps` | SSE of `AgentStep` | Replays, then tails until the task finishes |

SSE frames: `event: line` (or `step`) with one JSON object in `data`, `event: end` when the stream is
finished, and a `: ping` comment every 15 s. Each frame carries `id: <seq>` so `Last-Event-ID` resumes.

An agent under test reports what it is doing either through `POST /ui/agent/tasks/...` or by running
`pah agent-log start|step|finish`, which appends to the same files. A run the agent starts with
`pah run`, `pah batch` or the MCP server appears in `/ui/jobs` and streams live, because the UI
routes tail `events.jsonl`.

## Shapes

TypeScript is the reference; Python returns the same keys (camelCase on the wire).

```ts
type Outcome = 'supported' | 'narrowed' | 'refused' | 'incomplete';
type Result = 'pass' | 'warn' | 'stop' | 'skip' | 'reported' | 'pending';

interface Job {
  id: string; runId: string; name: string; task: string; taskName: string;
  tools: string[]; seeds: number;
  status: 'queued' | 'running' | 'done' | 'failed';
  layerIdx: number;             // layer currently running, 6 when done
  progress: number;             // 0..1 within layerIdx
  elapsedMs: number; createdAt: string;
  layers: { i: number; result: Result | null; done: boolean }[];   // 6 entries, worst result per layer
  verdict: Outcome | null;
}

interface LogLine {
  seq: number; ts: string; t: string;   // t = seconds since run start, "12.4s"
  layer: number | null;                 // 0..5 or null for run-level lines
  kind: 'fetch' | 'cache' | 'check' | 'layer' | 'exec' | 'run' | 'artifact' | 'log';
  result?: Result; text: string;        // text = terminal line, plain = one sentence
  plain: string;
}

interface UiCheck {               // schema $defs/check, plus the harness's own evidence
  id: string; name: string; tool?: string;
  gate: 'Stop' | 'Warn' | 'Reported';   // what failure does, from the task spec
  result: Result; evidence?: string; ms?: number;
  threshold?: { value: string; origin: string; evidenceLevel: string };
  message?: string; skipReason?: string;
  measurements?: { name: string; value: number | string | boolean | null; unit?: string | null }[];
  thresholds?: { name: string; value: number | string | boolean; comparator: string;
                 origin: string; evidenceLevel: string }[];
}

interface UiRunRecord {          // run-record.schema.json, with the additions marked
  id: string; createdAt: string; task: string; taskName: string; claim: string;
  tools: { id: string; name: string; version: string; family?: 'co-folding' | 'docking' }[];
  inputs: { target?: string; partner?: string | null; ligand?: string | null; reference?: string;
            ph?: number; seeds?: number };
  sources: { source: string; supplies?: string; accession: string; release: string; sha256: string;
             retrievedAt: string; cached?: boolean; ms?: number; url?: string; sizeBytes?: number }[];
  layers: { i: number; key: string; name: string; question: string; durationMs?: number;
            status: 'done' | 'running' | 'pending' | 'not_run';          // addition
            counts: Partial<Record<Result, number>>;                       // addition
            summary?: string[]; figures?: [string, string][]; checks: UiCheck[] }[];
  verdict: { claim: string; outcome: Outcome; statement: string; stops: string[];
             warnings: string[]; incomplete?: string[] };                  // incomplete: addition
  stats: Record<string, unknown>;   // only keys the harness computed; absent means not computed
  narrative: string[]; controls: { name: string; status: string; note?: string }[];
  outputs: string[];
  record: { hardware?: string; scheduler?: string; containers?: string[]; seeds?: number[];
            pahVersion?: string; toolVersions?: Record<string, string> };
  structures?: { id: string; label: string; kind: 'crystal' | 'medoid' | 'seed' | 'docking' | 'model';
                 url: string; format: 'mmcif' | 'pdb' | 'sdf' }[];        // addition, for Mol*
  renders?: { structure: string; png: string; pse: string; view: string }[];  // addition, PyMOL
  source: 'pah' | 'mock';                                                  // addition
}
```

`RunSettings`, `Step`, `EntityGroup`, `Tool`, `Task`, `AgentTask` and `AgentStep` follow the objects in
`web/design/prototype/data/runs.js` (`interpretRun`, `lookupEntities`, `TOOLS`, `TASKS`,
`AGENT_TASKS`). `AgentStep` adds `seq` and `ts`; `AgentTask` adds `createdAt` and `progress`.

## Harness record to UI record

The adapter (`src/pah/webui/adapter.py`) reads `runs/<id>/record.json`, `events.jsonl`,
`provenance.json`, `findings/` and `renders/`. It never invents values.

| UI field | Harness source |
| --- | --- |
| `task` | Task id mapped to the UI id: `monomer_structure`→`monomer`, `known_complex_assembly`→`known_complex`, `binding_site_identification`→`binding_site`, others unchanged |
| `verdict.outcome` | `pass`→`supported`, `pass_with_warnings`→`narrowed`, `stop`→`refused`, `incomplete`→`incomplete` |
| `verdict.statement` | Templated from the outcome, scope and check ids. Facts only |
| `layers[i].checks[j].result` | `Finding.gate` (`pass`, `warn`, `stop`, `skip`) |
| `layers[i].checks[j].gate` | `Stop` unless the check only ever warns (`Warn`) or is report-only (`Reported`), from the check class or task spec |
| `layers[i].checks[j].evidence` | `Finding.message` plus the first measurements, e.g. `undefined=1 of 1 stereo elements` |
| `layers[i].checks[j].threshold` | First threshold as `"<comparator> <value>"`, its origin and evidence level |
| `layers[i].durationMs` | `stage_end.ts - stage_start.ts` from the event stream |
| `layers[i].status` | `done` after `stage_end`, `running` after `stage_start`, `not_run` when the layer was not selected |
| `sources` | `provenance.json`: `source_id`, `accession`, `release` (or `"n/a"`), `sha256`, `retrieved_at`, `extra.cache == "hit"` |
| `stats` | Empty until layers 4 and 5 produce values. The UI shows "not computed" for a missing block |
| `structures` | Every `.cif`/`.pdb`/`.sdf` under `artifacts/`, served through `/runs/{id}/files/...` |
| `renders` | Render artifacts in `record.json` (`ArtifactKind` render entries from `pah.report.renders`: PNG views and `.pse` session per structure) |

Checks that are listed in the task but not registered appear with `result: skip` and
`skipReason: unknown_check`. The UI shows them in the check list as `not implemented` and counts
them, so a viewer can see how much of each layer actually ran.

## Number display

Minimal changes from the prototype, in `web/lib/format.ts`:

- All numbers in Geist Mono, with the unit after a thin space (`2.1 Å`, `412 ms`).
- A check row shows `measured cmp threshold` when both exist (`undefined 1 == 0`).
- Durations: below 1 s in ms, otherwise seconds to one decimal.
- sha256 shown as the first 12 hex characters; the full value in `title`.
- Counts as `pass 12 · warn 1 · stop 0 · skip 8`; zeros are shown muted, not hidden.
- Fractions keep the denominator (`implemented 13/41`).
- Missing values render as an en dash in muted ink, never as 0.

## Tools drive the display

Nothing in the UI is written for a particular executor. Every tool-specific label, metric, column,
docking card and log line comes from the tool register that `GET /tools` returns, and from the
`tools` list of the record being shown. Adding an executor to `configs/executors.yaml` (with its
`outputs` block) must make it selectable and displayable with no UI code change.

```ts
interface ToolOutput {            // one parsed field the executor reports (docs/EXECUTORS.md)
  key: string;                    // e.g. "confidence_score", "CNNscore", "minimizedAffinity"
  label: string;                  // e.g. "Confidence", "CNN pose score", "Vina score"
  unit?: string;                  // e.g. "kcal/mol", "Å", "pK"
  kind: 'confidence' | 'interface' | 'affinity' | 'score' | 'rmsd' | 'plddt' | 'pae' | 'other';
  scope: 'global' | 'interface' | 'ligand' | 'pose' | 'residue';
  range?: [number, number];
  higherIsBetter?: boolean;
  rankingOnly?: boolean;          // shown on its own line below the accent rule, never as pose quality
  note?: string;                  // e.g. "log10(IC50 µM); lower is stronger"
}
interface Tool {
  id: string; name: string; family: 'co-folding' | 'docking'; version: string | null;
  role: string; available: boolean; note?: string; licence?: string; repo?: string;
  runtime?: { profiles: string[]; gpu?: string; accel?: boolean };   // from configs/runtimes.yaml
  outputs: ToolOutput[];
  dockingParams?: { key: string; label: string; unit?: string; default?: string }[];
}
```

Rules for the screens:
- Executor chips group by `family` and show `available`/`note` from the register.
- Metric tables, ensemble columns, stat cards and figure legends are built from the `outputs` of
  the tools in the record. A metric with `rankingOnly` goes under the accent rule.
- Agreement matrices, seed plots and log lines label methods with `Tool.name` from the record.
- A tool missing from the register still renders with its id as the name and no metric columns.
- Mock mode uses the same `Tool` shape (`web/lib/mock` adds `outputs` to the prototype's `TOOLS`).

## Deployment

Default deployment is Modal (`configs/profiles/modal.yaml`). `deploy/modal/api_app.py` serves
`pah.interfaces.api:create_app` as an ASGI web endpoint with the `pah-runs` and `pah-cache` volumes mounted
at `/runs` and `/cache`. One container (`max_containers=1`, concurrent inputs) so live tails and
background runs share a process; the volume is committed after each run and on every write.
Executors run on GPU through `deploy/modal/executors_app.py`. The web UI is deployed to Vercel
(`web/vercel.json`) with `HARNESS_API_URL` set to the Modal endpoint, and can also be served from
Modal (`deploy/modal/web_app.py`, Next.js standalone build) when no Vercel token is configured.

## Testing hooks for agents

Every job card, layer cell, check row, log line and verdict carries `data-testid` and `data-state`
(the result or status). Examples: `data-testid="job-card" data-state="running"`,
`data-testid="check-row" data-check="l1.ligand.identity" data-state="pass"`,
`data-testid="verdict" data-state="narrowed"`. Playwright tests and agent harnesses select on these
rather than on text or classes.
