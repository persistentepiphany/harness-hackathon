# Deck Outline

- File: /home/user/harness-hackathon/bench/runs/2026-10-17T1859Z-849c856/results/deck.pptx
- Slides: 8

## Slide 1: (No title)

Body:
- PRESENTATION
- Does the fact file help reject invalid poses?
- Perturbation benchmark, run 2026-10-17T1859Z-849c856
- 1/8

Notes:
- Same agent, same predictions, two kinds of evidence: the model confidence score alone, or the harness fact file.

## Slide 2: (No title)

Body:
- Four systems, each wild type and perturbed
- Perturbed systems are invalid by construction
- TABLE INDEX
- 4 rows | System | Entry | Ligand | Perturbation
- S1: bench/runs/2026-10-17T1859Z-849c856 (stats.json, facts, renders) · Sources: S1
- 2/8

Notes:
- Each system is predicted by Boltz-2 and DiffDock-L with three seeds. A wild-type prediction is valid when its medoid lies within 2 Å of the deposited ligand.

## Slide 3: (No title)

Body:
- One perturbed prediction, two views
- CDK2, Boltz-2, 13 contacts to glycine
- Score only
- Confidence: ligand_iptm 0.925,
- pocket_plddt 82.3,
- confidence_score 0.877
- Wild type: ligand_iptm 0.978,
- pocket_plddt 95.1,
- confidence_score 0.958
- Harness fact file
- PoseBusters 20 of 20
- Deposited interactions recovered
- 1 of 9
- Buried unsatisfied polars 4
- Ensemble spread 1.3 Å;
- cross-executor 2.31 Å
- S1: bench/runs/2026-10-17T1859Z-849c856 (stats.json, facts, renders) · Sources: S1
- 3/8

Notes:
- 13 contact residues were cut to glycine. The confidence the model reports and the fact file for the same prediction.

## Slide 4: (No title)

Body:
- Medoid poses, wild type and perturbed
- CDK2, Boltz-2
- A. wild type
- Boltz-2 medoid pose
- B. perturbed
- Boltz-2 medoid pose
- Each panel oriented on its ligand; grey: residues ≤ 5 Å.
- S1: bench/runs/2026-10-17T1859Z-849c856 (stats.json, facts, renders) · Sources: S1
- 4/8

## Slide 5: (No title)

Body:
- What the perturbation did, by system
- Deposited contacts the medoid reproduces, wild type against perturbed
- TABLE INDEX
- 4 rows | System | Wild type contacts | Perturbed contacts | Perturbed medoid (Å)
- Each cell Boltz-2 / DiffDock-L. Medoid RMSD is to the deposited ligand; n/a where the perturbation modifies the ligand.
- S1: bench/runs/2026-10-17T1859Z-849c856 (stats.json, facts, renders) · Sources: S1
- 5/8

Notes:
- Contact recovery is the signal that separates the states. Confidence and PoseBusters stay clean on the perturbed poses.

## Slide 6: (No title)

Body:
- Decision per prediction
- A. Ground truth and majority verdict per prediction
- B2 Boltz-2, DD DiffDock-L. V valid, I invalid.
- S1: bench/runs/2026-10-17T1859Z-849c856 (stats.json, facts, renders) · Sources: S1
- 6/8

Notes:
- Score only kept 5 of 10 invalid predictions; the fact file arm kept 3 of 6 valid.

## Slide 7: (No title)

Body:
- Aggregate over this run
- Score only, pooled
- 0.5 (0.236 to 0.767)
- Fact file, pooled
- 0.75 (0.5 to 1.0)
- McNemar exact p
- 0.125; discordant 6 and 1
- 16 predictions; intervals are wide at this size. Invalid kept: score only 5 of 10, fact file 0 of 10. Dashed line at 0.5.
- S1: bench/runs/2026-10-17T1859Z-849c856 (stats.json, facts, renders) · Sources: S1
- 7/8

Notes:
- Boltz-2: score only 0.5 (0.5 to 0.5), fact file 0.833 (0.5 to 1.0). DiffDock-L: score only 0.5 (0.5 to 0.5), fact file 0.667 (0.5 to 1.0).

## Slide 8: (No title)

Body:
- What this run does and does not establish
- Measured
- 16 predictions, 2 executors
- Every prompt and response logged
- Ground truth fixed in advance
- Not established
- A significant difference
- Loss of binding (assumed)
- Effect of prompt length
- S1: bench/runs/2026-10-17T1859Z-849c856 (stats.json, facts, renders) · Sources: S1
- 8/8

Notes:
- Eight systems per executor support a demonstration, not a statistical claim. A length-matched control arm was not run.
