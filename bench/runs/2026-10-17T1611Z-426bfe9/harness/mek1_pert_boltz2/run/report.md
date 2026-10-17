# Run report · Ligand pose in a known pocket

Prediction assurance · run `ligand_pose-97e42e68b4f9` · 2026-10-17 17:04:20 UTC

**Refused** for the claim "Predicted pose of FZC in MEK1 is valid".

Refused over layers 2,3,4,5: 9 pass, 5 warn, 3 stop, 9 skip. Stopped by l2.context.cofactors, l4.posebusters, l5.controls.redocking. Warnings from l2.receptor.protonation, l2.ligand.protonation, l2.docking.box, l4.interactions.known_binders, l5.sampling.seeds. 8 checks not verified.

Stops: `l2.context.cofactors`, `l4.posebusters`, `l5.controls.redocking`.

Warnings: `l2.receptor.protonation`, `l2.ligand.protonation`, `l2.docking.box`, `l4.interactions.known_binders`, `l5.sampling.seeds`.

Not verified: 8 checks.

| Field | Value |
| --- | --- |
| Task | Ligand pose in a known pocket (`ligand_pose`) |
| Tools | Boltz-2 2.2.1 (co-folding), DiffDock-L (docking) |
| Target | `protein` |
| Ligand | `Cc1ccnc(n1)Oc2ccc(c(c2)Cl)c3cc4c(c(n[nH]4)C)c(c3)O[C@H]5CCC[C@H](C5)N` |
| Reference | `7XLP` |
| pH | 7.4 |
| Seeds | 3 |
| Layers run | 2, 3, 4, 5 |
| Run | `ligand_pose-97e42e68b4f9` |
| Created | 2026-10-17 17:04:20 UTC |
| Finished | 2026-10-17 17:04:53 UTC |
| pah version | 0.1.0 |
| Report schema | 1 |

## Layers

| Layer | Status | Result | pass | warn | stop | skip | Time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L0 Provenance | not run | n/a | n/a | n/a | n/a | n/a | n/a |
| L1 Input integrity | not run | n/a | n/a | n/a | n/a | n/a | n/a |
| L2 Input adequacy | done | stop | 3 | 3 | 1 | 1 | 3.6 s |
| L3 Applicability | done | pass | 5 | 0 | 0 | 1 | 3.2 s |
| L4 Output validity | done | stop | 1 | 1 | 1 | 4 | 26.5 s |
| L5 Output support | done | stop | 0 | 1 | 1 | 3 | 15 ms |

## Figures

![Horizontal stacked bars per layer, split into pass, warn, stop and skip counts.](figures/gates_by_layer.svg)

Fig. 1 · Check outcomes per layer for run ligand_pose-97e42e68b4f9. Totals: pass 9, warn 5, stop 3, skip 9.
Files: data [figures/gates_by_layer.csv](figures/gates_by_layer.csv).

## Structures

68 PyMOL renders.

![PyMOL cartoon of 7XLP mmCIF coloured by chain, ligands as sticks.](renders/7XLP_overview.png)

7XLP mmCIF (source_structure), whole structure. Chains A; organic components DMS, FZC. sha256 48ffbc34e5fd126d. PyMOL session: [renders/7XLP.pse](renders/7XLP.pse).

![PyMOL cartoon of 7XLP mmCIF coloured by chain, ligands as sticks.](renders/7XLP_pocket.png)

7XLP mmCIF (source_structure), ligand environment within 5 Å. Chains A; organic components DMS, FZC. sha256 48ffbc34e5fd126d. PyMOL session: [renders/7XLP.pse](renders/7XLP.pse).

![PyMOL cartoon of boltz2/seed1/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed1_sample0_overview.png)

boltz2/seed1/sample0 (prediction_structure), whole structure. Chains A, L; organic components LIG1. sha256 d3109735f7473f24. PyMOL session: [renders/boltz2_seed1_sample0.pse](renders/boltz2_seed1_sample0.pse).

![PyMOL cartoon of boltz2/seed1/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed1_sample0_pocket.png)

boltz2/seed1/sample0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG1. sha256 d3109735f7473f24. PyMOL session: [renders/boltz2_seed1_sample0.pse](renders/boltz2_seed1_sample0.pse).

![PyMOL cartoon of boltz2/seed2/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed2_sample0_overview.png)

boltz2/seed2/sample0 (prediction_structure), whole structure. Chains A, L; organic components LIG1. sha256 320651246ca63deb. PyMOL session: [renders/boltz2_seed2_sample0.pse](renders/boltz2_seed2_sample0.pse).

![PyMOL cartoon of boltz2/seed2/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed2_sample0_pocket.png)

boltz2/seed2/sample0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG1. sha256 320651246ca63deb. PyMOL session: [renders/boltz2_seed2_sample0.pse](renders/boltz2_seed2_sample0.pse).

![PyMOL cartoon of boltz2/seed3/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed3_sample0_overview.png)

boltz2/seed3/sample0 (prediction_structure), whole structure. Chains A, L; organic components LIG1. sha256 3dd5cb3f0f1e650b. PyMOL session: [renders/boltz2_seed3_sample0.pse](renders/boltz2_seed3_sample0.pse).

![PyMOL cartoon of boltz2/seed3/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed3_sample0_pocket.png)

boltz2/seed3/sample0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG1. sha256 3dd5cb3f0f1e650b. PyMOL session: [renders/boltz2_seed3_sample0.pse](renders/boltz2_seed3_sample0.pse).

![PyMOL cartoon of diffdock/seed1/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode0_overview.png)

diffdock/seed1/mode0 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 78ae8b3ed08f64a2. PyMOL session: [renders/diffdock_seed1_mode0.pse](renders/diffdock_seed1_mode0.pse).

![PyMOL cartoon of diffdock/seed1/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode0_pocket.png)

diffdock/seed1/mode0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 78ae8b3ed08f64a2. PyMOL session: [renders/diffdock_seed1_mode0.pse](renders/diffdock_seed1_mode0.pse).

![PyMOL cartoon of diffdock/seed1/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode1_overview.png)

diffdock/seed1/mode1 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 3121e202f5ca9c7d. PyMOL session: [renders/diffdock_seed1_mode1.pse](renders/diffdock_seed1_mode1.pse).

![PyMOL cartoon of diffdock/seed1/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode1_pocket.png)

diffdock/seed1/mode1 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 3121e202f5ca9c7d. PyMOL session: [renders/diffdock_seed1_mode1.pse](renders/diffdock_seed1_mode1.pse).

![PyMOL cartoon of diffdock/seed1/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode2_overview.png)

diffdock/seed1/mode2 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 25b62ddb535f11d6. PyMOL session: [renders/diffdock_seed1_mode2.pse](renders/diffdock_seed1_mode2.pse).

![PyMOL cartoon of diffdock/seed1/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode2_pocket.png)

diffdock/seed1/mode2 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 25b62ddb535f11d6. PyMOL session: [renders/diffdock_seed1_mode2.pse](renders/diffdock_seed1_mode2.pse).

![PyMOL cartoon of diffdock/seed1/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode3_overview.png)

diffdock/seed1/mode3 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 fefcbc8cf1869cf2. PyMOL session: [renders/diffdock_seed1_mode3.pse](renders/diffdock_seed1_mode3.pse).

![PyMOL cartoon of diffdock/seed1/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode3_pocket.png)

