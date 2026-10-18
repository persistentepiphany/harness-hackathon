# Run report · Ligand pose in a known pocket

Prediction assurance · run `ligand_pose-28341789d886` · 2026-10-17 17:10:12 UTC

**Refused** for the claim "Predicted pose of FZC in MEK1 is valid".

Refused over layers 2,3,4,5: 19 pass, 4 warn, 2 stop, 1 skip. Stopped by l2.context.cofactors, l5.controls.redocking. Warnings from l2.receptor.protonation, l2.ligand.protonation, l2.docking.box, l4.interactions.unsatisfied_polars.

Stops: `l2.context.cofactors`, `l5.controls.redocking`.

Warnings: `l2.receptor.protonation`, `l2.ligand.protonation`, `l2.docking.box`, `l4.interactions.unsatisfied_polars`.

| Field | Value |
| --- | --- |
| Task | Ligand pose in a known pocket (`ligand_pose`) |
| Tools | DiffDock-L v1.1.3 (docking), Boltz-2 (co-folding) |
| Target | `protein` |
| Ligand | `Cc1ccnc(n1)Oc2ccc(c(c2)Cl)c3cc4c(c(n[nH]4)C)c(c3)O[C@H]5CCC[C@H](C5)N` |
| Reference | `7XLP` |
| pH | 7.4 |
| Seeds | 3 |
| Layers run | 2, 3, 4, 5 |
| Run | `ligand_pose-28341789d886` |
| Created | 2026-10-17 17:10:12 UTC |
| Finished | 2026-10-17 17:14:13 UTC |
| pah version | 0.1.0 |
| Report schema | 1 |

## Layers

| Layer | Status | Result | pass | warn | stop | skip | Time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L0 Provenance | not run | n/a | n/a | n/a | n/a | n/a | n/a |
| L1 Input integrity | not run | n/a | n/a | n/a | n/a | n/a | n/a |
| L2 Input adequacy | done | stop | 3 | 3 | 1 | 1 | 2.2 s |
| L3 Applicability | done | pass | 6 | 0 | 0 | 0 | 3.5 s |
| L4 Output validity | done | warn | 6 | 1 | 0 | 0 | 234.5 s |
| L5 Output support | done | stop | 4 | 0 | 1 | 0 | 774 ms |

## Figures

![Horizontal stacked bars per layer, split into pass, warn, stop and skip counts.](figures/gates_by_layer.svg)

Fig. 1 · Check outcomes per layer for run ligand_pose-28341789d886. Totals: pass 19, warn 4, stop 2, skip 1.
Files: data [figures/gates_by_layer.csv](figures/gates_by_layer.csv).

## Structures

78 PyMOL renders.

![PyMOL cartoon of 7XLP mmCIF coloured by chain, ligands as sticks.](renders/7XLP_overview.png)

7XLP mmCIF (source_structure), whole structure. Chains A; organic components DMS, FZC. sha256 48ffbc34e5fd126d. PyMOL session: [renders/7XLP.pse](renders/7XLP.pse).

![PyMOL cartoon of 7XLP mmCIF coloured by chain, ligands as sticks.](renders/7XLP_pocket.png)

7XLP mmCIF (source_structure), ligand environment within 5 Å. Chains A; organic components DMS, FZC. sha256 48ffbc34e5fd126d. PyMOL session: [renders/7XLP.pse](renders/7XLP.pse).

![PyMOL cartoon of diffdock/seed1/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode0_overview.png)

diffdock/seed1/mode0 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 f1200afc793eb1a7. PyMOL session: [renders/diffdock_seed1_mode0.pse](renders/diffdock_seed1_mode0.pse).

![PyMOL cartoon of diffdock/seed1/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode0_pocket.png)

diffdock/seed1/mode0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 f1200afc793eb1a7. PyMOL session: [renders/diffdock_seed1_mode0.pse](renders/diffdock_seed1_mode0.pse).

![PyMOL cartoon of diffdock/seed1/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode1_overview.png)

diffdock/seed1/mode1 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 854f6a419e159f5c. PyMOL session: [renders/diffdock_seed1_mode1.pse](renders/diffdock_seed1_mode1.pse).

![PyMOL cartoon of diffdock/seed1/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode1_pocket.png)

diffdock/seed1/mode1 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 854f6a419e159f5c. PyMOL session: [renders/diffdock_seed1_mode1.pse](renders/diffdock_seed1_mode1.pse).

![PyMOL cartoon of diffdock/seed1/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode2_overview.png)

diffdock/seed1/mode2 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 117b19cc94a16661. PyMOL session: [renders/diffdock_seed1_mode2.pse](renders/diffdock_seed1_mode2.pse).

![PyMOL cartoon of diffdock/seed1/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode2_pocket.png)

diffdock/seed1/mode2 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 117b19cc94a16661. PyMOL session: [renders/diffdock_seed1_mode2.pse](renders/diffdock_seed1_mode2.pse).

![PyMOL cartoon of diffdock/seed1/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode3_overview.png)

diffdock/seed1/mode3 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 a6aa9b9af3c30741. PyMOL session: [renders/diffdock_seed1_mode3.pse](renders/diffdock_seed1_mode3.pse).

![PyMOL cartoon of diffdock/seed1/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode3_pocket.png)

diffdock/seed1/mode3 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 a6aa9b9af3c30741. PyMOL session: [renders/diffdock_seed1_mode3.pse](renders/diffdock_seed1_mode3.pse).

![PyMOL cartoon of diffdock/seed1/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode4_overview.png)

diffdock/seed1/mode4 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 a4400ef1d9055a46. PyMOL session: [renders/diffdock_seed1_mode4.pse](renders/diffdock_seed1_mode4.pse).

![PyMOL cartoon of diffdock/seed1/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode4_pocket.png)

diffdock/seed1/mode4 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 a4400ef1d9055a46. PyMOL session: [renders/diffdock_seed1_mode4.pse](renders/diffdock_seed1_mode4.pse).

![PyMOL cartoon of diffdock/seed1/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode5_overview.png)

diffdock/seed1/mode5 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 bb69a19c01513dc1. PyMOL session: [renders/diffdock_seed1_mode5.pse](renders/diffdock_seed1_mode5.pse).

![PyMOL cartoon of diffdock/seed1/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode5_pocket.png)

diffdock/seed1/mode5 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 bb69a19c01513dc1. PyMOL session: [renders/diffdock_seed1_mode5.pse](renders/diffdock_seed1_mode5.pse).

![PyMOL cartoon of diffdock/seed1/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode6_overview.png)

diffdock/seed1/mode6 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 8df073d07833955b. PyMOL session: [renders/diffdock_seed1_mode6.pse](renders/diffdock_seed1_mode6.pse).

![PyMOL cartoon of diffdock/seed1/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode6_pocket.png)

diffdock/seed1/mode6 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 8df073d07833955b. PyMOL session: [renders/diffdock_seed1_mode6.pse](renders/diffdock_seed1_mode6.pse).

![PyMOL cartoon of diffdock/seed1/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode7_overview.png)

diffdock/seed1/mode7 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 8e2b0a41ff0ffca1. PyMOL session: [renders/diffdock_seed1_mode7.pse](renders/diffdock_seed1_mode7.pse).

![PyMOL cartoon of diffdock/seed1/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode7_pocket.png)

diffdock/seed1/mode7 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 8e2b0a41ff0ffca1. PyMOL session: [renders/diffdock_seed1_mode7.pse](renders/diffdock_seed1_mode7.pse).

![PyMOL cartoon of diffdock/seed1/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode8_overview.png)

diffdock/seed1/mode8 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 6172bd3bc2cb2bfd. PyMOL session: [renders/diffdock_seed1_mode8.pse](renders/diffdock_seed1_mode8.pse).

![PyMOL cartoon of diffdock/seed1/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode8_pocket.png)

diffdock/seed1/mode8 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 6172bd3bc2cb2bfd. PyMOL session: [renders/diffdock_seed1_mode8.pse](renders/diffdock_seed1_mode8.pse).

![PyMOL cartoon of diffdock/seed1/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode9_overview.png)

diffdock/seed1/mode9 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 e8292b7388ee9247. PyMOL session: [renders/diffdock_seed1_mode9.pse](renders/diffdock_seed1_mode9.pse).

![PyMOL cartoon of diffdock/seed1/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed1_mode9_pocket.png)

diffdock/seed1/mode9 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 e8292b7388ee9247. PyMOL session: [renders/diffdock_seed1_mode9.pse](renders/diffdock_seed1_mode9.pse).

![PyMOL cartoon of diffdock/seed2/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode0_overview.png)

diffdock/seed2/mode0 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 6fd77e57d466f29a. PyMOL session: [renders/diffdock_seed2_mode0.pse](renders/diffdock_seed2_mode0.pse).

