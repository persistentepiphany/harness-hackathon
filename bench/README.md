# Perturbation benchmark

An agent decides whether a predicted pose is valid, once from the model's confidence score alone
and once from the harness fact file, across matched wild-type and perturbed systems from
published failure cases. Design and targets are fixed in `config/targets.yaml` before any run.

| Factor | Levels |
| --- | --- |
| System | FtsE (8X61, ATP), CDK2 (1B38, ATP), MEK1 (7XLP, FZC), glucose dehydrogenase (2VWH, BGC) |
| State | wild type; perturbed (contacts within 3.5 Å to glycine, or three glucose hydroxyls methylated) |
| Executor | Boltz-2 2.2.1, DiffDock-L v1.1.3; seeds 1, 2, 3 |
| Agent information | confidence score only; harness fact file (GLM-4.6 through Z.AI, temperature 0, 3 repeats) |

Ground truth by construction: a perturbed system is invalid; a wild-type system is valid when the
representative pose (medoid of the largest cluster at 2.0 Å) lies within 2 Å of the deposited
ligand. The RMSD to the deposited ligand is kept in `truth/` and never reaches the agent.

## Run

One run end to end, with its own seeds:

```bash
export MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=... ZAI_API_KEY=...
.venv/bin/python bench/run_pipeline.py --seeds 7,8,9
```

It writes the design to `runs/<id>/config/targets.yaml`, runs every stage, records the stage
exits in `runs/<id>/pipeline.json` and appends one row per scope to `bench/scores.csv`, replacing
any earlier rows for the same run. `--from <stage>` and `--to <stage>` resume or stop a run, for
example `--run-id <id> --from checks`. The stages also run on their own:

```bash
RUN_ID=$(date -u +%Y-%m-%dT%H%MZ)-$(git rev-parse --short HEAD)
.venv/bin/python bench/prep/fetch_and_perturb.py --out bench/runs/$RUN_ID/prep
.venv/bin/modal run bench/modal/perturbation_app.py::probe                      # images, GPU
.venv/bin/modal run bench/modal/perturbation_app.py::predict_all --run-id $RUN_ID
.venv/bin/modal run bench/modal/perturbation_app.py::fetch_all --run-id $RUN_ID
.venv/bin/python bench/checks/run_checks.py --run-id $RUN_ID --jobs 3
.venv/bin/python bench/agent/decide.py --run-id $RUN_ID
.venv/bin/python bench/analysis/score.py --run-id $RUN_ID
.venv/bin/python bench/analysis/report.py --run-id $RUN_ID
.venv/bin/python bench/analysis/deck.py --run-id $RUN_ID
.venv/bin/python bench/analysis/render_frames.py --run-id $RUN_ID
```

`predict_all --executors boltz2` or `--executors diffdock` reruns one executor. Behind a proxy
the Modal client needs `modal[api-proxy-support]` (in the `modal` extra). Results travel back
through the `pah-bench-results` volume in 256 KiB pieces, so no blob host is needed.

`decide.py --retry-errors` re-issues only the calls whose log entry holds an error, keeping the
successful ones; each retry is appended to `calls.jsonl` with the same index and readers take the
last entry for a prediction. The endpoint rate-limits above two workers.

### Binding the visual review of a deck

`deck.py` builds the deck and runs the skill's preflight, build and QA. The skill treats automated
QA as one layer and a visual review of the rendered slides as the other, so the deck is not
finished until a review is bound to it:

```bash
.venv/bin/python bench/analysis/deck.py --run-id $RUN_ID        # build; writes deck/qa/renders/
# inspect deck/qa/renders/slide-*.jpg, then write deck/visual_judgment.json (visual_judgment_v1)
.venv/bin/python bench/analysis/deck.py --run-id $RUN_ID --review bench/runs/$RUN_ID/deck/visual_judgment.json
```

The second call hashes the deck and every rendered slide into
`deck/visual_review_receipt.json` and reruns QA with `--require-bound-visual-review` into
`deck/qa_bound/`. Rebuilding the deck changes its hash and voids the receipt, so review again
after any change. A failing stage exits non-zero.

## Stages

| Stage | Script | Writes to `runs/<id>/` |
| --- | --- | --- |
| Prepare | `prep/fetch_and_perturb.py` | `prep/<system>_<state>/` (Boltz YAML, receptor PDB, SMILES, meta with mutations and checksums), `prep/sources.json` |
| Predict | `modal/perturbation_app.py` | `predictions/<system>/<executor>/seed_<n>/`, `modal.json` per job (image id, GPU, commands, durations) |
| Check | `checks/run_checks.py` | `harness/<system>_<executor>/` (manifest, run record, report, renders, `derived/`), `facts/`, `truth/` |
| Decide | `agent/decide.py` | `agent/calls.jsonl` (every prompt and response), `agent/settings.json`, `results/decisions.csv` |
| Score | `analysis/score.py` | `results/truth.csv`, `confusion.csv`, `stats.json`, `figures/` |
| Report | `analysis/report.py`, `deck.py`, `render_frames.py` | `manifest.json`, `report.md`, `results/deck.pptx`, `deck/visual_review_receipt.json`, `results/walkthrough.mp4` |

`report.md` opens with the per-system cases (each system's wild-type and perturbed medoid, the
deposited contacts it reproduces, and both verdicts) and keeps the pooled accuracy in a later
section, because four systems per state give wide intervals. Files a check computes from a pose,
the protein-only PDB and the minimisation result, go to `harness/<name>/run/derived/` and are
regenerable, so they are not committed.

The Modal images come from `configs/runtimes.yaml` through `pah.runtimes` (stock Boltz-2 pip pin
with a C toolchain for its kernels; DiffDock-L image pinned by digest). Weights are cached in the
`pah-weights` volume. Each fact file holds what the runbook's arm B prompt shows: confidence,
PoseBusters, the PLIP fingerprint against the deposited complex in the reference numbering,
strain, buried unsatisfied polars, hydrophobic complementarity, ensemble spread, medoid cluster
fraction and cross-executor agreement.

Runs are committed without the PyMOL renders, the harness's parsed pose copies and the raw MSA
server downloads (`.gitignore`). The Boltz MSA CSV used for each prediction is kept. Renders are
rebuilt from a run record with `pah report bench/runs/<id>/harness/<name>/run`.

