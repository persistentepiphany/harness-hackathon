# Executor contracts: structure prediction and docking tools

How each tool expects its input, how it is invoked, and what it writes out, all read from each tool's own repo (shallow `git clone`, read only, nothing run). Read on 2026-10-17. Citations are `path/in/repo:line` at the SHA given for each tool. **UNVERIFIED** means the cloned source does not settle the point.
To re-check a claim, clone the repo at the listed SHA and open the cited line.

| Tool | Repo @ SHA (commit date) | Version in repo | Code licence |
|---|---|---|---|
| Boltz | jwohlwend/boltz @ `b1ebfc46ecf57f5414e0d1a6f9027bbb122c53bc` (2026-05-29) | 2.2.1 (`pyproject.toml:7`) | MIT |
| Protenix | bytedance/Protenix @ `85767b811c40ed46e73a9b39519cf6bfca8701ba` (2026-09-21) | 2.0.0 (`protenix/version.py:15`) | Apache-2.0 |
| AlphaFold3 | google-deepmind/alphafold3 @ `03f4f48867748c164ae6d5144ae0529477df02e3` (2026-10-15) | n/a | Apache-2.0 (code). Weights fall under separate terms (`WEIGHTS_TERMS_OF_USE.md`, `OUTPUT_TERMS_OF_USE.md`). |
| Chai-1 | chaidiscovery/chai-lab @ `66c38d1fe5c6756a89ff8596b1dea87d305ec06f` (2026-06-30) | 0.6.1 (`chai_lab/__init__.py`) | Apache-2.0 for code **and weights** (`README.md:189`) |
| ColabFold | sokrypton/ColabFold @ `297da92fdff1348b8c99c2a946d7806a4eb4c25e` (2026-10-15) | 1.6.3 (`pyproject.toml:3`) | MIT (code). AF2 weight licence: UNVERIFIED (not in repo). |
| AutoDock Vina | ccsb-scripps/AutoDock-Vina @ `bb64e5e26b520569a86360d69248069b5e665b3f` (2026-10-15) | README badge 1.2.5 | Apache-2.0 |
| Gnina | gnina/gnina @ `6fe1ce2bb9c35c8067de9f49bb9169857dfbad70` (2026-06-29) | "GNINA 1.3" (README:17) | Dual GPL-2.0 / Apache-2.0. GPL applies because of OpenBabel (`README.md:472`). |
| DiffDock(-L) | gcorso/DiffDock @ `85c49b60d3e0b0182a59ee43a34a6d7036981284` (2025-05-02) | DiffDock-L is the default (README:13) | MIT |
| HADDOCK3 | haddocking/haddock3 @ `c8414e6e4dff70daf40ea548c775025add12f6fa` (2026-10-15) | 2026.10.0 (`pyproject.toml:7`) | Apache-2.0 |
| pyDock | not on GitHub | n/a | UNVERIFIED |

---

## 1. Boltz-1 / Boltz-2 (`jwohlwend/boltz`)

**Install / container:** `pip install boltz[cuda] -U`. Leave out `[cuda]` for CPU (`README.md:28`). The CLI entry point is `boltz = boltz.main:cli` (`pyproject.toml:38`). The repo documents no Docker image.
**Training cutoff:** no date given. The repo only mentions "our validation cut-off date" (`docs/evaluation.md:60`). UNVERIFIED.

### Input (YAML; FASTA is deprecated)
Schema: `docs/prediction.md:18-63`. Parser: `src/boltz/data/parse/schema.py:1006-1065`.
- `version` is optional and defaults to 1 (`schema.py:1006`).
- `sequences`: a list of `{<entity_type>: {...}}`, where the entity type is one of `protein|dna|rna|ligand` (`schema.py:1020-1023`).
- `id` is a string, or a list of strings for identical copies.
- `sequence` applies to polymers. A ligand takes exactly one of `smiles` or `ccd` (asserts at `schema.py:1029-1030`).
- Optional fields: `modifications[{position,ccd}]`, `cyclic`, and `msa` (protein only).
- `msa` takes one of:
  - a path to an `.a3m` file;
  - a CSV with columns `sequence,key`, used for paired multi-chain MSAs;
  - the literal `empty`, which forces single-sequence mode.
  If `msa` is missing, you must pass `--use_msa_server` (`docs/prediction.md:73-77`).
- `constraints`: `bond{atom1,atom2}`, `pocket{binder,contacts,max_distance,force}`, `contact{token1,token2,max_distance,force}`.
- `templates`: `cif|pdb`, `chain_id`, `template_id`, `force`, `threshold`.
- `properties: [{affinity: {binder: <ligand chain id>}}]`. The binder must be a `ligand` chain (`schema.py:1054-1065`). Only one binder is allowed, with at most 128 atoms (`docs/prediction.md:104`).
- The record name is the input file stem (`src/boltz/data/parse/yaml.py:67`).

Minimal example (protein + SMILES ligand + affinity):
```yaml
version: 1
sequences:
  - protein: {id: A, sequence: MVTPEGNVSLVDESLLVGVTDEDRAVRSAHQFY, msa: empty}
  - ligand:  {id: L, smiles: 'N[C@@H](Cc1ccc(O)cc1)C(=O)O'}
properties:
  - affinity: {binder: L}
```

### CLI
```
boltz predict <input.yaml|dir> --out_dir OUT [--use_msa_server] [--diffusion_samples N]
  [--recycling_steps 3] [--sampling_steps 200] [--output_format mmcif|pdb] [--seed S]
  [--use_potentials] [--model boltz1|boltz2] [--write_full_pae] [--write_full_pde] [--override]
```
- Option definitions: `src/boltz/main.py:818-1041`. Examples: `--diffusion_samples` (default 1) at :865, `--use_msa_server` at :925, `--model` (default `boltz2`) at :974, `--output_format` (default `mmcif`) at :902, `--write_full_pae` at :890.
- Without `--override`, existing predictions are reused (`main.py:341-359`).

