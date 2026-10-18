#!/usr/bin/env bash
# End to end through every interface against a live API: the CLI (`pah run`, `pah agent-log`),
# HTTP (native `POST /runs` and the /ui routes), and MCP over stdio (`pah mcp`). Each result is
# read back through the /ui routes the web UI renders from (jobs, log stream, record, agent tasks).
#
#   scripts/e2e_interfaces.sh                     # starts `pah serve` on 127.0.0.1:8120
#   scripts/e2e_interfaces.sh --port 8130 --profile local
#   scripts/e2e_interfaces.sh --base-url https://persistentepiphany--pah-api.us-east.modal.run
#
# Options:
#   --port N         port for the local `pah serve` (default 8120)
#   --profile P      profile name or YAML path for serve, CLI and MCP. Default: a temporary
#                    profile with its own runs directory and the repository's content cache
#   --offline        temporary profile reads the cache only
#   --base-url URL   use a deployed API; no server is started. The CLI, MCP and agent-log steps
#                    write a local runs directory that this API does not read, so they are
#                    skipped; the API gets read-only calls and one layer 0-1 run
#   --full           with --base-url, also the native and settings runs and one agent task
#   --quiet          no streamed lines, only the PASS, FAIL and SKIP lines
#   --keep           keep the work directory (logs, responses, temporary runs)
#
# Prints one PASS, FAIL or SKIP line per step. Exit 0 when nothing failed, 1 when a step failed,
# 2 for a usage error or a server that did not start.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAH="${PAH:-$ROOT/.venv/bin/pah}"
PY="${PY:-$ROOT/.venv/bin/python}"
PORT=8120
BASE_URL=""
PROFILE=""
OFFLINE=false
FULL=0
QUIET=0
KEEP=0
HTTP_TIMEOUT=60
RUN_TIMEOUT=600
MANIFEST_REL="examples/3ptb_ligand_pose/manifest.yaml"

usage() { sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while (($#)); do
  case "$1" in
    --port) PORT="${2:?--port needs a value}"; shift 2 ;;
    --profile) PROFILE="${2:?--profile needs a value}"; shift 2 ;;
    --offline) OFFLINE=true; shift ;;
    --base-url) BASE_URL="${2:?--base-url needs a value}"; shift 2 ;;
    --full) FULL=1; shift ;;
    --quiet) QUIET=1; shift ;;
    --keep) KEEP=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

REMOTE=0
if [[ -n "$BASE_URL" ]]; then
  REMOTE=1
  BASE="${BASE_URL%/}"
else
  BASE="http://127.0.0.1:$PORT"
fi
[[ -x "$PY" ]] || { echo "python not found at $PY (set PY)" >&2; exit 2; }
[[ $REMOTE == 1 || -x "$PAH" ]] || { echo "pah not found at $PAH (set PAH)" >&2; exit 2; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/pah-e2e.XXXXXX")"
H="$WORK/helper.py"
SERVER_PID=""
PASSES=0
FAILS=0
SKIPS=0

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null
    wait "$SERVER_PID" 2>/dev/null
  fi
  if [[ $KEEP == 1 ]]; then echo "work directory kept: $WORK"; else rm -rf "$WORK"; fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

line() { printf '%-4s  %-34s  %s\n' "$1" "$2" "$3"; }
pass() { PASSES=$((PASSES + 1)); line PASS "$1" "$2"; }
fail() { FAILS=$((FAILS + 1)); line FAIL "$1" "$2"; }
skip() { SKIPS=$((SKIPS + 1)); line SKIP "$1" "$2"; }
info() { [[ $QUIET == 1 ]] || printf '      %s\n' "$*"; }

cat >"$H" <<'PYHELPER'
"""Helpers for e2e_interfaces.sh: JSON checks, SSE parsing, stream printers, MCP stdio client."""
import asyncio
import json
import os
import sys

OUTCOMES = {"pass": "supported", "pass_with_warnings": "narrowed", "stop": "refused",
            "incomplete": "incomplete"}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def check(path, expr, detail=""):
    """Exit 0 when EXPR is true for d = the JSON in PATH; prints DETAIL (or the reason)."""
    try:
        d = load(path)
    except (OSError, ValueError) as exc:
        text = open(path, encoding="utf-8", errors="replace").read(300) if os.path.exists(path) else ""
        print(f"not JSON ({exc}): {text!r}")
        return 1
    scope = {"d": d, "env": os.environ, "OUTCOMES": OUTCOMES, "len": len, "set": set}
    try:
        ok = bool(eval(expr, scope))
    except Exception as exc:
        ok = False
        print(f"{type(exc).__name__}: {exc}; ", end="")
    try:
        print(eval(detail, scope) if detail else "")
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}")
    return 0 if ok else 1


