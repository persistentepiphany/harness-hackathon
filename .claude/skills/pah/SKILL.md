---
name: pah
description: Run the prediction assurance harness on co-folding or docking inputs and read its verdicts and reports. Use when asked to check, validate or report on a structure prediction or docking run, or on a set of targets.
---

# Prediction assurance harness

The harness decides whether inputs (and, from milestone 3, outputs) of a co-folding or docking
run can support a declared claim. Layers 0 (provenance) and 1 (input integrity) are implemented.

## Interfaces

| Interface | Use |
| --- | --- |
| MCP (`pah mcp`, registered in `.mcp.json`) | Tools `pah_run`, `pah_batch`, `pah_doctor`, `pah_list_tasks`, `pah_list_checks`, `pah_get_report`, `pah_get_findings`; resources `pah://runs/{id}/report.md`, `pah://tasks/{id}`, `pah://schemas/{name}` |
| CLI with JSON lines | `pah run <manifest> --format jsonl`, `pah batch <spec> --format jsonl`; one event per line |
| HTTP (`pah serve`) | `POST /runs`, `GET /runs/{id}/events` (SSE), `GET /runs/{id}/report?format=md` |

## Steps

1. Pick a task: `pah_list_tasks` (or `pah tasks`). The task fixes the claim and the checks.
2. Write a manifest. Schema: `pah://schemas/manifest` or `schemas/manifest.json`. Examples in
   `examples/` and `examples/targets/`. Declare engineered substitutions under `mutations` in
   UniProt numbering; undeclared differences stop the run.
3. Run: `pah_run(manifest=...)` or `pah_run(manifest_path=...)`. Progress arrives per finding.
4. Read `verdict`, `stops` and `warnings` from the result. `stop` means the claim is not
   supported by these inputs; `incomplete` means a check could not run.
5. Fetch the report: `pah_get_report(run_id)`. It is factual (values, thresholds with origin,
   provenance). To turn it into prose, apply
   `third_party/skills/claude-scientific-writer/skills/scientific-writing/SKILL.md` and
   `third_party/skills/humanizer/SKILL.md`, adding no claims beyond the report.
6. Several targets: `pah_batch(batch_path="examples/batches/validation.yaml")`, then
   `pah_get_report(batch_id)` for the comparative table and gate matrix.