diffdock/seed1/mode3 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 fefcbc8cf1869cf2. PyMOL session: [renders/diffdock_seed1_mode3.pse](renders/diffdock_seed1_mode3.pse).

![PyMOL cartoon of diffdock/seed1/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode4_overview.png)

diffdock/seed1/mode4 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 1e70558760f7cb82. PyMOL session: [renders/diffdock_seed1_mode4.pse](renders/diffdock_seed1_mode4.pse).

![PyMOL cartoon of diffdock/seed1/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode4_pocket.png)

diffdock/seed1/mode4 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 1e70558760f7cb82. PyMOL session: [renders/diffdock_seed1_mode4.pse](renders/diffdock_seed1_mode4.pse).

![PyMOL cartoon of diffdock/seed1/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode5_overview.png)

diffdock/seed1/mode5 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 8985a0a202b66ebe. PyMOL session: [renders/diffdock_seed1_mode5.pse](renders/diffdock_seed1_mode5.pse).

![PyMOL cartoon of diffdock/seed1/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode5_pocket.png)

diffdock/seed1/mode5 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 8985a0a202b66ebe. PyMOL session: [renders/diffdock_seed1_mode5.pse](renders/diffdock_seed1_mode5.pse).

![PyMOL cartoon of diffdock/seed1/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode6_overview.png)

diffdock/seed1/mode6 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 b312102dca3a2477. PyMOL session: [renders/diffdock_seed1_mode6.pse](renders/diffdock_seed1_mode6.pse).

![PyMOL cartoon of diffdock/seed1/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode6_pocket.png)

diffdock/seed1/mode6 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 b312102dca3a2477. PyMOL session: [renders/diffdock_seed1_mode6.pse](renders/diffdock_seed1_mode6.pse).

![PyMOL cartoon of diffdock/seed1/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode7_overview.png)

diffdock/seed1/mode7 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 6b7c31295f21af8f. PyMOL session: [renders/diffdock_seed1_mode7.pse](renders/diffdock_seed1_mode7.pse).

![PyMOL cartoon of diffdock/seed1/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode7_pocket.png)

diffdock/seed1/mode7 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 6b7c31295f21af8f. PyMOL session: [renders/diffdock_seed1_mode7.pse](renders/diffdock_seed1_mode7.pse).

![PyMOL cartoon of diffdock/seed1/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode8_overview.png)

diffdock/seed1/mode8 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 d7b509f2520e2937. PyMOL session: [renders/diffdock_seed1_mode8.pse](renders/diffdock_seed1_mode8.pse).

![PyMOL cartoon of diffdock/seed1/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode8_pocket.png)

diffdock/seed1/mode8 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 d7b509f2520e2937. PyMOL session: [renders/diffdock_seed1_mode8.pse](renders/diffdock_seed1_mode8.pse).

![PyMOL cartoon of diffdock/seed1/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode9_overview.png)

diffdock/seed1/mode9 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 fa249fa473e5bcf5. PyMOL session: [renders/diffdock_seed1_mode9.pse](renders/diffdock_seed1_mode9.pse).

![PyMOL cartoon of diffdock/seed1/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode9_pocket.png)

diffdock/seed1/mode9 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 fa249fa473e5bcf5. PyMOL session: [renders/diffdock_seed1_mode9.pse](renders/diffdock_seed1_mode9.pse).

![PyMOL cartoon of diffdock/seed2/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode0_overview.png)

diffdock/seed2/mode0 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 e930537ad18a4d3a. PyMOL session: [renders/diffdock_seed2_mode0.pse](renders/diffdock_seed2_mode0.pse).

![PyMOL cartoon of diffdock/seed2/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode0_pocket.png)

diffdock/seed2/mode0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 e930537ad18a4d3a. PyMOL session: [renders/diffdock_seed2_mode0.pse](renders/diffdock_seed2_mode0.pse).

![PyMOL cartoon of diffdock/seed2/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode1_overview.png)

diffdock/seed2/mode1 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 ae5414248a0a237c. PyMOL session: [renders/diffdock_seed2_mode1.pse](renders/diffdock_seed2_mode1.pse).

![PyMOL cartoon of diffdock/seed2/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode1_pocket.png)

diffdock/seed2/mode1 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 ae5414248a0a237c. PyMOL session: [renders/diffdock_seed2_mode1.pse](renders/diffdock_seed2_mode1.pse).

![PyMOL cartoon of diffdock/seed2/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode2_overview.png)

diffdock/seed2/mode2 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 e98c6d24cc762313. PyMOL session: [renders/diffdock_seed2_mode2.pse](renders/diffdock_seed2_mode2.pse).

![PyMOL cartoon of diffdock/seed2/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode2_pocket.png)

diffdock/seed2/mode2 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 e98c6d24cc762313. PyMOL session: [renders/diffdock_seed2_mode2.pse](renders/diffdock_seed2_mode2.pse).

![PyMOL cartoon of diffdock/seed2/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode3_overview.png)

diffdock/seed2/mode3 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 7bf30c130e331c7d. PyMOL session: [renders/diffdock_seed2_mode3.pse](renders/diffdock_seed2_mode3.pse).

![PyMOL cartoon of diffdock/seed2/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode3_pocket.png)

diffdock/seed2/mode3 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 7bf30c130e331c7d. PyMOL session: [renders/diffdock_seed2_mode3.pse](renders/diffdock_seed2_mode3.pse).

![PyMOL cartoon of diffdock/seed2/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode4_overview.png)

diffdock/seed2/mode4 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 f7476a62c200ed09. PyMOL session: [renders/diffdock_seed2_mode4.pse](renders/diffdock_seed2_mode4.pse).

![PyMOL cartoon of diffdock/seed2/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode4_pocket.png)

diffdock/seed2/mode4 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 f7476a62c200ed09. PyMOL session: [renders/diffdock_seed2_mode4.pse](renders/diffdock_seed2_mode4.pse).

![PyMOL cartoon of diffdock/seed2/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode5_overview.png)

diffdock/seed2/mode5 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 0d395223e8eb6623. PyMOL session: [renders/diffdock_seed2_mode5.pse](renders/diffdock_seed2_mode5.pse).

![PyMOL cartoon of diffdock/seed2/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode5_pocket.png)

diffdock/seed2/mode5 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 0d395223e8eb6623. PyMOL session: [renders/diffdock_seed2_mode5.pse](renders/diffdock_seed2_mode5.pse).

![PyMOL cartoon of diffdock/seed2/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode6_overview.png)

diffdock/seed2/mode6 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 dc57ae3b328617d6. PyMOL session: [renders/diffdock_seed2_mode6.pse](renders/diffdock_seed2_mode6.pse).

![PyMOL cartoon of diffdock/seed2/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode6_pocket.png)

diffdock/seed2/mode6 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 dc57ae3b328617d6. PyMOL session: [renders/diffdock_seed2_mode6.pse](renders/diffdock_seed2_mode6.pse).

![PyMOL cartoon of diffdock/seed2/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode7_overview.png)

diffdock/seed2/mode7 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 826be0ee388f20bf. PyMOL session: [renders/diffdock_seed2_mode7.pse](renders/diffdock_seed2_mode7.pse).

![PyMOL cartoon of diffdock/seed2/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode7_pocket.png)

diffdock/seed2/mode7 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 826be0ee388f20bf. PyMOL session: [renders/diffdock_seed2_mode7.pse](renders/diffdock_seed2_mode7.pse).

![PyMOL cartoon of diffdock/seed2/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode8_overview.png)