### Output layout
**Important:** the real root is `OUT/boltz_results_<input_stem>/`. Boltz appends this folder itself (`main.py:1133-1134`).
```
OUT/boltz_results_<stem>/predictions/<name>/<name>_model_<k>.cif       # writer.py:150,159,170 (.pdb if --output_format pdb)
OUT/boltz_results_<stem>/predictions/<name>/confidence_<name>_model_<k>.json   # writer.py:186-220
OUT/boltz_results_<stem>/predictions/<name>/plddt_<name>_model_<k>.npz  # key "plddt", shape [N_tokens]   writer.py:224-229
OUT/boltz_results_<stem>/predictions/<name>/pae_<name>_model_<k>.npz    # key "pae", [N_tok,N_tok]; only with --write_full_pae  writer.py:232-238
OUT/boltz_results_<stem>/predictions/<name>/pde_<name>_model_<k>.npz    # key "pde"; only with --write_full_pde  writer.py:241-247
OUT/boltz_results_<stem>/predictions/<name>/affinity_<name>.json        # only if properties.affinity  writer.py:331-334
OUT/boltz_results_<stem>/processed/...                                  # main.py:745-752
```
- `<k>` is the rank by `confidence_score`, sorted descending, so `model_0` is the best (`writer.py:74-75`).
- Globs:
  - structures: `**/predictions/*/*_model_*.cif`
  - confidence: `**/predictions/*/confidence_*_model_*.json`

### Parsed fields
Confidence JSON (`writer.py:190-212`):

| Key | Type |
|---|---|
| `confidence_score` | float |
| `ptm` | float |
| `iptm` | float |
| `ligand_iptm` | float |
| `protein_iptm` | float |
| `complex_plddt` | float, 0-1 |
| `complex_iplddt` | float |
| `complex_pde` | float, Å |
| `complex_ipde` | float, Å |
| `chains_ptm` | `{str(chain_idx): float}` |
| `pair_chains_iptm` | `{str(i): {str(j): float}}` |

Per the docs, `confidence_score` = 0.8·complex_plddt + 0.2·iptm, using ptm instead for single chains (`docs/prediction.md:201`).

Affinity JSON (`writer.py:310-326`):
- `affinity_pred_value` (float): log10(IC50 in µM); lower means a stronger binder.
- `affinity_probability_binary` (float, 0-1).
- `affinity_pred_value1`, `affinity_probability_binary1`, `affinity_pred_value2`, `affinity_probability_binary2`: only present for the ensemble.
- Conversion to kcal/mol per `docs/prediction.md:249`: `(6 - y) * 1.364`.

---

## 2. Protenix (`bytedance/Protenix`)

**Install / container:**
- pip: `pip install --upgrade protenix` (`README.md:51`). Entry point: `protenix = runner.batch_inference:protenix_cli` (`setup.py:74`).
- Docker image: `ai4s-share-public-cn-beijing.cr.volces.com/release/protenix:1.0.0.4` (`docs/docker_installation.md:16`). It has the dependencies but not the Protenix source.

**Training cutoff** (`docs/supported_models.md` table; `README.md` "Key Model Descriptions"):

| Model | Cutoff |
|---|---|
| `protenix_base_default_v1.0.0` (CLI default) | 2021-09-30 |
| `protenix-v2` | 2021-09-30 |
| all v0.5.0 models | 2021-09-30 |
| `protenix_base_20250630_v1.0.0` | 2025-06-30 |

### Input (JSON; a top-level **list** of jobs)
Spec: `docs/infer_json_format.md:10-365`. Each job has:
- `name` (str)
- `sequences` (list)
- optional `covalent_bonds`, `constraint`, `modelSeeds`

`modelSeeds` is only honoured with `--use_seeds_in_json` (`runner/inference.py:545`).

Entity kinds:
- `proteinChain{sequence,count,id?,modifications[{ptmType,ptmPosition}],pairedMsaPath?,unpairedMsaPath?,templatesPath?}`
- `dnaSequence{sequence,count,modifications[{modificationType,basePosition}]}`
- `rnaSequence{…,unpairedMsaPath?}`
- `ligand{ligand,count}`, where `ligand` is one of: `"CCD_ATP"`, `"CCD_NAG_BMA"` (multi-CCD), a bare SMILES string, or `"FILE_/path.sdf"`
- `ion{ion:"MG",count}`. Ion codes have no `CCD_` prefix.

Minimal example:
```json
[{"name": "job1",
  "sequences": [
    {"proteinChain": {"sequence": "MAQGSHQIDFQVLHDLRQ", "count": 1}},
    {"ligand": {"ligand": "CCD_ATP", "count": 1}}
  ]}]
```
(Same shape as `examples/input.json`.)

### CLI
The subcommand is **`pred`**, not `predict`. Subcommands are registered at `runner/batch_inference.py:1352-1356`: `pred`, `json`, `msa`, `mt`, `prep`. No `predict` alias exists; `SuggestGroup` only suggests near matches (:568-584).
```
protenix pred -i input.json -o OUT [-s 101,102] [-e 5] [-c 10] [-p 200] [-n protenix_base_default_v1.0.0]
  [--use_msa true] [--msa_server_mode protenix|colabfold] [--use_template false] [--use_rna_msa false]
  [--use_seeds_in_json false] [--need_atom_confidence false] [-d bf16]
```
- Options are defined at `runner/batch_inference.py:599-763`:

  | Flag | Default | Line |
  |---|---|---|
  | `-o/--out_dir` | `./output` | :603 |
  | `-s/--seeds` | `101` | :604 |
  | `-e/--sample` | 5 | :607 |
  | `-n/--model_name` | n/a | :610-613 |
  | `--use_msa` | True | :617-619 |

- With `--use_msa` on and no MSA paths in the JSON, an MSA search runs through the server (`batch_inference.py:114`).

