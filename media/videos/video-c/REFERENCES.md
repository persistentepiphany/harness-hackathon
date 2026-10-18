# Film C references

Bibliographic records and the statements used on screen were checked on 2026-10-18 against Europe
PMC (REST API: metadata, abstracts, and for the Mac1 study the full text of bioRxiv version 2,
PMC12776374). Publisher sites, arXiv and bioRxiv could not be reached from the build machine, so
the publisher PDFs were not opened.

## Published studies

1. Buttenschoen M, Morris GM, Deane CM. PoseBusters: AI-based docking methods fail to generate
   physically valid poses or generalise to novel sequences. Chem Sci. 2024;15(9):3130-3139.
   doi:10.1039/d3sc04185a. arXiv:2308.05777. PMC10901501.
   - Supports (scene 1 card and caption): five deep-learning docking methods (DeepDock, DiffDock,
     EquiBind, TankBind, Uni-Mol) compared with AutoDock Vina and CCDC Gold; RMSD to the native pose
     is not sufficient; deep-learning methods often produce physically implausible structures; no
     deep-learning method yet outperforms classical docking on physical plausibility and
     generalisation to examples distinct from the training data.
   - Verified: title, authors, journal, volume, issue, pages, DOI and all four statements against
     the Europe PMC record and abstract. The arXiv identifier is from the task brief and was not
     opened (arxiv.org unreachable).

2. Kim J, Correy GJ, Hall BW, Rachman MM, Mailhot O, Togo T, Gonciarz RL, Jaishankar P, Neitz RJ,
   Hantz ER, Doruk YU, Stevens MGV, Diolaiti ME, Reid R, Gopalkrishnan S, Krogan NJ, Renslo AR,
   Ashworth A, Shoichet BK, Fraser JS. Large-scale prospective evaluation of co-folding across
   hundreds of Mac1-ligand complexes and three virtual screens. eLife. 2026;15:RP110475 (reviewed
   preprint). doi:10.7554/eLife.110475. Preprint: bioRxiv doi:10.64898/2025.12.25.696505
   (version 2 titled "... across 557 Mac1-ligand complexes ..."), PMC12776374.
   - Supports (scene 1 card and caption): 557 Mac1 ligands determined after the models' training
     cutoffs; ROC analysis of poses within 2 Å, best AUC 0.76 for AF3 ligand pLDDT and 0.73 for
     Chai-1 ipTM; AF3 predicted 4 of 19 twisted and 0 of 20 open states correctly and made 8
     false-positive twisted predictions.
   - Verified: statements quoted from the bioRxiv v2 full text (Results, ROC paragraph and
     conformational-state paragraph); eLife DOI, volume and author list from the Europe PMC record
     of PMC13657626 (first published 2026-10-16).
   - Not used: docs/SPECIFICATION.md line 13 gives "489 complexes" and "about 75 ROC AUC", and line 169
     gives "53.8 ROC AUC" for Boltz-2 affinity. Version 2 reports 557 ligands, AUC 0.76 and 0.73, and
     AUC 0.55 for the Boltz-2 pIC50 score. The 489 and 53.8 figures appear to come from version 1,
     which could not be opened, so they are not on screen. The line 13 statement that ligand pLDDT
     and ipTM "remained high for physically implausible poses" was not traced to a source and is not
     on screen; the film shows that pattern only with the harness's own benchmark values.

3. Škrinjar P, Eberhardt J, Studer G, Tauriello G, Schwede T, Durairaj J. Evaluating generalization
   in protein-ligand cofolding methods. Nat Struct Mol Biol. 2026;33(5):782-794.
   doi:10.1038/s41594-026-01797-5. PMID 42103936.
   - Supports (scene 1 card and caption): Runs N' Poses, 2,600 protein-ligand systems released
     after the training cutoff; four co-folding methods largely memorise ligand poses from their
     training data.
   - Verified: metadata and both statements against the Europe PMC record and abstract.

## Project sources (numbers on screen)

| Scene | Values | Source |
| --- | --- | --- |
| Cold open | 12 structures, ipTM, pocket pLDDT, contacts recovered, buried unsatisfied polars, PoseBusters, torsion strain, arm A and arm B verdicts | `bench/runs/*/facts/<sys>_pert_boltz2.json`, `results/decisions.csv`, `results/truth.csv`, medoid seed from `harness/<sys>_pert_boltz2/run/record.json`; listed per image in `media/figures/twelve/README.md` |
| 2 The old way | confidence_score 0.877, ptm 0.932, iptm 0.925, ligand_iptm 0.925, complex_plddt 0.865, complex_iplddt 0.724 | `bench/runs/2026-10-17T1859Z-849c856/predictions/cdk2_pert/boltz2/seed_8/boltz_results_cdk2_pert/predictions/cdk2_pert/confidence_cdk2_pert_model_0.json` |
| 2 The old way | 13 residues cut to glycine; contacts 1 of 9; 4 buried polar atoms unpaired | `prep/cdk2_pert/meta.json`, `facts/cdk2_pert_boltz2.json` (run 3) |
| 3 With the harness | 70 registered checks; check groups and tools | `README.md` (check tables, Tools used), `src/pah/checks/` |
| 3 With the harness | CDK2 verdict stop, 14 pass, 8 warn, 2 stop, 1 incomplete, 1 not applicable; issue messages | `bench/runs/2026-10-17T1859Z-849c856/harness/cdk2_pert_boltz2/run/record.json` |
| Models | tool list, A100 or CPU, output checks only | `README.md` Tools used, live UI tools menu |
| 4 Input and output | run ligand_pose-249098d10007: 7 tools, 164 structures, verdict Refused, issues, medoid sha256, A100 timings, ensemble values, artifacts, thresholds | live UI at https://persistentepiphany--pah-web.us-east.modal.run, captured 2026-10-18 |
| 5 The AI agent result | balanced accuracy 0.50 and 0.75, 95% CI 0.50 to 1.0, McNemar exact p 0.125, 16 predictions, 3 of 6 valid poses rejected | `bench/runs/2026-10-17T1859Z-849c856/results/stats.json`, `report.md` |
| 5 The AI agent result | 12 of 12 vs 0 of 12 perturbed Boltz-2 poses rejected | `results/decisions.csv` of the three runs |