diffdock/seed2/mode8 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 165c50d55a4c7361. PyMOL session: [renders/diffdock_seed2_mode8.pse](renders/diffdock_seed2_mode8.pse).

![PyMOL cartoon of diffdock/seed2/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode8_pocket.png)

diffdock/seed2/mode8 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 165c50d55a4c7361. PyMOL session: [renders/diffdock_seed2_mode8.pse](renders/diffdock_seed2_mode8.pse).

![PyMOL cartoon of diffdock/seed2/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode9_overview.png)

diffdock/seed2/mode9 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 85e4925ecf5057a1. PyMOL session: [renders/diffdock_seed2_mode9.pse](renders/diffdock_seed2_mode9.pse).

![PyMOL cartoon of diffdock/seed2/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode9_pocket.png)

diffdock/seed2/mode9 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 85e4925ecf5057a1. PyMOL session: [renders/diffdock_seed2_mode9.pse](renders/diffdock_seed2_mode9.pse).

![PyMOL cartoon of diffdock/seed3/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode0_overview.png)

diffdock/seed3/mode0 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 da7bdcff1411ce51. PyMOL session: [renders/diffdock_seed3_mode0.pse](renders/diffdock_seed3_mode0.pse).

![PyMOL cartoon of diffdock/seed3/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode0_pocket.png)

diffdock/seed3/mode0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 da7bdcff1411ce51. PyMOL session: [renders/diffdock_seed3_mode0.pse](renders/diffdock_seed3_mode0.pse).

![PyMOL cartoon of diffdock/seed3/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode1_overview.png)

diffdock/seed3/mode1 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 6ccc9520567b38be. PyMOL session: [renders/diffdock_seed3_mode1.pse](renders/diffdock_seed3_mode1.pse).

![PyMOL cartoon of diffdock/seed3/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode1_pocket.png)

diffdock/seed3/mode1 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 6ccc9520567b38be. PyMOL session: [renders/diffdock_seed3_mode1.pse](renders/diffdock_seed3_mode1.pse).

![PyMOL cartoon of diffdock/seed3/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode2_overview.png)

diffdock/seed3/mode2 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 f1058ec975a0bd56. PyMOL session: [renders/diffdock_seed3_mode2.pse](renders/diffdock_seed3_mode2.pse).

![PyMOL cartoon of diffdock/seed3/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode2_pocket.png)

diffdock/seed3/mode2 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 f1058ec975a0bd56. PyMOL session: [renders/diffdock_seed3_mode2.pse](renders/diffdock_seed3_mode2.pse).

![PyMOL cartoon of diffdock/seed3/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode3_overview.png)

diffdock/seed3/mode3 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 6962856f161a8c07. PyMOL session: [renders/diffdock_seed3_mode3.pse](renders/diffdock_seed3_mode3.pse).

![PyMOL cartoon of diffdock/seed3/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode3_pocket.png)

diffdock/seed3/mode3 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 6962856f161a8c07. PyMOL session: [renders/diffdock_seed3_mode3.pse](renders/diffdock_seed3_mode3.pse).

![PyMOL cartoon of diffdock/seed3/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode4_overview.png)

diffdock/seed3/mode4 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 b39010b569d06e69. PyMOL session: [renders/diffdock_seed3_mode4.pse](renders/diffdock_seed3_mode4.pse).

![PyMOL cartoon of diffdock/seed3/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode4_pocket.png)

diffdock/seed3/mode4 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 b39010b569d06e69. PyMOL session: [renders/diffdock_seed3_mode4.pse](renders/diffdock_seed3_mode4.pse).

![PyMOL cartoon of diffdock/seed3/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode5_overview.png)

diffdock/seed3/mode5 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 c85f07d6aebe8c9d. PyMOL session: [renders/diffdock_seed3_mode5.pse](renders/diffdock_seed3_mode5.pse).

![PyMOL cartoon of diffdock/seed3/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode5_pocket.png)

diffdock/seed3/mode5 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 c85f07d6aebe8c9d. PyMOL session: [renders/diffdock_seed3_mode5.pse](renders/diffdock_seed3_mode5.pse).

![PyMOL cartoon of diffdock/seed3/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode6_overview.png)

diffdock/seed3/mode6 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 104722a469939ca8. PyMOL session: [renders/diffdock_seed3_mode6.pse](renders/diffdock_seed3_mode6.pse).

![PyMOL cartoon of diffdock/seed3/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode6_pocket.png)

diffdock/seed3/mode6 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 104722a469939ca8. PyMOL session: [renders/diffdock_seed3_mode6.pse](renders/diffdock_seed3_mode6.pse).

![PyMOL cartoon of diffdock/seed3/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode7_overview.png)

diffdock/seed3/mode7 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 8e33fd3f017cdc52. PyMOL session: [renders/diffdock_seed3_mode7.pse](renders/diffdock_seed3_mode7.pse).

![PyMOL cartoon of diffdock/seed3/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode7_pocket.png)

diffdock/seed3/mode7 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 8e33fd3f017cdc52. PyMOL session: [renders/diffdock_seed3_mode7.pse](renders/diffdock_seed3_mode7.pse).

![PyMOL cartoon of diffdock/seed3/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode8_overview.png)

diffdock/seed3/mode8 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 a59e361b1df755e8. PyMOL session: [renders/diffdock_seed3_mode8.pse](renders/diffdock_seed3_mode8.pse).

![PyMOL cartoon of diffdock/seed3/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode8_pocket.png)

diffdock/seed3/mode8 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 a59e361b1df755e8. PyMOL session: [renders/diffdock_seed3_mode8.pse](renders/diffdock_seed3_mode8.pse).

![PyMOL cartoon of diffdock/seed3/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode9_overview.png)

diffdock/seed3/mode9 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 14259246a04c1064. PyMOL session: [renders/diffdock_seed3_mode9.pse](renders/diffdock_seed3_mode9.pse).

![PyMOL cartoon of diffdock/seed3/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode9_pocket.png)

diffdock/seed3/mode9 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 14259246a04c1064. PyMOL session: [renders/diffdock_seed3_mode9.pse](renders/diffdock_seed3_mode9.pse).

## L0 Provenance

Where did every input come from?

Status: not run.

## L1 Input integrity

Did the run receive exactly what was declared?

Status: not run.

## L2 Input adequacy

Does the input carry enough information?

Status: done. Checks: pass 3 · warn 3 · stop 1 · skip 1. Time: 3.6 s.

#### Key figures

| Figure | Value |
| --- | --- |
| near site | 1 |
| missing | 1 |
| uniprot cofactors | 0 |
| pocket residues | 37 |
| incomplete | 0 |
| sequence gaps | 0 |
| state | holo |
| site ligands | 1 |

#### Docking

| Field | Value |
| --- | --- |
| center | -3.608, 64.879, 34.516 Å |
| size | 19.183 × 21.381 × 13.89 Å |
| origin | derived from FZC (+4 Å) |

#### Checks

