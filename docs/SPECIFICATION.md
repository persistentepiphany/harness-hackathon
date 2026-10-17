# Prediction Assurance Harness Specification

Oct 17, 2026 · @Hasard

## Overview

The harness decides, before and after every run, whether a structure prediction or docking result can support the specific claim its user intends to make. It generalises the existing PPI assurance harness from protein–protein screens to all tasks performed with AlphaFold-class co-folding models and with docking engines.

Each task is a declarative specification naming its required inputs, the checks run before and after execution, the controls it needs, and the claim it may support. Checks live in one shared library and are reused across tasks, so a check written once (PoseBusters validity, interaction chemistry, training exposure) serves every task that requires it.

The central principle is that a verdict is scoped to a claim. The same prediction may support "this pose is physically plausible" and fail to support "this ligand binds in this orientation", and the report states which. Every input is traced to its source with version and checksum, every check reports pass, warn or stop with its evidence, and every threshold carries its origin and evidence level.

The architecture rests on a finding reported across several independent evaluations, which is that a model's own confidence does not establish the validity of its output. Ligand pLDDT, ligand pTM and ipTM remained high for poses shown to be physically implausible, and on a prospective set of 489 complexes the best confidence metrics reached only about 75 ROC AUC for identifying poses within 2 Å. Confidence is therefore treated throughout as one input to the verdict rather than as evidence of correctness.

## Architecture

&#91;embedded content: harness architecture · six layers, three outcomes\]

The pre-run layers can refuse a run before any compute is spent, the post-run layers narrow the claim, and calibration sets the thresholds the verdict applies. Each layer is a set of checks from one shared library, so new task classes are added as specifications on the existing harness core rather than as new code.

## Layer 0. Provenance and sources

Every object entering a run is fetched from a named source and recorded with its accession, release, retrieval time and a SHA-256 of the payload, so any result traces back to the exact bytes it was computed from. Fetches go through a content-addressed cache, and a run never falls back silently to the network or to a different release.

| Source | Supplies | Recorded for provenance |
| --- | --- | --- |
| UniProt | Canonical sequences, isoforms, PTMs, active sites, cross-references | Accession, entry and sequence version, release, sequence checksum |
| RCSB PDB, PDBe | Experimental structures, resolution, method, release dates, bound ligands | PDB ID, revision, release date, mmCIF checksum |
| SIFTS | Residue-level mapping between PDB and UniProt numbering | SIFTS release |
| AlphaFold DB | Predicted structures with pLDDT and PAE | Accession, model version, file checksum |
| PDB Chemical Component Dictionary | Ligand definitions and ideal geometry | CCD code, dictionary version |
| PubChem, ChEMBL | Ligand identity, properties, bioactivities | CID or ChEMBL ID, ChEMBL release |
| BindingDB, Binding MOAD, BioLiP2 | Measured affinities, biologically relevant complexes | Release, record identifiers |
| PDBe-KB | Known binding sites aggregated across entries | Release |
| InterPro, Pfam | Domain boundaries | Release |
| MobiDB, DisProt | Disorder annotation | Release |
| STRING, IntAct | Known partners, candidate non-cognate partners | Release, evidence channel |
| MMseqs2 with UniRef30 and ColabFoldDB, or the ColabFold server | Multiple sequence alignments | Database snapshot, server version, query hash |
| PLINDER, PINDER | Similarity-aware complex sets for exposure and calibration | Release |
| DUD-E, DEKOIS 2.0, LIT-PCBA | Decoys and confirmed inactives | Release, set identifier |
| WHO TB mutation catalogue, CARD | Resistance variants for the variant-effect task | Catalogue version |

Two cross-source checks run on every fetch. The UniProt sequence must agree with the PDB SEQRES through the SIFTS mapping, and a ligand supplied as SMILES must match its CCD or PubChem record by InChIKey. A mismatch stops the run, because a silent disagreement between sources is exactly the error that produces confident and wrong results.

## Layer 1. Input integrity

This layer confirms that the run receives exactly what was declared. Its failures are unambiguous, so most of its checks stop the run rather than warn.

| Check | Applies to | Tool | Gate |
| --- | --- | --- | --- |
| Sequence in the run matches the manifest and the source record | Co-folding, docking | Harness `ppi.input.integrity`, generalised | Stop |
| No silent truncation or substitution of residues | Co-folding | Harness `ppi.input.integrity` | Stop |
| MSA belongs to the chain it is paired with, no cache collision | Co-folding | Harness `ppi.msa.integrity` | Stop |
| MSA generation completed and was not replaced by the query alone | Co-folding | Harness `ppi.msa.integrity` | Stop |
| Ligand parses, valences correct, charges sane | Both | RDKit sanitisation | Stop |
| Stereocentres and double-bond geometry explicitly defined | Both | RDKit stereo perception | Warn when undefined |
| Ligand identity matches its database record | Both | InChIKey against CCD or PubChem | Stop |
| Receptor file complete, chains and residue numbering as declared | Docking | Gemmi, SIFTS mapping | Stop |
| Alternate locations resolved deliberately, not by default | Docking | Gemmi, PDBFixer | Warn |
| Chain composition and stoichiometry match the declared assembly | Co-folding | Harness `ppi.context.composition` | Stop |
| Model version, checkpoint and database snapshot recorded and consistent | Both | Harness `ppi.provenance.consistency` | Stop |
| Expected outputs present, no duplicates, no stale files from earlier runs | Both | Harness `ppi.output.reconciliation` | Stop |

