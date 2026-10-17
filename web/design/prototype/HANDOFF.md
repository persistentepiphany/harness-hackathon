# Harness UI — handoff report for a Next.js + Tailwind port

Prototype: `Harness v2.dc.html` (current). `Harness.dc.html` is the earlier v1, kept for reference.
Data: `data/runs.js` (mock records, interpreter, entity lookups), `data/run-record.schema.json` (contract).
Logic source is also kept flat in `logic-v2.js` (same class as embedded in the DC) for easier reading.

This prototype was NOT built with Next.js, Tailwind or React components. It is a single streaming HTML
component (`<x-dc>` template with inline styles + one JS class). Everything below maps it one-to-one onto a
Next.js App Router project.

## 1 · Screens (routes)

| Prototype view (`state.view`) | Route | Purpose |
| --- | --- | --- |
| `new` | `/runs/new` | Prompt → Quick setup (streamed decisions) or Manual setup; target & ligand pickers with detail cards; co-folding executors (primary) vs docking (secondary, dashed); inputs; drop zone; "Sources" side panel auto-resolving UniProt / RCSB / AFDB / PDBe-KB / PubChem / CCD / ChEMBL |
| `jobs` | `/jobs` | Overview list; each card = name, task, executors, seeds, 6-segment layer progress, verdict or status |
| `run` | `/jobs/[jobId]` | Single job: elapsed seconds, per-layer time + counts strip, log (Plain default / Terminal), executors with docking parameters, inputs, verdict |
| `report` | `/reports/[runId]` | Verdict scoped to claim; layer sidebar (name + key figures + selected-layer data + check list); ensemble viewer with structure chips; ensemble table; site/pose/docking stat cards; checks table; PoseBusters battery; per-seed statistics; figures (PAE, interactions, seeds, agreement, calibration/ROC); confidence metrics; perturbation; thresholds; controls/outputs |
| `ensemble` | `/reports/[runId]/ensemble` | Grid of Mol* viewers (one per structure, cap = `gridViewers`), per-cell numbers, summary statistics table (median/mean/sd/min/max + strip plot) |
| `agent` | `/agent` | Autonomous-agent monitor (read-only): task list with progress, selected task's step timeline (thought · tool call · result · report · conclusion), outcome. Data: `AGENT_TASKS` → `GET /agent/tasks`, `GET /agent/tasks/:id/steps` (stream) |
| `docs` | `/documents/[runId]` | Printable A4 report: key numbers, structure + PAE, stat cards, figures, agreement, interactions, PoseBusters, per-seed table, confidence, layers, flagged findings, provenance table |

## 2 · Component map (prototype block → component)

