---
name: pah-report
description: Write or revise prose about a harness run or batch (methods paragraph, results summary, figure captions, a short report for a reader) from the run's own records. Use when asked to describe, summarise or document harness results in Markdown, for a manuscript, a slide or the web UI.
---

# Writing about harness results

Every number in the prose comes from the run directory. Nothing is estimated, rounded differently
or explained beyond what the records say.

## Inputs, in this order

1. `runs/<id>/ui_record.json` (the record the web UI renders: verdict, layers, checks, stats).
2. `runs/<id>/report.json` (typed report model: findings with measurements and thresholds).
3. `runs/<id>/record.json` and `provenance.json` when a value is missing above.
4. Figures under `runs/<id>/figures/` with their CSV files; renders under `runs/<id>/renders/`.

For a batch, start from `batch_report.json` and open each target's `ui_record.json`.

For a perturbation benchmark run under `bench/runs/<id>/`, the layout differs: benchmark-level
values are in `results/stats.json` (per-arm balanced accuracy with intervals, McNemar, repeat
agreement), `results/truth.csv` (ground truth and the majority verdict per prediction),
`results/decisions.csv` and `facts/<system>_<state>_<executor>.json` (exactly what the agent was
shown). Figures with their CSV files are in `results/figures/`, the design in
`config/targets.yaml`, and every prompt and response in `agent/calls.jsonl`. Each prediction's own
harness run sits at `harness/<system>_<executor>/run/`, with the usual `ui_record.json`,
`record.json` and renders. `truth/` holds the RMSD to the deposited ligand: it is the label, never
something the agent saw, so never present it as evidence the agent used.

## Skills to load

- `scientific-writing` for structure and register (methods before results, one claim per
  sentence, every value with its unit and the threshold it was tested against).
- `humanizer` before finishing any paragraph.
- `scientific-visualization` and `matplotlib` when a new figure is needed; plot from the CSV next
  to an existing figure, never from numbers typed into the prose.
- `markdown-mermaid-writing` for a provenance or pipeline diagram (`graph.mmd` is the source).

## Rules

- State the claim, the verdict and the scope (layers run) first.
- Report each check as value, comparator, threshold and the threshold's origin, as in the report
  tables: `pairwise RMSD median 0.07 Å; clusters at 2.0 Å (specification, layer 5)`.
- Keep site placement and pose accuracy in separate sentences. Keep Boltz-2 affinity on its own
  line, never next to pose confidence. Docking scores rank poses within one run only.
- A skipped check is reported as skipped with its reason. An unknown or not-run check is never
  described as passed.
- Training exposure is context: it narrows what the result shows about generalisation.
- For a benchmark run, lead with the named per-system cases and give the pooled accuracy with its
  interval afterwards; four systems per state do not support a claim of effect. Say which run an
  example comes from by its run id, not by an ordinal such as "the third run".
- No adjectives about quality, no "robust", "promising", "excellent", no em dashes, no bold-label
  lists.

## Check the text

```bash
.venv/bin/pah lint path/to/text.md        # humanizer rules used for generated reports
```

`pah lint` exits 1 and prints each line and rule when the text breaks a rule.