The harness rows marked reproduced in the existing catalogue (sequence substitution and alignment cache collision) are the strongest evidence that this layer is needed, since both occurred in a real screen.

## Layer 2. Input adequacy

This layer asks whether a correct input carries enough information for the task. Its checks mostly warn, and the task specification decides which warnings become stops for its claim.

| Check | Applies to | Tool | Typical gate |
| --- | --- | --- | --- |
| Alignment depth, distinct sequence count and Neff/L | Co-folding | Harness `ppi.msa.depth`, Neff from identity clustering with MMseqs2 | Warn when shallow, stop when query only |
| Paired alignment depth for complexes, species pairing validity | Co-folding complexes | Harness `ppi.msa.pairing` | Stop for interaction discovery |
| Paralog ambiguity in pairing | Co-folding complexes | Harness `ppi.msa.pairing` | Warn |
| Gap fraction and redundancy of the alignment | Co-folding | Harness `ppi.msa.depth` | Warn |
| Required cofactors, ions, nucleic acids or third partners present | Both | Harness `ppi.context.requirements`, UniProt cofactor annotation, PDBe-KB | Stop when a required cofactor is absent |
| Disorder in the region of interest | Both | MobiDB, DisProt, AlphaFold DB pLDDT | Warn |
| Pocket residues resolved, no missing loops lining the pocket | Docking | Gemmi, PDBFixer missing-residue report | Stop when the pocket is incomplete |
| Receptor state apo or holo, pocket open | Docking | PDB entry metadata, ligand presence, pocket volume from fpocket | Warn for apo |
| Receptor protonation at the stated pH | Docking | PROPKA, PDB2PQR | Warn when not assigned |
| Ligand protonation and tautomer enumerated at the stated pH | Both | Dimorphite-DL, RDKit tautomer enumeration | Warn when more than one plausible state |
| Ligand conformers generated and minimised | Docking | RDKit ETKDG, Meeko for Vina input | Stop when generation fails |
| Docking box encloses the pocket with margin | Docking | Box derived from a known ligand, P2Rank or fpocket | Stop when the box excludes pocket residues |
| Waters, metals and cofactors retained or removed deliberately | Docking | Rules against the source entry | Warn |

## Layer 3. Applicability

This layer asks whether the chosen tool is operating inside the regime where its accuracy was established. Its main output is the training exposure estimate, which separates a prediction from a likely recall of a training complex.

| Check | Applies to | Tool or source | Typical gate |
| --- | --- | --- | --- |
| Model training cutoff recorded | Co-folding, learned docking | Model registry, harness `ppi.provenance.model_db_config` | Stop when unknown |
| Pocket-level similarity to pre-cutoff complexes, measured as ligand pose SuCOS multiplied by pocket coverage | Co-folding, docking | PLINDER and PINDER precomputed tables, Foldseek | Warn above a similarity of 50 |
| Ligand prevalence, defined as analogues above 0.9 Tanimoto in more than 100 training systems | Co-folding, DiffDock | RDKit topological fingerprints against CCD and BioLiP2 | Warn when prevalent |
| Chain sequence identity to pre-cutoff complexes, reported as a secondary measure only | Co-folding | MMseqs2 against PDB SEQRES filtered by release date | Reported, never used alone |
| Template use distinguished from training exposure | Co-folding | Template hits and their release dates | Warn |
| Token count against the training crop | Co-folding | Model registry, Big mode flag from the accelerated kits | Warn for extrapolation |
| Modality inside the validated set (antibody, disordered motif, membrane, covalent, metal site, lipid) | Both | Harness `ppi.regime.applicability`, UniProt topology, TMbed | Warn or stop by task |
| Endpoint fits the tool (no affinity from interface confidence, no protein–protein affinity from Boltz-2) | Both | Harness `ppi.metric.endpoint`, generalised | Stop |
| Accelerated mode verified against stock on this hardware | Co-folding | Kit `ACTIVE` line, spot check of fast against exact | Warn when unverified |

The similarity measures are chosen deliberately. The conventional leakage thresholds, 40 percent sequence identity and 85 percent Morgan fingerprint similarity, have been shown to miss proteins from the same family and are therefore demoted to secondary reporting in favour of the pocket-level measure.