| Check | Result | Measured cmp threshold | Evidence | Id · time |
| --- | --- | --- | --- | --- |
| Alignment depth, distinct sequences, Neff and gap fraction | skip | n/a | no MSA declared for a co-folding model · not applicable | `l2.msa.depth` |
| Required cofactors, ions and partners present | stop | `pocket_distance <= 8` | components within 8.0 Å of FZC in 7XLP not supplied: CA · near_site=1, missing=1, uniprot_cofactors=0 | `l2.context.cofactors` · 1.5 s |
| Pocket residues resolved, no missing loops lining the pocket | pass | `pocket_distance <= 6` | 37 pocket residues complete in 7XLP.cif · pocket_residues=37, incomplete=0, sequence_gaps=0 | `l2.pocket.resolved` · 15 ms |
| Receptor state apo or holo | pass | n/a | 7XLP.cif holo: FZC in the site · state=holo, site_ligands=1 | `l2.receptor.state` · 15 ms |
| Receptor protonation at the stated pH | warn | `pka_margin > 1` | receptor has no hydrogens (protonation not assigned) · hydrogens_present=False, ph=7.4, pocket_titratable=12 | `l2.receptor.protonation` · 346 ms |
| Ligand protonation and tautomers enumerated at the stated pH | warn | `ph 7.4 == 1` | ligand: 16 states · ph=7.4, max_states=16, declared_not_enumerated=0 | `l2.ligand.protonation` · 126 ms |
| Ligand conformers generated and minimised | pass | `conformers >= 10` | 10 ETKDG conformers per ligand, MMFF minimised · ligands=1, failed=0, min_embedded=10 | `l2.ligand.conformers` · 1.6 s |
| Docking box encloses the pocket with margin | warn | `margin >= 2` | no box declared; derived box encloses 19 contact residues and the FZC ligand with 2.0 Å margin · volume_A3=5697, ligand_atoms_inside_margin=33, ligand_atoms=33 | `l2.docking.box` · 18 ms |

## L3 Applicability

Is the tool inside its validated regime?

Status: done. Checks: pass 5 · warn 0 · stop 0 · skip 1. Time: 3.2 s.

#### Key figures

| Figure | Value |
| --- | --- |
| executors | 2 |
| unknown | 0 |
| reference released | 2023-03-01 |
| cutoff | 2019-01-01 |
| systems | 0 |
| analogue components | 1 |
| entries 95 | 35 |
| entries 40 | 44 |

#### Checks

| Check | Result | Measured cmp threshold | Evidence | Id · time |
| --- | --- | --- | --- | --- |
| Model training cutoff recorded | pass | `training_cutoff == recorded` | boltz2 2023-06-01; diffdock 2019-01-01; reference 7XLP released 2023-03-01, before the cutoff of boltz2 · executors=2, unknown=0, reference_released=2023-03-01 | `l3.model.training_cutoff` · 57 ms |
| Pocket similarity to pre-cutoff complexes (SuCOS times pocket coverage) | skip | n/a | OutputUnavailableError: cannot read ligand of boltz2/seed1/sample0: /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/harness/mek1_pert_boltz2/run/predictions/00_boltz2/boltz2/seed1/sample0/ligand.sdf · error | `l3.exposure.pocket` · 213 ms |
| Ligand analogues in pre-cutoff training systems | pass | `tanimoto > 0.9` | 0 PDB entries released before 2019-01-01 (diffdock cutoff) contain analogues of ligand above Tanimoto 0.9: FZC · cutoff=2019-01-01, systems=0, analogue_components=1 | `l3.exposure.ligand_prevalence` · 673 ms |
| Chain sequence identity to pre-cutoff entries (secondary measure) | pass | `identity < 0.4` | protein: 35 entries at 95 percent identity, 44 at 40 percent, released before 2019-01-01 (reported, not gating) · cutoff=2019-01-01, entries_95=35, entries_40=44 | `l3.exposure.sequence` · 2.3 s |
| Modality inside the validated set; token count against the training crop | pass | n/a | modalities protein, protein_ligand inside the validated set; 381 tokens · modalities=2, tokens=381, outside=0 | `l3.regime.modality` · 19 ms |
| Endpoint fits the tool | pass | `endpoint pose in pose` | endpoint pose produced by boltz2, diffdock · endpoint=pose, executors=2, not_fitting=0 | `l3.metric.endpoint` · 0 ms |

## L4 Output validity

Is the result physically and chemically sensible?

Status: done. Checks: pass 1 · warn 1 · stop 1 · skip 4. Time: 26.5 s.

#### Key figures

| Figure | Value |
| --- | --- |
| poses | 3 |
| passed | 18 |
| total | 20 |
| poses all pass | 0 |
| interactions representative | 8 |
| distinct | 6 |
| hbonds representative | 3 |
| key interactions | 3 |

#### PoseBusters · 18/20 tests pass

| test | result | value |
| --- | --- | --- |
| sanitization | fail | fail |
| inchi_convertible | fail | fail |
| all_atoms_connected | pass | pass |
| no_radicals | pass | pass |
| bond_lengths | pass | 0 long outliers |
| bond_angles | pass | 0 outliers |
| internal_steric_clash | pass | 0 |
| aromatic_ring_flatness | pass | 0.01 Å |
| non-aromatic_ring_non-flatness | pass | pass |
| double_bond_flatness | pass | pass |
| internal_energy | pass | 4.6 times the ensemble mean |
| protein-ligand_maximum_distance | pass | 2.55 Å |
| minimum_distance_to_protein | pass | 2.55 Å |
| minimum_distance_to_organic_cofactors | pass | pass |
| minimum_distance_to_inorganic_cofactors | pass | pass |
| minimum_distance_to_waters | pass | pass |
| volume_overlap_with_protein | pass | 0.009 |
| volume_overlap_with_organic_cofactors | pass | pass |
| volume_overlap_with_inorganic_cofactors | pass | pass |
| volume_overlap_with_waters | pass | pass |

#### Per-pose physical checks

| pose | PoseBusters |
| --- | --- |
| boltz2/seed1/sample0 | 18/20 |
| boltz2/seed2/sample0 | 18/20 |
| boltz2/seed3/sample0 | 18/20 |
| median | 18/20 |

#### Interaction fingerprint · representative pose boltz2/seed1/sample0

| residue | type | distance | poses |
| --- | --- | --- | --- |
| GLY111A | hbond | 2.99 Å | 3/3 |
| GLY159A | hbond | 3.63 Å | 3/3 |
| SER150A | hbond | 3.18 Å | 3/3 |
| VAL82A | hydrophobic | 3.45 Å | 3/3 |
| ILE99A | hydrophobic | 3.23 Å | 2/3 |
| LEU74A | hydrophobic | 3.86 Å | 1/3 |

![Grid of PoseBusters tests (rows) by poses (columns); failed cells red with an x.](figures/posebusters_grid.svg)

Fig. 2 · PoseBusters tests (20) by pose (3). Failed cells marked x: 6 of 60.
Files: data [figures/posebusters_grid.csv](figures/posebusters_grid.csv).

![Heatmap of residues (rows) by interaction type (columns), shaded by pose count.](figures/interactions.svg)

Fig. 3 · Interactions by residue (6) and type (2); cell label: poses with the interaction over poses assessed.
Files: data [figures/interactions.csv](figures/interactions.csv).

#### Checks