### Output layout
**Important:** `docs/infer_json_format.md:371-379` describes `<name>/<seed>/<name>_<seed>_sample_0.cif`. The code does something different, and the code wins.
- `dump_dir = OUT/<dataset_name="">/<name>/seed_<seed>` (`runner/dumper.py:99-107`, `runner/inference.py:604-606`)
- Files go under `predictions/` (`dumper.py:128`):
```
OUT/<name>/seed_<seed>/predictions/<name>_sample_<rank>.cif                     # dumper.py:196-200 (B-factor = atom pLDDT*100)
OUT/<name>/seed_<seed>/predictions/<name>_summary_confidence_sample_<rank>.json # dumper.py:264-268
OUT/<name>/seed_<seed>/predictions/<name>_full_data_sample_<rank>.json          # only --need_atom_confidence; dumper.py:269-275
OUT/ERR/                                                                        # inference.py:137
```
- `<rank>` is ordered by `ranking_score` within each seed; rank 0 is the best (`dumper.py:218-238`).
- Globs:
  - structures: `OUT/*/seed_*/predictions/*_sample_*.cif`
  - summary confidence: `OUT/*/seed_*/predictions/*_summary_confidence_sample_*.json`

### Parsed fields (summary confidence JSON)
Computed in `protenix/model/sample_confidence.py:111-205`:

| Key | Type / shape | Notes |
|---|---|---|
| `plddt` | float | **0-100**, mean atom pLDDT ×100 |
| `gpde` | float | |
| `ptm` | float | |
| `iptm` | float | |
| `chain_ptm` | [N_chain] | |
| `chain_iptm` | [N_chain] | |
| `chain_pair_iptm` | [N_chain, N_chain] | |
| `chain_pair_iptm_global` | [N_chain, N_chain] | |
| `chain_plddt` | [N_chain] | |
| `chain_pair_plddt` | [N_chain, N_chain] | |
| `chain_gpde` | | |
| `chain_pair_gpde` | | |
| `chain_pair_pae_mean` | | |
| `chain_pair_pae_min` | | |
| `has_clash` | | |
| `num_recycles` | | |
| `disorder` | | always 0 (:171) |
| `ranking_score` | | 0.8·iptm + 0.2·ptm + 0.5·disorder − 100·has_clash (:172-176) |
| `pb_ranking_score` | | only when an interested-ligand mask is set (:178-205) |
| `has_vdw_pl_clash` | | same condition |
| `pb_ranking_score_vdw_penalized` | | same condition |

Full-data JSON keys:
- `atom_plddt`
- `token_pair_pde`
- `contact_probs`
- `token_pair_pae`
- `token_has_frame`
- `token_asym_id`
- `atom_to_token_idx`

`atom_coordinate` and `atom_is_polymer` are removed before saving (`dumper.py:40-42`; `sample_confidence.py:100-215`).

---

## 3. AlphaFold3 (`google-deepmind/alphafold3`)

**Install / container:** build it yourself with `docker build -t alphafold3 -f docker/Dockerfile .` (`docs/installation.md:301`). The repo publishes no prebuilt image. Run with `docker run … alphafold3 python run_alphafold.py …` (`docs/installation.md:319-331`). Weights must be requested separately.
**Training cutoff:** the repo does not state the training cutoff. The `--max_template_date` default is `2021-09-30` with the comment "use the date from the AlphaFold 3 paper" (`run_alphafold.py:302-305`). Training cutoff UNVERIFIED.

### Input (fold input JSON, dialect `alphafold3`)
- Accepted versions are `JSON_VERSIONS = (1,2,3,4)` and the current one is 4 (`src/alphafold3/common/folding_input.py:46-48`).
- `docs/input.md:172` still says "1 or 2". That is stale; v4 adds `description`, per `docs/input.md:179-188`.
- An `alphafoldserver` dialect is also accepted (`folding_input.py:50-51`).

Top level (`docs/input.md:124-139`):
- `name`
- `modelSeeds` (≥1 int)
- `sequences`
- `bondedAtomPairs?`
- `userCCD?` / `userCCDPath?`
- `dialect: "alphafold3"`
- `version`

Entities:
- `protein{id,sequence,modifications[{ptmType,ptmPosition}],unpairedMsa|unpairedMsaPath,pairedMsa|pairedMsaPath,templates}`
- `rna{id,sequence,modifications,unpairedMsa…}`
- `dna{id,sequence,modifications}`
- `ligand{id, ccdCodes:[..] | smiles}`. Ions are ligands with `ccdCodes`.

MSA rules (`docs/input.md:455-480`):
- Leave both `unpairedMsa` and `pairedMsa` unset and the pipeline builds them.
- Set both to `""` for MSA-free.
- `unpairedMsa: <a3m>` plus `pairedMsa: ""` gives a custom MSA.
- Set `templates: []` for template-free.

Bonds look like `[["A",1,"CA"],["L",1,"C1"]]` (`docs/input.md:678-700`).

Minimal example, MSA-free so no databases are needed when run with `--run_data_pipeline=false`:
```json
{"name": "job1", "modelSeeds": [1], "dialect": "alphafold3", "version": 4,
 "sequences": [
   {"protein": {"id": "A", "sequence": "PVLSCGEWQL", "unpairedMsa": "", "pairedMsa": "", "templates": []}},
   {"ligand": {"id": "L", "ccdCodes": ["ATP"]}}]}
```
Setting both MSA fields to `""` is documented as valid: the model then gets only the query sequence (`docs/input.md:466-468`).

### CLI
```
python run_alphafold.py --json_path=in.json | --input_dir=DIR  --output_dir=OUT  --model_dir=~/models
  [--db_dir=...] [--run_data_pipeline=true] [--run_inference=true] [--num_diffusion_samples=5]
  [--num_recycles=10] [--num_seeds=N] [--max_template_date=2021-09-30] [--save_embeddings=false]
  [--save_distogram=false] [--force_output_dir=false] [--compress_large_output_files=false]
```

| Flag | Line in `run_alphafold.py` |
|---|---|
| `--json_path` | :80-84 |
| `--input_dir` | :85-89 |
| `--output_dir` (required) | :90-94, :1098 |
| `--model_dir` | :95-99 |
| `--run_data_pipeline` / `--run_inference` | :101-110 |
| `--num_recycles` / `--num_diffusion_samples` / `--num_seeds` | :381-400 |
| `--save_embeddings` / `--save_distogram` / `--save_terms_of_use` / `--force_output_dir` / `--compress_large_output_files` | :406-440 |

