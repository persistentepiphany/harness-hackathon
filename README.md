# Prediction Assurance Harness

`pah` checks whether a structure prediction or docking result can support the claim its user
wants to make. It runs before and after each prediction in six layers (provenance, input
integrity, input adequacy, applicability, output validity, output support), and every check
returns pass, warn, stop or skip with the values and thresholds behind it. The design is in
[docs/SPECIFICATION.md](docs/SPECIFICATION.md). Working rules for contributors and agents are in
[CLAUDE.md](CLAUDE.md).

## Status

Milestone 1 is done. It covers the package skeleton, the event stream, and `pah doctor`, which
checks that every data source, check tool, executor repository, model weight file and writing
skill is reachable from the host it runs on. Layer checks, executor adapters, reports, the MCP
server and the HTTP API come next (see [Roadmap](#roadmap)).

## Install

Python 3.11 or later and [uv](https://docs.astral.sh/uv/) are required.

```bash
git clone --recurse-submodules https://github.com/persistentepiphany/harness-hackathon
cd harness-hackathon
scripts/setup_env.sh
```

The script creates `.venv` with all Python extras and `.tools/conda-env` with the tools that are
not on PyPI (openff-toolkit, fpocket, OpenJDK, APBS), initialises the skill submodules and runs
`pah fetch`. Each step runs on its own; a failed step is listed at the end and the rest still
complete. To install only the Python side: `uv pip install -e ".[all,dev]"`.

## Fetch

Some assets come from GitHub releases, static binary hosts, licensed sources or authenticated
buckets. `pah fetch` downloads them on the end user's host, as declared in
[configs/externals.yaml](configs/externals.yaml).

```bash
.venv/bin/pah fetch                      # default assets: P2Rank, MMseqs2, Foldseek, PLINDER/PINDER indexes
.venv/bin/pah fetch --only gnina         # one asset
.venv/bin/pah fetch --all                # also executor weights, gnina, ColabFold databases (large)
.venv/bin/pah fetch --dry-run --all      # list targets and sizes
```

| Asset | Source | Default | Note |
| --- | --- | --- | --- |
| `p2rank` | GitHub release `rdk/p2rank` | yes | Links `prank` into `.tools/bin` |
| `mmseqs` | mmseqs.com static build | yes | Links `mmseqs` |
| `foldseek` | mmseqs.com static build | yes | Links `foldseek` |
| `plinder_index`, `pinder_index` | `gs://plinder`, `gs://pinder` | yes | Needs `gcloud auth login`; skipped when gcloud is absent |
| `gnina` | GitHub release `gnina/gnina` | no | Executor hosts |
| `protenix_weights` | Protenix checkpoint host | no | Executor hosts, about 1.4 GB |
| `colabfold_databases` | ColabFold `setup_databases.sh` | no | About 1 TB uncompressed |
| `alphafold3_weights`, `pydock`, `phenix` | By request or licence | manual | Set `PAH_AF3_WEIGHTS`, `PAH_PYDOCK_HOME`, `PAH_PHENIX_HOME` |

Downloads go to a `.part` file and are renamed only when complete, with the sha256 recorded in
`.tools/externals.lock.json`. Archives are checked for paths that leave the target directory
before extraction. Assets already present are skipped unless `--force` is given. The doctor
finds fetched binaries in `.tools/bin`.

## Doctor

```bash
.venv/bin/pah doctor                       # all categories, local profile
.venv/bin/pah doctor --only sources        # one category
.venv/bin/pah doctor --format jsonl        # one JSON event per line on stdout
.venv/bin/pah doctor --profile csf3 --dry-run
```

Each probe prints a line as soon as it finishes, and each category ends with a count line.
The report goes to `runs/<run-id>/` as `doctor_report.json`, `doctor_report.md` and
`events.jsonl`. `--strict` exits with code 1 if any probe is not `ok`.

| Status | Meaning |
| --- | --- |
| `ok` | Reachable, importable or present |
| `blocked` | The network proxy refused the host |
| `unreachable` | DNS failure, connection failure or timeout |
| `http_error` | The host answered with an unexpected HTTP code; the body excerpt is in the detail |
| `missing` | Module, binary, variable or file not found |
| `manual` | Needs a licence or a by-request download; set the environment variable named in the detail |
| `error` | The probe itself failed |

### When something fails

A probe, a download or a registry entry that fails is recorded with its cause and the run
continues. A malformed entry in a YAML registry shows up as an `error` row for that entry; an
unknown category or missing registry file shows up as one `error` row for the category. A bad
profile name or an unwritable report directory stops the command with exit code 2 and a
one-line message. `--strict` turns any non-ok result into exit code 1 for scripts and CI.

### On CSF3

```bash
# login node
git clone --recurse-submodules https://github.com/persistentepiphany/harness-hackathon ~/harness-hackathon
cd ~/harness-hackathon && scripts/setup_env.sh ~/scratch/pah csf3
source deploy/csf3/env.sh
pah doctor --profile csf3

# compute node
sbatch deploy/csf3/doctor.sbatch
```

Compare the two reports. Sources that the login node reaches and the compute node does not
have to be fetched into the cache on the login node before a run. The partition and module
names in `configs/profiles/csf3.yaml` and `deploy/csf3/` have not been checked against CSF3
yet; confirm them with `sinfo -s` and `module avail`.

### On Modal

```bash
modal token new          # or set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET
modal run deploy/modal/doctor_app.py
```

The image installs the same extras as `pyproject.toml` and the same conda packages as
`environment/conda.yml`, then runs `pah fetch --profile modal`. Remote output streams to your terminal and the report is copied to
`runs/<run-id>/`.

## Results from the development sandbox

`pah doctor --profile local` on 2026-10-17 gave 101 probes: 88 ok, 4 blocked, 3 http_error,
4 missing, 2 manual.

| Probe | Status | Cause | Fix |
| --- | --- | --- | --- |
| `colabfold_db` | blocked | `opendata.mmseqs.org` not on the egress allowlist | Allow the host |
| `mmseqs_binaries` | blocked | `mmseqs.com` not on the allowlist | Allow the host, or `pah fetch` on the end user's host |
| `protenix.weights` | blocked | `protenix.tos-cn-beijing.volces.com` not on the allowlist | Allow the host, or `pah fetch --only protenix_weights` |
| `readthedocs_api.remote` | blocked | `app.readthedocs.org` not on the allowlist | Allow `app.readthedocs.org` and `*.readthedocs.io` |
| `plinder`, `pinder` | http_error | Google Cloud Storage refuses anonymous reads | `gcloud auth login`, then `pah fetch` |
| `gnina.release` | http_error | The session's GitHub scope covers git reads, not release downloads | `pah fetch --only gnina` on the executor host |
| `p2rank`, `mmseqs`, `foldseek` | missing | Release or static-binary hosts not reachable here | `pah fetch` on the end user's host |
| `molprobity` | missing | Ships with Phenix (academic licence) | Install Phenix where licensed |
| `alphafold3.weights` | manual | Weights issued by request | Set `PAH_AF3_WEIGHTS` |
| `pydock.licence` | manual | Academic licence, no public source | Set `PAH_PYDOCK_HOME` |

The check tools were also run on a real complex (PDB 3PTB, trypsin with benzamidine) fetched
live from RCSB. All passed.

| Tool | Version | Exercised |
| --- | --- | --- |
| gemmi | 0.7.5 | mmCIF parse, ligand and water removal |
| RDKit | 2026.9.1 | SDF parse, SMILES, InChIKey |
| PoseBusters | 0.6.5 | `dock` config, 22 tests |
| PLIP | 3.0.1 | Interaction set for BEN:A:1 |
| FreeSASA | 2.2.1 | Total SASA |
| spyrmsd | 0.9.0 | Symmetry-corrected RMSD |
| PDBFixer | 1.12.0 | Missing residue and atom scan |
| OpenMM | 8.6.1 | AMBER14 system, 50-step minimisation on CPU |
| PROPKA | 3.5.1 | pKa run |
| Meeko | 0.8.0 | PDBQT ligand preparation |
| Dimorphite-DL | 2.1.0 | Protonation at pH 7.0 to 7.4 |
| PyMOL (open source) | 3.2.0 | Headless ray-traced PNG and `.pse` session |
| DockQ | 2.1.3 | Import |
| AlphaJudge | 1.4.4 | Import |
| openff-toolkit | 0.19.0 | Import (conda prefix) |
| fpocket | conda-forge | Pocket detection on the receptor |
| APBS | 3.4.1 | Version |

## Executors

The harness does not install co-folding or docking engines. It writes their inputs, parses their
outputs and records their provenance. [docs/EXECUTORS.md](docs/EXECUTORS.md) gives the input
format, command line, output layout and field names for Boltz-1/2, Protenix, AlphaFold3, Chai-1,
ColabFold, AutoDock Vina, Gnina, DiffDock-L and HADDOCK3. Every entry was read from the tool's
source at a pinned commit and cites file and line. pyDock has no public source and is marked
unverified.

An agent benchmark that runs these tools itself can use the harness on their outputs alone.
That path needs only the output parser for the tool.

## Layout

| Path | Contents |
| --- | --- |
| `src/pah/core/` | Models and the event bus |
| `src/pah/doctor/` | Probes, catalog, runner, report |
| `src/pah/externals/` | `pah fetch`: downloader, installers per asset kind, lock file |
| `src/pah/interfaces/` | CLI (MCP server and HTTP API to follow) |
| `configs/` | Sources, tools, executors, externals and deployment profiles as YAML |
| `deploy/csf3/`, `deploy/modal/` | Slurm and Modal entry points |
| `environment/conda.yml` | Conda-only tools |
| `third_party/skills/` | Pinned writing, figure and documentation skills ([sources](third_party/skills/SOURCES.md)) |
| `docs/` | Specification, architecture, executor contracts |

## Development

```bash
make check     # ruff, ruff format --check, mypy --strict, pytest
```

Tests do not use the network. Live tests carry the `network` marker and are excluded by
`make check`.

## Roadmap

| Milestone | Scope |
| --- | --- |
| 2 | Engine, task specifications, Layer 0 source clients with sha256 cache and offline mode, Layer 1 checks |
| 3 | Layer 2 to 5 checks, executor adapters, Slurm and Modal backends |
| 4 | Reports: PyMOL renders for every structure output, figures, provenance graph, text from the run record |
| 5 | MCP server and HTTP API with an SSE event stream and JSON schemas for the frontend |

## Licence

GPL-3.0. See [LICENSE](LICENSE).