Exposure is reported as context and not as a predictor of failure. A correct prediction of a complex the model has seen is still correct, and a prospective evaluation on Mac1 found no meaningful correlation between pose accuracy and similarity to training ligands. Exposure accordingly narrows what a result demonstrates about generalisation, and does not by itself reduce confidence in the result, until the harness's own calibration establishes otherwise.

## Layer 4. Output validity

This layer asks whether the result is physically and chemically sensible, independent of how confident the tool was. A pose can pass every geometric test and still place a charged group in a greasy pocket, so geometry and interaction chemistry are checked separately.

### Geometry and physical validity

| Check | Applies to | Tool | Typical gate |
| --- | --- | --- | --- |
| Ligand bond lengths, angles, planarity, ring geometry | Ligand outputs | PoseBusters | Stop on failure |
| Stereochemistry preserved from input to output | Ligand outputs | PoseBusters | Stop on failure |
| Protein–ligand and ligand–cofactor clashes, volume overlap | Ligand outputs | PoseBusters | Stop on failure |
| Ligand placed in contact with the protein, not floating | Ligand outputs | PoseBusters minimum distance | Stop on failure |
| Torsional strain against a knowledge-based torsion library | Ligand outputs | RDKit torsion rules | Warn on unlikely torsions |
| Ligand strain energy against relaxed conformers | Ligand outputs | StrainRelief, deferred where GPU time is scarce | Warn above 16.1 kcal/mol, record non-convergence |
| Protein clashscore, Ramachandran outliers, rotamer outliers, Cβ deviations | All structures | MolProbity through Phenix, or harness `ppi.structure.geometry` and `stereochemistry` where Phenix is absent | Warn, stop on severe |
| Chains topologically entangled | Complexes | Harness `ppi.structure.topology` | Stop |
| Receptor conformational state against known states of that target | All structures | Superposition against PDB entries for the target, PDBe-KB | Warn on a missed state, warn on a state not observed experimentally |
| Pose stability under short restrained minimisation | Ligand outputs | OpenMM with AMBER and OpenFF | Warn when the pose moves beyond 2 Å |

### Interaction chemistry

| Check | Applies to | Tool | Typical gate |
| --- | --- | --- | --- |
| Interaction fingerprint (hydrogen bonds, salt bridges, π stacking, halogen bonds, hydrophobic contacts) | Ligand and protein interfaces | PLIP, ProLIF | Reported, compared below |
| Buried polar atoms with no hydrogen-bond partner | Both | FreeSASA per-atom burial with PLIP hydrogen-bond detection | Warn per unsatisfied atom, stop for buried charges |
| Hydrophobic complementarity (buried nonpolar ligand surface against nonpolar pocket surface) | Ligand outputs | FreeSASA with RDKit atom typing | Warn on mismatch |
| Charged group buried in a hydrophobic environment | Both | FreeSASA, PROPKA | Warn |
| Interface buried area, contacts, salt bridges, solvation proxy | Protein complexes | AlphaJudge, FreeSASA | Warn when small for the claim |
| Shape complementarity | Protein complexes | AlphaJudge shape complementarity | Warn when low |
| Electrostatic complementarity | Protein complexes | PDB2PQR with APBS | Reported |
| Fingerprint similarity to known binders in the same pocket | Ligand outputs | ProLIF fingerprints against PDB complexes from PDBe-KB | Warn when no key interaction is reproduced |

The final row is the most informative chemical check when known binders exist. A predicted pose that reproduces none of the interactions seen in every crystal structure of that pocket is suspect even when it is geometrically perfect.

The conformational state check addresses a documented blind spot. On the Mac1 set AlphaFold3 recovered 4 of 19 twisted backbone states and none of 20 open loop states, while producing 8 confident predictions of states not observed experimentally. The harness cannot supply the correct state, but it can report that the predicted state disagrees with the structural record.

### Physics escalation

Funnel metadynamics is the reference standard for establishing whether a ligand is genuinely bound, and at 1000 ns across three replicates it is not a routine check. The harness therefore runs cheaper approximations by default and escalates only where the claim requires it.

| Tier | Check | Tool | Approximate cost | What it detects |
| --- | --- | --- | --- | --- |
| 1, default | Torsional strain against a knowledge-based library | RDKit | Under a second | Unlikely torsions |
| 2, default | Restrained minimisation and pose drift | OpenMM with AMBER and OpenFF | 5 to 20 seconds | Poses that collapse under a force field |
| 3, on request | Ligand strain energy against relaxed conformers | StrainRelief, a MACE potential trained on DFT | About 44 seconds per molecule on a GPU | Internally strained ligands, to within 1.4 kcal/mol of DFT |
| 4, on request | MM/GBSA or MM/PBSA rescoring of the minimised complex | OpenMM with ambertools, gmx\_MMPBSA | Minutes | Energetically unfavourable poses |
| 4, on request | Interface energetics and per-residue decomposition | Rosetta InterfaceAnalyzer | Minutes | Poor packing, weak interface energy |
| 5, final candidates | Short unrestrained molecular dynamics, 10 to 50 ns, with pose RMSD and contact persistence | OpenMM | Tens of minutes per pose | Poses that drift or lose key contacts |