![PyMOL cartoon of diffdock/seed2/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode0_pocket.png)

diffdock/seed2/mode0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 6fd77e57d466f29a. PyMOL session: [renders/diffdock_seed2_mode0.pse](renders/diffdock_seed2_mode0.pse).

![PyMOL cartoon of diffdock/seed2/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode1_overview.png)

diffdock/seed2/mode1 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 483d9416f47538a4. PyMOL session: [renders/diffdock_seed2_mode1.pse](renders/diffdock_seed2_mode1.pse).

![PyMOL cartoon of diffdock/seed2/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode1_pocket.png)

diffdock/seed2/mode1 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 483d9416f47538a4. PyMOL session: [renders/diffdock_seed2_mode1.pse](renders/diffdock_seed2_mode1.pse).

![PyMOL cartoon of diffdock/seed2/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode2_overview.png)

diffdock/seed2/mode2 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 7401b21ba8b53083. PyMOL session: [renders/diffdock_seed2_mode2.pse](renders/diffdock_seed2_mode2.pse).

![PyMOL cartoon of diffdock/seed2/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode2_pocket.png)

diffdock/seed2/mode2 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 7401b21ba8b53083. PyMOL session: [renders/diffdock_seed2_mode2.pse](renders/diffdock_seed2_mode2.pse).

![PyMOL cartoon of diffdock/seed2/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode3_overview.png)

diffdock/seed2/mode3 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 761b8a238d18066a. PyMOL session: [renders/diffdock_seed2_mode3.pse](renders/diffdock_seed2_mode3.pse).

![PyMOL cartoon of diffdock/seed2/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode3_pocket.png)

diffdock/seed2/mode3 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 761b8a238d18066a. PyMOL session: [renders/diffdock_seed2_mode3.pse](renders/diffdock_seed2_mode3.pse).

![PyMOL cartoon of diffdock/seed2/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode4_overview.png)

diffdock/seed2/mode4 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 5fc9b69884d90e7a. PyMOL session: [renders/diffdock_seed2_mode4.pse](renders/diffdock_seed2_mode4.pse).

![PyMOL cartoon of diffdock/seed2/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode4_pocket.png)

diffdock/seed2/mode4 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 5fc9b69884d90e7a. PyMOL session: [renders/diffdock_seed2_mode4.pse](renders/diffdock_seed2_mode4.pse).

![PyMOL cartoon of diffdock/seed2/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode5_overview.png)

diffdock/seed2/mode5 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 15757142d66afef6. PyMOL session: [renders/diffdock_seed2_mode5.pse](renders/diffdock_seed2_mode5.pse).

![PyMOL cartoon of diffdock/seed2/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode5_pocket.png)

diffdock/seed2/mode5 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 15757142d66afef6. PyMOL session: [renders/diffdock_seed2_mode5.pse](renders/diffdock_seed2_mode5.pse).

![PyMOL cartoon of diffdock/seed2/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode6_overview.png)

diffdock/seed2/mode6 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 c4c6bab34d24fdfd. PyMOL session: [renders/diffdock_seed2_mode6.pse](renders/diffdock_seed2_mode6.pse).

![PyMOL cartoon of diffdock/seed2/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode6_pocket.png)

diffdock/seed2/mode6 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 c4c6bab34d24fdfd. PyMOL session: [renders/diffdock_seed2_mode6.pse](renders/diffdock_seed2_mode6.pse).

![PyMOL cartoon of diffdock/seed2/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode7_overview.png)

diffdock/seed2/mode7 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 cbc40c648deee3d5. PyMOL session: [renders/diffdock_seed2_mode7.pse](renders/diffdock_seed2_mode7.pse).

![PyMOL cartoon of diffdock/seed2/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode7_pocket.png)

diffdock/seed2/mode7 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 cbc40c648deee3d5. PyMOL session: [renders/diffdock_seed2_mode7.pse](renders/diffdock_seed2_mode7.pse).

![PyMOL cartoon of diffdock/seed2/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode8_overview.png)

diffdock/seed2/mode8 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 4b47be28f2e12b02. PyMOL session: [renders/diffdock_seed2_mode8.pse](renders/diffdock_seed2_mode8.pse).

![PyMOL cartoon of diffdock/seed2/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode8_pocket.png)

diffdock/seed2/mode8 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 4b47be28f2e12b02. PyMOL session: [renders/diffdock_seed2_mode8.pse](renders/diffdock_seed2_mode8.pse).

![PyMOL cartoon of diffdock/seed2/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode9_overview.png)

diffdock/seed2/mode9 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 3107d7827d1ddea7. PyMOL session: [renders/diffdock_seed2_mode9.pse](renders/diffdock_seed2_mode9.pse).

![PyMOL cartoon of diffdock/seed2/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed2_mode9_pocket.png)

diffdock/seed2/mode9 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 3107d7827d1ddea7. PyMOL session: [renders/diffdock_seed2_mode9.pse](renders/diffdock_seed2_mode9.pse).

![PyMOL cartoon of diffdock/seed3/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode0_overview.png)

diffdock/seed3/mode0 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 885cf27059be4b86. PyMOL session: [renders/diffdock_seed3_mode0.pse](renders/diffdock_seed3_mode0.pse).

![PyMOL cartoon of diffdock/seed3/mode0 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode0_pocket.png)

diffdock/seed3/mode0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 885cf27059be4b86. PyMOL session: [renders/diffdock_seed3_mode0.pse](renders/diffdock_seed3_mode0.pse).

![PyMOL cartoon of diffdock/seed3/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode1_overview.png)

diffdock/seed3/mode1 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 35867b511592d46c. PyMOL session: [renders/diffdock_seed3_mode1.pse](renders/diffdock_seed3_mode1.pse).

![PyMOL cartoon of diffdock/seed3/mode1 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode1_pocket.png)

diffdock/seed3/mode1 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 35867b511592d46c. PyMOL session: [renders/diffdock_seed3_mode1.pse](renders/diffdock_seed3_mode1.pse).

![PyMOL cartoon of diffdock/seed3/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode2_overview.png)

diffdock/seed3/mode2 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 8a05b25ccc6af016. PyMOL session: [renders/diffdock_seed3_mode2.pse](renders/diffdock_seed3_mode2.pse).

![PyMOL cartoon of diffdock/seed3/mode2 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode2_pocket.png)

diffdock/seed3/mode2 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 8a05b25ccc6af016. PyMOL session: [renders/diffdock_seed3_mode2.pse](renders/diffdock_seed3_mode2.pse).

![PyMOL cartoon of diffdock/seed3/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode3_overview.png)

diffdock/seed3/mode3 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 1ce97a1297ca0c26. PyMOL session: [renders/diffdock_seed3_mode3.pse](renders/diffdock_seed3_mode3.pse).

![PyMOL cartoon of diffdock/seed3/mode3 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode3_pocket.png)

diffdock/seed3/mode3 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 1ce97a1297ca0c26. PyMOL session: [renders/diffdock_seed3_mode3.pse](renders/diffdock_seed3_mode3.pse).

![PyMOL cartoon of diffdock/seed3/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode4_overview.png)

diffdock/seed3/mode4 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 cb8b504ffc06d918. PyMOL session: [renders/diffdock_seed3_mode4.pse](renders/diffdock_seed3_mode4.pse).

![PyMOL cartoon of diffdock/seed3/mode4 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode4_pocket.png)

diffdock/seed3/mode4 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 cb8b504ffc06d918. PyMOL session: [renders/diffdock_seed3_mode4.pse](renders/diffdock_seed3_mode4.pse).

![PyMOL cartoon of diffdock/seed3/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode5_overview.png)

diffdock/seed3/mode5 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 a807aa20759d66c5. PyMOL session: [renders/diffdock_seed3_mode5.pse](renders/diffdock_seed3_mode5.pse).

![PyMOL cartoon of diffdock/seed3/mode5 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode5_pocket.png)

diffdock/seed3/mode5 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 a807aa20759d66c5. PyMOL session: [renders/diffdock_seed3_mode5.pse](renders/diffdock_seed3_mode5.pse).

![PyMOL cartoon of diffdock/seed3/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode6_overview.png)

diffdock/seed3/mode6 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 78b2c8aebca297a2. PyMOL session: [renders/diffdock_seed3_mode6.pse](renders/diffdock_seed3_mode6.pse).

![PyMOL cartoon of diffdock/seed3/mode6 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode6_pocket.png)

diffdock/seed3/mode6 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 78b2c8aebca297a2. PyMOL session: [renders/diffdock_seed3_mode6.pse](renders/diffdock_seed3_mode6.pse).