### Output layout
- The job directory is `OUT/<sanitised_name>` (`run_alphafold.py:1082`).
- `sanitised_name` turns spaces into `_` and keeps only `[A-Za-z0-9_.-]`. **Case is preserved** (`folding_input.py:1081-1085`).
- If that directory already exists and is non-empty, AF3 writes to `OUT/<name>_<YYYYmmdd_HHMMSS>` instead, unless `--force_output_dir` is set (`run_alphafold.py:863-866`).
```
OUT/<job>/<job>_data.json                                        # run_alphafold.py:658
OUT/<job>/seed-<seed>_sample-<i>/<job>_seed-<seed>_sample-<i>_model.cif
OUT/<job>/seed-<seed>_sample-<i>/<job>_seed-<seed>_sample-<i>_confidences.json
OUT/<job>/seed-<seed>_sample-<i>/<job>_seed-<seed>_sample-<i>_summary_confidences.json   # :685-695 + post_processing.py:119-123
OUT/<job>/<job>_model.cif | <job>_confidences.json | <job>_summary_confidences.json      # top-ranked; :717-726
OUT/<job>/<job>_ranking_scores.csv     # header: seed,sample,ranking_score   :729-733
OUT/<job>/TERMS_OF_USE.md
OUT/<job>/seed-<seed>_embeddings/<job>_seed-<seed>_embeddings.npz   # keys single_embeddings, pair_embeddings (opt)
OUT/<job>/seed-<seed>_distogram/<job>_seed-<seed>_distogram.npz     # key distogram (opt)  :701-713
```
- The CSV is named `<job>_ranking_scores.csv`, not plain `ranking_scores.csv`. Some prose in `docs/output.md:44` says otherwise; the code is `run_alphafold.py:729`.
- With `--compress_large_output_files`, the cif and full confidences files get a `.zst` suffix (`post_processing.py:125-130`).
- Globs:
  - structures: `OUT/*/seed-*_sample-*/*_model.cif`
  - summaries: `OUT/*/seed-*_sample-*/*_summary_confidences.json`

### Parsed fields
`*_summary_confidences.json` (`src/alphafold3/model/confidence_types.py:178-187`):

| Key | Type / shape |
|---|---|
| `ptm` | float |
| `iptm` | float |
| `ranking_score` | float |
| `fraction_disordered` | float |
| `has_clash` | float (0/1) |
| `chain_pair_pae_min` | [C, C] |
| `chain_pair_iptm` | [C, C] |
| `chain_ptm` | [C] |
| `chain_iptm` | [C] |
| `chain_ids` | [C] str |

`ranking_score` = 0.8·ipTM + 0.2·pTM + 0.5·disorder − 100·has_clash (`docs/output.md:172-175`).

`*_confidences.json` (`confidence_types.py:240-245`):

| Key | Type / shape |
|---|---|
| `pae` | [T, T] |
| `token_chain_ids` | [T] str |
| `token_res_ids` | [T] int |
| `atom_plddts` | [A] float, 0-100 |
| `atom_chain_ids` | [A] str |
| `contact_probs` | [T, T] |

---

## 4. Chai-1 (`chaidiscovery/chai-lab`)

**Install / container:**
- `pip install chai_lab==0.6.1` (`README.md:15`). Entry point: `chai-lab = chai_lab.main:cli` (`pyproject.toml:73`).
- Weights are downloaded automatically to `<pkg>/downloads`, or to `$CHAI_DOWNLOADS_DIR` if set (README:65-71).
- `Dockerfile.chailab` is a build recipe. No published image name is documented (UNVERIFIED).

**Training cutoff:** not stated in the repo. UNVERIFIED.

### Input (FASTA with typed headers)
Parser: `chai_lab/data/dataset/inference_dataset.py:235-282`.
- Header format is `>{type}|{name}` or `>{type}|name={name}`.
- `type` is one of `protein`, `ligand`, `rna`, `dna`, `glycan`.
- Exactly one label part is allowed; anything else raises (:271-282).
- Ligands are given as SMILES.
- Modified residues are written inline, e.g. `AAA(SEP)AAA` (`examples/predict_structure.py:11-14`).
```
>protein|name=rec
AGSHSMRYFSTSVSRPGRGEPRFIAVGYVDDTQFVRFDSDAASPRGEPRAPWVEQEGPEYWDRETQKYKRQ
>ligand|name=lig
CCCCCCCCCCCCCC(=O)O
```
Optional extras:
- MSAs: a directory of `<seqhash>.aligned.pqt` parquet files with columns `sequence, source_database, pairing_key, comment` (`examples/msas/README.md`).
- Restraints CSV header: `chainA,res_idxA,chainB,res_idxB,connection_type,confidence,min_distance_angstrom,max_distance_angstrom,comment,restraint_id` (`examples/restraints/contact.restraints:1`).

### CLI
Typer wraps `run_inference` (`chai_lab/main.py`; signature at `chai_lab/chai1.py:499-522`):
```
chai-lab fold INPUT.fasta OUTPUT_DIR [--use-esm-embeddings/--no-use-esm-embeddings] [--use-msa-server]
  [--msa-server-url URL] [--msa-directory DIR] [--constraint-path CSV] [--use-templates-server]
  [--template-hits-path M8] [--num-trunk-recycles 3] [--num-diffn-timesteps 200] [--num-diffn-samples 5]
  [--num-trunk-samples 1] [--seed N] [--device cuda:0] [--fasta-names-as-cif-chains]
```
- The kebab-case flag names come from Typer's automatic conversion of the parameter names. They were not shown by running `--help` (unexecuted).
- `OUTPUT_DIR` must be missing or empty; otherwise an assert fires (`chai1.py:530-533`).

