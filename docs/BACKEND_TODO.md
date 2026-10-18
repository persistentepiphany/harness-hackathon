# Backend and API work list

Handover list for the API and backend changes the user asked for on 17 Oct 2026. Branch
`web-ui`, last pushed commit `7ea4456`. The working tree holds uncommitted work
from stopped agents; the state of each item is noted. `make check` currently fails 6 tests, all from
the partial gate-policy work (item 2):
`test_engine.py::test_stop_halts_later_layers`, `test_engine.py::test_task_escalates_warn_to_stop`,
`test_layers_2_5.py::test_configured_threshold_has_origin`,
`test_layers_2_5.py::test_ligand_prevalence_counts_pre_cutoff_entries`,
`test_webui_qa_fixes.py::test_checks_that_never_stop_do_not_declare_stop`,
`test_e2e_interfaces.py::test_http_runs_appear_in_ui_and_stream` (verdict `incomplete` vs
`not_assessed`).

## 1. Run the models from the UI (highest priority)

Today a run started from the UI executes no tool: log line 0 reads "executors not run (checks only)".

- When `RunSettings.execute` is true (default true for dispatchable tools), run the selected executors,
  write their outputs into `runs/<id>/predictions/<executor>/seed_<n>/`, add the `predictions` entries
  to the manifest, then run layers 4 and 5 on them.
- Vina runs locally in the API container (route `local`, like `pah dock`). Check that the vina binary
  is in the `pah-api` image; `/ui/tools` reports every tool `available: false` on Modal.
- GPU tools run on the deployed Modal apps `pah-gpu-<executor>` (boltz2, boltz1, protenix,
  protenix-v2, chai1, colabfold, openfold3, gnina, diffdock). Boltz-2 uses the optimisation-kit image
  (`pah runtimes kits fetch` worked); fall back to stock and record the fallback as an event and a
  finding, never silently.
- Emit execution events (`data.stage == "execute"`, phases queued, building, running, done, failed,
  skipped, with gpu, route, seed, elapsedMs) so the job page shows the engaged tool and timings.
  `EventBus(seq_start=...)` and `run_manifest(seq_start=...)` exist so the engine continues the seq.
- Guard the public endpoint: optional `PAH_EXEC_TOKEN` checked against a header the web proxy adds
  server-side, one GPU run at a time, seeds capped at 5.
- State: `src/pah/webui/execute.py` (833 lines, uncommitted), `configs/dispatch.yaml`,
  `deploy/modal/gpu_app.py`, `tests/test_webui_execute.py`. Not wired into `routes_write.py` end to
  end; no UI run has executed a model yet. Verify each tool with one real dispatch and record a table:
  image built, dispatched, ran, wall time, GPU, route, error.

## 2. Gate policy and check classification (from the user)

Policy: only a published threshold may, on its own, drive a verdict to invalid or refused. Inherited
and uncalibrated thresholds may warn or narrow, never decide alone. Definitional checks (exact
equality, logical rules) keep their stop gates. PoseBusters keeps decision power for physical
validity. Corroboration and stability can only narrow until the benchmark gives them published or
reproduced standing.

- Two labels on every check: category (provenance and identity, structural completeness, chemical
  state, applicability, physical validity, interaction chemistry, sampling and stability,
  corroboration and controls) and standing (definitional, published, inherited, uncalibrated), from
  the user's table. Expose `category`, `standing` and `decisive` on every check in the record and the
  `/ui` record.
- Verdict dimensions from categories: Inputs (first three categories), Exposure (applicability plus
  the endpoint stop), Physical validity, Chemical plausibility (interaction chemistry), Stability,
  Corroboration and physical response.
- Enforce the policy in the engine: a stop from a non-decisive check becomes a narrowing warning,
  recorded explicitly in the finding. Keep the change small and tested.
- Thresholds to ship, keep and drop, per the user's list:
  - Published, may gate: ligand RMSD < 2 Å with LDDT-PLI > 0.8; centre of mass within 2.5 Å; DockQ
    0.23/0.49/0.80 cited to DockQ and FoldBench, not CAPRI.
  - Published, context or construction only: perturbation within 3.5 Å (Gly, Phe, Miyata) plus apo
    control; retention 42 to 52 % vs 78 %; prevalent ligand (Tanimoto > 0.9 in > 100 systems);
    SuCOS-pocket > 50 for stratification only.
  - Inherited: PLIP geometry and PoseBusters tolerances recorded through the tool version; PLIP
    binding-site radius 7.5 Å (replaces 8 Å, warn only); ipTM ~0.75 Chai-1 and ~0.99 Protenix
    reported only; StrainRelief 16.1 kcal/mol warn only and deferred.
  - Uncalibrated, warn only: minimisation drift > 2 Å; medoid cluster < half the samples;
    cross-family disagreement > 2 Å; RDKit torsion strain without an energy cutoff; box contact
    radius 4 Å; pKa within 1 unit of pH; box margin 2 Å; net charge ≤ 2; five seeds and ten
    conformers as defaults.
  - Drop: 5 Å cofactor radius; twenty conformers for docking preparation; 16.1 kcal/mol on RDKit
    torsion strain; the CAPRI attribution for DockQ; SuCOS-pocket > 50 as a warning.