![PyMOL cartoon of diffdock/seed3/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode7_overview.png)

diffdock/seed3/mode7 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 0fbeb3d1f177cdbf. PyMOL session: [renders/diffdock_seed3_mode7.pse](renders/diffdock_seed3_mode7.pse).

![PyMOL cartoon of diffdock/seed3/mode7 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode7_pocket.png)

diffdock/seed3/mode7 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 0fbeb3d1f177cdbf. PyMOL session: [renders/diffdock_seed3_mode7.pse](renders/diffdock_seed3_mode7.pse).

![PyMOL cartoon of diffdock/seed3/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode8_overview.png)

diffdock/seed3/mode8 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 104a213e03d5b551. PyMOL session: [renders/diffdock_seed3_mode8.pse](renders/diffdock_seed3_mode8.pse).

![PyMOL cartoon of diffdock/seed3/mode8 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode8_pocket.png)

diffdock/seed3/mode8 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 104a213e03d5b551. PyMOL session: [renders/diffdock_seed3_mode8.pse](renders/diffdock_seed3_mode8.pse).

![PyMOL cartoon of diffdock/seed3/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode9_overview.png)

diffdock/seed3/mode9 (prediction_structure), whole structure. Chains A, L; organic components LIG. sha256 ae8e34ea125b8ba7. PyMOL session: [renders/diffdock_seed3_mode9.pse](renders/diffdock_seed3_mode9.pse).

![PyMOL cartoon of diffdock/seed3/mode9 coloured by chain, ligands as sticks.](renders/diffdock_seed3_mode9_pocket.png)

diffdock/seed3/mode9 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG. sha256 ae8e34ea125b8ba7. PyMOL session: [renders/diffdock_seed3_mode9.pse](renders/diffdock_seed3_mode9.pse).

![PyMOL cartoon of boltz2/seed1/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed1_sample0_overview.png)

boltz2/seed1/sample0 (prediction_structure), whole structure. Chains A, L; organic components LIG1. sha256 5e04882f8848fcda. PyMOL session: [renders/boltz2_seed1_sample0.pse](renders/boltz2_seed1_sample0.pse).

![PyMOL cartoon of boltz2/seed1/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed1_sample0_pocket.png)

boltz2/seed1/sample0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG1. sha256 5e04882f8848fcda. PyMOL session: [renders/boltz2_seed1_sample0.pse](renders/boltz2_seed1_sample0.pse).

![PyMOL cartoon of boltz2/seed2/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed2_sample0_overview.png)

boltz2/seed2/sample0 (prediction_structure), whole structure. Chains A, L; organic components LIG1. sha256 a7cd5dc842dcb98f. PyMOL session: [renders/boltz2_seed2_sample0.pse](renders/boltz2_seed2_sample0.pse).

![PyMOL cartoon of boltz2/seed2/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed2_sample0_pocket.png)

boltz2/seed2/sample0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG1. sha256 a7cd5dc842dcb98f. PyMOL session: [renders/boltz2_seed2_sample0.pse](renders/boltz2_seed2_sample0.pse).

![PyMOL cartoon of boltz2/seed3/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed3_sample0_overview.png)

boltz2/seed3/sample0 (prediction_structure), whole structure. Chains A, L; organic components LIG1. sha256 5819a056d9999c96. PyMOL session: [renders/boltz2_seed3_sample0.pse](renders/boltz2_seed3_sample0.pse).

![PyMOL cartoon of boltz2/seed3/sample0 coloured by chain, ligands as sticks.](renders/boltz2_seed3_sample0_pocket.png)

boltz2/seed3/sample0 (prediction_structure), ligand environment within 5 Å. Chains A, L; organic components LIG1. sha256 5819a056d9999c96. PyMOL session: [renders/boltz2_seed3_sample0.pse](renders/boltz2_seed3_sample0.pse).

![PyMOL cartoon of 3ZLS mmCIF coloured by chain, ligands as sticks.](renders/3ZLS_overview.png)

3ZLS mmCIF (source_structure), whole structure. Chains A; organic components 92P. sha256 ae30cf1ed7b4035f. PyMOL session: [renders/3ZLS.pse](renders/3ZLS.pse).

![PyMOL cartoon of 3ZLS mmCIF coloured by chain, ligands as sticks.](renders/3ZLS_pocket.png)

3ZLS mmCIF (source_structure), ligand environment within 5 Å. Chains A; organic components 92P. sha256 ae30cf1ed7b4035f. PyMOL session: [renders/3ZLS.pse](renders/3ZLS.pse).

![PyMOL cartoon of 3ZLX mmCIF coloured by chain, ligands as sticks.](renders/3ZLX_overview.png)

3ZLX mmCIF (source_structure), whole structure. Chains A; organic components 5EZ. sha256 1334dfc31103f3e6. PyMOL session: [renders/3ZLX.pse](renders/3ZLX.pse).

![PyMOL cartoon of 3ZLX mmCIF coloured by chain, ligands as sticks.](renders/3ZLX_pocket.png)

3ZLX mmCIF (source_structure), ligand environment within 5 Å. Chains A; organic components 5EZ. sha256 1334dfc31103f3e6. PyMOL session: [renders/3ZLX.pse](renders/3ZLX.pse).

![PyMOL cartoon of 3ZM4 mmCIF coloured by chain, ligands as sticks.](renders/3ZM4_overview.png)

3ZM4 mmCIF (source_structure), whole structure. Chains A; organic components 22T. sha256 eccb79a35cb7a9f2. PyMOL session: [renders/3ZM4.pse](renders/3ZM4.pse).

![PyMOL cartoon of 3ZM4 mmCIF coloured by chain, ligands as sticks.](renders/3ZM4_pocket.png)

3ZM4 mmCIF (source_structure), ligand environment within 5 Å. Chains A; organic components 22T. sha256 eccb79a35cb7a9f2. PyMOL session: [renders/3ZM4.pse](renders/3ZM4.pse).

![PyMOL cartoon of 5BX0 mmCIF coloured by chain, ligands as sticks.](renders/5BX0_overview.png)

5BX0 mmCIF (source_structure), whole structure. Chains A; organic components 4W5. sha256 7ef25dd3b72e153e. PyMOL session: [renders/5BX0.pse](renders/5BX0.pse).

![PyMOL cartoon of 5BX0 mmCIF coloured by chain, ligands as sticks.](renders/5BX0_pocket.png)

5BX0 mmCIF (source_structure), ligand environment within 5 Å. Chains A; organic components 4W5. sha256 7ef25dd3b72e153e. PyMOL session: [renders/5BX0.pse](renders/5BX0.pse).

![PyMOL cartoon of 3ZLY mmCIF coloured by chain, ligands as sticks.](renders/3ZLY_overview.png)

3ZLY mmCIF (source_structure), whole structure. Chains A; organic components YSO. sha256 e858c796adc5339d. PyMOL session: [renders/3ZLY.pse](renders/3ZLY.pse).

![PyMOL cartoon of 3ZLY mmCIF coloured by chain, ligands as sticks.](renders/3ZLY_pocket.png)

3ZLY mmCIF (source_structure), ligand environment within 5 Å. Chains A; organic components YSO. sha256 e858c796adc5339d. PyMOL session: [renders/3ZLY.pse](renders/3ZLY.pse).

## L0 Provenance

Where did every input come from?

Status: not run.

## L1 Input integrity

Did the run receive exactly what was declared?

Status: not run.

## L2 Input adequacy

Does the input carry enough information?

Status: done. Checks: pass 3 · warn 3 · stop 1 · skip 1. Time: 2.2 s.

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
| Required cofactors, ions and partners present | stop | `pocket_distance <= 8` | components within 8.0 Å of FZC in 7XLP not supplied: CA · near_site=1, missing=1, uniprot_cofactors=0 | `l2.context.cofactors` · 206 ms |
| Pocket residues resolved, no missing loops lining the pocket | pass | `pocket_distance <= 6` | 37 pocket residues complete in 7XLP.cif · pocket_residues=37, incomplete=0, sequence_gaps=0 | `l2.pocket.resolved` · 15 ms |
| Receptor state apo or holo | pass | n/a | 7XLP.cif holo: FZC in the site · state=holo, site_ligands=1 | `l2.receptor.state` · 14 ms |
| Receptor protonation at the stated pH | warn | `pka_margin > 1` | receptor has no hydrogens (protonation not assigned) · hydrogens_present=False, ph=7.4, pocket_titratable=15 | `l2.receptor.protonation` · 345 ms |
| Ligand protonation and tautomers enumerated at the stated pH | warn | `ph 7.4 == 1` | ligand: 16 states · ph=7.4, max_states=16, declared_not_enumerated=0 | `l2.ligand.protonation` · 123 ms |
| Ligand conformers generated and minimised | pass | `conformers >= 10` | 10 ETKDG conformers per ligand, MMFF minimised · ligands=1, failed=0, min_embedded=10 | `l2.ligand.conformers` · 1.4 s |
| Docking box encloses the pocket with margin | warn | `margin >= 2` | no box declared; derived box encloses 19 contact residues and the FZC ligand with 2.0 Å margin · volume_A3=5697, ligand_atoms_inside_margin=33, ligand_atoms=33 | `l2.docking.box` · 15 ms |