def val(path, expr):
    try:
        print(eval(expr, {"d": load(path), "env": os.environ, "OUTCOMES": OUTCOMES}))
    except Exception:
        return 1
    return 0


def frames(text):
    out, event, ident = [], "message", None
    for raw in text.splitlines():
        if raw.startswith("event:"):
            event = raw[6:].strip()
        elif raw.startswith("id:"):
            ident = raw[3:].strip()
        elif raw.startswith("data:"):
            try:
                data = json.loads(raw[5:].strip())
            except ValueError:
                data = raw[5:].strip()
            out.append({"event": event, "id": ident, "data": data})
            event, ident = "message", None
    return out


def sse_json(src, dst):
    with open(src, encoding="utf-8", errors="replace") as fh:
        rows = frames(fh.read())
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return 0


def print_sse():
    """Prints `line` and `step` frames from an SSE stream on stdin as they arrive."""
    event = "message"
    for raw in sys.stdin:
        raw = raw.rstrip("\n")
        if raw.startswith("event:"):
            event = raw[6:].strip()
        elif raw.startswith("data:"):
            try:
                data = json.loads(raw[5:].strip())
            except ValueError:
                continue
            if event == "line":
                print(f"      {data.get('seq', ''):>4} {data.get('text', '')[:110]}", flush=True)
            elif event == "step":
                print(f"      step {data.get('seq')} {data.get('kind')}: {data.get('text')}",
                      flush=True)
            elif event == "end":
                print(f"      end {json.dumps(data)[:110]}", flush=True)
    return 0


def print_jsonl():
    """Prints events from `pah run --format jsonl` on stdin as they arrive."""
    for raw in sys.stdin:
        try:
            e = json.loads(raw)
        except ValueError:
            print(f"      {raw.rstrip()[:120]}", flush=True)
            continue
        print(f"      {e.get('seq', ''):>4} {e.get('kind', ''):<11} {e.get('stage', ''):<7}"
              f" {str(e.get('message', ''))[:90]}", flush=True)
    return 0


def payload(result):
    if result.is_error:
        raise RuntimeError(f"tool error: {result.content}")
    data = result.structured_content
    if data is None:
        return json.loads(result.content[0].text)
    return data["result"] if isinstance(data, dict) and set(data) == {"result"} else data


def mcp(pah, profile, manifest, out, quiet):
    """One stdio session with `pah mcp`: pah_run, then agent_start/step/finish."""
    from mcp.client.client import Client
    from mcp.client.stdio import StdioServerParameters

    progress = []

    async def on_progress(p, total, message):
        progress.append(message)
        if quiet != "1":
            print(f"      progress {int(p)}/{int(total) if total else '?'} {message}"[:130],
                  flush=True)

    async def session():
        params = StdioServerParameters(command=pah, args=["mcp", "--profile", profile],
                                       cwd=os.getcwd())
        async with Client(params) as client:
            tools = sorted(t.name for t in (await client.list_tools()).tools)
            run = payload(await client.call_tool("pah_run", {"manifest_path": manifest},
                                                 progress_callback=on_progress))
            task = payload(await client.call_tool(
                "agent_start", {"goal": "e2e: MCP agent runs the 3PTB pose checks"}))
            ref = {"task_id": task["id"], "data": {"runId": run["run_id"]}}
            s1 = payload(await client.call_tool(
                "agent_step", {**ref, "kind": "tool", "text": f"pah_run {manifest}", "ms": 0}))
            s2 = payload(await client.call_tool(
                "agent_step", {**ref, "kind": "report", "text": f"verdict {run['verdict']}"}))
            done = payload(await client.call_tool(
                "agent_finish", {"task_id": task["id"], "status": "done", "label": "Completed",
                                 "detail": f"1 run, verdict {run['verdict']}", "runs": 1}))
            return {"tools": tools, "run": run, "task": task, "steps": [s1, s2], "done": done,
                    "progress": len(progress)}

    try:
        result = asyncio.run(asyncio.wait_for(session(), timeout=600))
    except BaseException as exc:  # reported by the caller as a FAIL line
        result = {"error": f"{type(exc).__name__}: {exc}"}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    fn = {"check": check, "val": val, "sse-json": sse_json, "print-sse": print_sse,
          "print-jsonl": print_jsonl, "mcp": mcp}[cmd]
    sys.exit(fn(*args))