StrainRelief is limited to neutral molecules in the gas phase and fails to converge for about 10 percent of molecules, so charged ligands and non-convergent cases fall back to the torsion library and the outcome is recorded rather than omitted.

## Layer 5. Output support

This layer asks whether a valid result is corroborated. It covers how confidence metrics are computed and read, how many independent samples were drawn, whether independent methods agree, and whether the controls the claim requires were run and are themselves sound.

### Confidence metrics

| Metric | Produced by | Read as | Checks applied |
| --- | --- | --- | --- |
| pLDDT, restricted to pocket or interface residues | Co-folding models | Local structural confidence | Global value never substituted for local |
| PAE across the interface or pocket | Co-folding models | Relative placement confidence | Interface block used, not the whole matrix |
| ipTM, pTM | Co-folding models | Interface and fold confidence | Partner-length confound, harness `ppi.metric.length_confound` |
| pDockQ, pDockQ2, ipSAE, LIS | AlphaJudge, harness adapters | Interface quality estimates | Implementation against published definition, harness `ppi.metric.definition_integrity`, cross-checked between AlphaJudge and the harness |
| Boltz-2 affinity value and binder probability | Boltz-2 | Relative ranking within a series, never pose quality | Reported on a separate line from pose confidence, since it reached only 53.8 ROC AUC for pose accuracy on Mac1 |
| Vina, Vinardo, Gnina affinity scores | Docking engines | Pose ranking within one run | Never compared across receptors or read as affinity |
| Gnina CNN pose score | Gnina | Pose plausibility | Reported beside, not instead of, PoseBusters |
| DiffDock confidence | DiffDock-L | Pose ranking | Calibrated on the benchmark before any threshold is used |

Confidence thresholds are stored per model and per task in the model registry and are never carried across models. The cut-off separating reliable from unreliable predictions has been reported to differ substantially by method, at approximately 0.75 ipTM for Chai-1 against approximately 0.99 for Protenix, so a single threshold applied across methods misclassifies by construction. Every threshold carries its origin. A cut-off taken from a benchmark on different data is flagged by harness `ppi.metric.threshold_provenance`, as is a threshold calibrated at a different prevalence of true binders than the deployment.

### Sampling and seeds

| Rule | Applies to | Enforced by |
| --- | --- | --- |
| Independent seeds counted separately from diffusion samples and model indices | Co-folding | Harness `ppi.execution.replicate_stability` |
| A duplicated run never presented as an independent replicate | Both | Harness `ppi.execution.replicate_identity` |
| Default of five seeds per co-folding prediction, calibrated per task | Co-folding | Task specification |
| Representative pose reported as the medoid of the largest cluster, never a mean | Both | spyrmsd clustering |
| Cluster populations reported alongside the representative pose | Both | spyrmsd clustering |
| Ensemble spread reported as the distribution of pairwise RMSDs, which sets the noise floor | Both | spyrmsd |
| Pose sampling reported separately from pose ranking | Both | Task specification |
| Site placement reported separately from pose accuracy | Both | Task specification |
| Ranking stability across seeds measured as Kendall tau | Both | Harness `ppi.execution.ranking_stability` |
| A result carried by a single repeat flagged | Both | Harness `ppi.execution.ranking_stability` |
| Docking repeated with independent random seeds at a declared exhaustiveness | Docking | Task specification |
| Benchmark success rates reported with bootstrap confidence intervals | Both | SciPy |

Site placement and pose accuracy are separated because they diverge sharply. On the Mac1 set the ligand was placed in the correct site for 90 to 93 percent of co-folding predictions while only 53 to 70 percent fell within 2 Å RMSD, so a single combined statement would mislead by twenty to forty points.

Sampling failure and ranking failure are likewise distinct. The correct pose may never have been generated, and the top-ranked pose has been reported to be little better than a random sample from the ensemble, so the harness reports whether any sampled pose is plausible separately from whether the ranking selected the best one.

### Agreement between methods

Agreement counts as evidence only when the methods can fail independently, so the verdict weights it by how independent the methods are.

| Comparison | What it shows | Weight |
| --- | --- | --- |
| Seeds of one model | Stability | Low |
| Two co-folding models (Boltz-2 and Protenix) | Robustness to architecture, shared training data | Moderate |
| Co-folding against physics-based docking (Boltz-2 against Gnina, AlphaFold3 against pyDock) | Independent support | High |
| Prediction against an experimental reference | Accuracy | Decisive, when available |

Pose agreement is measured with symmetry-aware ligand RMSD (spyrmsd) and complex agreement with DockQ and interface RMSD.

### Perturbation response

