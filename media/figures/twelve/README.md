# Twelve perturbed Boltz-2 predictions

PyMOL renders of the 12 perturbed Boltz-2 predictions of the perturbation benchmark: 4 systems in 3 bench runs. Each image shows the medoid pose named by `l5.sampling.clusters` in that run's harness record (`bench/runs/<run>/harness/<sys>_pert_boltz2/run/record.json`).

Rendering: `media/videos/video-c/render_twelve.py` (PyMOL open source 3.2, 960x720, ray traced). Each prediction is superposed by protein CA onto the run-3 prediction of the same system, and one camera per system is framed on the ligands of all three runs. Protein as cartoon (#C7D8CC, 0.55 transparency), ligand (chain L) as sticks with carbon #B07E2C, side chains within 4.5 Å of the ligand as thin grey sticks, cofactors in blue-grey, the CA atoms of residues cut to glycine as red spheres (#C4513B). Glucose dehydrogenase has no cut residues; its perturbation methylates 3 ring hydroxyls of the ligand.

`grid.png` is the 4x3 grid (columns CDK2, FtsE, MEK1, glucose dehydrogenase; rows runs 1 to 3). `twelve.json` holds every value below plus the agent votes and an example agent reason.

Values: ipTM is `ligand_iptm` and pocket pLDDT is `pocket_plddt` from `bench/runs/<run>/facts/<sys>_pert_boltz2.json`; contacts, buried unsatisfied polar atoms, PoseBusters and torsion strain come from the same fact file. Arm A is the agent (GLM-4.6, temperature 0) given only the confidence values; arm B is the agent given the fact file; each is the majority of 3 repeats from `results/decisions.csv`. Ground truth for all 12 is invalid (perturbed by construction, `results/truth.csv`).

Runs: run 1 `2026-10-17T1611Z-426bfe9`, run 2 `2026-10-17T1752Z-2f5a1c7`, run 3 `2026-10-17T1859Z-849c856`.

| Image | System | Run | Seed | Source structure | sha256 | ipTM | pocket pLDDT | Contacts recovered | Buried unsat. polars | PoseBusters | Torsion strain (kcal/mol) | Arm A | Arm B |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `cdk2_run1.png` | CDK2 1B38 | 1 | 3 | `bench/runs/2026-10-17T1611Z-426bfe9/predictions/cdk2_pert/boltz2/seed_3/boltz_results_cdk2_pert/predictions/cdk2_pert/cdk2_pert_model_0.cif` | `c7f58a2c281a45efc32b84480f923cdf41cd8c2637ca76d620f287c5b03657df` | 0.947 | 85.0 | 1 of 9 | 5 | 20/20 | 13.6 | valid | invalid |
| `ftse_run1.png` | FtsE 8X61 | 1 | 3 | `bench/runs/2026-10-17T1611Z-426bfe9/predictions/ftse_pert/boltz2/seed_3/boltz_results_ftse_pert/predictions/ftse_pert/ftse_pert_model_0.cif` | `b4d2962001814b2abc75cd90540ffc7d1d3b9a2796aebb787faae69c983fe8c6` | 0.898 | 85.5 | 0 of 16 | 3 | 20/20 | 20.38 | valid | invalid |
| `mek1_run1.png` | MEK1 7XLP | 1 | 2 | `bench/runs/2026-10-17T1611Z-426bfe9/predictions/mek1_pert/boltz2/seed_2/boltz_results_mek1_pert/predictions/mek1_pert/mek1_pert_model_0.cif` | `320651246ca63deb4c0bb75d549e3cd22246d96116ff8cd56f7e9caf1c60f6de` | 0.970 | 90.5 | 0 of 3 | 1 | 20/20 | 2.15 | valid | invalid |
| `glc_run1.png` | glucose dehydrogenase 2VWH | 1 | 2 | `bench/runs/2026-10-17T1611Z-426bfe9/predictions/glc_pert/boltz2/seed_2/boltz_results_glc_pert/predictions/glc_pert/glc_pert_model_0.cif` | `edaae86480a3f570b53ce2c85805afbf9ff82fa09f303dffc8a8f9c895664fb5` | 0.983 | 97.7 | 3 of 6 | 0 | 19/20 (minimum_distance_to_protein) | 9.58 | valid | invalid |
| `cdk2_run2.png` | CDK2 1B38 | 2 | 4 | `bench/runs/2026-10-17T1752Z-2f5a1c7/predictions/cdk2_pert/boltz2/seed_4/boltz_results_cdk2_pert/predictions/cdk2_pert/cdk2_pert_model_0.cif` | `9574f98d2e42accc44d0688b944db8357c6fe744f234924936785907dbefaa00` | 0.951 | 83.8 | 1 of 9 | 6 | 20/20 | 15.84 | valid | invalid |
| `ftse_run2.png` | FtsE 8X61 | 2 | 4 | `bench/runs/2026-10-17T1752Z-2f5a1c7/predictions/ftse_pert/boltz2/seed_4/boltz_results_ftse_pert/predictions/ftse_pert/ftse_pert_model_0.cif` | `eee2623ca6bde3050f873cf47729678968000886a9a6434883f4e38a703f6430` | 0.882 | 85.7 | 1 of 16 | 5 | 20/20 | 16.5 | valid | invalid |
| `mek1_run2.png` | MEK1 7XLP | 2 | 6 | `bench/runs/2026-10-17T1752Z-2f5a1c7/predictions/mek1_pert/boltz2/seed_6/boltz_results_mek1_pert/predictions/mek1_pert/mek1_pert_model_0.cif` | `e26539e3369081412a150dd7a223a437f9c6e7868abc54ab558ab4087bb65bbd` | 0.971 | 90.0 | 0 of 3 | 1 | 20/20 | 1.11 | valid | invalid |
| `glc_run2.png` | glucose dehydrogenase 2VWH | 2 | 4 | `bench/runs/2026-10-17T1752Z-2f5a1c7/predictions/glc_pert/boltz2/seed_4/boltz_results_glc_pert/predictions/glc_pert/glc_pert_model_0.cif` | `950a787e78b17c03552b6168f0027ad17ce4a8e5daca5cd6cbfa5a8913e9435c` | 0.980 | 97.7 | 3 of 6 | 0 | 20/20 | 13.44 | valid | invalid |
| `cdk2_run3.png` | CDK2 1B38 | 3 | 8 | `bench/runs/2026-10-17T1859Z-849c856/predictions/cdk2_pert/boltz2/seed_8/boltz_results_cdk2_pert/predictions/cdk2_pert/cdk2_pert_model_0.cif` | `c917bf5e0ff545e2c7e9665aa169329bd1333a1c9d36e7bcf8efcb17760b55aa` | 0.925 | 82.3 | 1 of 9 | 4 | 20/20 | 7.55 | valid | invalid |
| `ftse_run3.png` | FtsE 8X61 | 3 | 7 | `bench/runs/2026-10-17T1859Z-849c856/predictions/ftse_pert/boltz2/seed_7/boltz_results_ftse_pert/predictions/ftse_pert/ftse_pert_model_0.cif` | `679ca1d6f7ea4247ffce57fe9e744ad1c50ac951dd9a646ea444fd5fac835beb` | 0.893 | 84.2 | 1 of 16 | 4 | 20/20 | 20.22 | valid | invalid |
| `mek1_run3.png` | MEK1 7XLP | 3 | 8 | `bench/runs/2026-10-17T1859Z-849c856/predictions/mek1_pert/boltz2/seed_8/boltz_results_mek1_pert/predictions/mek1_pert/mek1_pert_model_0.cif` | `8b1f1ff5cc426848bfee02e7e8f4a5d129a73a47a437f4ed6797f0dc4e9ec43b` | 0.968 | 91.2 | 0 of 3 | 2 | 20/20 | 1.13 | valid | invalid |
| `glc_run3.png` | glucose dehydrogenase 2VWH | 3 | 7 | `bench/runs/2026-10-17T1859Z-849c856/predictions/glc_pert/boltz2/seed_7/boltz_results_glc_pert/predictions/glc_pert/glc_pert_model_0.cif` | `1c72788de7715609dcecb6b33a3858cc6e6b0070346701870d909b090dcd47de` | 0.984 | 97.8 | 3 of 6 | 0 | 19/20 (minimum_distance_to_protein) | 17.99 | valid | invalid |

PNG checksums (sha256):

- `cdk2_run1.png`: `1de51b4c1f8aaa1b37e1d00152b2062afb4bb257c09080035f829fa6c9deb650`
- `ftse_run1.png`: `402171f57ee25e3a726e4cb6c82a0bf551ea98a5361d1da94550189b82fa97bb`
- `mek1_run1.png`: `e6bf501e849c28de313c47e521ebe54e3968472051db65b1e08d3a317996ac3c`
- `glc_run1.png`: `86b47984f63f61e58c83c82c092da8675f8fd046de4985b1a748c386487f7601`
- `cdk2_run2.png`: `cfe22f35859ed211131034099fd299dc40fdb9e3a34b2658e97206498a497bce`
- `ftse_run2.png`: `30ec76fa4e6c3f39005dd08e0194c7b3e4d2af8cb10a739531042938d6c98c80`
- `mek1_run2.png`: `29c1ab51f41d8a59fddaaed517b15d8aca28181d49ef85be7cf743819c0323de`
- `glc_run2.png`: `765132ee5d1b1a5d47f7744913c7b0b139273f476191778b6ef08c58119f17d1`
- `cdk2_run3.png`: `6cd01b6d08096b2cce12c72af2ee97a7fe82ed7716280e7b5d9af5bd19c082ba`
- `ftse_run3.png`: `71b467d9897fb3d0d4f7be2c782955cfa06e6777e3329d3a17ea0d2e4e296be3`
- `mek1_run3.png`: `c7abb5dccd11e7330550258988ff4072f7e4d49e63530b1ee1ffa6a1bac62357`
- `glc_run3.png`: `9fa3dc11fddb9f1620b1e52bc19a8e2d1bd5d17c86a50d252fec1be1486d8678`