PYHELPER

# ---------------------------------------------------------------- helpers

# req METHOD PATH OUTFILE [JSON] -> prints the HTTP status code (000 when unreachable)
req() {
  local method=$1 path=$2 out=$3 body=${4:-}
  local args=(-sS -o "$out" -w '%{http_code}' --max-time "$HTTP_TIMEOUT" -X "$method")
  [[ -n "$body" ]] && args+=(-H 'Content-Type: application/json' --data "$body")
  curl "${args[@]}" "$BASE$path" 2>>"$WORK/curl.err"
  return 0
}

# expect NAME FILE EXPR [DETAIL]: PASS or FAIL from a Python expression over d = JSON in FILE
expect() {
  local name=$1 file=$2 expr=$3 detail=${4:-}
  local out
  if out=$("$PY" "$H" check "$file" "$expr" "$detail" 2>&1); then pass "$name" "$out"
  else fail "$name" "$out"; fi
}

jval() { "$PY" "$H" val "$1" "$2" 2>/dev/null; }

# get NAME PATH EXPR [DETAIL]: GET, then expect 200 and EXPR
get() {
  local name=$1 path=$2 expr=$3 detail=${4:-}
  local out="$WORK/resp-$RANDOM.json" code
  code=$(req GET "$path" "$out")
  if [[ "$code" != 200 ]]; then fail "$name" "GET $path -> HTTP $code $(head -c 200 "$out" 2>/dev/null)"; return; fi
  expect "$name" "$out" "$expr" "$detail"
}

# stream_log ID FILE: the /ui log stream of a run, printed live and saved; ends at event: end
stream_log() {
  local id=$1 file=$2
  if [[ $QUIET == 1 ]]; then
    curl -sSN --max-time "$RUN_TIMEOUT" "$BASE/ui/jobs/$id/log" >"$file" 2>>"$WORK/curl.err"
  else
    curl -sSN --max-time "$RUN_TIMEOUT" "$BASE/ui/jobs/$id/log" 2>>"$WORK/curl.err" \
      | tee "$file" | "$PY" "$H" print-sse
  fi
  "$PY" "$H" sse-json "$file" "$file.json"
}

# wait_run ID: polls the server's JobStore (GET /runs/ID) until the job is no longer running
wait_run() {
  local id=$1 deadline=$((SECONDS + RUN_TIMEOUT)) code status
  while ((SECONDS < deadline)); do
    code=$(req GET "/runs/$id" "$WORK/wait.json")
    status=$(jval "$WORK/wait.json" 'd.get("status")')
    if [[ "$code" == 200 && -n "$status" && "$status" != running ]]; then
      echo "$status"
      return 0
    fi
    sleep 1
  done
  echo "timeout"
  return 1
}

# ui_run LABEL ID [LOGFILE]: the run as the web UI shows it (job card, log, record, SSE)
ui_run() {
  local label=$1 id=$2 sse=${3:-}
  export E2E_ID="$id"
  get "ui jobs: $label" "/ui/jobs" \
    'any(j["id"] == env["E2E_ID"] and j["status"] == "done" for j in d)' \
    '["%s %s verdict=%s layers=%s" % (j["id"], j["status"], j["verdict"], [c["result"] for c in j["layers"]]) for j in d if j["id"] == env["E2E_ID"]][0]'
  get "ui log json: $label" "/ui/jobs/$id/log?format=json" \
    'len(d) > 0 and [x["seq"] for x in d] == sorted(x["seq"] for x in d)' \
    '"%d log lines, kinds %s" % (len(d), sorted(set(x["kind"] for x in d)))'
  local logn
  logn=$(curl -sS --max-time "$HTTP_TIMEOUT" "$BASE/ui/jobs/$id/log?format=json" 2>/dev/null \
    | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)))' 2>/dev/null)
  export E2E_LOGN="${logn:-0}"
  get "ui record: $label" "/ui/runs/$id/record" \
    'd["id"] == env["E2E_ID"] and d["verdict"]["outcome"] in OUTCOMES.values() and len(d["layers"]) == 6' \
    '"outcome=%s stops=%s warnings=%s renders=%d" % (d["verdict"]["outcome"], d["verdict"]["stops"], d["verdict"]["warnings"], len(d.get("renders") or []))'
  if [[ -n "$sse" ]]; then
    expect "ui log sse: $label" "$sse.json" \
      '[f["event"] for f in d][-1] == "end" and d[-1]["data"]["reason"] == "run_end" and sum(f["event"] == "line" for f in d) == int(env["E2E_LOGN"])' \
      '"%d event: line frames, then event: end %s" % (sum(f["event"] == "line" for f in d), d[-1]["data"])'
  fi
}