A prediction that does not change when the input is altered in a way that should abolish binding is evidence that the model is not responding to the chemistry. This is the cheapest available probe of whether confidence tracks anything physical, and it is recommended independently by two of the sources below.

| Perturbation | Construction | Expected response |
| --- | --- | --- |
| Contact removal | Side chains within 3.5 Å of the ligand mutated to glycine | Ligand displaced or pose substantially altered |
| Overpacking | The same residues mutated to phenylalanine | Ligand displaced, or clashes reported |
| Chemical inversion | The same residues replaced with chemically dissimilar ones selected by Miyata distance | Ligand displaced |
| Ligand modification | Progressive methylation of hydroxyls, or replacement of a charged group with a neutral or oppositely charged one | Binding weakened or lost |
| Apo control | The mutated receptor predicted without ligand | Fold unchanged, confirming that persistence is not explained by a changed fold |

The apo control is required rather than optional, since without it a persistent pose cannot be distinguished from an unchanged binding site. On the published CASF-2016 analysis, apo predictions of mutated proteins stayed within 1.5 Å Cα RMSD of the holo structures in 95 percent of cases.

The reference rate for interpretation comes from the same analysis. Among predictions with confidence above 80, between 42 and 52 percent retained the original pose under perturbation, against 78 percent without perturbation. A harness implementation reporting rates far from these on the same benchmark should be treated as misconfigured.

### Controls and decoys

Controls are required only where the claim is comparative. A pose claim needs a redocking control and no decoys. A discovery, screening or specificity claim cannot be reported without decoys, and the harness refuses it rather than reporting an unsupported number.

| Control | Required by | Source | Scrutiny applied |
| --- | --- | --- | --- |
| Redocking of a known ligand | Pose prediction, both families | Holo PDB entries for the target | Must reproduce the crystal pose before new poses are trusted |
| Known positive pair or binder | Discovery, affinity ranking | PDB complexes, experimentally supported STRING and IntAct edges, ChEMBL actives | Must score as a positive under the same pipeline |
| Non-cognate decoy partners | Interaction discovery | Proteins from the same proteome, matched for length and composition, with no interaction evidence in STRING or IntAct | Harness panel checks for completeness, duplicates, absent paralogs, changes after results were visible, and testing the wrong null |
| Sticky control | Interaction discovery | A protein known to score highly against many partners | Harness `ppi.controls.specificity`, reproduced failure mode |
| Property-matched ligand decoys | Virtual screening | DUD-E, DEKOIS 2.0, or generated decoys | Property matching checked with RDKit (mass, logP, donors, acceptors, charge), topological dissimilarity to actives confirmed, known DUD-E analogue bias noted |
| Confirmed inactives | Virtual screening, affinity ranking | LIT-PCBA, ChEMBL inactives | Preferred over generated decoys where available |
| Wild type against itself across seeds | Variant effect | Same run settings as the variant | Sets the noise floor the variant must exceed |
| Scrambled or non-cognate designs | Design validation | Generated from the design set | Must fail where the designs pass |

## Task specifications for co-folding tools

Eight task classes cover the uses of AlphaFold-class models. Each row names the layers it draws on most heavily; every task also runs the full integrity layer.

| Task | Primary tools | Required before | Required after | Controls | Permitted claim |
| --- | --- | --- | --- | --- | --- |
| Monomer structure | AlphaFold3, Boltz-2, AlphaFold DB lookup | MSA depth, disorder annotation | Local pLDDT, MolProbity | None | Fold of confident regions |
| Known complex assembly | AlphaFold3, Boltz-2, Protenix | Stoichiometry, cofactors, paired MSA depth, exposure | Interface PAE and ipTM, AlphaJudge descriptors, clashes, topology | Exposure report | Interface geometry, scoped by exposure |
| Interaction discovery | AlphaFold3, with Protenix and pyDock as cross-checks | Paired MSA depth, paralog ambiguity, exposure, regime | Interface confidence with length confound check, interface chemistry, seed stability | Decoy partners, sticky control, known positive | Plausible relative to controls, never that the proteins bind |
| Ligand pose | Boltz-2, Protenix, Chai-1 | Ligand validity and protonation, cofactors, pocket and ligand exposure | PoseBusters, pocket pLDDT and PAE, interaction chemistry, minimisation stability | Redocking of a known ligand | Pose within stated uncertainty |
| Binding site identification | Boltz-2, Protenix, with P2Rank | Disorder, cofactors | Site consistency across seeds and models | Known sites from PDBe-KB | Candidate sites ranked |
| Affinity ranking | Boltz-2 affinity, with physics corroboration | Series in distribution, chemotype exposure | Rank stability across seeds, poses valid under PoseBusters, agreement with MM/GBSA or docking scores | Known actives and inactives from ChEMBL, target-specific recalibration | Relative order within a congeneric series, never absolute affinity |
| Variant effect | Boltz-2, AlphaFold3 | Wild type and variant under identical settings and MSA | Local structural difference against the seed noise floor, pocket chemistry change | Wild type against itself across seeds | Change detected, or not distinguishable from model noise |
| Design validation | AlphaFold3, Boltz-2, Protenix | Designed sequence integrity | Refolding self-consistency, interface confidence, interface chemistry | Scrambled or non-cognate designs | Design is self-consistent, not that it binds |