### Output layout
```
OUTPUT_DIR/pred.model_idx_<i>.cif        # chai1.py:1023 (B-factor = 100*pLDDT)
OUTPUT_DIR/scores.model_idx_<i>.npz      # chai1.py:1048-1050
OUTPUT_DIR/msa_depth.pdf                 # chai1.py:976 (when MSAs used)
OUTPUT_DIR/trunk_<t>/...                 # only if --num-trunk-samples > 1; chai1.py:556-560
```
- `<i>` is the diffusion **sample index and is not sorted**: the loop is `for idx in range(num_diffn_samples)`. The harness must rank by `aggregate_score` itself.
- Globs: `pred.model_idx_*.cif`, `scores.model_idx_*.npz`.

### Parsed fields (npz keys)
From `chai_lab/ranking/rank.py:115-125`:

| Key | Shape | Notes |
|---|---|---|
| `aggregate_score` | (1,) | 0.2·ptm + 0.8·iptm − 100·has_inter_chain_clashes (`rank.py:95-99`) |
| `ptm` | (1,) | |
| `iptm` | (1,) | |
| `per_chain_ptm` | (1, C) | |
| `per_chain_pair_iptm` | (1, C, C) | |
| `has_inter_chain_clashes` | (1,) bool | |
| `chain_chain_clashes` | (1, C, C) int | |

pLDDT is **not** in the npz. Read it from the CIF B-factors.

---

## 5. ColabFold / AF2-multimer (`sokrypton/ColabFold`)

**Install / container:**
- pip: `pip install colabfold[alphafold,openmm] jax[cuda12] openmm[cuda12]` (`README.md:72`). Entry point: `colabfold_batch = colabfold.batch:main` (`pyproject.toml:58`).
- Docker: `ghcr.io/sokrypton/colabfold:1.6.3-cuda12` (`README.md:84`).

**Training cutoff / weights licence:** AF2 parameters are not part of this repo. UNVERIFIED.

### Input
Parser: `colabfold/input.py:276-320`.
- **CSV/TSV:** needs columns `id` and `sequence`. Chains in `sequence` are joined with `:`. Optional columns `a3mpath` and `templatepath` (:281-292).
- **FASTA** (`.fasta/.faa/.fa`): the header becomes the job name. A `:`-separated sequence means a complex.
- In complex mode, entries with `|` are classified as non-protein (`moltype|seq|copies`) by `classify_molecules` (:118-143). These are not used by AF2.
- **A3M:** the first sequence is the query, and the file stem becomes the job name (:294-301).
- **Directory:** any of `.a3m/.fasta/.faa/.fa/.pdb/.cif` inside it (:337).
- The job name is passed through `safe_filename`: any character that is not alphanumeric or `_ . -` becomes `_` (:8-9; `batch.py:1458`).
```
id,sequence
cplx1,PIAQIHILEGRSDEQKETLIREVSEAISRSLDAPLTSVRVIITEMAKGHFGIGGELASK:MKTAYIAKQRQISFVKSHFSRQ
```

### CLI
`colabfold_batch INPUT RESULTS_DIR [opts]`. Positional arguments are at `batch.py:1817-1822`.
- Key options:

  | Flag | Default | Line in `batch.py` |
  |---|---|---|
  | `--msa-mode` | `mmseqs2_uniref_env`; also `single_sequence` etc. | :1831 |
  | `--pair-mode` | `unpaired_paired` | :1844-1847 |
  | `--templates` | n/a | :1861 |
  | `--num-recycle` | n/a | :1910 |
  | `--num-seeds` | 1 | :1932 |
  | `--random-seed` | 0 | n/a |
  | `--num-models` | 5 | :1945 |
  | `--model-type` | `auto`; also `alphafold2_ptm`, `alphafold2_multimer_v1/v2/v3`, … | :1953-1967 |
  | `--amber` | n/a | :2029 |
  | `--num-relax` | n/a | n/a |
  | `--rank` | `auto`; also plddt, ptm, iptm, multimer | :2078-2082 |
  | `--skip-output` | msa, plots, pae_json | :2125-2128 |
  | `--overwrite-existing-results` | n/a | n/a |
  | `--host-url` | n/a | n/a |

- With `--rank auto`, complexes rank by `multimer` and monomers by `plddt`. Non-pTM models always rank by plddt (`batch.py:1329-1332`).
- The formula for `ranking_confidence` lives in the alphafold-colabfold fork, not in this repo. UNVERIFIED.

### Output layout
All files go flat into `RESULTS_DIR`. The per-model tag is `{model_type}_{model_name}_seed_{seed:03d}` (`batch.py:482`), with `model_name = model_{n}` (`colabfold/alphafold/models.py:264`). After ranking, files are renamed to `{jobname}_{kind}_rank_{NNN}_{tag}.{ext}` (`batch.py:671-675`; `file_manager` at :394-405).
```
<job>_unrelaxed_rank_001_alphafold2_multimer_v3_model_1_seed_000.pdb   # batch.py:583
<job>_relaxed_rank_001_<tag>.pdb          # only first --num-relax ranks; :667
<job>_scores_rank_001_<tag>.json          # :627-631
<job>_predicted_aligned_error_v1.json     # rank-1 PAE, keys predicted_aligned_error, max_predicted_aligned_error; :1684-1687
<job>.a3m  <job>_coverage.png  <job>_pae.png  <job>_plddt.png  <job>.done.txt   # :1522,1554,1695,1710,1469
config.json  log.txt  cite.bibtex                                       # :1420, :2234, :1426 (citations.py:139)
```
- Ranks are 1-based and `rank_001` is the best.
- Globs:
  - structures: `*_unrelaxed_rank_*_*.pdb`
  - scores: `*_scores_rank_*_*.json`
  - Use the regex `_rank_(\d{3})_(.+)_seed_(\d{3})` to recover rank, tag and seed.

### Parsed fields (scores JSON)
From `batch.py:596-631`:

