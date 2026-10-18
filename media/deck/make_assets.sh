#!/usr/bin/env bash
# Rebuild the composite figures in media/deck/assets/ from their source files.
# Run from the repository root. Needs a Python with matplotlib (PY, default: the presentation-skill venv).
set -euo pipefail
PY=${PY:-.claude/skills/presentation-skill/.venv/bin/python}
A=media/deck/assets
RUN3=bench/runs/2026-10-17T1859Z-849c856
CDK2=$RUN3/harness/cdk2_pert_boltz2/run

$PY media/deck/make_layers.py $A/layers.png

TRIM=12 FS=15 WS=0.06 $PY media/deck/make_runfiles.py $A/3ptb_pair.png \
  docs/images/render-3ptb-overview.png "3PTB deposited, benzamidine" \
  docs/images/render-3ptb-vina-seed0.png "Vina seed 0 top pose"

# graph_crop2.png is a cropped raster of $CDK2/graph.svg (crop not scripted)
$PY media/deck/make_runfiles.py $A/runfiles.png \
  $A/graph_crop2.png "graph.svg" \
  $CDK2/figures/posebusters_grid.png "PoseBusters, 3 seeds" \
  $CDK2/figures/interactions.png "Interactions, 3 seeds"

FS=12 $PY media/deck/make_runfiles.py $A/results_pair.png \
  $RUN3/results/figures/balanced_accuracy.png "Balanced accuracy, 95% CI" \
  $RUN3/results/figures/confusion.png "Pooled confusion matrices"

# values from bench/finding/values.csv, run 2026-10-17T1611Z-426bfe9, CDK2 rows
FS=15 $PY media/deck/make_runfiles.py $A/cdk2_pair.png \
  bench/finding/panels/cdk2_wt.png $'Wild type\nipTM 0.975, pocket pLDDT 94.9\n5 of 9 contacts' \
  bench/finding/panels/cdk2_pert.png $'13 pocket residues to glycine\nipTM 0.947, pocket pLDDT 85.0\n1 of 9 contacts'