The variant effect task carries its own control because co-folding models are weakly sensitive to point mutations. Without the wild-type noise floor, a difference between two predictions cannot be distinguished from sampling variation, and it links directly to resistance prediction.

## Task specifications for docking tools

Six task classes cover the docking family, five for small molecules and one for protein–protein docking. Redocking is both a task and the control for the others.

| Task | Primary tools | Required before | Required after | Controls | Permitted claim |
| --- | --- | --- | --- | --- | --- |
| Redocking | AutoDock Vina, Gnina | Holo structure, ligand extracted intact, box from the crystal ligand | Symmetry-aware RMSD to the crystal pose | It is itself the control | The protocol reproduces known poses on this receptor |
| Pose prediction in a known pocket | Gnina, Vina, DiffDock-L | Receptor state, protonation, box definition, waters and metals, ligand preparation | PoseBusters, interaction chemistry, cluster population, fingerprint similarity to known binders | Redocking on the same receptor | Pose within stated uncertainty |
| Blind docking | DiffDock-L, Gnina with P2Rank and fpocket | Pocket detection agreement between methods | Site consistency across runs, PoseBusters | Known site where one exists | Candidate sites, low confidence |
| Virtual screening | Vina or Gnina as primary, Boltz-2 rescoring only where calibration on the target supports it | Library preparation, property filters, protonation states | Score distribution, interaction chemistry of top hits, enrichment | Property-matched decoys or confirmed inactives | Enrichment over decoys, not individual affinities |
| Series scoring | Gnina, Vina | Congeneric series, common scaffold | Pose consistency of the shared scaffold | Known actives from ChEMBL | Weak ranking, explicitly flagged |
| Protein–protein docking | pyDock, HADDOCK | Both structures validated, restraints declared with their source | Cluster population, interface chemistry, AlphaJudge descriptors, DockQ when a reference exists | Non-cognate partner | Candidate arrangements |

Virtual screening does not route to co-folding by default. A prospective comparison across three hit lists gave mixed results, with Boltz-2 reaching 83.8 AUC against DOCK3.7 at 78.8 on one target, 68.1 against 76.5 on another, and AlphaFold3 confidence falling to 46.4 on a third, below random. The pose prediction task is run by both families on the same inputs, which is the comparison the hackathon demonstration rests on, and that comparison is informative because co-folding and docking errors have been found to be only moderately correlated.

## Reporting

Each run produces one report with four parts and a machine-readable run record behind them. The report is generated from the run record, so nothing in it can disagree with what was computed.

| Part | Contents | Tools |
| --- | --- | --- |
| Verdict | The declared claim, the verdict for that claim, and every warning and stop with its reason and evidence level | Harness findings and policy layer |
| Visual analysis | Structure view with pocket or interface confidence coloured, flagged residues and unsatisfied polar atoms marked, overlay of models and seeds, interaction diagram, PAE heatmap | Mol\* embedded viewer, PLIP interaction images, matplotlib |
| Textual analysis | Plain account of each layer's result and what it implies for the claim, written from the findings without new assertions | Template over the run record, optional language model summary constrained to the findings |
| Statistical analysis | Seed spread with intervals, agreement matrix across models, enrichment and ROC against decoys, calibration curve on the benchmark | NumPy, SciPy, scikit-learn, matplotlib |
| Tool outputs | Raw PoseBusters table, AlphaJudge CSV, MolProbity summary, PLIP and ProLIF fingerprints, docking logs, confidence files | Attached unchanged |
| Run record | Source accessions and checksums, tool versions and containers, parameters, seeds, hardware, accelerated mode used | JSON record, reproducible notebook generated with papermill |

The notebook reruns every query and check from the run record, which answers the question of whether any statement in the report was computed rather than asserted.

### Visual inspection

Expert visual judgement detects problems that no encoded check anticipates, so the harness produces the views that make inspection efficient and records the resulting verdict rather than attempting to replace it. Four views carry most of the value, these being a 2D interaction diagram of the kind chemists read directly, a pocket view with the predicted pose superposed on every known ligand in that pocket, an overlay of all seeds and both tool families in one frame, and a flagged view highlighting clashes, unsatisfied polar atoms and strained torsions.

The design follows the active-learning approach taken by Autoparty, in which expert grades on a subset train a model to extend those grades across a larger set. Automated judgement of rendered images by a vision model is not part of the verdict, since no validation of that approach exists and an unevidenced judge would contradict the premise of the system. It can be run as a labelled experiment against the benchmark and reported as agreement with the checks.

### Runtime budget