| Check | Result | Measured cmp threshold | Evidence | Id · time |
| --- | --- | --- | --- | --- |
| PoseBusters geometry, stereochemistry, clashes and protein contact | stop | `tests_failed == 0` | representative pose boltz2/seed1/sample0 fails sanitization, inchi_convertible · poses=3, passed=18, total=20 | `l4.posebusters` · 5.8 s |
| Torsional strain of the ligand pose | skip | n/a | OutputUnavailableError: cannot read ligand of boltz2/seed1/sample0: /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/harness/mek1_pert_boltz2/run/predictions/00_boltz2/boltz2/seed1/sample0/ligand.sdf · error | `l4.torsion_strain` · 1 ms |
| Interaction fingerprint (PLIP) | pass | n/a | 8 interactions in boltz2/seed1/sample0 (hbond, hydrophobic); 6 distinct across 3 poses (reported) · poses=3, interactions_representative=8, distinct=6 | `l4.interactions.fingerprint` · 1.3 s |
| Buried ligand polar atoms without a hydrogen-bond partner | skip | n/a | OutputUnavailableError: cannot read ligand of boltz2/seed1/sample0: /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/harness/mek1_pert_boltz2/run/predictions/00_boltz2/boltz2/seed1/sample0/ligand.sdf · error | `l4.interactions.unsatisfied_polars` · 2 ms |
| Hydrophobic complementarity of buried ligand surface | skip | n/a | OutputUnavailableError: cannot read ligand of boltz2/seed1/sample0: /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/harness/mek1_pert_boltz2/run/predictions/00_boltz2/boltz2/seed1/sample0/ligand.sdf · error | `l4.interactions.hydrophobic` · 0 ms |
| Interactions of the crystal ligand reproduced by the pose | warn | `reproduced 0 >= 1` | boltz2/seed1/sample0 reproduces none of 3 FZC interactions · key_interactions=3, reproduced=0, poses_reproducing_all=0 | `l4.interactions.known_binders` · 375 ms |
| Pose stability under short restrained minimisation (OpenMM, AMBER14 and OpenFF) | skip | n/a | OutputUnavailableError: minimisation failed for every pose:     AddHs(RDKit::ROMol mol, RDKit::MolOps::AddHsParameters params, boost::python::api::object onlyOnAtoms=None);     AddHs(RDKit::ROMol mol, RDKit::MolOps::AddHsParameters params, boost::python::api::object onlyOnAtoms=None);     AddHs(RDKit::ROMol mol, RDKit::MolOps::AddHsParameters params, boost::python::api::object onlyOnAtoms=None) · error | `l4.minimisation_drift` · 19.1 s |

## L5 Output support

Is a valid result corroborated?

Status: done. Checks: pass 0 · warn 1 · stop 1 · skip 3. Time: 15 ms.

#### Key figures

| Figure | Value |
| --- | --- |
| independent seeds | 3 |
| samples | 3 |
| duplicated outputs | 0 |

#### Checks

| Check | Result | Measured cmp threshold | Evidence | Id · time |
| --- | --- | --- | --- | --- |
| Confidence restricted to the pocket; per-model thresholds | skip | n/a | OutputUnavailableError: cannot read ligand of boltz2/seed1/sample0: /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/harness/mek1_pert_boltz2/run/predictions/00_boltz2/boltz2/seed1/sample0/ligand.sdf · error | `l5.confidence.local` · 8 ms |
| Independent seeds counted separately from samples; duplicates flagged | warn | `seeds_cofolding >= 5` | 3 independent seeds (3 poses); task default 5 · independent_seeds=3, samples=3, duplicated_outputs=0 | `l5.sampling.seeds` · 1 ms |
| Medoid of the largest cluster, populations, pairwise spread, site and pose accuracy | skip | n/a | OutputUnavailableError: cannot read ligand of boltz2/seed1/sample0: /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/harness/mek1_pert_boltz2/run/predictions/00_boltz2/boltz2/seed1/sample0/ligand.sdf · error | `l5.sampling.clusters` · 1 ms |
| Agreement between methods, weighted by independence | skip | n/a | OutputUnavailableError: cannot read ligand of boltz2/seed1/sample0: /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/harness/mek1_pert_boltz2/run/predictions/00_boltz2/boltz2/seed1/sample0/ligand.sdf · error | `l5.agreement.cross_family` · 1 ms |
| Redocking control reproduces the crystal pose | stop | `rmsd <= 2` | redocking control required by the task and not supplied (controls.redocking) | `l5.controls.redocking` · 0 ms |

## Controls

| control | status | result |
| --- | --- | --- |
| redocking | incomplete | redocking control required by the task and not supplied (controls.redocking) |

## Provenance

7 objects · 0 cached · 7 network.

| Source | Accession | Release | SHA-256 | Retrieved | Bytes | Cache | Used by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rcsb_files | 7XLP | n/a | `48ffbc34e5fd` | 2026-10-17 17:04:21 UTC | 527387 | miss | l2.context.cofactors, l2.pocket.resolved, l2.receptor.state, l2.docking.box, l3.exposure.pocket, l3.regime.modality, l4.posebusters, l4.interactions.fingerprint, l4.interactions.known_binders, l5.sampling.clusters, l5.agreement.cross_family |
| ccd | FZC | 2023-02-24 | `6ce219c20fef` | 2026-10-17 17:04:21 UTC | 3599 | miss | l2.context.cofactors, l3.exposure.ligand_prevalence |
| rcsb | 7XLP | 1.2 | `66dacec771f9` | 2026-10-17 17:04:23 UTC | 12056 | miss | l3.model.training_cutoff |
| rcsb_search | chem:Cc1ccnc(n1)Oc2ccc(c(c2)Cl)c3cc4c(c(n[nH]4)C)c(c3)O[C@H]5CCC[C@H](C5)N | n/a | `6503a4c7b794` | 2026-10-17 17:04:24 UTC | 186 | miss | l3.exposure.ligand_prevalence |
| rcsb_search | comp:FZC:2019-01-01 | n/a | `e3b0c44298fc` | 2026-10-17 17:04:24 UTC | 0 | miss | l3.exposure.ligand_prevalence |
| rcsb_search | seq0.95:2019-01-01:348 | n/a | `137b5572110a` | 2026-10-17 17:04:26 UTC | 402 | miss | l3.exposure.sequence |
| rcsb_search | seq0.4:2019-01-01:348 | n/a | `d6df9b9b71ba` | 2026-10-17 17:04:27 UTC | 402 | miss | l3.exposure.sequence |

Provenance graph: [json](graph.json), [mmd](graph.mmd), [svg](graph.svg).

## Thresholds