# raw_matches_ui LABEL ID: record.json verdict (local runs directory) against the UI outcome
raw_matches_ui() {
  local label=$1 id=$2 raw
  raw=$(jval "$RUNS_DIR/$id/record.json" 'd["verdict"]["outcome"]')
  export E2E_RAW="$raw" E2E_ID="$id"
  get "ui verdict mapping: $label" "/ui/runs/$id/record" \
    'd["verdict"]["outcome"] == OUTCOMES[env["E2E_RAW"]]' \
    '"record.json %s -> UI %s" % (env["E2E_RAW"], d["verdict"]["outcome"])'
}

# http_run LABEL PATH JSON: POST a run, stream its log live, wait, check it in the UI
http_run() {
  local label=$1 path=$2 body=$3
  local out="$WORK/post-$RANDOM.json" code id
  LAST_RUN=""
  code=$(req POST "$path" "$out" "$body")
  id=$(jval "$out" 'd.get("runId") or d.get("id")')
  if [[ "$code" != 202 || -z "$id" ]]; then
    fail "http $label" "POST $path -> HTTP $code $(head -c 300 "$out")"
    return 1
  fi
  pass "http $label" "POST $path -> 202 run $id"
  info "streaming /ui/jobs/$id/log"
  stream_log "$id" "$WORK/sse-$id"
  local status
  status=$(wait_run "$id")
  if [[ "$status" == done ]]; then pass "http wait: $label" "GET /runs/$id status=done"
  else fail "http wait: $label" "GET /runs/$id status=$status $(head -c 200 "$WORK/wait.json")"; fi
  ui_run "$label" "$id" "$WORK/sse-$id"
  LAST_RUN="$id"
}

# agent_ui LABEL TASK_ID STEPS RUN_ID: the agent task as the Agent view shows it
agent_ui() {
  local label=$1 tid=$2 n=$3 run=$4
  export E2E_TID="$tid" E2E_N="$n" E2E_RUN="$run"
  get "ui agent tasks: $label" "/ui/agent/tasks" \
    'any(t["id"] == env["E2E_TID"] and t["status"] == "done" and t["steps"] == int(env["E2E_N"]) for t in d)' \
    '["%s %s steps=%s progress=%s outcome=%s" % (t["id"], t["status"], t["steps"], t["progress"], t["outcome"]) for t in d if t["id"] == env["E2E_TID"]][0]'
  get "ui agent steps: $label" "/ui/agent/tasks/$tid/steps?format=json" \
    'len(d) == int(env["E2E_N"]) and env["E2E_RUN"] in [(s.get("data") or {}).get("runId") for s in d]' \
    '"%s data.runId=%s" % ([(s["seq"], s["kind"]) for s in d], env["E2E_RUN"])'
  local sse="$WORK/agent-$tid"
  if [[ $QUIET == 1 ]]; then
    curl -sSN --max-time "$HTTP_TIMEOUT" "$BASE/ui/agent/tasks/$tid/steps" >"$sse" 2>>"$WORK/curl.err"
  else
    curl -sSN --max-time "$HTTP_TIMEOUT" "$BASE/ui/agent/tasks/$tid/steps" 2>>"$WORK/curl.err" \
      | tee "$sse" | "$PY" "$H" print-sse
  fi
  "$PY" "$H" sse-json "$sse" "$sse.json"
  expect "ui agent sse: $label" "$sse.json" \
    '[f["event"] for f in d] == ["step"] * int(env["E2E_N"]) + ["end"] and d[-1]["data"]["status"] == "done"' \
    '"%s event: step frames, then event: end status=%s" % (env["E2E_N"], d[-1]["data"]["status"])'
}