Timings are estimates for one CPU core on a complex of a few hundred residues, apart from the StrainRelief figure, which is taken from its paper. They are to be measured on the target cluster before being relied upon.

| Layer | Approximate time | Note |
| --- | --- | --- |
| 0, provenance | 2 to 5 seconds | Under a second once cached |
| 1, input integrity | 2 to 3 seconds |  |
| 2, input adequacy | 8 to 12 seconds | Assumes an existing alignment |
| 3, applicability | 2 to 3 seconds | Against precomputed exposure tables |
| 4, output validity | 10 to 25 seconds | Excludes minimisation and MolProbity |
| 5, output support | 3 to 5 seconds | Clustering and statistics |

The default path totals roughly 25 to 50 seconds per prediction, rising to 30 to 70 seconds with restrained minimisation and a further 10 to 30 seconds where MolProbity is available. Alignment generation, live structural searches, StrainRelief, MM/GBSA and short molecular dynamics fall outside this path and are precomputed or requested explicitly. Submitted as a SLURM array, a few hundred predictions complete within a minute of wall time.

## Tool register

The register lists every tool the harness runs or wraps, grouped by role. Databases are listed under Layer 0.

| Tool | Role | Source | In MVP |
| --- | --- | --- | --- |
| AlphaFold3 | Executor, co-folding | Weights by request, non-commercial terms | No |
| Boltz-2 | Executor and affinity, co-folding | github.com/jwohlwend/boltz, weights on Hugging Face | Yes |
| Protenix | Executor, co-folding | github.com/bytedance/Protenix | No |
| Chai-1 | Executor, co-folding | github.com/chaidiscovery/chai-lab | No |
| AutoDock Vina | Executor, docking | github.com/ccsb-scripps/AutoDock-Vina | Yes |
| Gnina | Executor with CNN rescoring, docking | github.com/gnina/gnina | Yes |
| DiffDock-L | Executor, learned docking | github.com/gcorso/DiffDock | No |
| pyDock | Executor, protein–protein docking | Academic licence | No |
| HADDOCK | Executor, protein–protein docking | Academic licence | No |
| MMseqs2 | Alignments, sequence exposure | github.com/soedinglab/MMseqs2 | Precomputed |
| Foldseek | Structural exposure search | github.com/steineggerlab/foldseek | Precomputed |
| RDKit | Ligand parsing, stereo, conformers, fingerprints, torsion strain | github.com/rdkit/rdkit | Yes |
| Dimorphite-DL | Ligand protonation | github.com/durrantlab/dimorphite\_dl | Yes |
| Meeko | Vina preparation | github.com/forlilab/Meeko | Yes |
| PDBFixer | Missing residues and atoms | github.com/openmm/pdbfixer | Yes |
| PROPKA, PDB2PQR | Receptor protonation and charges | github.com/Electrostatics/pdb2pqr | Yes |
| Gemmi | Structure parsing and validation | github.com/project-gemmi/gemmi | Yes |
| P2Rank | Pocket detection | github.com/rdk/p2rank | Yes |
| fpocket | Pocket volume | github.com/Discngine/fpocket | Yes |
| PoseBusters | Ligand physical validity | github.com/maabuu/posebusters | Yes |
| MolProbity | Protein geometry | Distributed with Phenix, academic licence | Only if Phenix is present |
| AlphaJudge | Interface confidence and descriptors | github.com/KosinskiLab/AlphaJudge | Yes |
| PLIP | Interaction fingerprints and diagrams | github.com/pharmai/plip | Yes |
| ProLIF | Fingerprint comparison across poses | github.com/chemosim-lab/ProLIF | Yes |
| FreeSASA | Burial, unsatisfied polars, complementarity | github.com/mittinatten/freesasa | Yes |
| APBS | Electrostatic complementarity | github.com/Electrostatics/apbs | No |
| OpenMM with OpenFF | Minimisation, MM/GBSA, short MD | github.com/openmm | Minimisation only |
| StrainRelief | Quantum-accurate ligand strain | github.com/microsoft/strain-relief, MACE potentials on Hugging Face | No |
| Rosetta InterfaceAnalyzer | Interface energetics | Academic licence | No |
| spyrmsd | Symmetry-aware RMSD and clustering | github.com/RMeli/spyrmsd | Yes |
| DockQ | Complex accuracy against a reference | github.com/bjornwallner/DockQ | Yes |
| PPI Harness core and pack | Integrity, MSA, provenance, replicate, metric, control and claim checks | Private repository | Yes |
| Anthropic optimisation kits | Accelerated co-folding inference | github.com/anthropics/uplifting-biomolecular-modeling | Optional |
| Mol\*, matplotlib, papermill | Report rendering and reproducible notebook | Open source | Yes |
| SLURM with Apptainer | Execution on CSF3 | One container per executor | Yes |