| Check | Threshold | Value | Origin | Evidence level |
| --- | --- | --- | --- | --- |
| `l2.context.cofactors` | pocket_distance | <= 8 | Harness rule: a component of the reference entry within 8 Å of the declared ligand is required context; not yet calibrated | uncalibrated |
| `l2.pocket.resolved` | pocket_distance | <= 6 | Harness rule: pocket residues have a heavy atom within 6 Å of the ligand; not yet calibrated | uncalibrated |
| `l2.pocket.resolved` | missing_pocket_residues | == 0 | Specification layer 2: stop when the pocket is incomplete | published |
| `l2.receptor.protonation` | pka_margin | > 1 | Harness rule: a titratable pocket residue with PROPKA pKa within 1 unit of the stated pH has an ambiguous state; not yet calibrated | uncalibrated |
| `l2.ligand.protonation` | ph_window | == 1 | Harness rule: states enumerated by Dimorphite-DL within 1 pH unit of the stated pH; not yet calibrated | uncalibrated |
| `l2.ligand.protonation` | states | == 1 | Specification layer 2: warn when more than one plausible state | published |
| `l2.ligand.conformers` | conformers | >= 10 | Harness default number of ETKDG conformers; not yet calibrated | uncalibrated |
| `l2.docking.box` | margin | >= 2 | Harness rule: every pocket heavy atom lies at least 2 Å inside the box; not yet calibrated | uncalibrated |
| `l2.docking.box` | contact_distance | <= 4 | Harness rule: contact residues (heavy atom within 4 Å of the reference ligand) must have an atom inside the box; not yet calibrated | uncalibrated |
| `l3.model.training_cutoff` | training_cutoff | == recorded | Specification, Layer 3 (applicability): stop when unknown | published |
| `l3.exposure.ligand_prevalence` | tanimoto | > 0.9 | Specification layer 3: analogues above 0.9 Tanimoto (RDKit topological fingerprint) | published |
| `l3.exposure.ligand_prevalence` | systems | <= 100 | Specification layer 3: prevalent when analogues occur in more than 100 training systems | published |
| `l3.exposure.sequence` | identity | < 0.4 | Specification layer 3: conventional 40 percent identity leakage threshold, reported as a secondary measure only | published |
| `l3.metric.endpoint` | endpoint | in pose | Specification, Layer 3 (applicability): no affinity from interface confidence, no protein-protein affinity from Boltz-2 | published |
| `l4.posebusters` | tests_failed | == 0 | Specification, Layer 4 (output validity): stop on failure | published |
| `l4.interactions.known_binders` | reproduced | >= 1 | Specification layer 4: warn when no key interaction is reproduced | published |
| `l5.sampling.seeds` | seeds_cofolding | >= 5 | Specification layer 5: default of five seeds per co-folding prediction | published |
| `l5.controls.redocking` | rmsd | <= 2 | Specification layer 5: redocking must reproduce the crystal pose (2 Å ligand RMSD) | published |

Tool versions: dimorphite_dl 2.1.0, freesasa 2.2.1, gemmi 0.7.5, numpy 1.26.4, openbabel 3.2.1, plip 3.0.1, posebusters 0.6.5, propka 3.5.1, rdkit 2026.9.1, scipy 1.17.1, spyrmsd 0.9.0.

## Limitations

- This report covers layers 2, 3, 4, 5. Layers not run: 0, 1.
- The harness establishes when a result should not be trusted. Passing checks are not evidence that a prediction is correct.
- Thresholds marked uncalibrated come from the specification or harness defaults and have not been recalibrated on the harness benchmark.

## Files