# http_agent LABEL RUN_ID: an agent task written over HTTP
http_agent() {
  local label=$1 run=$2 out="$WORK/agent-http.json" code tid
  code=$(req POST "/ui/agent/tasks" "$out" '{"goal": "e2e: HTTP agent reports on one run"}')
  tid=$(jval "$out" 'd["id"]')
  if [[ "$code" != 201 || -z "$tid" ]]; then fail "http agent start" "HTTP $code $(head -c 200 "$out")"; return; fi
  local c1 c2 c3
  c1=$(req POST "/ui/agent/tasks/$tid/steps" "$WORK/s1.json" \
    "{\"kind\": \"tool\", \"text\": \"POST /ui/runs\", \"ms\": 0, \"data\": {\"runId\": \"$run\", \"progress\": 0.5}}")
  c2=$(req POST "/ui/agent/tasks/$tid/steps" "$WORK/s2.json" \
    "{\"kind\": \"conclusion\", \"text\": \"run $run read back\", \"data\": {\"runId\": \"$run\"}}")
  c3=$(req POST "/ui/agent/tasks/$tid/finish" "$WORK/s3.json" \
    '{"status": "done", "outcome": {"label": "Completed", "detail": "1 run read back", "runs": 1}}')
  if [[ "$c1 $c2 $c3" == "201 201 200" ]]; then pass "http agent task" "task $tid: start 201, steps 201 201, finish 200"
  else fail "http agent task" "task $tid: steps $c1 $c2, finish $c3"; fi
  agent_ui "$label" "$tid" 2 "$run"
}

# ---------------------------------------------------------------- server

echo "pah e2e interfaces: $BASE ($( ((REMOTE)) && echo deployed || echo local))"
LAST_RUN=""

if ((REMOTE == 0)); then
  if [[ -z "$PROFILE" ]]; then
    PROFILE="$WORK/e2e.yaml"
    cat >"$PROFILE" <<YAML