Model weights for Boltz-2, Chai-1 and Protenix, and the MACE potentials underlying StrainRelief, are distributed through Hugging Face. A Hugging Face Space is the most practical host for the demonstration interface, since the checks are CPU-light while predictions are precomputed on CSF3, and a Space provides a shareable link that does not depend on cluster access.

## Hackathon scope

The weekend build implements the engine generically and runs three tasks end to end, chosen so they share checks and produce one direct comparison between tool families.

| Task | Family | Executors | Why it is included |
| --- | --- | --- | --- |
| Ligand pose in a known pocket | Both | Boltz-2 and Gnina on the same inputs | Clear ground truth, exercises PoseBusters and interaction chemistry, shows where the families agree and which one the checks distrust |
| Interaction discovery | Co-folding | AlphaFold3 or Boltz-2 | Reuses the harness checks already reproduced in a real screen, and is where blind reading of confidence misleads most |
| Virtual screening | Docking | Vina or Gnina | Introduces decoys and the enrichment claim |

Everything retained for the minimum build runs in seconds per prediction on CPU, so several hundred process concurrently during the demonstration. Retained are ligand validity and chirality through RDKit, the PoseBusters battery, interaction fingerprints through PLIP and ProLIF including comparison against known binders in the same pocket, burial and complementarity through FreeSASA, torsion-library strain, the harness integrity and provenance checks, pocket-level exposure from precomputed tables, the ensemble statistics, cross-family agreement between Boltz-2 and Gnina, separate site and pose reporting, a precomputed perturbation result, and the calibration figure. Deferred are MolProbity where Phenix is absent, StrainRelief, MM/GBSA, short molecular dynamics, Rosetta energetics, APBS, and anything requiring AlphaFold3 weights. Predictions for the benchmark set are computed on CSF3 before the event, so only the input checks, output checks and report generation run live. The benchmark is a few dozen complexes from Runs N' Poses and PLINDER split by training similarity, and the demonstration ends with one calibration plot showing that predictions the harness flags fail more often against crystal structures than those it passes. The remaining task classes ship as written specifications that the same engine would execute.

## Evaluation design

The harness is evaluated as a decision rule against ground truth, separately from any question about whether an agent can act on its output. Conflating the two places agent variance on top of the effect being measured, which is why the earlier agent experiment was inconclusive.

The primary comparison holds three rules over the same complexes.

1. Confidence threshold alone, which is current practice
2. Harness verdict alone
3. Confidence and harness combined

The primary outcome is precision within the high-confidence band rather than discrimination across the whole distribution. Confidence metrics already reach roughly 75 ROC AUC overall, so a rule competing on the full distribution fights for small margins, whereas the band in which confidence accepts a prediction is where it fails by construction and where the published evidence places the errors.

| Element | Choice | Reason |
| --- | --- | --- |
| Items | 60 to 200 complexes with experimental ground truth | The complex is the unit of analysis, which is what supplies statistical power |
| Design | Paired, every complex through every rule | Removes between-item variance |
| Primary outcome | Precision among confidence-accepted predictions | Targets the stratum where the baseline fails |
| Secondary outcomes | ROC AUC over the full set, calibration | Comparable with published figures |
| Test | McNemar for paired binary decisions, bootstrap intervals throughout | Correct for a paired design |
| Stratification | By exposure and by confidence band | Establishes where the harness helps, not only whether |

The benchmark composition, the targets drawn from published failure cases, and the reasoning that keeps the enrichment honest are recorded separately in the Harness Evaluation Stress Set.

A negative result is informative and is reported as such. Failure to improve on confidence within the high-confidence band would indicate that current confidence metrics already capture what the inexpensive checks capture, directing effort toward exposure and perturbation response, the two signals confidence demonstrably does not carry. The design is to be recorded in the repository before the evaluation is run.

## Limitations

The harness establishes when a result should not be trusted and does not establish that a result is correct. A pose may be wrong while remaining physically valid, chemically sensible and stable across seeds, and on a prospective set of 489 complexes between 30 and 47 percent of poses exceeded 2 Å RMSD, a substantial share of which would pass every check described here. Absence of a detected failure is therefore not evidence of accuracy.

Most failure modes in the existing catalogue are suspected rather than reproduced, so the harness can screen for them without yet showing that each one changes outcomes. The calibration step addresses this only for the tasks it covers, and the remaining tasks stay at the suspected level until benchmarked.

Training exposure can be measured but not resolved. A prediction of a near-duplicate complex may be correct by generalisation or by recall, and no check here distinguishes the two, so the verdict reports the exposure and narrows the claim rather than rejecting the prediction.

Thresholds borrowed from published benchmarks were set on other data and at other prevalences. Until each is recalibrated on the harness benchmark, verdicts that depend on them are reported with the threshold's origin attached.

Several tools carry licence constraints (AlphaFold3 weights, Phenix, pyDock, HADDOCK). Where one is unavailable the harness runs the open substitute named in the register and records the substitution, which may change the sensitivity of the affected check.