## L3 Applicability

Is the tool inside its validated regime?

Status: done. Checks: pass 6 · warn 0 · stop 0 · skip 0. Time: 3.5 s.

#### Key figures

| Figure | Value |
| --- | --- |
| executors | 2 |
| unknown | 0 |
| reference released | 2023-03-01 |
| cutoff | 2019-01-01 |
| entries compared | 5 |
| max similarity | 32.3 |
| pocket residues | 36 |
| systems | 0 |

#### Checks

| Check | Result | Measured cmp threshold | Evidence | Id · time |
| --- | --- | --- | --- | --- |
| Model training cutoff recorded | pass | `training_cutoff == recorded` | diffdock 2019-01-01; boltz2 2023-06-01; reference 7XLP released 2023-03-01, before the cutoff of boltz2 · executors=2, unknown=0, reference_released=2023-03-01 | `l3.model.training_cutoff` · 0 ms |
| Pocket similarity to pre-cutoff complexes (SuCOS times pocket coverage) | pass | `similarity <= 50` | max similarity 32.3 to 3ZM4 (22T, SuCOS 0.506, coverage 0.639), released before 2019-01-01 · cutoff=2019-01-01, entries_compared=5, max_similarity=32.3 | `l3.exposure.pocket` · 3.5 s |
| Ligand analogues in pre-cutoff training systems | pass | `tanimoto > 0.9` | 0 PDB entries released before 2019-01-01 (diffdock cutoff) contain analogues of ligand above Tanimoto 0.9: FZC · cutoff=2019-01-01, systems=0, analogue_components=1 | `l3.exposure.ligand_prevalence` · 0 ms |
| Chain sequence identity to pre-cutoff entries (secondary measure) | pass | `identity < 0.4` | protein: 35 entries at 95 percent identity, 46 at 40 percent, released before 2019-01-01 (reported, not gating) · cutoff=2019-01-01, entries_95=35, entries_40=46 | `l3.exposure.sequence` · 1 ms |
| Modality inside the validated set; token count against the training crop | pass | n/a | modalities protein, protein_ligand inside the validated set; 381 tokens · modalities=2, tokens=381, outside=0 | `l3.regime.modality` · 9 ms |
| Endpoint fits the tool | pass | `endpoint pose in pose` | endpoint pose produced by diffdock, boltz2 · endpoint=pose, executors=2, not_fitting=0 | `l3.metric.endpoint` · 0 ms |

## L4 Output validity

Is the result physically and chemically sensible?

Status: done. Checks: pass 6 · warn 1 · stop 0 · skip 0. Time: 234.5 s.

#### Key figures

| Figure | Value |
| --- | --- |
| poses | 3 |
| passed | 20 |
| total | 20 |
| poses all pass | 1 |
| unlikely torsions | 0 |
| torsions | 7 |
| strain kcal | 2.06 |
| poses with unlikely | 0 |

#### PoseBusters · 20/20 tests pass

| test | result | value |
| --- | --- | --- |
| sanitization | pass | pass |
| inchi_convertible | pass | pass |
| all_atoms_connected | pass | pass |
| no_radicals | pass | pass |
| bond_lengths | pass | 0 long outliers |
| bond_angles | pass | 0 outliers |
| internal_steric_clash | pass | 0 |
| aromatic_ring_flatness | pass | 0.00 Å |
| non-aromatic_ring_non-flatness | pass | pass |
| double_bond_flatness | pass | pass |
| internal_energy | pass | 1.4 times the ensemble mean |
| protein-ligand_maximum_distance | pass | 2.57 Å |
| minimum_distance_to_protein | pass | 2.57 Å |
| minimum_distance_to_organic_cofactors | pass | pass |
| minimum_distance_to_inorganic_cofactors | pass | pass |
| minimum_distance_to_waters | pass | pass |
| volume_overlap_with_protein | pass | 0.015 |
| volume_overlap_with_organic_cofactors | pass | pass |
| volume_overlap_with_inorganic_cofactors | pass | pass |
| volume_overlap_with_waters | pass | pass |

#### Per-pose physical checks

| pose | seed | drift Å | converged | unlikely torsions | unsat. polars | buried charged | PoseBusters |
| --- | --- | --- | --- | --- | --- | --- | --- |
| diffdock/seed1/mode0 | 1 | 0.76 | true | 0/7 | 2 | 0 | 20/20 |
| diffdock/seed2/mode0 | 2 | 0.88 | true | 0/7 | 2 | 0 | 19/20 |
| diffdock/seed3/mode0 | 3 | 1.81 | true | 0/7 | 1 | 0 | 19/20 |
| median | n/a | 0.88 | n/a | 0 | 2 | 0 | 19/20 |

#### Interaction fingerprint · representative pose diffdock/seed1/mode0

| residue | type | distance | poses |
| --- | --- | --- | --- |
| MET146A | hbond | 3.09 Å | 3/3 |
| LEU74A | hydrophobic | 2.54 Å | 3/3 |
| VAL82A | hydrophobic | 2.9 Å | 3/3 |
| ALA95A | halogen | 3.52 Å | 2/3 |
| GLU144A | hbond | 2.94 Å | 2/3 |
| LYS97A | hbond | 3.19 Å | 2/3 |
| LEU115A | hydrophobic | 3.33 Å | 2/3 |
| ALA76A | hbond | 3.84 Å | 1/3 |
| ASP208A | hbond | 4.04 Å | 1/3 |
| SER150A | hbond | 2.03 Å | 1/3 |
| SER194A | hbond | 3.96 Å | 1/3 |
| ALA95A | hydrophobic | 3.66 Å | 1/3 |
| ASP208A | hydrophobic | 3.71 Å | 1/3 |
| GLN153A | hydrophobic | 3.9 Å | 1/3 |
| ILE141A | hydrophobic | 3.83 Å | 1/3 |
| LEU118A | hydrophobic | 3.41 Å | 1/3 |
| LEU197A | hydrophobic | 3.77 Å | 1/3 |
| LEU215A | hydrophobic | 3.76 Å | 1/3 |
| LYS97A | hydrophobic | 3.49 Å | 1/3 |
| VAL211A | hydrophobic | 3.52 Å | 1/3 |

![Grid of PoseBusters tests (rows) by poses (columns); failed cells red with an x.](figures/posebusters_grid.svg)

Fig. 2 · PoseBusters tests (20) by pose (3). Failed cells marked x: 2 of 60.
Files: data [figures/posebusters_grid.csv](figures/posebusters_grid.csv).

![Heatmap of residues (rows) by interaction type (columns), shaded by pose count.](figures/interactions.svg)

Fig. 3 · Interactions by residue (17) and type (3); cell label: poses with the interaction over poses assessed.
Files: data [figures/interactions.csv](figures/interactions.csv).

#### Checks

| Check | Result | Measured cmp threshold | Evidence | Id · time |
| --- | --- | --- | --- | --- |
| PoseBusters geometry, stereochemistry, clashes and protein contact | pass | `tests_failed == 0` | 20 of 20 tests pass for diffdock/seed1/mode0; 1 of 3 poses pass all · poses=3, passed=20, total=20 | `l4.posebusters` · 5.6 s |
| Torsional strain of the ligand pose | pass | `torsion_energy <= 2.5` | 0 of 7 torsions above 2.5 kcal/mol in diffdock/seed1/mode0; strain 2.06 kcal/mol · poses=3, unlikely_torsions=0, torsions=7 | `l4.torsion_strain` · 7.2 s |
| Interaction fingerprint (PLIP) | pass | n/a | 13 interactions in diffdock/seed1/mode0 (halogen, hbond, hydrophobic); 20 distinct across 3 poses (reported) · poses=3, interactions_representative=13, distinct=20 | `l4.interactions.fingerprint` · 1.0 s |
| Buried ligand polar atoms without a hydrogen-bond partner | warn | `relative_sasa < 0.1` | 2 of 6 buried polar ligand atoms without a partner in diffdock/seed1/mode0 · poses=3, unsatisfied=2, buried_charged=0 | `l4.interactions.unsatisfied_polars` · 257 ms |
| Hydrophobic complementarity of buried ligand surface | pass | `fraction >= 0.35` | nonpolar fraction of protein contacts around 26 buried nonpolar ligand atoms in diffdock/seed1/mode0: 0.698 · poses=3, complementarity=0.698, buried_nonpolar=26 | `l4.interactions.hydrophobic` · 254 ms |
| Interactions of the crystal ligand reproduced by the pose | pass | `reproduced 2 >= 1` | diffdock/seed1/mode0 reproduces 2 of 3 FZC interactions: halogen ALA95A, hbond MET146A · key_interactions=3, reproduced=2, poses_reproducing_all=1 | `l4.interactions.known_binders` · 455 ms |
| Pose stability under short restrained minimisation (OpenMM, AMBER14 and OpenFF) | pass | `drift_A 0.76 <= 2` | diffdock/seed1/mode0 moves 0.764 Å under restrained minimisation; 0 of 3 poses above 2.0 Å · poses=3, drift_A=0.764, max_drift_A=1.81 | `l4.minimisation_drift` · 219.8 s |

