# Dock Harness deck: figures, numbers and references

Each slide of `media/deck/dock-harness.pptx` (source `media/deck/outline.json`) with its image, the
file the image came from, and every number on the slide with the file and line it comes from.
Hashes are sha256 of the files as checked on 2026-10-18. Line numbers refer to those versions.
Composite images are rebuilt with `bash media/deck/make_assets.sh` from the repository root.

Run identifiers used below:

| Short name | Directory |
| --- | --- |
| run 1 | `bench/runs/2026-10-17T1611Z-426bfe9/` |
| run 2 | `bench/runs/2026-10-17T1752Z-2f5a1c7/` |
| run 3 | `bench/runs/2026-10-17T1859Z-849c856/` |

## Source file hashes

| File | sha256 |
| --- | --- |
| `README.md` | `5330ab915a87792d2efbbf1d77d6c1b07169e38738b3665a673efd3979ddbfca` |
| `docs/SPECIFICATION.md` | `cc511b4411f223d8da11e1a758602ff6f1558faf0716ed5a78f618d9a2c15f4a` |
| `configs/sources.yaml` | `8b3799e2d4dda97a2a2dc2c1ef6e6a963107bc23120f491931e4b5b13c547851` |
| `configs/executors.yaml` | `d11ec26687140703086c47b4138c4bca2fd1109d9fbf4e816f201ead66dc7ea0` |
| `configs/runtimes.yaml` | `1fb0d9a6929bcb2ed99bc3a5fd83184bd0cbd4fa83f96d7fb433478f444a1286` |
| `bench/README.md` | `ed0bda2e737d7530ab0325da4a7994cb69f39c4b6be9bb957827a8d47d7a25fc` |
| `bench/finding/flip.csv` | `0efd9a74674c2460cefe3cde4a5ef156d652205940014c6ce8c570a267a08bf7` |
| `bench/finding/values.csv` | `2e01979cd1035baa17e6d412edeae1585af3b1d45e5808f849334040ec13d6d0` |
| run 1 `report.md` | `481c5cddb72f1a82da5f3948725e2cc7a2bfb28dc354cf11efc2d6e39cbb3f1c` |
| run 2 `report.md` | `78ab5b99b3f1795d1e8b8015f206b1e4779f6db40d5879ce3c1657d6fec4008b` |
| run 3 `report.md` | `99c371968584c6c175c4059819b3eea0c5bd1643e9f4355ece1fc479889283d1` |
| `out/deck/evidence/python_test_functions.txt` | `00cdf4e8ce306d9762e473f8428f95102401da679946766d36a2d0c4bc28e088` |
| `out/deck/evidence/web_vitest_list.txt` | `e6ddd765677512583f1e011a06ceb9b9e1605fb71c181e597c6b40a562140c9e` |
| `out/deck/evidence/web_playwright_list.txt` | `de7394a664872308a9175c8b780ac9a73f9d678f3c95d149d55b376e33b1357d` |
| `out/deck/evidence/pah_checks.txt` | `59c73d3b403629f71ace8d873ca4ab79a932d0f0e2bfeb6d9c06627fd4aed835` |

The four `out/deck/evidence/` files were written on 2026-10-18 from this checkout:
`grep -rn "def test_" tests` (394 lines), `npx vitest list` in `web/` (162 lines, one test per
line), `npx playwright test --list` in `web/` (last line `Total: 63 tests in 5 files`) and
`.venv/bin/pah checks` (70 lines, one registered check per line).

## Slides

### 1. Dock Harness (title)

No image and no numbers.

### 2. 12 perturbed poses: valid on confidence, rejected with the harness (new)

| Image | Made from | sha256 |
| --- | --- | --- |
| `media/figures/twelve/grid.png` (used directly) | 12 PyMOL renders by `media/videos/video-c/render_twelve.py`, documented in `media/figures/twelve/README.md` (lines 3-7) with values in `twelve.json` | grid `1fdc32798f20ef3ad130a0dc68363922b6b99f65525cfcff8f6b436fc4a1fbae`; `twelve.json` `567047506cf063b975f4149929c8a81ad20d9ab9b8410c34a91550412bc3288a`; `README.md` `895432abd4b2314b4b8167f5c215cb211b195a430579c2528435f3af5acaf894` |

