# CLAUDE.md

Working rules for this repository. Keep this file under 150 lines.

## Project

Prediction Assurance Harness (`pah`). It decides whether a co-folding or docking result can support a
declared claim. Layers: L0 provenance, L1 input integrity, L2 input adequacy, L3 applicability,
L4 output validity, L5 output support. Each check reports pass, warn, stop or skip, with evidence.
This repository is engineering only. The scientific thresholds come from the specification and from
`configs/`, not from code comments or ad hoc judgement.

## Identity and attribution

- Commit as `persistentepiphany <tennesseeshtick@proton.me>` (repo-local `git config`).
- No Claude, Anthropic or AI attribution anywhere: no `Co-Authored-By` trailers, no session links,
  no footers in commits, PR bodies, code or docs.
- Development branch: `claude/blissful-johnson-j76s9r`. Do not push elsewhere without asking.

## Commits

- Commit often, one logical change per commit.
- Messages are short and factual: `add http probe`, `fix cache key for mmcif`. No narration.
- Run `make check` before each push.

## Commands

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[all,dev]"
make check                     # ruff + mypy + pytest
.venv/bin/pah doctor           # reachability of sources, tools, weights, skills
.venv/bin/pah doctor --profile csf3 --dry-run
.venv/bin/pah fetch            # binaries and data from configs/externals.yaml
.venv/bin/pah run examples/3ptb_ligand_pose/manifest.yaml   # layers 0-1, streamed findings
.venv/bin/pah tasks && .venv/bin/pah checks
.venv/bin/pah dock <manifest> --out <dir>    # local Vina, writes a manifest with predictions
.venv/bin/pah lint <file.md>                 # humanizer rules for generated prose
.venv/bin/python bench/run_pipeline.py --seeds 7,8,9   # perturbation benchmark (Modal, Z.AI)
.venv/bin/python bench/analysis/deck.py --run-id <id> --review <judgment.json>  # bind slide review
```

Adding a check: subclass `pah.core.check.Check` in `src/pah/checks/layer<n>_*.py`, decorate with
`@register`, give every threshold an origin (`resolve.threshold`), list its id in the task YAML.

Conda-only tools (openff-toolkit, fpocket, p2rank) live in `.tools/conda-env`, installed with
micromamba (see README). The harness finds them through `PAH_CONDA_PREFIX`.

## Layout

| Path | Role |
| --- | --- |
| `src/pah/core/` | Models (Gate, Finding, Event, RunRecord), event bus and sinks |
| `src/pah/doctor/` | Probes: http, git, python, binary, env; reachability report |
| `src/pah/externals/` | `pah fetch`: per-asset installers, atomic downloads, lock file |
| `src/pah/sources/` | Layer 0 clients behind one `SourceClient` protocol, sha256 content cache |
| `src/pah/checks/` | Shared check library, one module per layer |
| `src/pah/executors/` | Adapters per tool: build inputs, parse outputs, command spec |
| `src/pah/backends/` | Local, Slurm (CSF3, Apptainer), Modal |
| `src/pah/report/` | PyMOL renders, figures, provenance graph, report writer, style lint |
| `src/pah/interfaces/` | CLI (typer), MCP server, HTTP API (FastAPI + SSE) |
| `configs/` | Sources, tools, executors, profiles, task specs (data, not code) |
| `deploy/` | CSF3 sbatch and Apptainer files, Modal app |
| `bench/` | Perturbation benchmark: prep, Modal app, checks, agent, scoring, report, deck |
| `third_party/skills/` | Pinned skill submodules (see `third_party/skills/SOURCES.md`) |

## Engineering rules

- SOLID. One responsibility per class. Extend through protocols and registries (`Check`, `Probe`,
  `SourceClient`, `Executor`, `Backend`, `Sink`, `Renderer`), never through `if tool == ...` chains.
- Data in YAML under `configs/`; behaviour in code. Adding a source, tool or task should not need
  edits to core modules.
- Typed Python 3.11+, `mypy --strict` on `src/pah`, ruff clean, pytest for every module.
- Heavy optional imports (rdkit, gemmi, pymol, posebusters) stay inside the functions that use them,
  so the core installs and runs without the `checks` extra.
- No silent fallbacks. A failed fetch, a missing tool or a substituted tool is recorded as a finding.
- Fail soft: one bad registry entry, probe, download or check never stops the others. Only an
  unusable profile or output directory stops a command (exit 2).
- Tests must not need the network. Mark live tests `@pytest.mark.network`.

## Runtime behaviour (mandatory)

- Verbose streaming: every stage emits events as it happens (start, finding, artifact, layer
  summary, end). Results are written to `runs/<id>/` the moment they exist, not at the end.
- Every structure output from an executor gets a PyMOL session (`.pse`) and PNG renders. A run
  whose structure outputs lack renders fails report generation.
- Every run writes a provenance document graph (`graph.json`, `graph.mmd`, `graph.svg`):
  sources, files, tools, checks, findings and the verdict, with sha256 checksums and versions.
- Reports are generated from the run record only. Text is factual: values, thresholds with origin,
  gates, provenance. No commentary or adjectives.

## Writing

- README and reports follow `third_party/skills/humanizer/SKILL.md` (no em dashes, no staged
  contrasts, no filler, no bold-label lists) and the scientific-writing skill at
  `third_party/skills/claude-scientific-writer/skills/scientific-writing/SKILL.md`.
- Figures follow `third_party/skills/scientific-agent-skills/skills/scientific-visualization/SKILL.md`
  and `.../skills/matplotlib/SKILL.md`. Diagrams follow `.../skills/markdown-mermaid-writing/SKILL.md`.
- Tool documentation lookups: `third_party/skills/readthedocs-skills/skills/readthedocs-search-api/`
  when `app.readthedocs.org` is reachable; otherwise read the tool repository docs at a pinned SHA.
- Update README.md in the same commit as any user-facing change.

## Deployment targets

- CSF3 (Manchester): Slurm + Apptainer, one container per executor. Compute nodes may lack
  outbound access, so sources are fetched into the content cache on the login node first.
- Modal: one image per executor, GPU functions for executors, CPU for checks.
- Jobs are not submitted from this sandbox. Profiles in `configs/profiles/` are validated with
  `--dry-run`.

## Review

- CodeRabbit and Greptile review the PR through GitHub. Address their findings or reply with the
  reason. Running out of credits is not a blocker; self-review with `make check` and a diff read.

## References

- Specification: `docs/SPECIFICATION.md`
- Architecture: `docs/ARCHITECTURE.md`
- Executor I/O contracts: `docs/EXECUTORS.md`

## Web UI

`web/` is the Next.js + Tailwind port of `web/design/prototype/Harness v2.dc.html`. The contract
between the UI and the harness is `docs/UI.md`. `pah serve` is the HTTP API it talks to.

## Demo, video and presentation skills

Vendored in `.claude/skills/` (sources in `.claude/skills/VENDORED.md`): `playwright-cli` (browser
demos), `product-film` (Remotion films), `presentation-skill` (`.pptx`), `sound-effects` (needs
`EACHLABS_API_KEY`), `human-pace` (load with anything that records or times), `humanizer`.
`npm run setup` at the root installs their dependencies. Rendered media goes to `out/` (ignored).
