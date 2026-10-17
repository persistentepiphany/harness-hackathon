# Interfaces

The harness is driven from the command line, over HTTP (`pah serve`), over MCP (`pah mcp`) and,
for an agent's own step log, with `pah agent-log`. Every interface writes the same directories
under the profile's `runs_dir`, and the web UI reads only those directories through the `/ui`
routes. A run or an agent task therefore shows up in the UI whichever interface started it, as
long as the API and the writer use the same profile. Shapes are in [UI.md](UI.md), the step
format in [AGENT_LOG.md](AGENT_LOG.md).

## Command line

| Command | Writes | Shown in the UI as |
| --- | --- | --- |
| `pah run <manifest> [--format jsonl] [--out DIR]` | `runs/<id>/`: events, findings, record, report, renders, graph | Job card, live log, report |
| `pah batch <spec>` | `runs/batch-<id>/` with one run directory per target inside it | Not listed; read the batch report |
| `pah agent-log start\|step\|finish\|show` | `runs/agent-<id>/task.json`, `steps.jsonl` | Agent task with its steps |
| `pah serve`, `pah mcp` | Start the other two interfaces | |

`--format jsonl` prints one event per line on stdout while the same events go to
`events.jsonl`. The job id in the UI is the run directory name, so `--out runs/cli-1` gives job
`cli-1`; the harness run id stays in the record (`harnessRunId`).

## HTTP API

`pah serve --port 8000` serves the native routes and the `/ui` routes on one app and one job
store. Native: `POST /runs` (`manifest` or `manifest_path`), `GET /runs/{id}`,
`GET /runs/{id}/events` (raw events as SSE), `/report`, `/findings`, `/files/{rel}`,
`POST /batches`, `/tasks`, `/checks`, `/schemas/{name}`, `/health`. UI: `GET /ui/jobs`,
`/ui/jobs/{id}`, `/ui/jobs/{id}/log` (SSE `event: line` frames, then `event: end`;
`?format=json` for a list), `/ui/runs/{id}/record`, `POST /ui/runs` with `RunSettings` or
`{"manifest": "examples/.../manifest.yaml"}`, `POST /ui/interpret`, `GET /ui/entities`,
`/ui/catalog`, `/ui/tools`, `/ui/tasks`, `/ui/examples`, `POST /ui/uploads`, and the agent routes
`GET` and `POST /ui/agent/tasks`, `POST /ui/agent/tasks/{id}/steps`, `POST .../finish`,
`GET .../steps` (SSE `event: step` frames, then `event: end`). Manifest paths are resolved on the
server.

## MCP server

`pah mcp` speaks stdio and is registered in `.mcp.json`; `pah mcp --http --port 8766` serves
streamable HTTP. Tools: `pah_run`, `pah_batch`, `pah_doctor`, `pah_list_tasks`,
`pah_list_checks`, `pah_get_report`, `pah_get_findings`, `agent_start(goal)`,
`agent_step(task_id, kind, text, ms?, data?)` and
`agent_finish(task_id, status, label, detail?, runs?, reports?)`. Resources:
`pah://runs/{id}/report.md`, `pah://runs/{id}/record.json`, `pah://tasks/{id}`,
`pah://schemas/{name}`. `pah_run` sends one progress notification per finding and returns the
summary with `run_id`.

## In the web UI

| On disk | Read through | Page |
| --- | --- | --- |
| `runs/<id>/events.jsonl` and the files next to it | `/ui/jobs`, `/ui/jobs/{id}/log`, `/ui/runs/{id}/record` | `/jobs`, `/jobs/<id>`, `/reports/<id>`, `/documents/<id>` |
| `runs/agent-<id>/` | `/ui/agent/tasks`, `/ui/agent/tasks/{id}/steps` | `/agent` |

`/ui/jobs` lists top-level run directories and leaves out `agent-*`, `batch-*`, `doctor-*`,
`fetch-*` and `uploads`. A step whose `data` holds `runId`, `runIds`, `jobId` or `jobIds` links to
`/jobs/<id>` and `/reports/<id>`. That id is the job id: `run_id` from `pah_run` and
`POST /runs`, `runId` from `POST /ui/runs`, the `--out` directory name from `pah run`.

To watch: `pah serve --port 8000`, then `cd web && HARNESS_API_URL=http://127.0.0.1:8000 npm run dev`
and open `http://localhost:3000/jobs` or `/agent`. Runs and steps appear while they are written.

## End-to-end checks

`tests/test_e2e_interfaces.py` drives each interface offline and reads the result back through
the `/ui` routes. `scripts/e2e_interfaces.sh` does the same against a live `pah serve` (port
8120), or with `--base-url` against a deployed API, printing one PASS, FAIL or SKIP line per step.