```
components/
  nav/TopNav.tsx                    tabs with count badges; cluster status dot
  run/PromptBox.tsx                 textarea + sample prompts + Quick/Manual buttons
  run/DecisionStream.tsx            rows {label, value, status} with spinner→check (quickSetup())
  run/TargetPicker.tsx              chips from CATALOG.proteins; TargetDetailCard (rows from CATALOG)
  run/LigandPicker.tsx              chips from CATALOG.ligands; LigandDetailCard
  run/TaskPicker.tsx                3 chips (TASKS)
  run/ExecutorChips.tsx             two groups: co-folding (solid) / docking (dashed, secondary)
  run/InputsForm.tsx                target, partner, reference, seeds, pH, SMILES
  run/DropZone.tsx                  drag-drop + hidden <input type=file>; FileChip with parse status
  run/SourcesPanel.tsx              grouped by entity; row = source · query → rows (lookupEntities())
  run/RunPlan.tsx                   name, claim, executors, controls, Start run
  jobs/JobCard.tsx                  LayerProgress (6 segments; colour = worst result of layer)
  jobs/RunHeader.tsx                elapsed (mono 30px), status, Open report
  jobs/LayerStrip.tsx               6 columns: name, time or %, pass/warn/stop counts
  jobs/LogPanel.tsx                 Plain|Terminal toggle; LogLine {t, dot, text}
  jobs/ExecutorList.tsx             record.execution rows
  report/VerdictHeader.tsx
  report/LayerSidebar.tsx           LayerNavItem (name, summary, dot) + LayerFigures (figures k/v) + check list
  report/StructureViewer.tsx        Mol* client component (see §5)
  report/EnsembleTable.tsx          rows from stats.ensemble
  report/StatCards.tsx              stats.site, stats.pose, record.docking
  report/CheckTable.tsx             layer.checks (id, tool, gate, result, evidence, ms)
  report/PoseBustersGrid.tsx        stats.posebusters
  report/SeedStatsTable.tsx         stats.physics + median row
  report/figures/PaeHeatmap.tsx     canvas (drawPae) — replace with real PAE matrix
  report/figures/InteractionDiagram.tsx   radial SVG from stats.interactions
  report/figures/SeedSpread.tsx     SVG scatter + CI band (stats.seeds, stats.pairwise)
  report/figures/AgreementMatrix.tsx
  report/figures/CalibrationCurve.tsx + RocCurve.tsx
  report/MetricsTable.tsx           stats.metrics; `separate` → ranking scores below an accent rule
  report/PerturbationTable.tsx · ThresholdsTable.tsx · ControlsList.tsx
  ensemble/StructureGrid.tsx        N StructureViewer cells + per-cell stats
  ensemble/SummaryStats.tsx         strip plots + median/mean/sd/min/max
  agent/TaskList.tsx · agent/StepTimeline.tsx   kinds: thought (hollow dot, grey) · tool/result (square, blue/grey, mono) · report (accent) · conclusion (ink, 500)
  document/ReportDocument.tsx       A4 page; print CSS hides chrome
```

## 3 · Design tokens → `tailwind.config.ts`

```ts
colors: {
  canvas: '#F7F7F4', surface: '#FFFFFF', line: '#E6E6E1', line2: '#EFEFEB', line3: '#F3F3EF',
  ink: '#1A1A18', ink2: '#55554F', muted: '#8B8B85', faint: '#B9B9B3',
  accent: { DEFAULT: '#B07E2C', deep: '#8E6420', tint: '#F6EEDC', soft: '#FBF7EE' },
  pass: { DEFAULT: '#3B8A58', tint: '#E4F1E8' }, warn: { DEFAULT: '#C28A1A', tint: '#FAF0D9' },
  stop: { DEFAULT: '#C4513B', tint: '#F9E5E0' }, reported: '#8B8B85',
  cofolding: '#B07E2C', docking: '#5B7FA6', seed: '#C9A86A', model: '#8B6FB5',
  terminal: { bg: '#1A1A18', fg: '#E8E8E3', pass: '#6FBF8A', warn: '#E3B45A', stop: '#E8826E' },
}
fontFamily: { sans: ['var(--font-geist)'], mono: ['var(--font-geist-mono)'] }   // next/font Geist + Geist Mono
fontSize: base 13px / 1.45; eyebrow 11px uppercase tracking .06em; mono data 11.5px
borderRadius: { DEFAULT: '6px', card: '8px' }
```
Patterns: no card chrome except where data is tabular (`bg-surface border border-line rounded-card`);
section eyebrows uppercase muted; selected state = `bg-ink text-white` chip or `border-l-2 border-ink` nav item;
status dot 6–8px; docking elements dashed border; all numbers in mono.
Animations: `fadeUp .3s` on mount, `spin .8s` for pending, `pulse 1.2s` for running dots.

## 4 · Tool register and task classes

`TOOLS` lists every executor from the specification register (Boltz-2, Protenix, AlphaFold3, Chai-1, AlphaFold DB lookup; Gnina, AutoDock Vina, DiffDock-L, pyDock, HADDOCK) with `family`, `version`, `available`, `note`. Unavailable tools render disabled with their reason; users add more through the dashed "+ executor" input (`addKey('tool')`), which in the port should POST to a tool-registry endpoint (`/tools`).