| Key | Type / shape | When present |
|---|---|---|
| `plddt` | list[float], length L, 0-100 | always |
| `max_pae` | float | when PAE exists |
| `pae` | [L, L] | when PAE exists |
| `ptm` | float | when PAE exists |
| `iptm` | float | complexes only (popped for monomers at :553) |
| `ipsae` | `{"A-B": float}` | complexes (`colabfold/alphafold/ipsae.py:61`) |
| `pdockq` | `{"A-B": float}` | complexes |
| `pdockq2` | `{"A-B": float}` | complexes |
| `pairwise_actifptm` | dict | only with `--calc-extra-ptm` (`extra_ptm.py:270,288`) |
| `pairwise_iptm` | dict | only with `--calc-extra-ptm` |
| `per_chain_ptm` | dict | only with `--calc-extra-ptm` |
| `actifptm` | float | only with `--calc-extra-ptm` |

---

## 6. AutoDock Vina (`ccsb-scripps/AutoDock-Vina`)

**Install / container:** `pip install vina` (Python bindings), or `conda install -c conda-forge …` then `pip install vina` (`docs/source/installation.rst:33,52-53`). The binary is `vina`. No Docker image is documented. A docking engine has no training cutoff (N/A).

### Input
- Receptor and ligand must be **PDBQT**. Use Meeko or ADFR for preparation; `mk_export.py` converts the output back to SDF (`docs/source/docking_basic.rst:136-145`).
- The config file holds the same options as the CLI, one per line as `key = value`. Example (`docking_basic.rst:111-118`):
```
receptor = rec.pdbqt
ligand = lig.pdbqt
center_x = 15.190
center_y = 53.903
center_z = 16.917
size_x = 20.0
size_y = 20.0
size_z = 20.0
exhaustiveness = 8
```

### CLI
Options are defined at `src/main/main.cpp:180-255`.
```
vina --receptor rec.pdbqt --ligand lig.pdbqt [--flex flex.pdbqt] [--config box.txt]
     --center_x X --center_y Y --center_z Z --size_x SX --size_y SY --size_z SZ
     [--scoring vina|vinardo|ad4] [--maps PREFIX] [--exhaustiveness 8] [--num_modes 9]
     [--energy_range 3.0] [--min_rmsd 1.0] [--spacing 0.375] [--seed N] [--cpu 0]
     [--out out.pdbqt] [--score_only] [--local_only] [--autobox] [--batch L1 L2 --dir OUTDIR]
```
- `--scoring` defaults to `vina` (`main.cpp:122,184`).
- `ad4` requires `--maps` and is incompatible with `--receptor` (:308-330).
- `--autobox` only works with `--score_only` or `--local_only` (:196).

### Output layout
- The default output for a single ligand is `<ligand without .pdbqt>_out.pdbqt` (`src/lib/utils.cpp:56-61`).
- Batch mode writes `<dir>/<ligand>_out.pdbqt` (:72-79).
- Repeated names get `_instance<i>_out.pdbqt` (:64-69).
- Output is multi-model PDBQT: `MODEL n` … `ENDMDL` (`src/lib/model.cpp:736,744`). Poses are sorted best first.

### Parsed fields
REMARK lines per model (`src/lib/vina.cpp:535-555`):
```
REMARK VINA RESULT:    <energy kcal/mol>  <rmsd_lb>  <rmsd_ub>     # %9.3f each; RMSD vs best mode
REMARK INTER + INTRA:  <total>
REMARK INTER:          <inter>
REMARK INTRA:          <intra>
REMARK CONF_INDEPENDENT: <x>      # ad4 only
REMARK UNBOUND:        <unbound>
```
Regex: `^REMARK VINA RESULT:\s+(-?\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)`

### Python API
Class `vina.Vina`, in `build/python/vina/vina.py`:

| Method | Line |
|---|---|
| `Vina(sf_name='vina', cpu=0, seed=0, no_refine=False, verbosity=1)` | :19 |
| `set_receptor(rigid_pdbqt_filename, flex_pdbqt_filename)` | :126 |
| `set_ligand_from_file(path)` | :164 |
| `set_ligand_from_string(s)` | :188 |
| `set_weights` | :209 |
| `compute_vina_maps(center, box_size, spacing=0.375, force_even_voxels=False)` | :232 |
| `load_maps(prefix)` | :268 |
| `write_maps` | :280 |
| `write_pose(fn, remarks='', overwrite=False)` | :306 |
| `write_poses(fn, n_poses=9, energy_range=3.0, overwrite=False)` | :323 |
| `poses(n_poses=9, energy_range=3.0, coordinates_only=False)` | :348 |
| `energies(n_poses=9, energy_range=3.0)` | :374 |
| `randomize(max_steps=10000)` | :398 |
| `score(unbound_energy=None)` | :407 |
| `optimize(max_steps=0)` | :431 |
| `dock(exhaustiveness=8, n_poses=20, min_rmsd=1.0, max_evals=0)` | :456 |

Return shapes:
- `energies()`: ndarray with one row per pose. Columns are `[total, inter, intra, torsions, intra_best_pose]` (vina/vinardo) or `[total, inter, intra, torsions, -intra]` (ad4) (:381-389).
- `score()`: `[total, lig_inter, flex_inter, other_inter, flex_intra, lig_intra, torsions, lig_intra_best]`.

---

## 7. Gnina (`gnina/gnina`)

**Install / container:**
- The recommended route is the prebuilt binary from GitHub releases (`README.md:63`).
- A Docker image exists under hub.docker.com/u/gnina (`README.md:58`). The exact image name and tag are not written in the repo (UNVERIFIED; often `gnina/gnina`).
- Dockerfiles: `docker/ubuntu-22.04`, `docker/ubuntu-24.04`, `docker/compat`.
- No pip package.

**Training data:** the CNN models are trained on CrossDocked2020 / PDBbind-derived sets (`README.md` model names). No cutoff date is given. UNVERIFIED.

### Input
- Receptor: any OpenBabel-readable format (pdb, pdbqt, …).
- Ligand: sdf, mol2, pdbqt, and so on; the format comes from the file extension.
- The box is either explicit `center_*`/`size_*`, or `--autobox_ligand ref.sdf` with `--autobox_add` (default +4 Å).