The 12 source structures and their sha256 are listed in `media/figures/twelve/README.md` lines
15-26. Every ipTM and pocket pLDDT printed in the grid was compared with the fact-file table of the
run's `report.md` (CDK2 line 109, FtsE line 113, glucose DH line 117, MEK1 line 121 in each of the
three reports); all 24 values match.

| Value | Source |
| --- | --- |
| 12 perturbed Boltz-2 predictions, 4 systems by 3 runs | `media/figures/twelve/README.md` lines 3, 7 |
| Without the harness (score only): 12 of 12 called valid | `<sys>_pert · Boltz-2` rows in each run's `report.md` (lines 88, 92, 96, 100), score-only column `valid (valid,valid,valid)`; `media/figures/twelve/README.md` lines 15-26, Arm A |
| With the harness (fact file): 12 of 12 rejected | same rows, fact-file column `invalid (invalid,invalid,invalid)`; README lines 15-26, Arm B |
| ipTM and pocket pLDDT per panel | `media/figures/twelve/README.md` lines 15-26; run `report.md` lines 109, 113, 117, 121 |
| Best published confidence ROC AUC 0.756 for poses within 2 Å | Kim et al. 2026 [R2], full text: "AF3 L-pLDDT (AUC = 75.6)"; 489 evaluated complexes (speaker notes) |

### 3. Six layers; each check carries evidence

| Image | Made from | sha256 |
| --- | --- | --- |
| `media/deck/assets/layers.png` | `media/deck/make_layers.py` (no data input) | image `3dc65003bac8f02da762fd85a42294aba73da531be7e8bcdf801d401712f99cb`, script `08d049b9ff8a03737cba0d33787c9c55b7556a547553770b430a44f98705a251` |

| Value | Source |
| --- | --- |
| Six layers L0 to L5 and their names | `README.md` lines 17-18 |
| Outcomes pass, warn, stop, skip | `README.md` lines 18-19 |

### 4. Models it runs and checks (new)

No image.

| Value | Source |
| --- | --- |
| Boltz-1, Boltz-2, Chai-1, Protenix, ColabFold (AlphaFold2), OpenFold3, DiffDock-L, Gnina on Modal A100 GPUs; AutoDock Vina on CPU | `README.md` lines 21-22 |
| AlphaFold3, HADDOCK3 and pyDock outputs supplied by the user | `README.md` lines 22-23; `configs/executors.yaml` lines 77, 196, 210 |
| OpenFold3 runtime | `configs/runtimes.yaml` lines 268-289 (openfold3 0.4.1) |

### 5. Check tools, sources and interfaces

No image.

| Value | Source |
| --- | --- |
| 34 sources | `configs/sources.yaml`: 34 entries under `sources:` (line 5), counted with a YAML parser |
| Check libraries | `README.md` lines 288-301 (Tools used table) |
| MCP server, HTTP API, web UI Agent view | `README.md` lines 23-24 |

### 6. 3PTB: Vina passes, Boltz-2 stops

| Image | Made from | sha256 |
| --- | --- | --- |
| `media/deck/assets/3ptb_pair.png` | `make_runfiles.py` with `TRIM=12` from `docs/images/render-3ptb-overview.png` and `docs/images/render-3ptb-vina-seed0.png` (PyMOL renders, `README.md` lines 210-213) | image `86b569a634c7b532833150b5c623d683adea9ba953ac4bddac7f4676f42b4545`; inputs `b40ff876163fa37656721765aa543cd332f743a858b9c082ae0d57080ce044e4`, `11d66821f236daae08006505daa408f897ff7ab66843efbede90b4035fd1e779` |