name: e2e
backend: local
cache_dir: $ROOT/cache
runs_dir: $WORK/runs
offline: $OFFLINE
tools_dir: $ROOT/.tools
conda_prefix: $ROOT/.tools/conda-env
YAML
  fi
  RUNS_DIR=$(cd "$ROOT" && "$PY" -c 'import sys
from pah.config import load_profile, resolve_path
print(resolve_path(load_profile(sys.argv[1]).runs_dir))' "$PROFILE" 2>"$WORK/profile.err")
  if [[ -z "$RUNS_DIR" ]]; then
    fail "profile" "$(tail -n 3 "$WORK/profile.err")"
    exit 2
  fi
  mkdir -p "$RUNS_DIR"
  if curl -s --max-time 2 -o /dev/null "$BASE/health"; then
    fail "serve" "port $PORT is already in use; pass --port or --base-url"
    exit 2
  fi
  (cd "$ROOT" && exec "$PAH" serve --profile "$PROFILE" --port "$PORT") >"$WORK/serve.log" 2>&1 &
  SERVER_PID=$!
  started=0
  for _ in $(seq 1 120); do
    if curl -sf --max-time 2 -o /dev/null "$BASE/health"; then started=1; break; fi
    kill -0 "$SERVER_PID" 2>/dev/null || break
    sleep 0.5
  done
  if ((started == 0)); then
    fail "serve" "pah serve did not answer on $BASE: $(tail -n 5 "$WORK/serve.log")"
    exit 2
  fi
  pass "serve" "pah serve --profile $(basename "$PROFILE") --port $PORT (pid $SERVER_PID), runs in $RUNS_DIR"
fi

# ---------------------------------------------------------------- read-only routes

get "http health" "/health" 'd["status"] == "ok"' '"version %s, profile %s" % (d["version"], d["profile"])'
get "http ui tools" "/ui/tools" 'len(d) > 0' '"%d tools: %s" % (len(d), [t["id"] for t in d][:6])'
get "http ui tasks" "/ui/tasks" 'len(d) > 0' '"%d tasks: %s" % (len(d), [t["id"] for t in d][:6])'
get "http ui examples" "/ui/examples" \
  'any(e.get("path") == "examples/3ptb_ligand_pose/manifest.yaml" for e in d)' '"%d examples" % len(d)'
get "http ui jobs" "/ui/jobs" 'isinstance(d, list) and not any(j["id"].startswith("agent-") for j in d)' \
  '"%d jobs, no agent-* entries" % len(d)'
get "http ui agent tasks" "/ui/agent/tasks" 'isinstance(d, list)' '"%d agent tasks" % len(d)'

NATIVE_ID="" CLI_ID="" MCP_RUN=""
LOCAL_ONLY="pah writes to the local runs directory, which the deployed API does not read"
ONE_RUN="a deployed API gets one run here; pass --full for this step"

# ---------------------------------------------------------------- 1. CLI
if ((REMOTE)); then
  skip "cli pah run" "$LOCAL_ONLY"
else
  CLI_ID="cli-$(date +%Y%m%d%H%M%S)-$$"
  info "pah run $MANIFEST_REL --format jsonl --out $RUNS_DIR/$CLI_ID"
  if [[ $QUIET == 1 ]]; then
    (cd "$ROOT" && "$PAH" run "$MANIFEST_REL" --profile "$PROFILE" --format jsonl \
      --out "$RUNS_DIR/$CLI_ID") >"$WORK/cli.jsonl" 2>"$WORK/cli.err"
    rc=$?
  else
    (cd "$ROOT" && "$PAH" run "$MANIFEST_REL" --profile "$PROFILE" --format jsonl \
      --out "$RUNS_DIR/$CLI_ID") 2>"$WORK/cli.err" | tee "$WORK/cli.jsonl" | "$PY" "$H" print-jsonl
    rc=${PIPESTATUS[0]}
  fi
  "$PY" -c 'import json,sys; print(json.dumps([json.loads(l) for l in open(sys.argv[1]) if l.strip()]))' \
    "$WORK/cli.jsonl" >"$WORK/cli.json" 2>/dev/null
  if [[ $rc == 0 ]]; then
    expect "cli pah run" "$WORK/cli.json" '[e["kind"] for e in d].count("run_end") == 1' \
      '"exit 0, %d events, %d findings, verdict %s" % (len(d), [e["kind"] for e in d].count("finding"), [e for e in d if e["kind"] == "run_end"][0]["data"]["verdict"]["outcome"])'
  else
    fail "cli pah run" "exit $rc: $(tail -n 3 "$WORK/cli.err")"
  fi
  ui_run "cli run" "$CLI_ID"
  export E2E_EVENTS
  E2E_EVENTS=$(jval "$WORK/cli.json" 'len(d)')
  get "ui log = cli stream: cli run" "/ui/jobs/$CLI_ID/log?format=json" \
    'len(d) == int(env["E2E_EVENTS"])' '"%d log lines for %s streamed events" % (len(d), env["E2E_EVENTS"])'
  raw_matches_ui "cli run" "$CLI_ID"
fi

# ---------------------------------------------------------------- 2. HTTP
# Manifest paths are resolved on the server: relative to its working directory (the checkout).
http_run "ui run from manifest" "/ui/runs" "{\"manifest\": \"$MANIFEST_REL\", \"layers\": [0, 1]}"
((REMOTE == 0)) && [[ -n "$LAST_RUN" ]] && raw_matches_ui "ui run from manifest" "$LAST_RUN"
if ((REMOTE == 0 || FULL)); then
  http_run "native run" "/runs" "{\"manifest_path\": \"$MANIFEST_REL\"}"
  NATIVE_ID="$LAST_RUN"
  ((REMOTE == 0)) && [[ -n "$NATIVE_ID" ]] && raw_matches_ui "native run" "$NATIVE_ID"
  http_run "ui run from settings" "/ui/runs" \
    '{"name": "e2e settings", "task": "ligand_pose", "tools": ["boltz2"], "target": "P00760", "reference": "3PTB", "ligand": "NC(=N)c1ccccc1", "seeds": 1}'
  ((REMOTE == 0)) && [[ -n "$LAST_RUN" ]] && raw_matches_ui "ui run from settings" "$LAST_RUN"
else
  skip "http native run" "$ONE_RUN"
  skip "http ui run from settings" "$ONE_RUN"
fi

# ---------------------------------------------------------------- 3. MCP over stdio
if ((REMOTE)); then
  skip "mcp stdio" "$LOCAL_ONLY"
else
  info "pah mcp --profile $(basename "$PROFILE") (stdio): pah_run, agent_start, agent_step x2, agent_finish"
  (cd "$ROOT" && "$PY" "$H" mcp "$PAH" "$PROFILE" "$MANIFEST_REL" "$WORK/mcp.json" "$QUIET") \
    2>"$WORK/mcp.err"
  expect "mcp stdio session" "$WORK/mcp.json" \
    '"error" not in d and {"pah_run", "agent_start", "agent_step", "agent_finish"} <= set(d["tools"])' \
    'd.get("error") or "%d tools; pah_run %s verdict %s, %d progress notifications" % (len(d["tools"]), d["run"]["run_id"], d["run"]["verdict"], d["progress"])'
  MCP_RUN=$(jval "$WORK/mcp.json" 'd["run"]["run_id"]')
  MCP_TASK=$(jval "$WORK/mcp.json" 'd["task"]["id"]')
  if [[ -n "$MCP_RUN" && -n "$MCP_TASK" ]]; then
    expect "mcp agent tools" "$WORK/mcp.json" \
      'd["done"]["status"] == "done" and [s["seq"] for s in d["steps"]] == [1, 2]' \
      '"task %s: steps %s, status %s" % (d["task"]["id"], [s["seq"] for s in d["steps"]], d["done"]["status"])'
    ui_run "mcp run" "$MCP_RUN"
    raw_matches_ui "mcp run" "$MCP_RUN"
    agent_ui "mcp task" "$MCP_TASK" 2 "$MCP_RUN"
  else
    fail "mcp agent tools" "no run or task from the MCP session: $(tail -n 3 "$WORK/mcp.err")"
  fi
fi

# ---------------------------------------------------------------- 4. pah agent-log
if ((REMOTE)); then
  skip "agent-log cli" "$LOCAL_ONLY"
else
  AL_ID=$(cd "$ROOT" && "$PAH" agent-log start --profile "$PROFILE" \
    --goal "e2e: bash agent reports on run $CLI_ID" 2>"$WORK/agent-log.err")
  if [[ -n "$AL_ID" ]]; then
    s1=$(cd "$ROOT" && "$PAH" agent-log step "$AL_ID" --profile "$PROFILE" --kind thought \
      --text "ligand pose task; layers 0 and 1" 2>>"$WORK/agent-log.err")
    s2=$(cd "$ROOT" && "$PAH" agent-log step "$AL_ID" --profile "$PROFILE" --kind tool \
      --text "pah run $MANIFEST_REL" --ms 0 --data "{\"runId\": \"$CLI_ID\", \"progress\": 0.8}" \
      2>>"$WORK/agent-log.err")
    fin=$(cd "$ROOT" && "$PAH" agent-log finish "$AL_ID" --profile "$PROFILE" --status done \
      --label Completed --detail "1 run" --runs 1 2>>"$WORK/agent-log.err")
    if [[ "$s1 $s2 $fin" == "1 2 $AL_ID done" ]]; then
      pass "agent-log cli" "start $AL_ID, step 1, step 2 (data.runId $CLI_ID), finish done"
    else
      fail "agent-log cli" "steps '$s1' '$s2', finish '$fin': $(tail -n 2 "$WORK/agent-log.err")"
    fi
    agent_ui "agent-log task" "$AL_ID" 2 "$CLI_ID"
  else
    fail "agent-log cli" "start printed no id: $(tail -n 3 "$WORK/agent-log.err")"
  fi
fi

# ---------------------------------------------------------------- HTTP agent routes
if ((REMOTE == 0 || FULL)) && [[ -n "$NATIVE_ID" ]]; then
  http_agent "http task" "$NATIVE_ID"
elif ((REMOTE)) && ((FULL == 0)); then
  skip "http agent task" "$ONE_RUN"
fi

# ---------------------------------------------------------------- 5. across interfaces
if ((REMOTE == 0)); then
  linked=0 total=0
  for id in "$CLI_ID" "$MCP_RUN" "$NATIVE_ID"; do
    [[ -z "$id" ]] && continue
    total=$((total + 1))
    j=$(req GET "/ui/jobs/$id" "$WORK/x.json")
    r=$(req GET "/ui/runs/$id/record" "$WORK/y.json")
    [[ "$j $r" == "200 200" ]] && linked=$((linked + 1))
  done
  if ((total == 3 && linked == 3)); then
    pass "cross: step run ids resolve" "agent-log -> $CLI_ID (cli), mcp -> $MCP_RUN, http -> $NATIVE_ID: /ui/jobs/{id} and /ui/runs/{id}/record 200"
  else
    fail "cross: step run ids resolve" "$linked of $total linked run ids resolve"
  fi
fi

echo "summary: $PASSES passed, $FAILS failed, $SKIPS skipped ($BASE)"
((FAILS == 0)) || exit 1
exit 0