### CLI
README:136-190 and options at `gninasrc/main/main.cpp:916-1057`:
```
gnina -r rec.pdb -l lig.sdf --autobox_ligand ref.sdf [--autobox_add 4] -o docked.sdf(.gz)
  [--center_x/y/z --size_x/y/z] [--scoring vina|vinardo|ad4_scoring|default|dkoes_*]
  [--cnn_scoring none|rescore|refinement|metrorescore|metrorefine|all] [--cnn MODEL]
  [--exhaustiveness 8] [--num_modes 9] [--seed N] [--cpu N] [--minimize] [--score_only]
  [--pose_sort_order CNNscore|CNNaffinity|Energy] [--no_gpu] [--log FILE] [--config FILE]
```
- `--cnn_scoring` defaults to `rescore` (`main.cpp:1019`).
- `--pose_sort_order` defaults to `CNNscore` (:967).
- The default CNN is an ensemble of `dense_1_3`, `dense_1_3_PT_KD_3` and `crossdock_default2018_KD_4` (README "CNN Scoring").

### Output layout
- A single file at the `-o` path. Its format comes from the extension; `.gz` is supported.
- There is no directory structure.

### Parsed fields
Native SDF output, per molecule, from `gninasrc/lib/result_info.cpp:122-151`:

| SD tag | Type | When present |
|---|---|---|
| `minimizedAffinity` | float, kcal/mol | always |
| `minimizedRMSD` | float | only if computed (rmsd ≥ 0) |
| `CNNscore` | float, 0-1 pose probability | if cnnscore ≥ 0 |
| `CNNaffinity` | float, pK units per gnina papers (UNVERIFIED in source) | if ≠ 0 |
| `CNN_VS` | float | if CNNaffinity ≠ 0; equals CNNscore × CNNaffinity (:141-142) |
| `CNNaffinity_variance` | float | ensemble only |
| `atomic_interaction_terms` | n/a | with `--atom_term_data` |

PDBQT output instead uses `REMARK minimizedAffinity|minimizedRMSD|CNNscore|CNNaffinity <v>` lines (:159-172). Other formats get the same property names set through OpenBabel (:185-205).

---

## 8. DiffDock / DiffDock-L (`gcorso/DiffDock`)

**Install / container:**
- conda `environment.yml`. No pip package.
- Docker: `docker pull rbgcsail/diffdock`, or build with `docker build . -f Dockerfile -t diffdock` (`README.md:85-102`).
- The default model is DiffDock-L. The original DiffDock is only available from git history (README:13).

**Training cutoff:** not stated (PDBBind / BindingMOAD splits only). UNVERIFIED.

### Input
- **Single complex:** `--protein_path rec.pdb` (or `--protein_sequence SEQ`, which folds with ESMFold) plus `--ligand_description <SMILES or path>` and `--complex_name`.
- **Batch:** `--protein_ligand_csv file.csv` with columns `complex_name,protein_path,ligand_description,protein_sequence` (`inference.py:156-160`; `data/protein_ligand_example.csv`). Empty cells become None. A missing name becomes `complex_<i>` (:167).
```
complex_name,protein_path,ligand_description,protein_sequence
c1,data/1a0q/1a0q_protein_processed.pdb,COc(cc1)ccc1C#N,
```

### CLI
Arguments are at `inference.py:59-103`.
```
python -m inference --config default_inference_args.yaml --protein_ligand_csv in.csv --out_dir OUT
  [--samples_per_complex 10] [--inference_steps 20] [--batch_size 10] [--save_visualisation]
  [--gnina_minimize --gnina_path gnina]
```
- `default_inference_args.yaml` points at `./workdir/v1.1/score_model` and `./workdir/v1.1/confidence_model`.
- `--out_dir` defaults to `results/user_inference` (:69).

### Output layout
From `inference.py:169-170` and :275-299:
```
OUT/<complex_name>/rank1.sdf                          # copy of top pose
OUT/<complex_name>/rank<k>_confidence<c:.2f>.sdf      # k = 1..samples_per_complex, sorted by confidence desc
OUT/<complex_name>/rank<k>_reverseprocess.pdb         # only with --save_visualisation
```
- `c` is the raw confidence-model output, formatted `%.2f`. It can be negative (e.g. `rank3_confidence-1.27.sdf`).
- Parse with the regex `rank(\d+)_confidence(-?\d+\.\d+)\.sdf`.
- Complexes that fail are skipped with a warning, so their directory stays empty (:227).

### Parsed fields
- Pose coordinates come from the SDF.
- Confidence (float) and rank (int) come **only from the filename**. No SD properties are written.

---

## 9. HADDOCK3 (`haddocking/haddock3`)

**Install / container:**
- `pip install haddock3` (`README.md:29`). Entry point: `haddock3 = haddock.clis.cli:maincli` (`pyproject.toml:87`).
- The pip package bundles a CNS binary at `haddock/bin/cns`; you may need to recompile it (`docs/pages/INSTALL.md:40-63`).
- A `Dockerfile` is in the repo. No published image is documented (UNVERIFIED).
- Physics-based; no training cutoff (N/A).

### Input (run config, TOML-like `.cfg`/`.toml`)
- **Global keys:**
  - `run_dir`
  - `molecules` (list of PDB paths)
  - `mode = "local"` (default `local`)
  - `ncores` (default 4)
  - `clean` (default true)
  - `offline`
  - `postprocess` (default true)
  - Defaults: `src/haddock/modules/defaults.yaml` (ncores :12, mode :36, clean :113, offline :133) and `src/haddock/core/optional.yaml:14`.
- **Module sections:** each `[<module>]` section adds one step, in order. Repeating a section (e.g. several `[caprieval]`) is allowed. Sub-tables look like `[topoaa.mol1]`.
- **Module names:**

  | Group | Modules |
  |---|---|
  | topology | `topoaa`, `topocg` |
  | sampling | `rigidbody`, `gdock`, `lightdock` |
  | refinement | `flexref`, `emref`, `mdref`, `openmm`, `cgtoaa` |
  | scoring | `emscoring`, `mdscoring`, `prodigyprotein`, `prodigyligand`, `sasascore`, `deeprank` |
  | analysis | `caprieval`, `caprifilter`, `clustfcc`, `clustrmsd`, `rmsdmatrix`, `ilrmsdmatrix`, `seletop`, `seletopclusts`, `filter`, `contactmap`, `alascan`, `dnascan`, `rnascan` |
  | extras | `exit` |

  (Directory listing of `src/haddock/modules/*/`.)