| Value | Source |
| --- | --- |
| Vina, 5 seeds, pass with warnings | `README.md` line 344 |
| PoseBusters 20/20 | `README.md` line 344 |
| Medoid 0.38 Å from crystal | `README.md` line 344 |
| Redocking 0.42 Å | `README.md` line 344 |
| Boltz-2 stop | `README.md` line 345 |
| ipTM 0.962; pocket pLDDT 98.6 | `README.md` line 345 |
| No redocking control | `README.md` line 345 |
| 314 pre-cutoff benzamidine entries | `README.md` line 345 |
| UniProt P00760, CCD BEN | `README.md` lines 80-81 |

### 7. Each run writes a report, graph and figures

| Image | Made from | sha256 |
| --- | --- | --- |
| `media/deck/assets/runfiles.png` | `make_runfiles.py` from `media/deck/assets/graph_crop2.png`, run 3 `harness/cdk2_pert_boltz2/run/figures/posebusters_grid.png` and `.../interactions.png` | image `9a133266ddb050dfe8cbf2745e9590fd6d5ce4bd271117d4fa7ecbee45292421` (rebuild matches the original byte for byte) |
| `media/deck/assets/graph_crop2.png` | cropped raster of run 3 `harness/cdk2_pert_boltz2/run/graph.svg`; the crop step is not scripted. Node labels checked against the SVG (`verdict: stop`, `l2.msa.depth [skip]`, `l5.controls.redocking [stop]`, `posebusters 0.6.5`, `propka 3.5.1`) | crop `89734ed419c84fb5b5745497e000dc4f61ab394cf4af8a2883e1b755913a6d97`; SVG `79d08b67858429ff833a1505da4db5035f1c65b4cfc9388a21e8db11f87022b2` |
| PoseBusters panel | `posebusters_grid.png` / `.csv` | `634ec01fece8de81bed4d762e659a909dc90a0571d39921af9c264157221247e` / `9582688514937ae89d423c6403b8e6b8614861c04f5d9e1e9df7206715c66e97` |
| Interactions panel | `interactions.png` / `.csv` | `34edcbac88b597ca3da6faa2ba65ebf1fdb534eb86376db011b0fa4f9bc9e5a3` / `19a877f008411878c8460f715e7fbb494633909c761ed96000b7ec7e54a26cfb` |

| Value | Source |
| --- | --- |
| 3 seeds (seed 7, 8, 9) | `posebusters_grid.csv` line 1 |
| One failed test, `minimum_distance_to_protein`, seed 7 | `posebusters_grid.csv` line 14 |
| Interaction counts (3/3, 2/3, 1/3) | `interactions.csv` lines 2-15 |
| Files listed (report.html, report.md, record.json, provenance.json) | directory listing of run 3 `harness/cdk2_pert_boltz2/run/` |

### 8. Benchmark: remove the pocket, ask an agent

No image.

| Value | Source |
| --- | --- |
| Pocket contacts to glycine, or glucose hydroxyls methylated | `bench/README.md` line 12 |
| Boltz-2, DiffDock-L; 3 seeds | `bench/README.md` line 13 |
| GLM-4.6 agent; score only or fact file | `bench/README.md` line 14 |
| FtsE 8X61, CDK2 1B38, MEK1 7XLP, glucose DH 2VWH | run 3 `report.md` lines 77-82 |
| 16 predictions per run | run 3 `report.md` line 3 |
| 3 runs | `README.md` lines 376-378 |
| Perturbed counts as invalid; wild type valid within 2.0 Å (notes) | run 3 `report.md` line 75 |

### 9. Run 3 balanced accuracy: 0.50 score only, 0.75 fact file

| Image | Made from | sha256 |
| --- | --- | --- |
| `media/deck/assets/results_pair.png` | `make_runfiles.py` from run 3 `results/figures/balanced_accuracy.png` and `results/figures/confusion.png` | image `2e66b8c7d7b57fed8546149a51cfc013211a6d7c012d49e7c4bb435679e08860`; inputs `1691a49842eee0a9279808c86360e1353d3ac8d8da178005470aa29dd2abf58d`, `82369c73ca4ac3d6b5996e8cb9d71a971ee00d6cf9062567712a02391e482e33` |

