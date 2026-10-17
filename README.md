# Prediction Assurance Harness

`pah` checks whether a structure prediction or docking result can support the claim its user
wants to make. It runs before and after each prediction in six layers (provenance, input
integrity, input adequacy, applicability, output validity, output support), and every check
returns pass, warn, stop or skip with the values and thresholds behind it. The design is in
[docs/SPECIFICATION.md](docs/SPECIFICATION.md). Working rules for contributors and agents are in
[CLAUDE.md](CLAUDE.md).

## Status

Milestones 1 and 2 are done.

| Milestone | Delivered |
| --- | --- |
| 1 | Package skeleton, event stream, `pah doctor` (reachability of sources, tools, weights, skills), `pah fetch` |
| 2 | Engine, run manifest, task specifications, Layer 0 source clients with a sha256 content cache and offline mode, Layer 0 and Layer 1 checks, `pah run` |

Layers 2 to 5, executor adapters, reports, the MCP server and the HTTP API come next
(see [Roadmap](#roadmap)).

## Run

```bash
.venv/bin/pah run examples/3ptb_ligand_pose/manifest.yaml            # layers 0 and 1
.venv/bin/pah run examples/3ptb_ligand_pose/manifest.yaml --offline  # cache only, no network
.venv/bin/pah run examples/3ptb_faulty_inputs/manifest.yaml --no-halt
.venv/bin/pah run <manifest> --format jsonl                          # one JSON event per line
.venv/bin/pah tasks                                                  # task specifications
.venv/bin/pah checks                                                 # registered checks
```

A manifest names the task, the claim, and the inputs as given to the executor: protein
accessions, PDB chain and sequence, MSA file, intended mutations, ligand SMILES, CCD code,
PubChem CID or SDF file, the receptor and the model version. Mutations are written in UniProt
numbering (`mutations: [L99A, M102Q]`). Each must match the UniProt wild-type residue. Declared
substitutions are applied to the reference sequence and accepted against SEQRES; any other
difference stops the run. The engine runs each layer in order. It prints every finding
the moment the check returns and writes it to `runs/<run-id>/findings/` at the same time.
Each layer ends with a count line. A stop in a pre-run layer skips the later layers unless
`--no-halt` is given.

| File in `runs/<run-id>/` | Contents |
| --- | --- |
| `events.jsonl` | Every event in order |
| `findings/L<n>_<check>.json` | One finding: gate, measurements, thresholds with origin, evidence |
| `record.json` | Run record: manifest, findings, provenance, tool versions, verdict |
| `provenance.json` | Every source record used: source, accession, release, URL, sha256, size |
| `artifacts/sources/` | Fetched files, for example the receptor mmCIF |

| Verdict | Condition |
| --- | --- |
| `pass` | Every applicable check passed |
| `pass_with_warnings` | No stop, at least one warn |
| `stop` | At least one stop; the claim is not supported by these inputs |
| `incomplete` | A check could not run because a tool was missing, it raised an error, or it is not registered |

A check that does not apply to the inputs (no MSA declared, no receptor) is skipped as
`not_applicable` and does not affect the verdict. A task can turn specific warnings into stops
for its claim (`escalate` in the task file).

### Sources and cache

Every record fetched for a run goes through a content-addressed cache (`cache/` by default,
set by the profile). Each payload is stored under its sha256 and indexed by request, with
source, accession, release, URL, size and retrieval time. A cached object that fails its
checksum is treated as missing. With `--offline`, or `offline: true` in the profile as on CSF3
compute nodes, a cache miss is a stop finding in `l0.sources.resolved`. The run never falls
back to the network.

| Client | Records |
| --- | --- |
| UniProt REST | Sequence, entry and sequence version, MD5, release (`X-UniProt-Release`) |
| RCSB data API | Entry revision, release dates, resolution, method; CCD descriptors (InChIKey, SMILES) |
| RCSB file service | mmCIF |
| PDBe API | Entity sequences (SEQRES), bound ligands; SIFTS UniProt mappings |
| PubChem PUG REST | InChIKey, SMILES |
| AlphaFold DB | Entry, model version, sequence checksum |

### Checks in layers 0 and 1

| Check | Gate on failure | What it compares |
| --- | --- | --- |
| `l0.sources.resolved` | stop | Every declared identifier resolves to a record with checksum |
| `l0.cross.uniprot_seqres` | stop | UniProt sequence against PDB SEQRES over the SIFTS-mapped range |
| `l0.cross.ligand_inchikey` | stop; warn for metal ligands matching on skeleton only | InChIKey of the declared SMILES against CCD and PubChem |
| `l1.sequence.matches_record` | stop | Sequence given to the run against the record (SIFTS range when a PDB chain is declared) |
| `l1.sequence.no_truncation_substitution` | stop | N- and C-terminal truncation, substitutions, deletions, insertions, non-standard residues |
| `l1.msa.integrity` | stop | MSA query equals the chain, alignment is not query-only, one file is not shared by different chains |
| `l1.ligand.sanitization` | stop; warn above net charge ±2 | RDKit chemistry problems, valence, radicals |
| `l1.ligand.stereo_defined` | warn | Unassigned stereocentres and double bonds |
| `l1.ligand.identity` | stop; warn for metal ligands matching on skeleton only | InChIKey of the ligand file (3D stereo assigned) against CCD and PubChem |
| `l1.receptor.chains` | stop | Declared chains present; residue names against SEQRES at each label_seq position |
| `l1.receptor.altlocs` | warn | Alternate locations present without a declared `altloc_policy` |
| `l1.context.composition` | stop | Declared copies against the chains of the reference entity (co-folding tasks) |
| `l1.provenance.model_config` | stop | Executor, version, checkpoint (co-folding) and database snapshot (with an MSA) recorded |

Every threshold in a finding carries its origin, either the specification section or "harness
default, not yet calibrated", and an evidence level.

Ligands containing a metal get one extra step. When every RDKit valence problem sits on an atom
bonded to the metal, the metal bonds are disconnected, as standard InChI does, and
sanitisation is retried. Any other valence problem still stops. The InChIKey stereo and charge
blocks of such ligands depend on how each toolkit draws the metal bonds. So a match on the
first block alone is a warning carrying that reason, and a different first block still stops.

### Validation on further targets

Layers 0 and 1 were run live on these entries with manifests built from SIFTS, UniProt and
RCSB.

| Entry | Content | Verdict | Non-pass findings |
| --- | --- | --- | --- |
| 1STP | Streptavidin, biotin (3 stereocentres) | pass | none |
| 1HSG | HIV-1 protease homodimer, indinavir (5 stereocentres) | pass | none |
| 2RH1 | beta2 adrenergic receptor with T4 lysozyme insert, carazolol; 7 declared mutations over two UniProt entries on one chain | pass | none |
| 4HHB | Haemoglobin, two entities with two copies each, haem | pass_with_warnings | InChIKey skeleton-only match for haem (metal rule), layers 0 and 1 |
| 1M17 | EGFR kinase domain, erlotinib | pass_with_warnings | 2 residues with alternate locations, no policy declared |
| 3HTB | T4 lysozyme L99A, 6 declared mutations | pass_with_warnings | 10 residues with alternate locations, no policy declared |
| 4HHB alpha/beta | Interaction discovery task | pass | none |
| 1M17 + 4 ligands | Virtual screening task; one SMILES paired with the wrong CID, racemic ibuprofen | stop | InChIKey mismatch in layers 0 and 1; one undefined stereocentre |

Without declared mutations, 3HTB and 2RH1 stop in `l0.cross.uniprot_seqres` and list the
substitutions (L99A, M102Q, C54T, C97A, N187E and others). Declaring a mutation with the wrong
wild-type residue stops with the UniProt residue named. A missing ligand file stops in
`l1.ligand.sanitization`.

### Examples

`examples/3ptb_ligand_pose/` is a ligand pose run on PDB 3PTB: bovine trypsin (UniProt
P00760) with benzamidine (CCD BEN, PubChem 2332). Run live or offline, it gives 12 passes and
one warning: the amidine C=N bond in the SDF has no assigned geometry.
`examples/3ptb_faulty_inputs/` has seven planted faults and gives seven stops:
- a sequence with five N-terminal residues removed and three substitutions, failing two checks
- a query-only MSA
- a benzylamine SMILES declared as CCD BEN, failing the layer 0 and layer 1 identity checks
- a chain B that the entry does not have
- a missing checkpoint and database snapshot
The MSA in the clean example is synthetic test data.

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
| `p2rank_source` | `git clone` and Gradle build | fallback | Runs only when the `p2rank` release download fails; needs Java 17+ |
| `mmseqs` | mmseqs.com static build | yes | Links `mmseqs` |
| `foldseek` | mmseqs.com static build | yes | Links `foldseek` |
| `plinder_index`, `pinder_index` | `gs://plinder`, `gs://pinder` | yes | Needs `gcloud auth login`; skipped when gcloud is absent |
| `gnina` | GitHub release `gnina/gnina` | no | Executor hosts |
| `protenix_weights` | Protenix checkpoint host | no | Executor hosts, about 1.4 GB |
| `colabfold_databases` | ColabFold `setup_databases.sh` | no | About 1 TB uncompressed |
| `alphafold3_weights`, `pydock`, `phenix` | By request or licence | manual | Set `PAH_AF3_WEIGHTS`, `PAH_PYDOCK_HOME`, `PAH_PHENIX_HOME` |

Downloads go to a `.part` file and are renamed only when complete, with the sha256 recorded in
`.tools/externals.lock.json`. Archives are checked for paths that leave the target directory
before extraction. Assets already present are skipped unless `--force` is given. Fetched
binaries get small wrapper scripts in `.tools/bin`, which the doctor searches.

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

`pah doctor --profile local` on 2026-10-17, after `pah fetch`, gave 101 probes: 95 ok,
3 http_error, 1 missing, 2 manual.

| Probe | Status | Cause | Fix |
| --- | --- | --- | --- |
| `plinder`, `pinder` | http_error | Google Cloud Storage refuses anonymous reads | `gcloud auth login`, then `pah fetch` |
| `gnina.release` | http_error | The session's GitHub scope covers git reads, not release downloads | `pah fetch --only gnina` on the executor host |
| `molprobity` | missing | Ships with Phenix (academic licence) | Install Phenix where licensed |
| `alphafold3.weights` | manual | Weights issued by request | Set `PAH_AF3_WEIGHTS` |
| `pydock.licence` | manual | Academic licence, no public source | Set `PAH_PYDOCK_HOME` |

`pah fetch` installed MMseqs2 and Foldseek from mmseqs.com. P2Rank's release download was
refused here, so the `p2rank_source` fallback cloned and built it (P2Rank 2.6-alpha.8). On
the 3PTB receptor, its top-ranked pocket lists residues A57, A189 to A192, A195, A214 to A216
and A219.

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

### Running executors on GPU hosts

The core harness installs no engines. The optional `pah runtimes` commands install, build and
run them on GPU hosts: Boltz-1/2, Protenix v1 and v2, Chai-1, AlphaFold3, AlphaFold3 on OpenFold3
weights, ColabFold, OpenFold3, DiffDock-L, Gnina, AutoDock Vina and AutoDock-GPU. Where an
[optimisation kit](https://github.com/anthropics/uplifting-biomolecular-modeling) exists for the
tool, it is used by default in `fast` mode whenever it can engage on the host; otherwise the stock
tool runs and the reason is recorded in `runtime_record.json` and a `runtime.accel` finding.
`--accel stock` or `PAH_ACCEL=stock` turns the kits off, and `--accel kit` makes them mandatory.

```bash
pah runtimes list
pah runtimes hardware                         # GPUs here and the route each executor would take
pah runtimes kits fetch                       # kits at the commit pinned in configs/accel.yaml
pah runtimes build boltz2 --target apptainer  # kit image; it also runs stock as mode off
pah runtimes run boltz2 -p input=x.yaml --out runs/b2
```

Routes, launchers (host, Docker, Apptainer), the CSF3 and Modal entry points and what was
verified without a GPU are in [docs/RUNTIMES.md](docs/RUNTIMES.md).

## Layout

| Path | Contents |
| --- | --- |
| `src/pah/core/` | Models, event bus, manifest, task specs, check registry, engine, verdict policy |
| `src/pah/sources/` | Content-addressed cache, cached HTTP, Layer 0 source clients |
| `src/pah/checks/` | Shared check library (`layer0_provenance.py`, `layer1_integrity.py`) |
| `src/pah/doctor/` | Probes, catalog, runner, report |
| `src/pah/externals/` | `pah fetch`: downloader, installers per asset kind, lock file |
| `src/pah/runtimes/` | Executor install, image recipes, kit or stock routing, launchers, runner |
| `src/pah/interfaces/` | CLI (MCP server and HTTP API to follow) |
| `configs/` | Sources, tools, executors, externals, task specifications and deployment profiles as YAML |
| `examples/` | Run manifests |
| `deploy/csf3/`, `deploy/modal/` | Slurm and Modal entry points |
| `environment/conda.yml` | Conda-only tools |
| `third_party/skills/` | Pinned writing, figure and documentation skills ([sources](third_party/skills/SOURCES.md)) |
| `docs/` | Specification, architecture, executor contracts |

## Development

```bash
make check     # ruff, ruff format --check, mypy --strict, pytest
```

Tests do not use the network. Source responses recorded from the public APIs live in
`tests/fixtures/sources/` and are served by `tests/fakeweb.py`. Live tests carry the `network`
marker and are excluded by `make check`.

## Roadmap

| Milestone | Scope |
| --- | --- |
| 3 | Layer 2 to 5 checks, executor adapters, Slurm and Modal backends |
| 4 | Reports: PyMOL renders for every structure output, figures, provenance graph, text from the run record |
| 5 | MCP server and HTTP API with an SSE event stream and JSON schemas for the frontend |

## Licence

GPL-3.0. See [LICENSE](LICENSE).