Minimal example (cf. `examples/docking-protein-protein/docking-protein-protein-test.cfg`):
```toml
run_dir = "run1"
mode = "local"
ncores = 4
molecules = ["rec.pdb", "lig.pdb"]
[topoaa]
[rigidbody]
ambig_fname = "air.tbl"
sampling = 20
[flexref]
ambig_fname = "air.tbl"
[emref]
ambig_fname = "air.tbl"
[clustfcc]
[seletopclusts]
[caprieval]          # reference_fname optional; default = best-scoring model (caprieval/defaults.yaml:1-7)
```

### CLI
`haddock3 run.cfg`. Related tools: `haddock3-analyse`, `haddock3-clean`, `haddock3-traceback`, `haddock3-unpack`, among others.

### Output layout
- Step folders are named `<idx>_<module>`, with zero-filled indices starting at `0_topoaa` (`src/haddock/gear/zerofill.py:84-99`).
```
<run_dir>/data/                                   # gear/prepare_run.py:1033
<run_dir>/<N>_<module>/io.json                    # core/defaults.py:23; libontology.py:160-165
<run_dir>/<N>_<module>/<module>_<i>.pdb[.gz]      # e.g. 1_rigidbody/rigidbody_373.pdb; .gz when clean=true (gear/clean_steps.py:47)
<run_dir>/<N>_caprieval/capri_ss.tsv              # caprieval/__init__.py:173-180
<run_dir>/<N>_caprieval/capri_clt.tsv             # :183-192
<run_dir>/<N>_caprieval/capri_ss_multiref.tsv     # only with >1 reference; :196-203
<run_dir>/analysis/<N>_caprieval_analysis/report.html   # postprocess; core/defaults.py:37; clis/cli_analyse.py:775,853
<run_dir>/traceback/traceback.tsv                 # core/defaults.py:40; clis/cli_traceback.py:351
```

### Parsed fields
**`capri_ss.tsv`** is tab-separated with one row per model (`src/haddock/libs/libcapri.py:846-866`). Columns:
- `model`: relative path, e.g. `../1_rigidbody/rigidbody_373.pdb`
- `md5`
- `caprieval_rank`
- `score`
- `irmsd`
- `fnat`
- `lrmsd`
- `ilrmsd`
- `dockq`
- `rmsd`
- `cluster_id`
- `cluster_ranking`
- `model-cluster_ranking`
- then every key of the unweighted energies dict: `air`, `angles`, `bonds`, `bsa`, `cdih`, `coup`, `dani`, `desolv`, `dihe`, `elec`, `improper`, `rdcs`, `rg`, `total`, `vdw`, `vean`, `xpcs` (see the header of `tests/golden_data/capri_ss_example.tsv`).
- If there is more than one reference, a `ref_id` column is added.
- Missing values are written as `-`.
- Rows are sorted by `sortby` (default `score`) in ascending order (`caprieval/defaults.yaml:127-150`).
- The golden test file is older and lacks the `rmsd` column; the code is authoritative.

**`capri_clt.tsv`** starts with a `#` comment banner, then a header row (`libcapri.py:912-1000`). Columns:
- `cluster_rank`
- `cluster_id`
- `n`
- `under_eval` (`yes` or `-`)
- `score`, `score_std`
- `<k>`, `<k>_std` for each k in `irmsd, fnat, lrmsd, dockq, ilrmsd, rmsd`
- `<e>`, `<e>_std` for each e in `air, bsa, desolv, elec, total, vdw`
- `caprieval_rank`

Statistics are computed over the top `clt_threshold` (default 4) models of each cluster. When parsing, skip the `#` lines.

**`io.json`** is jsonpickle-encoded `{"input": [...], "output": [...]}` (`libontology.py:160-173`). Each entry is a `PDBFile` with these attributes (`libontology.py:37-55, 76-110`):
- `file_name`
- `path` (absolute)
- `rel_path`
- `md5`
- `score`
- `unw_energies` (dict)
- `clt_id`
- `clt_rank`
- `clt_model_rank`
- `seed`
- `topology`
- `restr_fname`
- `created`

The objects carry `py/object` tags, so either use `jsonpickle.decode` or read the plain fields from the dicts.

---

## 10. pyDock

- **Source:** not on GitHub. Nothing was cloned.
- **PyPI:** the `pydock` package (0.0.8) is an **unrelated** Docker-CLI wrapper from Duckietown (`PKG-INFO`: "A decent Python wrapper for Docker CLI", MIT). It is a name collision. `pyDock3`, `pydock3` and `pyDockDNA` are not on PyPI.
- **Everything else is UNVERIFIED:** input format, CLI, output layout, score fields, licence, install route and container. It cannot be verified from source here, so do not build an executor contract from memory.

---

## Cross-tool gotchas for the harness

- **Boltz** nests its output under `boltz_results_<stem>/`. **Protenix** nests it under `<name>/seed_<seed>/predictions/`. Do not trust the two tools' docs on these paths.
- **Protenix**:
  - The subcommand is `pred`.
  - `plddt` is on a 0-100 scale. Boltz's `complex_plddt` is 0-1.
- **AF3**:
  - The CSV is `<job>_ranking_scores.csv`.
  - The job directory may get a timestamp suffix unless `--force_output_dir` is set.
  - Name case is preserved.
- **Chai** files are not rank-ordered, and the output directory must be empty.
- **ColabFold** ranks are 1-based (`rank_001`). Monomer score files have no `iptm`.
- **DiffDock** confidence appears only in the filename, and it can be negative.
- **Vina** reads and writes only PDBQT. **Gnina** writes SD tags.
- **HADDOCK3** model paths in `capri_ss.tsv` are relative to the caprieval step folder, and may be `.gz` once cleaned.