## L5 Output support

Is a valid result corroborated?

Status: done. Checks: pass 4 · warn 0 · stop 1 · skip 0. Time: 774 ms.

#### Key figures

| Figure | Value |
| --- | --- |
| poses | 3 |
| diffdock confidence | 0.35 |
| independent seeds | 3 |
| samples | 30 |
| duplicated outputs | 0 |
| clusters | 2 |
| largest cluster | 2 |
| pairwise rmsd median A | 11.446 |

#### Sampling

| Field | Value |
| --- | --- |
| site placement | 2 of 3 poses within 4.0 Å of the site (FZC in 7XLP) |
| pose accuracy | 2 of 3 poses within 2.0 Å of the medoid |
| pairwise RMSD median | 11.4 Å |
| pairwise RMSD IQR | 6.59 to 11.5 Å |
| pairs | 3 |
| medoid | diffdock/seed1/mode0 |

#### Clusters

| Field | Value |
| --- | --- |
| cluster 1 | 2/3 poses (diffdock/seed1/mode0) |
| cluster 2 | 1/3 poses (diffdock/seed3/mode0) |

#### Per-seed statistics

| seed | pose | cluster | RMSD to medoid | confidence |
| --- | --- | --- | --- | --- |
| 1 | diffdock/seed1/mode0 | 1 | 0 Å | 0.35 |
| 2 | diffdock/seed2/mode0 | 1 | 1.74 Å | 0.2 |
| 3 | diffdock/seed3/mode0 | 2 | 11.4 Å | -1.06 |
| median | n/a | n/a | 1.74 Å | 0.2 |

#### Ensemble

| structure | kind | source | RMSD to medoid | cluster | pocket pLDDT | ipTM |
| --- | --- | --- | --- | --- | --- | --- |
| diffdock/seed1/mode0 | medoid | diffdock | 0 Å | 1 | n/a | n/a |
| diffdock/seed2/mode0 | docking | diffdock | 1.74 Å | 1 | n/a | n/a |
| diffdock/seed3/mode0 | docking | diffdock | 11.4 Å | 2 | n/a | n/a |

#### Agreement between methods

| method | boltz2 | crystal 7XLP |
| --- | --- | --- |
| diffdock | 1.45 Å (high) | 1.51 Å (decisive) |
| boltz2 | n/a | 0.61 Å (decisive) |

![Dot plot of RMSD to the medoid per pose, coloured by cluster, with a dashed median line.](figures/seed_spread.svg)

Fig. 4 · RMSD to the medoid for 3 poses, coloured by cluster (2 clusters). Dashed line: median 1.74 Å; range 0.00 to 11.45 Å.
Files: data [figures/seed_spread.csv](figures/seed_spread.csv).

![Matrix of methods (rows) against comparators (columns), shaded by the difference.](figures/agreement.svg)

Fig. 5 · Agreement between 2 methods and 2 comparators; range 0.613 to 1.51 Å.
Files: data [figures/agreement.csv](figures/agreement.csv).

#### Checks

| Check | Result | Measured cmp threshold | Evidence | Id · time |
| --- | --- | --- | --- | --- |
| Confidence restricted to the pocket; per-model thresholds | pass | n/a | diffdock/seed1/mode0: diffdock_confidence 0.35; no per-model confidence threshold registered for diffdock (reported) · poses=3, diffdock_confidence=0.35 | `l5.confidence.local` · 0 ms |
| Independent seeds counted separately from samples; duplicates flagged | pass | `seeds_docking >= 3` | 3 independent seeds, 30 poses, no duplicates · independent_seeds=3, samples=30, duplicated_outputs=0 | `l5.sampling.seeds` · 0 ms |
| Medoid of the largest cluster, populations, pairwise spread, site and pose accuracy | pass | `cluster_rmsd <= 2` | medoid diffdock/seed1/mode0; 2 clusters, largest 2 of 3; pairwise RMSD median 11.45 Å (IQR 6.59 to 11.46); 2 of 3 poses within 4.0 Å of the site (FZC in 7XLP); 2 of 3 poses within 2.0 Å of the medoid · poses=3, clusters=2, largest_cluster=2 | `l5.sampling.clusters` · 348 ms |
| Agreement between methods, weighted by independence | pass | `rmsd_to_crystal_A 1.51 <= 2` | diffdock vs boltz2 1.452 Å (high); diffdock vs crystal 7XLP 1.51 Å (decisive); boltz2 vs crystal 7XLP 0.613 Å (decisive) · methods=2, comparisons=3, disagreeing=0 | `l5.agreement.cross_family` · 350 ms |
| Redocking control reproduces the crystal pose | stop | `rmsd <= 2` | redocking control required by the task and not supplied (controls.redocking) | `l5.controls.redocking` · 0 ms |

## Controls

| control | status | result |
| --- | --- | --- |
| redocking | incomplete | redocking control required by the task and not supplied (controls.redocking) |

## Provenance

13 objects · 7 cached · 6 network.

