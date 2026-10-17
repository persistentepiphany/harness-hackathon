# Agent step log

An agent under test reports what it does as a task with numbered steps. The UI's Agent view lists
the tasks and streams each one's steps live. Every interface writes the same files under the runs
directory: `agent-<id>/task.json` (goal, status, progress, step count, outcome) and
`agent-<id>/steps.jsonl` (one step per line). Writers lock `agent-<id>/.lock`, so the CLI, the HTTP
API and the MCP server can append to one task at the same time.

A step has a `kind` (`thought`, `tool`, `result`, `report` or `conclusion`), a one-line `text`, an
optional duration `ms` and an optional JSON object `data`. A number in `data.progress` (0 to 1) sets
the task's progress. A task ends with `finish`, status `done` or `failed`, and an outcome
`{label, detail, runs?, reports?}`. Steps sent after that are refused.

From bash, `pah agent-log` prints the task id on `start` and the step number on `step`. It uses the
profile's runs directory, or `--runs-dir`:

```bash
id=$(pah agent-log start --goal "Decide whether the 3PTB benzamidine inputs support a pose claim")
pah agent-log step "$id" --kind thought --text "Ligand pose task; layers 0 and 1 run as checks"
pah agent-log step "$id" --kind tool --text "pah run examples/3ptb_ligand_pose/manifest.yaml" --ms 4100
pah agent-log step "$id" --kind report --text "pass_with_warnings; l1.ligand.stereo_defined warns" \
  --data '{"progress": 0.8}'
pah agent-log finish "$id" --status done --label Completed --detail "1 run, verdict pass_with_warnings" --runs 1
```

Over HTTP the same sequence is `POST /ui/agent/tasks` with `{"goal": ...}` (201, returns the task
with its `id`), `POST /ui/agent/tasks/{id}/steps` with `{"kind", "text", "ms", "data"}` (201,
returns the step with `seq` and `ts`), and `POST /ui/agent/tasks/{id}/finish` with
`{"status": "done", "outcome": {...}}`. `GET /ui/agent/tasks/{id}/steps` is a server-sent event
stream (`event: step`, `id: <seq>`, then `event: end` once the task has finished);
`?format=json` returns the list, and `Last-Event-ID` resumes after a step.

An agent that drives the harness over MCP (`pah mcp`) has the tools `agent_start`, `agent_step` and
`agent_finish` with the same arguments. Runs the agent starts with `pah run`, `pah_run` or
`POST /ui/runs` appear in the Jobs view on their own; a run id in a step's `data` records which
run the step refers to.