| Value | Source |
| --- | --- |
| 0.50 score only, 0.75 fact file (run 3, pooled) | run 3 `results/figures/balanced_accuracy.csv` lines 6-7; run 3 `report.md` line 67 |
| Bars 0.83 and 0.67 (Boltz-2, DiffDock-L fact file) | `balanced_accuracy.csv` lines 3, 5; run 3 `report.md` lines 68-69 |
| Fact file 95% CI 0.50 to 1.0 | `balanced_accuracy.csv` line 7 |
| p = 0.125 (McNemar exact, named in the notes) | run 3 `report.md` line 67 |
| Score only 95% CI 0.236 to 0.767 | `balanced_accuracy.csv` line 6 |
| Runs 1 and 2 fact file 0.53 and 0.58 | run 1 `report.md` line 67 (0.533); run 2 `report.md` line 67 (0.583); `README.md` lines 376-377 |
| Confusion counts 3, 3, 5, 5 and 3, 3, 0, 10 | run 3 `results/figures/confusion.csv` lines 2-3 (sha256 `3afab288a5627ce73f63fc3f6b843adbe45e29fad0e332994effbb51a00bd3c0`) |

### 10. CDK2: confidence holds without the pocket

| Image | Made from | sha256 |
| --- | --- | --- |
| `media/deck/assets/cdk2_pair.png` | `make_runfiles.py` from `bench/finding/panels/cdk2_wt.png` and `cdk2_pert.png` (PyMOL renders, `bench/finding/MATERIALS.md` lines 14 and 22-23) | image `5f0721545b280f3d4ab28beb5ed622f6c209e2d6a3c6f21eac0becc32f59cfc4`; inputs `a09378c1bce426458c6092f760a6b448013c1583fd309fefdd2d2f191730c0ff`, `d5fe9f15d4eab3326957f410facd79f5dbd9caf7fa10dbdfaa5bf65001033134` |

| Value | Source |
| --- | --- |
| Wild type ipTM 0.975, pocket pLDDT 94.9, 5 of 9 contacts | `bench/finding/values.csv` line 2 |
| Perturbed ipTM 0.947, pocket pLDDT 85.0, 1 of 9 contacts | `bench/finding/values.csv` line 3 |
| Perturbed PoseBusters 20/20 | `bench/finding/values.csv` line 3 |
| 13 pocket residues to glycine | run 1 `report.md` line 11 |
| RMSD 2.39 Å (perturbed medoid to deposited ATP) | run 1 `report.md` line 17 (2.392) |
| Fact file invalid (score only valid, in the title and notes) | run 1 `report.md` line 17 |

### 11. Tests and interfaces

No image.

| Value | Source |
| --- | --- |
| 394 Python test functions | `out/deck/evidence/python_test_functions.txt`, 394 lines |
| 225 web UI tests: 162 Vitest, 63 Playwright | `out/deck/evidence/web_vitest_list.txt` (162 lines); `web_playwright_list.txt` line 65 |
| 7 of 7 planted input faults stopped | `README.md` lines 83-86 |
| 70 registered checks, L0 to L5 | `out/deck/evidence/pah_checks.txt`, 70 lines (L0 3, L1 10, L2 13, L3 7, L4 13, L5 24) |
| Web UI URL | `README.md` line 3 |

### 12. Each number traces to a check and a source

| Image | Made from | sha256 |
| --- | --- | --- |
| run 3 `results/figures/decisions.png` (used directly) | run 3 `results/figures/decisions.csv` | `538fc8d1e628857255e13aca60b382edeb33fb03b96e573be37a6fb8e6ba49fc` / `f23b42acaafe699aba304534a276463079705d1fa3618f3bf5385d31b117f4a0` |