`TASKS` lists all 14 task classes (8 co-folding, 6 docking) with `group`, `kind` (`monomer | complex | ligand` — drives which inputs, figures and stat cards appear), `defaultTools`, `claim`, `controls`, `inputs`. The mock record generator shapes data by `kind`; the real backend returns the record directly. Tool names in metrics, agreement matrices, ensemble labels, docking cards and log lines are taken from the run's executors, never hard-coded.

## 5 · Data contract and wiring

Everything renders from one `RunRecord` (`data/run-record.schema.json`). Fields added since v1 and used by the UI:
- `layers[i].summary: string[]` and `layers[i].figures: [k, v][]` — sidebar key figures
- `layers[i].checks[].ms` — per-check time
- `stats.metrics[]` with `separate: true` for ranking-only scores (Boltz-2 affinity, Vina, Gnina CNN affinity, pyDock)
- `stats.ensemble[]` — one row per structure `{id, label, kind: crystal|medoid|seed|docking|model, source, rmsdToMedoid, pocketPlddt, iptm, cnn, posebusters, cluster}`
- `stats.pairwise {median, iqr, ci95, n}`, `stats.physics[]` (per-seed drift, torsions, clashes, strain, unsatisfied, pbPassed, clashscore, rama)
- `stats.posebusters[] {test, pass, value}`, `stats.interactions[] {residue, type, distance, known}`, `stats.site`, `stats.pose`, `stats.roc`, `stats.auc`, `stats.enrichment`
- `docking: { tool, rows: [k, v][] } | null` — docking stat card for whichever docking executor ran

- Catalog chips (targets, ligands, executors) are examples; the dashed "+" inputs add arbitrary entries (`addKey()`), which must call the real resolvers in the port.
- Drop zone (`DropZone.tsx`) is always visible under Files; accepted: .pdb .cif .fasta .sdf .mol2 .smi .csv .json → POST /uploads then parse status.

API surface the UI expects (`lib/harness-api.ts`):
```
POST /runs                 body = RunSettings {task, tools[], target, partner?, ligand?, reference, ph, seeds, name?}
GET  /jobs                 → Job[] {id, name, status, layerIdx, progress, elapsedMs}
GET  /jobs/:id/log         → stream of LogLine {t, layer, kind: fetch|cache|check|layer|exec, result?, text, plain}
GET  /runs/:id/record      → RunRecord
POST /interpret            body {text} → RunSettings + steps[] {field, value, because}   (replaces interpretRun())
GET  /entities?q=          → resolver groups as returned by lookupEntities()               (replaces mock)
GET  /catalog              → {proteins[], ligands[]}                                       (replaces CATALOG)
```
Simulation code to delete in the port: `tick()`, `emitLayer()`, `linesFor()`, `makeJob()`'s synthetic timing,
`scheduleLookup()` timeouts, `addFiles()` fake parsing. Keep the rendering/derivation code in `renderVals()`;
it becomes selectors/hooks (`useRunRecord(runId)`, `useJobLog(jobId)`).

## 6 · Mol* viewer notes

- `molstar` npm package, client component, `Viewer.create(el, viewerOpts)` with the option object in `viewerOpts`.
- Selection → load: `crystal` / docking poses → `loadPdb(reference)`; seeds / medoid / models → currently
  `loadAlphaFoldDb(target)` as a stand-in; `overlay` → both. Replace with `loadStructureFromUrl(poseUrl)` per
  `stats.ensemble[].id` once per-seed coordinates are served.
- Per-residue colouring (pocket pLDDT, flagged residues, unsatisfied polars) is pending `stats.residues[]` in the record.
- Ensemble grid: one viewer per cell, capped (`gridViewers`, default 6) to stay under the browser WebGL context limit.

## 7 · Tweaks in the prototype (become config/env)
`simSpeed`, `maxConcurrent` (remove with the simulator), `gridViewers`, `viewerMode` (`molstar | placeholder`).

## 8 · Git
Suggested branch `ui/harness-prototype`; commits: `add run-record schema` · `add mock data + interpreter` ·
`add harness ui v2` · `add handoff report`.