| Source | Accession | Release | SHA-256 | Retrieved | Bytes | Cache | Used by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rcsb_files | 7XLP | n/a | `48ffbc34e5fd` | 2026-10-17 17:04:21 UTC | 527387 | hit | l2.context.cofactors, l2.pocket.resolved, l2.receptor.state, l2.docking.box, l3.exposure.pocket, l3.regime.modality, l4.interactions.fingerprint, l4.interactions.known_binders, l5.sampling.clusters, l5.agreement.cross_family |
| ccd | FZC | 2023-02-24 | `6ce219c20fef` | 2026-10-17 17:04:21 UTC | 3599 | hit | l2.context.cofactors, l3.exposure.pocket |
| rcsb | 7XLP | 1.2 | `66dacec771f9` | 2026-10-17 17:04:23 UTC | 12056 | hit | l3.model.training_cutoff |
| rcsb_search | chem:Cc1ccnc(n1)Oc2ccc(c(c2)Cl)c3cc4c(c(n[nH]4)C)c(c3)O[C@H]5CCC[C@H](C5)N | n/a | `b46bdf444038` | 2026-10-17 17:04:25 UTC | 186 | hit | l3.exposure.pocket |
| rcsb_search | comp:FZC:2019-01-01 | n/a | `e3b0c44298fc` | 2026-10-17 17:04:24 UTC | 0 | hit | l3.exposure.pocket |
| rcsb_search | seq0.9:2019-01-01:348 | n/a | `881c989bed9d` | 2026-10-17 17:10:15 UTC | 2568 | miss | l3.exposure.pocket |
| rcsb_files | 3ZLS | n/a | `ae30cf1ed7b4` | 2026-10-17 17:10:16 UTC | 315218 | miss | l3.exposure.pocket |
| rcsb_files | 3ZLX | n/a | `1334dfc31103` | 2026-10-17 17:10:17 UTC | 313366 | miss | l3.exposure.pocket |
| rcsb_files | 3ZM4 | n/a | `eccb79a35cb7` | 2026-10-17 17:10:17 UTC | 321513 | miss | l3.exposure.pocket |
| rcsb_files | 5BX0 | n/a | `7ef25dd3b72e` | 2026-10-17 17:10:17 UTC | 312068 | miss | l3.exposure.pocket |
| rcsb_files | 3ZLY | n/a | `e858c796adc5` | 2026-10-17 17:10:17 UTC | 310846 | miss | l3.exposure.pocket |
| rcsb_search | seq0.95:2019-01-01:348 | n/a | `1d2d688f2f0a` | 2026-10-17 17:04:34 UTC | 402 | hit | l3.exposure.sequence |
| rcsb_search | seq0.4:2019-01-01:348 | n/a | `baa9d256b8ae` | 2026-10-17 17:04:35 UTC | 393 | hit | l3.exposure.sequence |

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
| `l3.exposure.pocket` | similarity | <= 50 | Specification layer 3: warn above a pocket similarity (SuCOS times pocket coverage) of 50 | published |
| `l3.exposure.pocket` | entries | <= 5 | Harness budget: pre-cutoff holo entries compared per run | uncalibrated |
| `l3.exposure.ligand_prevalence` | tanimoto | > 0.9 | Specification layer 3: analogues above 0.9 Tanimoto (RDKit topological fingerprint) | published |
| `l3.exposure.ligand_prevalence` | systems | <= 100 | Specification layer 3: prevalent when analogues occur in more than 100 training systems | published |
| `l3.exposure.sequence` | identity | < 0.4 | Specification layer 3: conventional 40 percent identity leakage threshold, reported as a secondary measure only | published |
| `l3.metric.endpoint` | endpoint | in pose | Specification, Layer 3 (applicability): no affinity from interface confidence, no protein-protein affinity from Boltz-2 | published |
| `l4.posebusters` | tests_failed | == 0 | Specification, Layer 4 (output validity): stop on failure | published |
| `l4.torsion_strain` | torsion_energy | <= 2.5 | Harness rule: a rotatable torsion whose MMFF energy lies more than 2.5 kcal/mol above the minimum of its rigid scan is unlikely; not yet calibrated | uncalibrated |
| `l4.interactions.unsatisfied_polars` | relative_sasa | < 0.1 | Harness rule: a ligand polar atom with relative SASA below 0.1 in the complex is buried; not yet calibrated | uncalibrated |
| `l4.interactions.unsatisfied_polars` | hbond_distance | <= 3.5 | PLIP hydrogen bond distance cut-off (donor-acceptor 4.1 Å; harness uses 3.5 Å heavy-atom distance) | published |
| `l4.interactions.hydrophobic` | fraction | >= 0.35 | Harness default anchored on 3PTB: the crystal benzamidine scores 0.51, Vina and Boltz-2 poses within 0.5 Å of it score 0.45 and 0.49; not calibrated on the benchmark | uncalibrated |
| `l4.interactions.hydrophobic` | relative_sasa | < 0.1 | Harness rule: a ligand polar atom with relative SASA below 0.1 in the complex is buried; not yet calibrated | uncalibrated |
| `l4.interactions.known_binders` | reproduced | >= 1 | Specification layer 4: warn when no key interaction is reproduced | published |
| `l4.minimisation_drift` | drift | <= 2 | Specification layer 4: warn when the pose moves beyond 2 Å under restrained minimisation | published |
| `l5.sampling.seeds` | seeds_docking | >= 3 | Harness default for independent docking seeds; not yet calibrated | uncalibrated |
| `l5.sampling.clusters` | cluster_rmsd | <= 2 | Specification layer 5: 2 Å symmetry-aware ligand RMSD (spyrmsd) separates pose clusters | published |
| `l5.sampling.clusters` | site_distance | <= 4 | Harness rule: a ligand centroid within 4 Å of the reference site centroid is placed in the site; not yet calibrated | uncalibrated |
| `l5.sampling.clusters` | largest_fraction | >= 0.5 | Harness rule: the largest cluster holds at least half of the poses; not yet calibrated | uncalibrated |
| `l5.agreement.cross_family` | rmsd | <= 2 | Specification layer 5: pose agreement by symmetry-aware ligand RMSD at 2 Å | published |
| `l5.controls.redocking` | rmsd | <= 2 | Specification layer 5: redocking must reproduce the crystal pose (2 Å ligand RMSD) | published |

Tool versions: dimorphite_dl 2.1.0, freesasa 2.2.1, gemmi 0.7.5, numpy 1.26.4, openbabel 3.2.1, openmm 8.6.1, plip 3.0.1, posebusters 0.6.5, propka 3.5.1, rdkit 2026.9.1, scipy 1.17.1, spyrmsd 0.9.0.

## Limitations

- This report covers layers 2, 3, 4, 5. Layers not run: 0, 1.
- The harness establishes when a result should not be trusted. Passing checks are not evidence that a prediction is correct.
- Thresholds marked uncalibrated come from the specification or harness defaults and have not been recalibrated on the harness benchmark.

## Files

