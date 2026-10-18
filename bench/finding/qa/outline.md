# Deck Outline

- File: /home/user/harness-hackathon/bench/finding/finding.pptx
- Slides: 8

## Slide 1: (No title)

Body:
- PRESENTATION
- Confidence missed every sabotaged pose
- The harness caught all 9 of 9
- 1/8

Notes:
- Same predictions, same agent, two kinds of evidence: the model's own confidence score, or the harness fact file.

## Slide 2: (No title)

Body:
- Three targets, each predicted twice
- TABLE INDEX
- 3 rows | Target | Entry and ligand | Sabotage | Medoid pose
- Boltz-2 2.2.1 on A100, three seeds per prediction, three independent runs. A sabotaged system cannot bind as deposited, so every sabotaged pose should be rejected.
- S1: bench/runs (2026-10-17T1611Z-426bfe9, 2026-10-17T1752Z-2f5a1c7, 2026-10-17T1859Z-849c856) · Sources: S1
- 2/8

## Slide 3: (No title)

Body:
- CDK2: the ligand stays, the contacts go
- 1B38 chain A, Boltz-2 medoid boltz2/seed3/sample0, 13 contacts cut to glycine
- A. as deposited
- B. pocket cut away
- Contacts 5 of 9 then 1 of 9; ipTM 0.975 then 0.947.
- S1: bench/runs (2026-10-17T1611Z-426bfe9, 2026-10-17T1752Z-2f5a1c7, 2026-10-17T1859Z-849c856) · Sources: S1
- 3/8

Notes:
- One camera, proteins superposed; red marks the residues cut to glycine. Confidence barely moves (0.975 to 0.947) and PoseBusters still passes 20 of 20. The interactions are what collapse, and that is what the fact file reports.

## Slide 4: (No title)

Body:
- MEK1: the ligand stays, the contacts go
- 7XLP chain A, Boltz-2 medoid boltz2/seed2/sample0, 11 contacts cut to glycine
- A. as deposited
- B. pocket cut away
- Contacts 2 of 3 then 0 of 3; ipTM 0.988 then 0.97.
- S1: bench/runs (2026-10-17T1611Z-426bfe9, 2026-10-17T1752Z-2f5a1c7, 2026-10-17T1859Z-849c856) · Sources: S1
- 4/8

Notes:
- One camera, proteins superposed; red marks the residues cut to glycine. Confidence barely moves (0.988 to 0.97) and PoseBusters still passes 20 of 20. The interactions are what collapse, and that is what the fact file reports.

## Slide 5: (No title)

Body:
- What the confidence score sees
- As deposited / sabotaged, run 2026-10-17T1611Z-426bfe9
- TABLE INDEX
- 3 rows | Target | Ligand ipTM | Pocket pLDDT | PoseBusters
- Confidence stays high after the pocket is cut away, and for glucose dehydrogenase the pocket pLDDT rises. PoseBusters passes almost everywhere.
- S1: bench/runs (2026-10-17T1611Z-426bfe9, 2026-10-17T1752Z-2f5a1c7, 2026-10-17T1859Z-849c856) · Sources: S1
- 5/8

Notes:
- This is the whole problem. Nothing in these columns tells the agent the pocket is gone.

## Slide 6: (No title)

Body:
- What the harness sees
- As deposited / sabotaged, run 2026-10-17T1611Z-426bfe9
- TABLE INDEX
- 3 rows | Target | Deposited contacts recovered | Cross-executor RMSD (A) | Strain (kcal/mol)
- Contact recovery falls on every target. Cross-executor RMSD rises on CDK2 and MEK1 and falls on glucose dehydrogenase, where both tools were already far apart.
- S1: bench/runs (2026-10-17T1611Z-426bfe9, 2026-10-17T1752Z-2f5a1c7, 2026-10-17T1859Z-849c856) · Sources: S1
- 6/8

## Slide 7: (No title)

Body:
- Every sabotaged pose, both ways of judging
- A
- 9 sabotaged predictions: 3 targets by 3 runs.
- S1: bench/runs (2026-10-17T1611Z-426bfe9, 2026-10-17T1752Z-2f5a1c7, 2026-10-17T1859Z-849c856) · Sources: S1
- 7/8

Notes:
- Confidence missed 9 of 9; the fact file caught 9.

## Slide 8: (No title)

Body:
- What it buys and what it costs
- Buys
- 9 of 9 sabotaged poses rejected
- Same answer in three runs
- A reason recorded per decision
- Costs
- Good poses rejected too
- CDK2 as deposited, all runs
- Mostly high strain estimates
- S1: bench/runs (2026-10-17T1611Z-426bfe9, 2026-10-17T1752Z-2f5a1c7, 2026-10-17T1859Z-849c856) · Sources: S1
- 8/8

Notes:
- A fourth target, FtsE, is held back: its reference is a homodimer and its values predate a superposition fix.