| Value | Source |
| --- | --- |
| 16 predictions per run | `decisions.csv` lines 2-17 |

### 13 to 15. References

No images. Slides 13 and 14 list R1 to R14, R17 and R18; slide 15 lists R15, R16, R19 to R26 as
cards (PDB entry primary citations in the table below). Each entry's verification is below.

## Changes made in this revision

| Slide | Before | After | Reason |
| --- | --- | --- | --- |
| Problem slide (`flip.png`) | Interpretation said 12 of 12 under a figure showing 9 of 9 | Removed once the twelve-prediction slide was added; its 12 of 12 statement and the published AUC moved to slide 2 | Figure and text disagreed; slide 2 shows all 12 |
| Problem slide | "about 75 ROC AUC for poses within 2 Å (489 complexes)", sourced to `docs/SPECIFICATION.md` | "ROC AUC 0.756 for poses within 2 Å", cited to Kim et al. 2026 [R2] | Primary source found: AlphaFold3 ligand pLDDT AUC 75.6 (percent), 489 of 551 Mac1 ligands evaluated |
| 3PTB | Right panel was a Mol* screenshot of the web UI with no file in the repository | Both panels are PyMOL renders from `docs/images/` | Screenshot could not be traced to a file |
| Run outputs | "Also written: ... PyMOL renders" | PyMOL renders removed from the list | The run directory has no renders (no `.pse` or render PNG) |
| Tools | Executors card duplicated the new models slide | Card replaced by Interfaces | Models now have their own slide |
| Results | Title gave run 3 values as if they were the result | Title names run 3; text adds runs 1 and 2 (0.53, 0.58) | Run 3 is the best of three runs |
| Results | "rejected 12 of 12 perturbed Boltz-2 poses and valid high-strain DiffDock-L poses" | Removed from this slide | The 12 of 12 rejection leads slide 2; text shortened to fit one line |
| Results | "no interval excludes 0.5" on the results slide | Kept on the closing slide only | Readout shortened to fit one line |
| CDK2 | "2.39 Å off" | "2.39 Å from deposited ATP" | States the reference |
| Tests | 221 web UI tests | 225 (162 Vitest, 63 Playwright) | Counted from the test runners' list output |
| Tests | 68 registered checks, layers 2 to 5 | 70 registered checks, L0 to L5 | `pah checks` lists 70 (57 in L2 to L5) |

## References and verification

Bibliographic records were checked on 2026-10-18 against Europe PMC (MED or PPR records, fetched
by DOI from `www.ebi.ac.uk/europepmc/webservices/rest/search`), against arXiv listings for the two
DiffDock papers (web search results for arXiv 2210.01776 and 2402.18396), against the RCSB PDB
data API for the PDB entries, and against rdkit.org for the RDKit citation guidance. Crossref,
doi.org and arXiv were not reachable from the sandbox.

