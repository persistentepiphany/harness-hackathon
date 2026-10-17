---
name: pah
description: Run the prediction assurance harness on co-folding or docking inputs and read its verdicts and reports. Use when asked to check, validate or report on a structure prediction or docking run, or on a set of targets.
---

# Prediction assurance harness

The harness decides whether the inputs and outputs of a co-folding or docking run can support a
declared claim. All six layers are implemented: 0 provenance, 1 input integrity, 2 input
adequacy, 3 applicability, 4 output validity, 5 output support. Layers 4 and 5 need a
`predictions:` block in the manifest (executor id and output path; see `examples/3ptb_vina/`).
`pah dock <manifest> --out DIR` docks the ligand with local Vina and writes such a manifest.

## Interfaces

| Interface | Use |
| --- | --- |
| MCP (`pah mcp`, registered in `.mcp.json`) | Tools `pah_run`, `pah_batch`, `pah_doctor`, `pah_list_tasks`, `pah_list_checks`, `pah_get_report`, `pah_get_findings`; resources `pah://runs/{id}/report.md`, `pah://tasks/{id}`, `pah://schemas/{name}` |
| CLI with JSON lines | `pah run <manifest> --format jsonl`, `pah batch <spec> --format jsonl`; one event per line |
| HTTP (`pah serve`) | `POST /runs`, `GET /runs/{id}/events` (SSE), `GET /runs/{id}/report?format=md` |
| MCP agent log tools | `agent_start(goal)`, `agent_step(task_id, kind, text, ms?, data?)`, `agent_finish(task_id, status, label, detail?, runs?, reports?)` |
| CLI agent log | `pah agent-log start --goal ...`, `pah agent-log step <id> --kind ... --text ... [--ms N] [--data JSON]`, `pah agent-log finish <id> --status done --label ... --detail ...` |
| HTTP UI routes (`/ui`) | `GET /ui/jobs`, `GET /ui/jobs/{id}/log` (SSE), `GET /ui/runs/{id}/record`, `POST /ui/runs`, `/ui/agent/tasks/...`; see `docs/INTERFACES.md` |

## Steps

1. Pick a task: `pah_list_tasks` (or `pah tasks`). The task fixes the claim and the checks.
2. Write a manifest. Schema: `pah://schemas/manifest` or `schemas/manifest.json`. Examples in
   `examples/` and `examples/targets/`. Declare engineered substitutions under `mutations` in
   UniProt numbering; undeclared differences stop the run.
3. Run: `pah_run(manifest=...)` or `pah_run(manifest_path=...)`. Progress arrives per finding.
4. Read `verdict`, `stops` and `warnings` from the result. `stop` means the claim is not
   supported by these inputs; `incomplete` means a check could not run.
5. Fetch the report: `pah_get_report(run_id)`. It is factual (values, thresholds with origin,
   provenance). To turn it into prose, use the `pah-report` skill (it loads
   `scientific-writing` and `humanizer`) and check the text with `pah lint`.
6. Several targets: `pah_batch(batch_path="examples/batches/validation.yaml")`, then
   `pah_get_report(batch_id)` for the comparative table and gate matrix.

## Report your own steps

The harness UI has an Agent view that lists tasks and streams their steps. Log what you do so a
person can follow it there:

1. Start a task: `agent_start(goal="...")` over MCP, or `id=$(pah agent-log start --goal "...")`.
2. After each action, add a step: `agent_step(task_id, kind, text, ms, data)` or
   `pah agent-log step "$id" --kind tool --text "..." --ms 900 --data '{"runId": "<id>"}'`.
   `kind` is `thought`, `tool`, `result`, `report` or `conclusion`. `data.progress` (0 to 1) sets
   the task's progress.
3. Put the id of each run you start in `data.runId`: `run_id` from `pah_run`, `runId` from
   `POST /ui/runs`, or the `--out` directory name from `pah run`. The Agent view links the step to
   that run's job and report pages.
4. Finish: `agent_finish(task_id, status="done", label="Completed", detail="...", runs=1)` or
   `pah agent-log finish "$id" --status done --label Completed --detail "..." --runs 1`. Steps sent
   after that are refused.

The MCP server, the CLI and the HTTP routes write the same `runs/agent-<id>/` files, so the three
can append to one task. The step format is in `docs/AGENT_LOG.md`.

## Watch a run in the web UI

Start the API on the same profile that the CLI or MCP server uses, then the web app:

```bash
.venv/bin/pah serve --port 8000
cd web && HARNESS_API_URL=http://127.0.0.1:8000 npm run dev    # http://localhost:3000
```

Runs appear under `/jobs` while they are written (job id = run directory name), with the live log
and the report at `/reports/<id>`; agent tasks appear under `/agent`. A run directory in another
profile's `runs_dir` is not shown. `scripts/e2e_interfaces.sh` checks all of this against a live
server and prints one PASS or FAIL line per step.