| Path | Kind | Bytes | SHA-256 |
| --- | --- | --- | --- |
| artifacts/sources/7XLP.cif | source_structure | 527387 | `48ffbc34e5fd` |
| predictions/00_diffdock/diffdock/seed1/mode0/complex.pdb | prediction_structure | 193326 | `f1200afc793e` |
| predictions/00_diffdock/diffdock/seed1/mode0/ligand.sdf | data | 2874 | `1147cf9aedcb` |
| predictions/00_diffdock/diffdock/seed1/mode1/complex.pdb | prediction_structure | 193326 | `854f6a419e15` |
| predictions/00_diffdock/diffdock/seed1/mode1/ligand.sdf | data | 2874 | `f01a05b925f9` |
| predictions/00_diffdock/diffdock/seed1/mode2/complex.pdb | prediction_structure | 193326 | `117b19cc94a1` |
| predictions/00_diffdock/diffdock/seed1/mode2/ligand.sdf | data | 2874 | `c22ab16b2d57` |
| predictions/00_diffdock/diffdock/seed1/mode3/complex.pdb | prediction_structure | 193326 | `a6aa9b9af3c3` |
| predictions/00_diffdock/diffdock/seed1/mode3/ligand.sdf | data | 2874 | `d2ddf0c685da` |
| predictions/00_diffdock/diffdock/seed1/mode4/complex.pdb | prediction_structure | 193326 | `a4400ef1d905` |
| predictions/00_diffdock/diffdock/seed1/mode4/ligand.sdf | data | 2874 | `5763a59ce45e` |
| predictions/00_diffdock/diffdock/seed1/mode5/complex.pdb | prediction_structure | 193326 | `bb69a19c0151` |
| predictions/00_diffdock/diffdock/seed1/mode5/ligand.sdf | data | 2874 | `82cd405a8d6e` |
| predictions/00_diffdock/diffdock/seed1/mode6/complex.pdb | prediction_structure | 193326 | `8df073d07833` |
| predictions/00_diffdock/diffdock/seed1/mode6/ligand.sdf | data | 2874 | `4f56c4857e26` |
| predictions/00_diffdock/diffdock/seed1/mode7/complex.pdb | prediction_structure | 193326 | `8e2b0a41ff0f` |
| predictions/00_diffdock/diffdock/seed1/mode7/ligand.sdf | data | 2874 | `2b92eef96b2a` |
| predictions/00_diffdock/diffdock/seed1/mode8/complex.pdb | prediction_structure | 193326 | `6172bd3bc2cb` |
| predictions/00_diffdock/diffdock/seed1/mode8/ligand.sdf | data | 2874 | `3207d937b7a8` |
| predictions/00_diffdock/diffdock/seed1/mode9/complex.pdb | prediction_structure | 193326 | `e8292b7388ee` |
| predictions/00_diffdock/diffdock/seed1/mode9/ligand.sdf | data | 2874 | `407b7dee147b` |
| predictions/00_diffdock/diffdock/seed2/mode0/complex.pdb | prediction_structure | 193326 | `6fd77e57d466` |
| predictions/00_diffdock/diffdock/seed2/mode0/ligand.sdf | data | 2874 | `dd5497ac50c2` |
| predictions/00_diffdock/diffdock/seed2/mode1/complex.pdb | prediction_structure | 193326 | `483d9416f475` |
| predictions/00_diffdock/diffdock/seed2/mode1/ligand.sdf | data | 2874 | `ce09d98dfcaf` |
| predictions/00_diffdock/diffdock/seed2/mode2/complex.pdb | prediction_structure | 193326 | `7401b21ba8b5` |
| predictions/00_diffdock/diffdock/seed2/mode2/ligand.sdf | data | 2874 | `45beba11edc4` |
| predictions/00_diffdock/diffdock/seed2/mode3/complex.pdb | prediction_structure | 193326 | `761b8a238d18` |
| predictions/00_diffdock/diffdock/seed2/mode3/ligand.sdf | data | 2874 | `093478187c0b` |
| predictions/00_diffdock/diffdock/seed2/mode4/complex.pdb | prediction_structure | 193326 | `5fc9b69884d9` |
| predictions/00_diffdock/diffdock/seed2/mode4/ligand.sdf | data | 2874 | `6d3c33ddbc25` |
| predictions/00_diffdock/diffdock/seed2/mode5/complex.pdb | prediction_structure | 193326 | `15757142d66a` |
| predictions/00_diffdock/diffdock/seed2/mode5/ligand.sdf | data | 2874 | `4b1d5c5cf5a8` |
| predictions/00_diffdock/diffdock/seed2/mode6/complex.pdb | prediction_structure | 193326 | `c4c6bab34d24` |
| predictions/00_diffdock/diffdock/seed2/mode6/ligand.sdf | data | 2874 | `759ad880db28` |
| predictions/00_diffdock/diffdock/seed2/mode7/complex.pdb | prediction_structure | 193326 | `cbc40c648dee` |
| predictions/00_diffdock/diffdock/seed2/mode7/ligand.sdf | data | 2874 | `5b2e6f12c93a` |
| predictions/00_diffdock/diffdock/seed2/mode8/complex.pdb | prediction_structure | 193326 | `4b47be28f2e1` |
| predictions/00_diffdock/diffdock/seed2/mode8/ligand.sdf | data | 2874 | `7c91c4f8623f` |
| predictions/00_diffdock/diffdock/seed2/mode9/complex.pdb | prediction_structure | 193326 | `3107d7827d1d` |
| predictions/00_diffdock/diffdock/seed2/mode9/ligand.sdf | data | 2874 | `57cef7c79e02` |
| predictions/00_diffdock/diffdock/seed3/mode0/complex.pdb | prediction_structure | 193326 | `885cf27059be` |
| predictions/00_diffdock/diffdock/seed3/mode0/ligand.sdf | data | 2874 | `ac742cd9cb95` |
| predictions/00_diffdock/diffdock/seed3/mode1/complex.pdb | prediction_structure | 193326 | `35867b511592` |
| predictions/00_diffdock/diffdock/seed3/mode1/ligand.sdf | data | 2874 | `9810ef95ca6c` |
| predictions/00_diffdock/diffdock/seed3/mode2/complex.pdb | prediction_structure | 193326 | `8a05b25ccc6a` |
| predictions/00_diffdock/diffdock/seed3/mode2/ligand.sdf | data | 2874 | `efb7cc6b6129` |
| predictions/00_diffdock/diffdock/seed3/mode3/complex.pdb | prediction_structure | 193326 | `1ce97a1297ca` |
| predictions/00_diffdock/diffdock/seed3/mode3/ligand.sdf | data | 2874 | `5e4f208390dd` |
| predictions/00_diffdock/diffdock/seed3/mode4/complex.pdb | prediction_structure | 193326 | `cb8b504ffc06` |
| predictions/00_diffdock/diffdock/seed3/mode4/ligand.sdf | data | 2874 | `6c9741a91d65` |
| predictions/00_diffdock/diffdock/seed3/mode5/complex.pdb | prediction_structure | 193326 | `a807aa20759d` |
| predictions/00_diffdock/diffdock/seed3/mode5/ligand.sdf | data | 2874 | `cbffda2e1a03` |
| predictions/00_diffdock/diffdock/seed3/mode6/complex.pdb | prediction_structure | 193326 | `78b2c8aebca2` |
| predictions/00_diffdock/diffdock/seed3/mode6/ligand.sdf | data | 2874 | `e0d1e42dbbbd` |
| predictions/00_diffdock/diffdock/seed3/mode7/complex.pdb | prediction_structure | 193326 | `0fbeb3d1f177` |
| predictions/00_diffdock/diffdock/seed3/mode7/ligand.sdf | data | 2874 | `b4745bbf6c01` |
| predictions/00_diffdock/diffdock/seed3/mode8/complex.pdb | prediction_structure | 193326 | `104a213e03d5` |
| predictions/00_diffdock/diffdock/seed3/mode8/ligand.sdf | data | 2874 | `55c5397b9528` |
| predictions/00_diffdock/diffdock/seed3/mode9/complex.pdb | prediction_structure | 193326 | `ae8e34ea125b` |
| predictions/00_diffdock/diffdock/seed3/mode9/ligand.sdf | data | 2874 | `25d0f0256101` |
| /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/predictions/mek1_wt/boltz2/seed_1/boltz_results_mek1_wt/predictions/mek1_wt/mek1_wt_model_0.cif | prediction_structure | 243806 | `5e04882f8848` |
| predictions/01_boltz2/boltz2/seed1/sample0/ligand.sdf | data | 2874 | `3686bc8d5f76` |
| /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/predictions/mek1_wt/boltz2/seed_2/boltz_results_mek1_wt/predictions/mek1_wt/mek1_wt_model_0.cif | prediction_structure | 243944 | `a7cd5dc842dc` |
| predictions/01_boltz2/boltz2/seed2/sample0/ligand.sdf | data | 2874 | `65aff4905d87` |
| /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/predictions/mek1_wt/boltz2/seed_3/boltz_results_mek1_wt/predictions/mek1_wt/mek1_wt_model_0.cif | prediction_structure | 244117 | `5819a056d999` |
| predictions/01_boltz2/boltz2/seed3/sample0/ligand.sdf | data | 2874 | `36ba1d1bfc62` |
| artifacts/sources/3ZLS.cif | source_structure | 315218 | `ae30cf1ed7b4` |
| artifacts/sources/3ZLX.cif | source_structure | 313366 | `1334dfc31103` |
| artifacts/sources/3ZM4.cif | source_structure | 321513 | `eccb79a35cb7` |
| artifacts/sources/5BX0.cif | source_structure | 312068 | `7ef25dd3b72e` |
| artifacts/sources/3ZLY.cif | source_structure | 310846 | `e858c796adc5` |
| renders/7XLP_overview.png | render | 242097 | `42c1ad451238` |
| renders/7XLP_pocket.png | render | 242052 | `793b8c8a67e7` |
| renders/7XLP.pse | session | 804538 | `aa39cf0ddb90` |
| renders/diffdock_seed1_mode0_overview.png | render | 232139 | `18e1f044cc05` |
| renders/diffdock_seed1_mode0_pocket.png | render | 359947 | `cb518909ac7b` |
| renders/diffdock_seed1_mode0.pse | session | 678206 | `feb9926231a2` |
| renders/diffdock_seed1_mode1_overview.png | render | 232693 | `c2658f873eec` |
| renders/diffdock_seed1_mode1_pocket.png | render | 310517 | `8de8e4929fda` |
| renders/diffdock_seed1_mode1.pse | session | 678268 | `ac562e21db02` |
| renders/diffdock_seed1_mode2_overview.png | render | 232191 | `87e291a36836` |
| renders/diffdock_seed1_mode2_pocket.png | render | 310661 | `71ed7c88adf5` |
| renders/diffdock_seed1_mode2.pse | session | 678240 | `e92402e20684` |
| renders/diffdock_seed1_mode3_overview.png | render | 232738 | `59d7ae65c67b` |
| renders/diffdock_seed1_mode3_pocket.png | render | 382097 | `077447689b4a` |
| renders/diffdock_seed1_mode3.pse | session | 678274 | `ce896a72dd39` |
| renders/diffdock_seed1_mode4_overview.png | render | 233480 | `80d5a34169dc` |
| renders/diffdock_seed1_mode4_pocket.png | render | 310833 | `e625e029cae9` |
| renders/diffdock_seed1_mode4.pse | session | 678300 | `3fa482adc163` |
| renders/diffdock_seed1_mode5_overview.png | render | 232011 | `6f049565b6d2` |
| renders/diffdock_seed1_mode5_pocket.png | render | 309213 | `24b86df80708` |
| renders/diffdock_seed1_mode5.pse | session | 678302 | `9946250f2309` |
| renders/diffdock_seed1_mode6_overview.png | render | 232266 | `6255ff84ccec` |
| renders/diffdock_seed1_mode6_pocket.png | render | 317636 | `e6f5e63444f2` |
| renders/diffdock_seed1_mode6.pse | session | 678271 | `d5266bb7e09f` |
| renders/diffdock_seed1_mode7_overview.png | render | 231403 | `de9b63586021` |
| renders/diffdock_seed1_mode7_pocket.png | render | 317894 | `3948b24633e9` |
| renders/diffdock_seed1_mode7.pse | session | 678569 | `ba14bf745c95` |
| renders/diffdock_seed1_mode8_overview.png | render | 232305 | `7c9f8f3687b2` |
| renders/diffdock_seed1_mode8_pocket.png | render | 375766 | `ab6c798bea78` |
| renders/diffdock_seed1_mode8.pse | session | 678602 | `1fd92cc46fb8` |
| renders/diffdock_seed1_mode9_overview.png | render | 231732 | `70bade350847` |
| renders/diffdock_seed1_mode9_pocket.png | render | 375658 | `c9cc50dbbee7` |
| renders/diffdock_seed1_mode9.pse | session | 678761 | `2fc2f1ca7eeb` |
| renders/diffdock_seed2_mode0_overview.png | render | 233065 | `9f5193b19cc5` |
| renders/diffdock_seed2_mode0_pocket.png | render | 366629 | `305f3e4427cc` |
| renders/diffdock_seed2_mode0.pse | session | 678211 | `d897df267437` |
| renders/diffdock_seed2_mode1_overview.png | render | 232250 | `dbcd836a80ff` |
| renders/diffdock_seed2_mode1_pocket.png | render | 358085 | `9287445d6582` |
| renders/diffdock_seed2_mode1.pse | session | 678264 | `2cb7b894ec29` |
| renders/diffdock_seed2_mode2_overview.png | render | 232251 | `89ef2d01de8d` |
| renders/diffdock_seed2_mode2_pocket.png | render | 352159 | `54b1a77d2307` |
| renders/diffdock_seed2_mode2.pse | session | 678264 | `c50fa7e43024` |
| renders/diffdock_seed2_mode3_overview.png | render | 233467 | `5df498116c07` |
| renders/diffdock_seed2_mode3_pocket.png | render | 311464 | `54694e88ab81` |
| renders/diffdock_seed2_mode3.pse | session | 678264 | `79816bafdcae` |
| renders/diffdock_seed2_mode4_overview.png | render | 232979 | `8cac222f7028` |
| renders/diffdock_seed2_mode4_pocket.png | render | 306799 | `49a0221d491f` |
| renders/diffdock_seed2_mode4.pse | session | 678237 | `e5f68647ec6d` |
| renders/diffdock_seed2_mode5_overview.png | render | 232076 | `bb5bb20b464c` |
| renders/diffdock_seed2_mode5_pocket.png | render | 305123 | `84d7d9b91ffb` |
| renders/diffdock_seed2_mode5.pse | session | 678305 | `48f0a02be5df` |
| renders/diffdock_seed2_mode6_overview.png | render | 234572 | `93db168c5e68` |
| renders/diffdock_seed2_mode6_pocket.png | render | 339761 | `74a02229d6fd` |
| renders/diffdock_seed2_mode6.pse | session | 678284 | `755aacab4652` |
| renders/diffdock_seed2_mode7_overview.png | render | 231318 | `dbade34d16c1` |
| renders/diffdock_seed2_mode7_pocket.png | render | 303457 | `e0aca62b5f85` |
| renders/diffdock_seed2_mode7.pse | session | 678467 | `60ce6726e702` |
| renders/diffdock_seed2_mode8_overview.png | render | 233982 | `c3a89e4f4e51` |
| renders/diffdock_seed2_mode8_pocket.png | render | 347291 | `ef4a171b14b8` |
| renders/diffdock_seed2_mode8.pse | session | 678566 | `aca93aecbb1f` |
| renders/diffdock_seed2_mode9_overview.png | render | 230102 | `2c53aa6d4041` |
| renders/diffdock_seed2_mode9_pocket.png | render | 383763 | `d140c690d19f` |
| renders/diffdock_seed2_mode9.pse | session | 678511 | `fbb56aa182ae` |
| renders/diffdock_seed3_mode0_overview.png | render | 232919 | `ef49b9985a5a` |
| renders/diffdock_seed3_mode0_pocket.png | render | 314111 | `464da80fbe81` |
| renders/diffdock_seed3_mode0.pse | session | 678254 | `c5093d3f36a3` |
| renders/diffdock_seed3_mode1_overview.png | render | 232407 | `82ab7141b3b1` |
| renders/diffdock_seed3_mode1_pocket.png | render | 310187 | `1af6af05aca8` |
| renders/diffdock_seed3_mode1.pse | session | 678301 | `3c811436c850` |
| renders/diffdock_seed3_mode2_overview.png | render | 232261 | `73a4f968c10f` |
| renders/diffdock_seed3_mode2_pocket.png | render | 308884 | `a4edb0eb647b` |
| renders/diffdock_seed3_mode2.pse | session | 678274 | `bf72e203d3bc` |
| renders/diffdock_seed3_mode3_overview.png | render | 233370 | `f6fc8738a4cf` |
| renders/diffdock_seed3_mode3_pocket.png | render | 307688 | `81f21c7c8b85` |
| renders/diffdock_seed3_mode3.pse | session | 678300 | `b6f4e660ea41` |
| renders/diffdock_seed3_mode4_overview.png | render | 233386 | `48aa911f1605` |
| renders/diffdock_seed3_mode4_pocket.png | render | 307575 | `fd0d265b1b2a` |
| renders/diffdock_seed3_mode4.pse | session | 678300 | `ab45311b662b` |
| renders/diffdock_seed3_mode5_overview.png | render | 232689 | `f764ce67be83` |
| renders/diffdock_seed3_mode5_pocket.png | render | 303375 | `a950d23e6e8b` |
| renders/diffdock_seed3_mode5.pse | session | 678382 | `9c748b8885f0` |
| renders/diffdock_seed3_mode6_overview.png | render | 228444 | `28d8206ac436` |
| renders/diffdock_seed3_mode6_pocket.png | render | 387355 | `bad513c3fa36` |
| renders/diffdock_seed3_mode6.pse | session | 678625 | `035110776ac5` |
| renders/diffdock_seed3_mode7_overview.png | render | 232158 | `44fc775f1996` |
| renders/diffdock_seed3_mode7_pocket.png | render | 362763 | `200af62c685c` |
| renders/diffdock_seed3_mode7.pse | session | 678572 | `f051cb4d2b43` |
| renders/diffdock_seed3_mode8_overview.png | render | 231423 | `6955ce0ffcb7` |
| renders/diffdock_seed3_mode8_pocket.png | render | 399539 | `fa334b503b3b` |
| renders/diffdock_seed3_mode8.pse | session | 678521 | `7ac0d954e9db` |
| renders/diffdock_seed3_mode9_overview.png | render | 231221 | `56123a648c28` |
| renders/diffdock_seed3_mode9_pocket.png | render | 386440 | `2bf3448b2260` |
| renders/diffdock_seed3_mode9.pse | session | 678640 | `79886d423ccb` |
| renders/boltz2_seed1_sample0_overview.png | render | 233007 | `e337ee828f94` |
| renders/boltz2_seed1_sample0_pocket.png | render | 418381 | `588f615671eb` |
| renders/boltz2_seed1_sample0.pse | session | 913512 | `c7a022f18db0` |
| renders/boltz2_seed2_sample0_overview.png | render | 236397 | `aca7e1d968a4` |
| renders/boltz2_seed2_sample0_pocket.png | render | 373295 | `eaf3779cc6ac` |
| renders/boltz2_seed2_sample0.pse | session | 913485 | `482ce833d720` |
| renders/boltz2_seed3_sample0_overview.png | render | 240044 | `1a5a7346687d` |
| renders/boltz2_seed3_sample0_pocket.png | render | 423216 | `599ee5cb9e18` |
| renders/boltz2_seed3_sample0.pse | session | 913571 | `6a1f33972f4f` |
| renders/3ZLS_overview.png | render | 233512 | `a782d06ae9a5` |
| renders/3ZLS_pocket.png | render | 298397 | `20833fb9de54` |
| renders/3ZLS.pse | session | 835492 | `0d9c9ce9ecdc` |
| renders/3ZLX_overview.png | render | 240762 | `1c58b309a897` |
| renders/3ZLX_pocket.png | render | 279354 | `2db88aaa54a0` |
| renders/3ZLX.pse | session | 828753 | `e61eba4ec136` |
| renders/3ZM4_overview.png | render | 239209 | `1cf4ea12da51` |
| renders/3ZM4_pocket.png | render | 255583 | `ef506ce0128c` |
| renders/3ZM4.pse | session | 821169 | `73087a05075e` |
| renders/5BX0_overview.png | render | 236172 | `047d521d360b` |
| renders/5BX0_pocket.png | render | 270947 | `50da71002d4d` |
| renders/5BX0.pse | session | 832059 | `6e7fc62059db` |
| renders/3ZLY_overview.png | render | 241239 | `a623f621bd35` |
| renders/3ZLY_pocket.png | render | 242331 | `7d736153f811` |
| renders/3ZLY.pse | session | 821599 | `82e874ba7192` |
| figures/gates_by_layer.svg | figure | 88863 | `c14a276ae4ed` |
| figures/gates_by_layer.csv | data | 135 | `417a77f8712a` |
| figures/seed_spread.svg | figure | 12707 | `91c4e97cc2ee` |
| figures/seed_spread.csv | data | 157 | `ca23b4f20056` |
| figures/posebusters_grid.svg | figure | 27459 | `f093c7bcd970` |
| figures/posebusters_grid.csv | data | 888 | `84e4fe7c89d8` |
| figures/interactions.svg | figure | 26163 | `4058721688b6` |
| figures/interactions.csv | data | 579 | `121d0880b8cd` |
| figures/agreement.svg | figure | 10976 | `2cfb9a41f3ed` |
| figures/agreement.csv | data | 139 | `df8dd2c59b55` |
| graph.json | graph | 42293 | `3660f552da9d` |
| graph.mmd | graph | 8239 | `d23bde7efb16` |
| graph.svg | graph | 119039 | `c59bef524be3` |