| ID | Reference | Checked against |
| --- | --- | --- |
| R1 | Buttenschoen M, Morris GM, Deane CM. PoseBusters: AI-based docking methods fail to generate physically valid poses or generalise to novel sequences. Chem Sci. 2024;15(9):3130-3139. doi:10.1039/d3sc04185a | Europe PMC MED 38425520 |
| R2 | Kim J, Correy G, Hall B, Rachman M, Mailhot O, Togo T, et al., Shoichet B, Fraser J. Large-scale prospective evaluation of co-folding across hundreds of Mac1-ligand complexes and three virtual screens. eLife. 2026;15. doi:10.7554/eLife.110475. Preprint: bioRxiv 2025, doi:10.64898/2025.12.25.696505 | Europe PMC PMC13657626 (PMID 42862171) full text: 551 ligands, "489 of which are of sufficient quality for evaluation"; "best performance for AF3 L-pLDDT (AUC = 75.6)" for poses with L-RMSD under 2 Å |
| R3 | Wohlwend J, Corso G, Passaro S, Getz N, Reveiz M, Leidal K, et al. Boltz-1: Democratizing Biomolecular Interaction Modeling. bioRxiv. 2024. doi:10.1101/2024.11.19.624167 | Europe PMC PPR943186 |
| R4 | Passaro S, Corso G, Wohlwend J, Reveiz M, Thaler S, Somnath VR, et al. Boltz-2: Towards Accurate and Efficient Binding Affinity Prediction. bioRxiv. 2025. doi:10.1101/2025.06.14.659707 | Europe PMC PPR1039145 |
| R5 | Chai Discovery, Boitreaud J, Dent J, McPartlon M, Meier J, Reis V, Rogozhnikov A, Wu K. Chai-1: Decoding the molecular interactions of life. bioRxiv. 2024. doi:10.1101/2024.10.10.615955 | Europe PMC PPR922953 |
| R6 | ByteDance AML AI4Science Team, Chen X, Zhang Y, Lu C, Ma W, Guan J, et al. Protenix: Advancing Structure Prediction Through a Comprehensive AlphaFold3 Reproduction. bioRxiv. 2025. doi:10.1101/2025.01.08.631967 | Europe PMC PPR964843 |
| R7 | Mirdita M, Schütze K, Moriwaki Y, Heo L, Ovchinnikov S, Steinegger M. ColabFold: making protein folding accessible to all. Nat Methods. 2022;19(6):679-682. doi:10.1038/s41592-022-01488-1 | Europe PMC MED 35637307 |
| R8 | Abramson J, Adler J, Dunger J, Evans R, Green T, Pritzel A, et al. Accurate structure prediction of biomolecular interactions with AlphaFold 3. Nature. 2024;630(8016):493-500. doi:10.1038/s41586-024-07487-w | Europe PMC MED 38718835 |
| R9 | Corso G, Stärk H, Jing B, Barzilay R, Jaakkola T. DiffDock: Diffusion Steps, Twists, and Turns for Molecular Docking. arXiv:2210.01776. 2022 | arXiv listing (submitted 4 Oct 2022, revised 11 Feb 2023). The ICLR 2023 venue was not confirmed, so the arXiv record is cited |
| R10 | Corso G, Deng A, Fry B, Polizzi N, Barzilay R, Jaakkola T. Deep Confident Steps to New Pockets: Strategies for Docking Generalization. ICLR 2024. arXiv:2402.18396 | arXiv listing, journal reference ICLR 2024 |
| R11 | McNutt AT, Francoeur P, Aggarwal R, Masuda T, Meli R, Ragoza M, Sunseri J, Koes DR. GNINA 1.0: molecular docking with deep learning. J Cheminform. 2021;13(1):43. doi:10.1186/s13321-021-00522-2 | Europe PMC MED 34108002 |
| R12 | Trott O, Olson AJ. AutoDock Vina: improving the speed and accuracy of docking with a new scoring function, efficient optimization, and multithreading. J Comput Chem. 2010;31(2):455-461. doi:10.1002/jcc.21334 | Europe PMC MED 19499576 |
| R13 | Eberhardt J, Santos-Martins D, Tillack AF, Forli S. AutoDock Vina 1.2.0: New Docking Methods, Expanded Force Field, and Python Bindings. J Chem Inf Model. 2021;61(8):3891-3898. doi:10.1021/acs.jcim.1c00203 | Europe PMC MED 34278794 |
| R14 | Salentin S, Schreiber S, Haupt VJ, Adasme MF, Schroeder M. PLIP: fully automated protein-ligand interaction profiler. Nucleic Acids Res. 2015;43(W1):W443-W447. doi:10.1093/nar/gkv315. Adasme MF, Linnemann KL, Bolz SN, Kaiser F, Salentin S, Haupt VJ, Schroeder M. PLIP 2021: expanding the scope of the protein-ligand interaction profiler to DNA and RNA. Nucleic Acids Res. 2021;49(W1):W530-W534. doi:10.1093/nar/gkab294 | Europe PMC MED 25873628, 33950214 |
| R15 | RDKit: Open-source cheminformatics, version 2026.9.1 (version from `README.md` line 291). https://www.rdkit.org. Concept DOI 10.5281/zenodo.591637 | rdkit.org Overview page: no formal paper; cite the software and the Zenodo DOI |
| R16 | The PyMOL Molecular Graphics System, open-source version 3.2.0 (version from `README.md` line 294). Schrödinger, LLC | No paper or DOI exists; software credit |
| R17 | Eastman P, Galvelis R, Peláez RP, Abreu CRA, Farr SE, Gallicchio E, et al. OpenMM 8: Molecular Dynamics Simulation with Machine Learning Potentials. J Phys Chem B. 2024;128(1):109-116. doi:10.1021/acs.jpcb.3c06662 | Europe PMC MED 38154096 |
| R18 | Giulini M, Reys V, Teixeira JMC, Jiménez-García B, Honorato RV, Kravchenko A, et al. HADDOCK3: A Modular and Versatile Platform for Integrative Modeling of Biomolecular Complexes. J Chem Inf Model. 2025;65(13):7315-7324. doi:10.1021/acs.jcim.5c00969 | Europe PMC MED 40526044 |
| R19 | Cheng TM, Blundell TL, Fernandez-Recio J. pyDock: electrostatics and desolvation for effective scoring of rigid-body protein-protein docking. Proteins. 2007;68(2):503-515. doi:10.1002/prot.21419 | Europe PMC MED 17444519 |
| R20 | OpenFold3 preview, OpenFold Consortium and AlQuraishi Lab. Software, openfold3 0.4.1 (`configs/runtimes.yaml` lines 268-285). https://github.com/aqlaboratory/openfold-3 | No peer-reviewed paper or preprint DOI was found; the technical report on the OpenFold portal was not opened, so only the software is credited |
| R21 | Berman HM, Westbrook J, Feng Z, Gilliland G, Bhat TN, Weissig H, Shindyalov IN, Bourne PE. The Protein Data Bank. Nucleic Acids Res. 2000;28(1):235-242. doi:10.1093/nar/28.1.235 | Europe PMC MED 10592235 |
| R22 | PDB 3PTB. Marquart M, Walter J, Deisenhofer J, et al. The Geometry of the Reactive Site and of the Peptide Groups in Trypsin, Trypsinogen and its Complexes with Inhibitors. Acta Crystallogr B. 1983 | RCSB data API, entry 3PTB primary citation |
| R23 | PDB 1B38. Brown NR, Noble ME, Lawrie AM, et al. Effects of phosphorylation of threonine 160 on cyclin-dependent kinase 2 structure and activity. J Biol Chem. 1999 | RCSB data API, entry 1B38 |
| R24 | PDB 8X61. Chen Y, Gu J, Yang B, et al. Structure and activity of the septal peptidoglycan hydrolysis machinery crucial for bacterial cell division. PLoS Biol. 2024 | RCSB data API, entry 8X61 |
| R25 | PDB 7XLP. Takano K, Munehira Y, Hatanaka M, et al. Discovery of a Novel ATP-Competitive MEK Inhibitor DS03090629 that Overcomes Resistance Conferred by BRAF Overexpression in BRAF-Mutated Melanoma. Mol Cancer Ther. 2023 | RCSB data API, entry 7XLP |
| R26 | PDB 2VWH. Baker PJ, Britton KL, Fisher M, et al. Active site dynamics in the zinc-dependent medium chain alcohol dehydrogenase superfamily. Proc Natl Acad Sci U S A. 2009 | RCSB data API, entry 2VWH |

Methods named in the deck without a separate reference: gemmi and FreeSASA (check libraries; their
citations are in `README.md` Attributions and Tools used, not re-verified here), GLM-4.6 (the
benchmark agent, a hosted model with no paper cited).

## Assets not used by the deck

`media/deck/assets/3ptb-overview.png`, `graph.png` and `graph_crop.png` are left over from the first
build and appear on no slide.
