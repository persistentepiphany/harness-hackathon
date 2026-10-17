# Demo materials: what the harness caught

The claim these materials support: across three targets and three independent runs, the agent
judging on the model's confidence score accepted every sabotaged pose, and the same agent judging
on the harness fact file rejected every one. Nine sabotaged Boltz-2 predictions, 0 caught against
9 caught.

## Files

| File | What it is |
| --- | --- |
| `finding.pptx` | Eight slides, built with the presentation skill, visual review bound to the render hashes |
| `flip.png`, `flip.svg`, `flip.csv` | The result in one figure, and the rows behind it |
| `panels/` | PyMOL renders, one camera per target, protein superposed between states |
| `values.csv` | Every measured value for all 18 predictions (3 targets, 2 states, 3 runs) |
| `outline.json` | The deck source; rebuild with `bench/analysis/finding_deck.py` |
| `qa/`, `qa_bound/` | Automated QA and the strict pass that requires the bound visual review |
| `visual_review_receipt.json` | Hash-bound record of the slide review |

## Structure references

Each panel is the Boltz-2 medoid pose, with the perturbed prediction superposed onto the
wild-type prediction by protein CA so both states share one camera.

| Target | Entry | Chain | Ligand | Sabotage |
| --- | --- | --- | --- | --- |
| CDK2 | 1B38 | A | ATP | 13 pocket contacts cut to glycine |
| MEK1 | 7XLP | A | FZC | 11 pocket contacts cut to glycine |
| glucose dehydrogenase | 2VWH | A | BGC | 3 ring hydroxyls methylated |

Source mmCIF files are in each run's `prep/sources/`, with sha256 recorded in `prep/sources.json`.

## The numbers that matter

Values from run 2026-10-17T1611Z-426bfe9, deposited then sabotaged.

| Target | Ligand ipTM | Pocket pLDDT | PoseBusters | Contacts recovered |
| --- | --- | --- | --- | --- |
| CDK2 | 0.975, 0.947 | 94.9, 85.0 | 19/20, 20/20 | 5 of 9, 1 of 9 |
| MEK1 | 0.988, 0.970 | 96.5, 90.5 | 20/20, 20/20 | 2 of 3, 0 of 3 |
| glucose DH | 0.990, 0.983 | 97.3, 97.7 | 20/20, 19/20 | 4 of 6, 3 of 6 |

Confidence stays high after the pocket is removed, and on glucose dehydrogenase the pocket pLDDT
rises. CDK2 passes more PoseBusters tests sabotaged than deposited. Contact recovery is the
column that moves.

## Rebuilding

```bash
.venv/bin/python bench/analysis/finding_panels.py --run-id <run>
.venv/bin/python bench/analysis/finding_figure.py --out bench/finding --runs <run> <run> <run>
.venv/bin/python bench/analysis/finding_deck.py --runs <run> <run> <run>
# inspect bench/finding/qa/renders, write visual_judgment.json, then
.venv/bin/python bench/analysis/finding_deck.py --runs <run> --review bench/finding/visual_judgment.json
```

## Scope

FtsE (8X61) is left out. Its deposited entry is a homodimer, and the harness superposed a single
predicted chain across both copies, which fit neither and corrupted its pose RMSD and interaction
map. The fix is commit de35af7; FtsE's values are being recomputed and are not part of these
materials. The three targets here were unaffected: their fits are 0.4 to 1.2 Å.

Sabotaged systems are negatives by construction, so that labelling never depended on the
superposition. The harness also rejects some genuine poses, most consistently CDK2 as deposited,
which it rejected in all three runs.
