# Deck Outline

- File: /home/user/harness-hackathon/bench/runs/2026-10-17T1611Z-426bfe9/results/deck.pptx
- Slides: 8

## Slide 1: (No title)

Body:
- PRESENTATION
- Does the fact file help reject invalid poses?
- Perturbation benchmark, run 2026-10-17T1611Z-426bfe9
- 1/8

Notes:
- Same agent, same predictions, two kinds of evidence: the model confidence score alone, or the harness fact file.

## Slide 2: (No title)

Body:
- Four systems, each wild type and perturbed
- Perturbed systems are invalid by construction
- TABLE INDEX
- 4 rows | System | Entry | Ligand | Perturbation
- S1: bench/runs/2026-10-17T1611Z-426bfe9 (stats.json, facts, renders) · Sources: S1
- 2/8

Notes:
- Each system is predicted by Boltz-2 and DiffDock-L with three seeds. A wild-type prediction is valid when its medoid lies within 2 Å of the deposited ligand.

## Slide 3: (No title)

Body:
- One perturbed prediction, two views (CDK2,
- Boltz-2)
- Score only
- Confidence: ligand_iptm 0.947,
- pocket_plddt 85,
- confidence_score 0.894
- Wild type: ligand_iptm 0.975,
- pocket_plddt 94.9,
- confidence_score 0.958
- Harness fact file
- PoseBusters 20 of 20
- Deposited interactions recovered
- 1 of 9
- Buried unsatisfied polars 5
- Ensemble spread 0.894 Å;
- cross-executor 2.66 Å
- S1: bench/runs/2026-10-17T1611Z-426bfe9 (stats.json, facts, renders) · Sources: S1
- 3/8

Notes:
- 13 contact residues were cut to glycine. The confidence the model reports and the fact file for the same prediction.

## Slide 4: (No title)

Body:
- The ligand stays in a pocket whose contacts
- are gone
- A. wild type
- Boltz-2 medoid pose
- B. perturbed
- Boltz-2 medoid pose
- PyMOL renders of the medoid poses, same view per panel.
- S1: bench/runs/2026-10-17T1611Z-426bfe9 (stats.json, facts, renders) · Sources: S1
- 4/8

## Slide 5: (No title)

Body:
- Confusion counts, pooled over both executors
- TABLE INDEX
- 2 rows | Arm | Valid kept | Valid rejected | Invalid kept | Invalid rejected
- 16 predictions (6 valid, 10 invalid); majority verdict over three repeats.
- S1: bench/runs/2026-10-17T1611Z-426bfe9 (stats.json, facts, renders) · Sources: S1
- 5/8

## Slide 6: (No title)

Body:
- Balanced accuracy with 95% intervals
- Pooled
- Score only 0.5 (0.236 to
- 0.767); fact file 0.533
- (0.375 to 0.75)
- McNemar
- Exact p 0.6875 (4 for, 2
- against)
- Bootstrap over predictions; dashed line at 0.5.
- S1: bench/runs/2026-10-17T1611Z-426bfe9 (stats.json, facts, renders) · Sources: S1
- 6/8

Notes:
- Boltz-2: score only 0.5 (0.5 to 0.5), fact file 0.567 (0.25 to 0.929). DiffDock-L: score only 0.5 (0.5 to 0.5), fact file 0.5 (0.5 to 0.5).

## Slide 7: (No title)

Body:
- Decision per prediction
- A
- B2 Boltz-2, DD DiffDock-L. V valid, I invalid.
- S1: bench/runs/2026-10-17T1611Z-426bfe9 (stats.json, facts, renders) · Sources: S1
- 7/8

Notes:
- Score only kept 5 of 10 invalid predictions; the fact file arm kept 1 of 6 valid.

## Slide 8: (No title)

Body:
- What this run does and does not establish
- Measured
- 16 predictions of 4 systems, 2
- executors
- Every prompt and response recorded
- Ground truth fixed before any
- decision
- Not established
- A statistical difference
- between arms
- Binding loss beyond the source
- studies
- Effect of prompt length alone
- S1: bench/runs/2026-10-17T1611Z-426bfe9 (stats.json, facts, renders) · Sources: S1
- 8/8

Notes:
- Eight systems per executor support a demonstration, not a statistical claim. A length-matched control arm was not run.