- State: `configs/standing.yaml` (77 checks classified), `src/pah/core/standing.py`, edits in
  `src/pah/core/engine.py`, `src/pah/core/policy.py` and `configs/thresholds.yaml`, all partial and
  the cause of the 6 failing tests. Finish or revert before committing.

## 3. Missing tools and checks (real tools, no approximations)

- MolProbity: cctbx 2026.1 (`molprobity.molprobity`, ramalyze, rotalyze, cbetadev, clashscore),
  reduce 4.15 and probe 2.18 are installed in `.tools/conda-env` and registered in
  `configs/tools.yaml` and `configs/externals.yaml`. `src/pah/checks/layer4_molprobity.py` exists
  (`l4.molprobity`, listed in `monomer_structure.yaml` only). Finish: Top8000 reference data through
  `pah fetch --only molprobity_data`, list the check in every task that has predicted protein
  structures, tests with `tests/fixtures/molprobity/`, report Ramachandran outliers and favoured %,
  rotamer outliers, clashscore, Cβ deviations and the MolProbity score with tool name and version.
- OpenMM 8.6.1, PDBFixer, openmmforcefields, OpenFF: installed and registered; the Modal API image
  block (micromamba, `environment/conda.yml`) is written in `deploy/modal/api_app.py` but not
  deployed. Fix `l4.minimisation_drift` to name OpenMM as its tool.
- Disorder annotation (L2): MobiDB and DisProt clients behind `SourceClient` with the sha256 cache,
  and the check. Not started.
- Known binders (L4): PDBe-KB (and BioLiP2 if feasible) source so `l4.interactions.known_binders`
  runs. Not started.
- Ranking stability, Kendall tau across seeds (L5), and sampling separated from ranking (L5). Not
  started.
- Waters and metals retained deliberately (L2). Not started.
- Receptor conformational state against known states (L4) and perturbation response (L5): reuse the
  perturbation benchmark code in `bench/`. Not started.
- `doctor` and `pah fetch` must report every one of these tools and sources.

## 4. Verdict honesty in the record (done in the /ui adapter, keep consistent)

Done in `src/pah/webui/adapter.py` and `assessment.py` and deployed with `7ea4456`: pre-run runs say
`not_assessed`, scope lists the evaluated layers, output checks without predictions are `pending`
rather than `not_applicable`, tools are marked exercised or declared only. Still to do:

- Move the same rules into the engine or the report writer so `record.json` and `report.html` agree
  with the UI: `not_assessed` outcome, scope from evaluated layers, skip reason `pending_input`.
- Exercised vs declared tools in the report footer (versions listed only for tools that ran).
- PAE and method agreement read "not applicable" for tools that cannot produce them.
- Gate labels: `gate` is the worst severity a check can emit; align the field name or docs.

## 5. API surface for the new UI

- `GET /ui/glossary`: every score key from `configs/executors.yaml` outputs and the check
  measurements the UI shows, with label, unit, producer and what goes into it.
  `src/pah/webui/glossary.py` exists, uncommitted; confirm the route is mounted and tested.
- `/ui/tasks`: `endpoint`, `compatibleTools`, `quickSetup`, `group` (helpers exist in the adapter).
- `/ui/catalog`: `prompts` from `configs/catalog.yaml`.
- `/ui/tools`: `dispatchable`, `gpu`, `route` from `configs/dispatch.yaml`; `available` must not read
  "not installed on this host" for tools that run on Modal.
- Interpreter warnings at the top level of the `/ui/interpret` response (now nested under
  `settings.warnings`).
- Record fields for the job page story: renders with executor, seed, rank, main score and per-pose
  check results while the run is in progress; `sourceSummary` counts.
- Report stage status on job cards (job `reportStatus` stuck at `running` on some old runs).

## 6. Deploy

- Redeploy `pah-api` after items 1 to 3 pass `make check`; the image now builds the conda prefix
  (OpenMM, MolProbity), so the first build takes longer. Deploy from a clean worktree of a pushed
  commit with `scripts/deploy_modal.sh`.
- Run one real UI-started job per executor on the deployed app and confirm layers 4 and 5 evaluate.