| Path | Kind | Bytes | SHA-256 |
| --- | --- | --- | --- |
| artifacts/sources/7XLP.cif | source_structure | 527387 | `48ffbc34e5fd` |
| /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/predictions/mek1_pert/boltz2/seed_1/boltz_results_mek1_pert/predictions/mek1_pert/mek1_pert_model_0.cif | prediction_structure | 240701 | `d3109735f747` |
| predictions/00_boltz2/boltz2/seed1/sample0/ligand.sdf | data | 2874 | `85041ad5031a` |
| /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/predictions/mek1_pert/boltz2/seed_2/boltz_results_mek1_pert/predictions/mek1_pert/mek1_pert_model_0.cif | prediction_structure | 240650 | `320651246ca6` |
| predictions/00_boltz2/boltz2/seed2/sample0/ligand.sdf | data | 2874 | `bebe7cf03026` |
| /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/predictions/mek1_pert/boltz2/seed_3/boltz_results_mek1_pert/predictions/mek1_pert/mek1_pert_model_0.cif | prediction_structure | 240924 | `3dd5cb3f0f1e` |
| predictions/00_boltz2/boltz2/seed3/sample0/ligand.sdf | data | 2874 | `d18e7286402f` |
| predictions/01_diffdock/diffdock/seed1/mode0/complex.pdb | prediction_structure | 190005 | `78ae8b3ed08f` |
| predictions/01_diffdock/diffdock/seed1/mode0/ligand.sdf | data | 2874 | `40f31978ee4c` |
| predictions/01_diffdock/diffdock/seed1/mode1/complex.pdb | prediction_structure | 190005 | `3121e202f5ca` |
| predictions/01_diffdock/diffdock/seed1/mode1/ligand.sdf | data | 2874 | `bd0c0e753343` |
| predictions/01_diffdock/diffdock/seed1/mode2/complex.pdb | prediction_structure | 190005 | `25b62ddb535f` |
| predictions/01_diffdock/diffdock/seed1/mode2/ligand.sdf | data | 2874 | `22dca1f6aae4` |
| predictions/01_diffdock/diffdock/seed1/mode3/complex.pdb | prediction_structure | 190005 | `fefcbc8cf186` |
| predictions/01_diffdock/diffdock/seed1/mode3/ligand.sdf | data | 2874 | `0ce95c9b67f8` |
| predictions/01_diffdock/diffdock/seed1/mode4/complex.pdb | prediction_structure | 190005 | `1e70558760f7` |
| predictions/01_diffdock/diffdock/seed1/mode4/ligand.sdf | data | 2874 | `6b6b6c641031` |
| predictions/01_diffdock/diffdock/seed1/mode5/complex.pdb | prediction_structure | 190005 | `8985a0a202b6` |
| predictions/01_diffdock/diffdock/seed1/mode5/ligand.sdf | data | 2874 | `5a8457c2bef2` |
| predictions/01_diffdock/diffdock/seed1/mode6/complex.pdb | prediction_structure | 190005 | `b312102dca3a` |
| predictions/01_diffdock/diffdock/seed1/mode6/ligand.sdf | data | 2874 | `222bd3a4323f` |
| predictions/01_diffdock/diffdock/seed1/mode7/complex.pdb | prediction_structure | 190005 | `6b7c31295f21` |
| predictions/01_diffdock/diffdock/seed1/mode7/ligand.sdf | data | 2874 | `e6b48f5bcab2` |
| predictions/01_diffdock/diffdock/seed1/mode8/complex.pdb | prediction_structure | 190005 | `d7b509f2520e` |
| predictions/01_diffdock/diffdock/seed1/mode8/ligand.sdf | data | 2874 | `b671d5482d7f` |
| predictions/01_diffdock/diffdock/seed1/mode9/complex.pdb | prediction_structure | 190005 | `fa249fa473e5` |
| predictions/01_diffdock/diffdock/seed1/mode9/ligand.sdf | data | 2874 | `e734897a6a2c` |
| predictions/01_diffdock/diffdock/seed2/mode0/complex.pdb | prediction_structure | 190005 | `e930537ad18a` |
| predictions/01_diffdock/diffdock/seed2/mode0/ligand.sdf | data | 2874 | `8a60d7081742` |
| predictions/01_diffdock/diffdock/seed2/mode1/complex.pdb | prediction_structure | 190005 | `ae5414248a0a` |
| predictions/01_diffdock/diffdock/seed2/mode1/ligand.sdf | data | 2874 | `424054651752` |
| predictions/01_diffdock/diffdock/seed2/mode2/complex.pdb | prediction_structure | 190005 | `e98c6d24cc76` |
| predictions/01_diffdock/diffdock/seed2/mode2/ligand.sdf | data | 2874 | `0203db493c67` |
| predictions/01_diffdock/diffdock/seed2/mode3/complex.pdb | prediction_structure | 190005 | `7bf30c130e33` |
| predictions/01_diffdock/diffdock/seed2/mode3/ligand.sdf | data | 2874 | `e2c0d171691d` |
| predictions/01_diffdock/diffdock/seed2/mode4/complex.pdb | prediction_structure | 190005 | `f7476a62c200` |
| predictions/01_diffdock/diffdock/seed2/mode4/ligand.sdf | data | 2874 | `0623a7d42943` |
| predictions/01_diffdock/diffdock/seed2/mode5/complex.pdb | prediction_structure | 190005 | `0d395223e8eb` |
| predictions/01_diffdock/diffdock/seed2/mode5/ligand.sdf | data | 2874 | `321b0aaaaa71` |
| predictions/01_diffdock/diffdock/seed2/mode6/complex.pdb | prediction_structure | 190005 | `dc57ae3b3286` |
| predictions/01_diffdock/diffdock/seed2/mode6/ligand.sdf | data | 2874 | `375950327bf9` |
| predictions/01_diffdock/diffdock/seed2/mode7/complex.pdb | prediction_structure | 190005 | `826be0ee388f` |
| predictions/01_diffdock/diffdock/seed2/mode7/ligand.sdf | data | 2874 | `5d506ff4c9d6` |
| predictions/01_diffdock/diffdock/seed2/mode8/complex.pdb | prediction_structure | 190005 | `165c50d55a4c` |
| predictions/01_diffdock/diffdock/seed2/mode8/ligand.sdf | data | 2874 | `c06ccc53e4fd` |
| predictions/01_diffdock/diffdock/seed2/mode9/complex.pdb | prediction_structure | 190005 | `85e4925ecf50` |
| predictions/01_diffdock/diffdock/seed2/mode9/ligand.sdf | data | 2874 | `14d33926985b` |
| predictions/01_diffdock/diffdock/seed3/mode0/complex.pdb | prediction_structure | 190005 | `da7bdcff1411` |
| predictions/01_diffdock/diffdock/seed3/mode0/ligand.sdf | data | 2874 | `1e7a412b1e18` |
| predictions/01_diffdock/diffdock/seed3/mode1/complex.pdb | prediction_structure | 190005 | `6ccc9520567b` |
| predictions/01_diffdock/diffdock/seed3/mode1/ligand.sdf | data | 2874 | `936c30a8aa00` |
| predictions/01_diffdock/diffdock/seed3/mode2/complex.pdb | prediction_structure | 190005 | `f1058ec975a0` |
| predictions/01_diffdock/diffdock/seed3/mode2/ligand.sdf | data | 2874 | `351f10cacc60` |
| predictions/01_diffdock/diffdock/seed3/mode3/complex.pdb | prediction_structure | 190005 | `6962856f161a` |
| predictions/01_diffdock/diffdock/seed3/mode3/ligand.sdf | data | 2874 | `766247d28e18` |
| predictions/01_diffdock/diffdock/seed3/mode4/complex.pdb | prediction_structure | 190005 | `b39010b569d0` |
| predictions/01_diffdock/diffdock/seed3/mode4/ligand.sdf | data | 2874 | `bc6036a3e31b` |
| predictions/01_diffdock/diffdock/seed3/mode5/complex.pdb | prediction_structure | 190005 | `c85f07d6aebe` |
| predictions/01_diffdock/diffdock/seed3/mode5/ligand.sdf | data | 2874 | `b36e49b428f8` |
| predictions/01_diffdock/diffdock/seed3/mode6/complex.pdb | prediction_structure | 190005 | `104722a46993` |
| predictions/01_diffdock/diffdock/seed3/mode6/ligand.sdf | data | 2874 | `836f4dbbf65a` |
| predictions/01_diffdock/diffdock/seed3/mode7/complex.pdb | prediction_structure | 190005 | `8e33fd3f017c` |
| predictions/01_diffdock/diffdock/seed3/mode7/ligand.sdf | data | 2874 | `43d32e548538` |
| predictions/01_diffdock/diffdock/seed3/mode8/complex.pdb | prediction_structure | 190005 | `a59e361b1df7` |
| predictions/01_diffdock/diffdock/seed3/mode8/ligand.sdf | data | 2874 | `c77637d6e366` |
| predictions/01_diffdock/diffdock/seed3/mode9/complex.pdb | prediction_structure | 190005 | `14259246a04c` |
| predictions/01_diffdock/diffdock/seed3/mode9/ligand.sdf | data | 2874 | `2ddaaa4ff249` |
| renders/7XLP_overview.png | render | 242097 | `42c1ad451238` |
| renders/7XLP_pocket.png | render | 242052 | `793b8c8a67e7` |
| renders/7XLP.pse | session | 804538 | `aa39cf0ddb90` |
| renders/boltz2_seed1_sample0_overview.png | render | 242216 | `712a43960cc5` |
| renders/boltz2_seed1_sample0_pocket.png | render | 404431 | `f4e122d53b00` |
| renders/boltz2_seed1_sample0.pse | session | 899798 | `69254539fdac` |
| renders/boltz2_seed2_sample0_overview.png | render | 245083 | `d3f28a5f0bfc` |
| renders/boltz2_seed2_sample0_pocket.png | render | 436724 | `6a389b61bfcc` |
| renders/boltz2_seed2_sample0.pse | session | 899877 | `c98869ccb3c7` |
| renders/boltz2_seed3_sample0_overview.png | render | 257536 | `2760b51bffdd` |
| renders/boltz2_seed3_sample0_pocket.png | render | 349691 | `c6ddb51f004c` |
| renders/boltz2_seed3_sample0.pse | session | 899829 | `2652c6be3071` |
| renders/diffdock_seed1_mode0_overview.png | render | 230660 | `c72c174ffd6c` |
| renders/diffdock_seed1_mode0_pocket.png | render | 349309 | `76acfbd0c9e7` |
| renders/diffdock_seed1_mode0.pse | session | 666483 | `09679345d0bd` |
| renders/diffdock_seed1_mode1_overview.png | render | 231675 | `5c2fe42a119c` |
| renders/diffdock_seed1_mode1_pocket.png | render | 368109 | `28b9ce958558` |
| renders/diffdock_seed1_mode1.pse | session | 666473 | `31ebad6e581d` |
| renders/diffdock_seed1_mode2_overview.png | render | 229435 | `c2144b863625` |
| renders/diffdock_seed1_mode2_pocket.png | render | 350894 | `c81bf60c9f10` |
| renders/diffdock_seed1_mode2.pse | session | 666544 | `73053a15cc1b` |
| renders/diffdock_seed1_mode3_overview.png | render | 231118 | `c325e9a9363e` |
| renders/diffdock_seed1_mode3_pocket.png | render | 355056 | `1185e7233c77` |
| renders/diffdock_seed1_mode3.pse | session | 666478 | `c97b4dc9df8d` |
| renders/diffdock_seed1_mode4_overview.png | render | 230712 | `61becc254774` |
| renders/diffdock_seed1_mode4_pocket.png | render | 355194 | `5b1f528f494f` |
| renders/diffdock_seed1_mode4.pse | session | 666505 | `3f89753943d8` |
| renders/diffdock_seed1_mode5_overview.png | render | 229227 | `591e32f559bd` |
| renders/diffdock_seed1_mode5_pocket.png | render | 366143 | `996829ced36e` |
| renders/diffdock_seed1_mode5.pse | session | 666607 | `319491c68d1e` |
| renders/diffdock_seed1_mode6_overview.png | render | 229487 | `45b5154ef647` |
| renders/diffdock_seed1_mode6_pocket.png | render | 364509 | `c73e40f1f272` |
| renders/diffdock_seed1_mode6.pse | session | 666513 | `8680e18ef70e` |
| renders/diffdock_seed1_mode7_overview.png | render | 231140 | `755d03b3af3f` |
| renders/diffdock_seed1_mode7_pocket.png | render | 308137 | `8e4da08d2eb8` |
| renders/diffdock_seed1_mode7.pse | session | 666516 | `39964cba0dde` |
| renders/diffdock_seed1_mode8_overview.png | render | 229529 | `d809d41ddaae` |
| renders/diffdock_seed1_mode8_pocket.png | render | 340850 | `c17c978ef7f3` |
| renders/diffdock_seed1_mode8.pse | session | 666521 | `1cfb9634035f` |
| renders/diffdock_seed1_mode9_overview.png | render | 229823 | `f67d0fbe23e2` |
| renders/diffdock_seed1_mode9_pocket.png | render | 382925 | `50413b6faab2` |
| renders/diffdock_seed1_mode9.pse | session | 666511 | `f61aa7d0bb23` |
| renders/diffdock_seed2_mode0_overview.png | render | 231584 | `4d6b73728772` |
| renders/diffdock_seed2_mode0_pocket.png | render | 360198 | `09c188768f31` |
| renders/diffdock_seed2_mode0.pse | session | 666486 | `8903e24df77b` |
| renders/diffdock_seed2_mode1_overview.png | render | 230219 | `3b56a2b10a56` |
| renders/diffdock_seed2_mode1_pocket.png | render | 362505 | `45ce7aa595c2` |
| renders/diffdock_seed2_mode1.pse | session | 666478 | `d63221e4a943` |
| renders/diffdock_seed2_mode2_overview.png | render | 230308 | `8632b114a4ad` |
| renders/diffdock_seed2_mode2_pocket.png | render | 367420 | `2c418e1efb1c` |
| renders/diffdock_seed2_mode2.pse | session | 666517 | `bab224a671c7` |
| renders/diffdock_seed2_mode3_overview.png | render | 231469 | `b96b78408ab4` |
| renders/diffdock_seed2_mode3_pocket.png | render | 361204 | `1aab38d17338` |
| renders/diffdock_seed2_mode3.pse | session | 666482 | `79907e6bdd4e` |
| renders/diffdock_seed2_mode4_overview.png | render | 228758 | `3f0a21d2c528` |
| renders/diffdock_seed2_mode4_pocket.png | render | 347446 | `c27c7aafa0ea` |
| renders/diffdock_seed2_mode4.pse | session | 666507 | `44f8e06d37a3` |
| renders/diffdock_seed2_mode5_overview.png | render | 229723 | `5fccbb26eb2d` |
| renders/diffdock_seed2_mode5_pocket.png | render | 375469 | `5d7f854a8bd6` |
| renders/diffdock_seed2_mode5.pse | session | 666491 | `fcf5309daba7` |
| renders/diffdock_seed2_mode6_overview.png | render | 230241 | `b7d8b67dd9c8` |
| renders/diffdock_seed2_mode6_pocket.png | render | 299175 | `a60ac9973b97` |
| renders/diffdock_seed2_mode6.pse | session | 666612 | `1b86c26f7c68` |
| renders/diffdock_seed2_mode7_overview.png | render | 231167 | `84400c84e12c` |
| renders/diffdock_seed2_mode7_pocket.png | render | 368916 | `214e546544e8` |
| renders/diffdock_seed2_mode7.pse | session | 666511 | `fab65381bbac` |
| renders/diffdock_seed2_mode8_overview.png | render | 227465 | `e9a480da3e46` |
| renders/diffdock_seed2_mode8_pocket.png | render | 381376 | `3dca177948ac` |
| renders/diffdock_seed2_mode8.pse | session | 666628 | `afec70dfb0a5` |
| renders/diffdock_seed2_mode9_overview.png | render | 231347 | `98be224ae81b` |
| renders/diffdock_seed2_mode9_pocket.png | render | 408437 | `d4b28224b07c` |
| renders/diffdock_seed2_mode9.pse | session | 666534 | `fee1bd7f1766` |
| renders/diffdock_seed3_mode0_overview.png | render | 231805 | `4ed8516ed117` |
| renders/diffdock_seed3_mode0_pocket.png | render | 368116 | `c29c501aba1b` |
| renders/diffdock_seed3_mode0.pse | session | 666475 | `37317d164c70` |
| renders/diffdock_seed3_mode1_overview.png | render | 231933 | `53bc7a60b935` |
| renders/diffdock_seed3_mode1_pocket.png | render | 363648 | `41836da74b89` |
| renders/diffdock_seed3_mode1.pse | session | 666472 | `b516849718ca` |
| renders/diffdock_seed3_mode2_overview.png | render | 232056 | `f2842644a679` |
| renders/diffdock_seed3_mode2_pocket.png | render | 363783 | `39496f69658c` |
| renders/diffdock_seed3_mode2.pse | session | 666475 | `30746c9beb1e` |
| renders/diffdock_seed3_mode3_overview.png | render | 230307 | `9fcff6a5773b` |
| renders/diffdock_seed3_mode3_pocket.png | render | 361845 | `988077d6d071` |
| renders/diffdock_seed3_mode3.pse | session | 666517 | `e2d6503bf4b1` |
| renders/diffdock_seed3_mode4_overview.png | render | 231020 | `4d14aea280cc` |
| renders/diffdock_seed3_mode4_pocket.png | render | 362237 | `7152ac0dce7b` |
| renders/diffdock_seed3_mode4.pse | session | 666505 | `487902cccfd6` |
| renders/diffdock_seed3_mode5_overview.png | render | 230109 | `1883690a5f86` |
| renders/diffdock_seed3_mode5_pocket.png | render | 366913 | `711e09ba56c4` |
| renders/diffdock_seed3_mode5.pse | session | 666511 | `0ee728a101dc` |
| renders/diffdock_seed3_mode6_overview.png | render | 229511 | `dc4b0630e5b3` |
| renders/diffdock_seed3_mode6_pocket.png | render | 361142 | `3cc1dd4668f9` |
| renders/diffdock_seed3_mode6.pse | session | 666527 | `f533086b9c76` |
| renders/diffdock_seed3_mode7_overview.png | render | 230757 | `904383bf49f2` |
| renders/diffdock_seed3_mode7_pocket.png | render | 358875 | `c3ee9c9c3c7b` |
| renders/diffdock_seed3_mode7.pse | session | 666484 | `7dae59f4002b` |
| renders/diffdock_seed3_mode8_overview.png | render | 229350 | `aea7881da7e9` |
| renders/diffdock_seed3_mode8_pocket.png | render | 354032 | `7f1825c599c3` |
| renders/diffdock_seed3_mode8.pse | session | 666513 | `b7b5abe0b4f5` |
| renders/diffdock_seed3_mode9_overview.png | render | 228970 | `cf844addfa52` |
| renders/diffdock_seed3_mode9_pocket.png | render | 362011 | `5fce94cce5da` |
| renders/diffdock_seed3_mode9.pse | session | 666603 | `94e8b26bb7c2` |
| figures/gates_by_layer.svg | figure | 90259 | `f72a683709b6` |
| figures/gates_by_layer.csv | data | 135 | `b7c5cc42bb78` |
| figures/posebusters_grid.svg | figure | 28913 | `6f661024c4a9` |
| figures/posebusters_grid.csv | data | 888 | `9f0dc3dbb122` |
| figures/interactions.svg | figure | 13832 | `e651dc0b8f17` |
| figures/interactions.csv | data | 193 | `78cf1757a953` |
| graph.json | graph | 35783 | `4668db2a75bc` |
| graph.mmd | graph | 7144 | `b244d2a3a6a8` |
| graph.svg | graph | 103352 | `b0cce1141673` |
