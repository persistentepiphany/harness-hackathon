"""End to end through every interface: the CLI, the HTTP API (native and /ui routes) and the MCP
server, each checked through the /ui read routes the web UI renders from.

Offline: the 3PTB sources come from the pre-filled cache of `offline_profile` (tests/conftest.py)
and PyMOL renders are placeholder files (the autouse `_fake_pymol` fixture).
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from pah.config import Profile
from tests.conftest import ROOT

pytest.importorskip("fastapi")
pytest.importorskip("sse_starlette")
pytest.importorskip("mcp")
from fastapi.testclient import TestClient
from mcp.client.client import Client

from pah.interfaces.api import create_app
from pah.interfaces.cli import app as cli
from pah.interfaces.mcp_server import build_server

POSE = ROOT / "examples/3ptb_ligand_pose/manifest.yaml"
VINA = ROOT / "examples/3ptb_vina/manifest.yaml"
OUTCOMES = {
    "pass": "supported",
    "pass_with_warnings": "narrowed",
    "stop": "refused",
    "incomplete": "incomplete",
}
SETTINGS = {
    "task": "ligand_pose",
    "tools": ["boltz2"],
    "target": "P00760",
    "reference": "3PTB",
    "ligand": "NC(=N)c1ccccc1",
    "seeds": 1,
}

runner = CliRunner()


# ---------------------------------------------------------------- helpers


@pytest.fixture
def profile_yaml(offline_profile: Profile, tmp_path: Path) -> Path:
    """The offline profile as a YAML file, for `--profile` and PAH_PROFILE."""
    path = tmp_path / "offline.yaml"
    path.write_text(
        f"name: offline\nbackend: local\ncache_dir: {offline_profile.cache_dir}\n"
        f"runs_dir: {offline_profile.runs_dir}\noffline: true\n"
    )
    return path


@pytest.fixture
def ui(offline_profile: Profile) -> TestClient:
    """The API the web UI talks to (`pah serve`), over the same runs directory."""
    return TestClient(create_app(offline_profile))


def _invoke(args: list[str], env: dict[str, str] | None = None) -> Result:
    result = runner.invoke(cli, args, env=env)
    assert result.exit_code == 0, result.output
    return result


def _jsonl(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _cli_run(
    manifest: Path, profile_yaml: Path, out: Path, *extra: str, env: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """`pah run <manifest> --format jsonl --out <out>`; the streamed events."""
    args = ["run", str(manifest), "--profile", str(profile_yaml), "--format", "jsonl"]
    return _jsonl(_invoke([*args, "--out", str(out), *extra], env=env).stdout)


def _settle(run_dir: Path) -> None:
    """Back-dates events.jsonl of a finished run, so the live tail closes at once instead of
    waiting out its quiet period after `run_end`."""
    old = time.time() - 60
    os.utime(run_dir / "events.jsonl", (old, old))


def _sse(client: TestClient, url: str, **kw: Any) -> list[tuple[str, str | None, Any]]:
    """(event, id, data) for every frame of a server-sent event stream."""
    frames: list[tuple[str, str | None, Any]] = []
    event, ident = "message", None
    with client.stream("GET", url, **kw) as resp:
        assert resp.status_code == 200, resp.read()
        assert resp.headers["content-type"].startswith("text/event-stream")
        for raw in resp.iter_lines():
            if raw.startswith("event:"):
                event = raw[6:].strip()
            elif raw.startswith("id:"):
                ident = raw[3:].strip()
            elif raw.startswith("data:"):
                frames.append((event, ident, json.loads(raw[5:].strip())))
                event, ident = "message", None
    return frames


def _wait(client: TestClient, run_id: str, timeout: float = 180) -> dict[str, Any]:
    """Polls the shared JobStore (native `GET /runs/{id}`) until the job has finished."""
    end = time.time() + timeout
    while time.time() < end:
        body = client.get(f"/runs/{run_id}").json()
        if body.get("status") not in ("running", None):
            return body  # type: ignore[no-any-return]
        time.sleep(0.1)
    raise AssertionError(f"job {run_id} did not finish")


def _in_ui(client: TestClient, profile: Profile, run_id: str) -> dict[str, Any]:
    """The run as the web UI reads it: job card, log lines and record, with the harness verdict
    mapped to the UI outcome."""
    raw = json.loads((Path(profile.runs_dir) / run_id / "record.json").read_text())
    # A run without predictions (pre-run) has its passing engine verdict scoped to not_assessed
    # (docs/UI.md, Assessment scope); a stop stays refused.
    engine = OUTCOMES[raw["verdict"]["outcome"]]
    pre_run = client.get(f"/ui/runs/{run_id}/record").json().get("assessment") == "pre-run"
    passing = ("supported", "narrowed", "incomplete")
    outcome = "not_assessed" if pre_run and engine in passing else engine
    jobs = {j["id"]: j for j in client.get("/ui/jobs").json()}
    assert run_id in jobs, sorted(jobs)
    job = jobs[run_id]
    assert job == client.get(f"/ui/jobs/{run_id}").json()
    assert job["status"] == "done" and job["verdict"] == outcome and job["layerIdx"] == 6
    assert job["harnessRunId"] == raw["run_id"]
    log = client.get(f"/ui/jobs/{run_id}/log", params={"format": "json"}).json()
    assert log and all({"seq", "t", "kind", "text", "plain"} <= set(line) for line in log)
    record = client.get(f"/ui/runs/{run_id}/record").json()
    assert record["id"] == run_id and record["source"] == "pah"
    assert record["verdict"]["outcome"] == outcome
    assert record["verdict"]["stops"] == raw["verdict"]["stops"]
    return {"job": job, "log": log, "record": record, "raw": raw}


def _payload(result: Any) -> Any:
    assert not result.is_error, result.content
    data = result.structured_content
    if data is None:
        return json.loads(result.content[0].text)
    return data["result"] if isinstance(data, dict) and set(data) == {"result"} else data


# ---------------------------------------------------------------- 1. CLI


def test_cli_run_appears_in_ui(
    offline_profile: Profile, profile_yaml: Path, ui: TestClient
) -> None:
    events = _cli_run(POSE, profile_yaml, Path(offline_profile.runs_dir) / "cli-1")
    kinds = [e["kind"] for e in events]
    assert kinds.count("finding") == 13 and "run_end" in kinds

    seen = _in_ui(ui, offline_profile, "cli-1")
    job, log, record = seen["job"], seen["log"], seen["record"]
    assert job["task"] == "ligand_pose" and job["checksDone"] == job["checksTotal"] == 13
    assert job["harnessRunId"] == events[0]["run_id"] != "cli-1"  # id = run directory name
    # one log line per streamed event, in the same order
    assert [line["seq"] for line in log] == [e["seq"] for e in events]
    checks = [line for line in log if line["kind"] == "check"]
    assert len(checks) == 13 and {line["result"] for line in checks} == {"pass", "warn"}
    assert record["verdict"]["outcome"] == "not_assessed"
    assert record["verdict"]["warnings"] == ["l1.ligand.stereo_defined"]
    assert [layer["status"] for layer in record["layers"]] == ["done"] * 2 + ["not_run"] * 4
    assert record["renders"] and record["report"]["status"] == "done"


def test_cli_vina_all_layers_appear_in_ui(
    offline_profile: Profile, profile_yaml: Path, ui: TestClient, tmp_path: Path
) -> None:
    events = _cli_run(
        VINA,
        profile_yaml,
        Path(offline_profile.runs_dir) / "cli-vina",
        "--layers",
        "0,1,2,3,4,5",
        env={"PAH_CONDA_PREFIX": str(tmp_path / "no-conda")},  # same tools on every host
    )
    seen = _in_ui(ui, offline_profile, "cli-vina")
    record = seen["record"]
    assert [line["seq"] for line in seen["log"]] == [e["seq"] for e in events]
    assert [layer["status"] for layer in record["layers"]] == ["done"] * 6
    assert all(cell["done"] for cell in seen["job"]["layers"])
    assert [(t["id"], t["family"]) for t in record["tools"]] == [("vina", "docking")]
    kinds = {s["kind"] for s in record["structures"]}
    assert "crystal" in kinds and kinds & {"medoid", "seed", "docking", "model"}
    assert all(s["url"].startswith("/runs/cli-vina/files/") for s in record["structures"])
    assert record["renders"]


# ---------------------------------------------------------------- 2. HTTP


def test_http_runs_appear_in_ui_and_stream(offline_profile: Profile, ui: TestClient) -> None:
    assert ui.get("/health").json()["status"] == "ok"
    native = ui.post("/runs", json={"manifest_path": str(POSE)})
    assert native.status_code == 202, native.text
    by_manifest = ui.post(
        "/ui/runs", json={"manifest": "examples/3ptb_ligand_pose/manifest.yaml", "layers": [0, 1]}
    )
    by_settings = ui.post("/ui/runs", json={**SETTINGS, "name": "e2e settings"})
    assert by_manifest.status_code == by_settings.status_code == 202
    assert by_manifest.json()["jobId"] == by_manifest.json()["runId"]
    ids = [native.json()["id"], by_manifest.json()["runId"], by_settings.json()["runId"]]

    for run_id in ids:
        assert _wait(ui, run_id)["status"] == "done"
    names = {}
    for run_id in ids:
        seen = _in_ui(ui, offline_profile, run_id)
        names[run_id] = seen["job"]["name"]
        _settle(Path(offline_profile.runs_dir) / run_id)
        frames = _sse(ui, f"/ui/jobs/{run_id}/log")
        assert [f[0] for f in frames] == ["line"] * (len(frames) - 1) + ["end"]
        lines = [f for f in frames if f[0] == "line"]
        assert [f[2]["seq"] for f in lines] == [line["seq"] for line in seen["log"]]
        assert all(f[1] == str(f[2]["seq"]) for f in lines)  # id: <seq>, for Last-Event-ID
        assert frames[-1][2] == {"reason": "run_end", "lastSeq": lines[-1][2]["seq"]}
    assert names[ids[2]] == "e2e settings"
    assert _in_ui(ui, offline_profile, ids[0])["record"]["verdict"]["outcome"] == "not_assessed"


# ---------------------------------------------------------------- 3. MCP


def test_mcp_run_and_agent_tools_appear_in_ui(offline_profile: Profile, ui: TestClient) -> None:
    progress: list[Any] = []

    async def on_progress(p: float, total: float | None, message: str | None) -> None:
        progress.append((p, total, message))

    async def session() -> tuple[set[str], dict[str, Any], dict[str, Any], dict[str, Any]]:
        async with Client(build_server(offline_profile)) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            run = _payload(
                await client.call_tool(
                    "pah_run", {"manifest_path": str(POSE)}, progress_callback=on_progress
                )
            )
            task = _payload(await client.call_tool("agent_start", {"goal": "MCP pose check"}))
            step = {"task_id": task["id"], "data": {"runId": run["run_id"]}}
            tool = {"kind": "tool", "text": "pah_run 3ptb_ligand_pose", "ms": 900}
            await client.call_tool("agent_step", {**step, **tool})
            report = {"kind": "report", "text": f"verdict {run['verdict']}"}
            await client.call_tool("agent_step", {**step, **report})
            outcome = {"label": "Completed", "detail": "1 run", "runs": 1}
            finish = {"task_id": task["id"], "status": "done", **outcome}
            done = _payload(await client.call_tool("agent_finish", finish))
            return names, run, task, done

    names, run, task, done = asyncio.run(session())
    assert {"pah_run", "agent_start", "agent_step", "agent_finish"} <= names
    assert len(progress) == 13 and done["status"] == "done"

    seen = _in_ui(ui, offline_profile, run["run_id"])
    assert seen["record"]["verdict"]["outcome"] == "not_assessed"
    tasks = {t["id"]: t for t in ui.get("/ui/agent/tasks").json()}
    shown = tasks[task["id"]]
    assert shown["goal"] == "MCP pose check" and shown["status"] == "done"
    assert shown["steps"] == 2 and shown["progress"] == 1.0
    assert shown["outcome"] == {"label": "Completed", "detail": "1 run", "runs": 1}
    steps = ui.get(f"/ui/agent/tasks/{task['id']}/steps", params={"format": "json"}).json()
    assert [(s["seq"], s["kind"]) for s in steps] == [(1, "tool"), (2, "report")]
    assert all(s["data"]["runId"] == run["run_id"] for s in steps) and steps[0]["ms"] == 900
    frames = _sse(ui, f"/ui/agent/tasks/{task['id']}/steps")
    assert [f[0] for f in frames] == ["step", "step", "end"]
    assert frames[-1][2]["status"] == "done"


# ---------------------------------------------------------------- 4. pah agent-log


def test_agent_log_cli_appears_in_ui(
    offline_profile: Profile, profile_yaml: Path, ui: TestClient
) -> None:
    runs = Path(offline_profile.runs_dir)
    _cli_run(POSE, profile_yaml, runs / "cli-2")
    env = {"PAH_PROFILE": str(profile_yaml)}
    task_id = _invoke(["agent-log", "start", "--goal", "CLI pose check"], env=env).stdout.strip()
    first = _invoke(
        ["agent-log", "step", task_id, "--kind", "thought", "--text", "layers 0 and 1"], env=env
    )
    second = _invoke(
        [
            "agent-log", "step", task_id, "--kind", "tool", "--text", "pah run 3ptb",
            "--ms", "1500", "--data", json.dumps({"runId": "cli-2", "progress": 0.6}),
            "--runs-dir", str(runs),
        ]
    )  # fmt: skip
    assert (first.stdout.strip(), second.stdout.strip()) == ("1", "2")
    running = ui.get(f"/ui/agent/tasks/{task_id}").json()
    assert running["status"] == "running" and running["progress"] == 0.6
    finished = _invoke(
        [
            "agent-log", "finish", task_id, "--status", "done", "--label", "Completed",
            "--detail", "1 run, verdict pass_with_warnings", "--runs", "1",
        ],
        env=env,
    )  # fmt: skip
    assert finished.stdout.strip() == f"{task_id} done"

    shown = {t["id"]: t for t in ui.get("/ui/agent/tasks").json()}[task_id]
    assert shown["goal"] == "CLI pose check" and shown["status"] == "done"
    assert shown["steps"] == 2 and shown["outcome"]["runs"] == 1
    steps = ui.get(f"/ui/agent/tasks/{task_id}/steps", params={"format": "json"}).json()
    assert [s["kind"] for s in steps] == ["thought", "tool"]
    assert steps[1]["data"] == {"runId": "cli-2", "progress": 0.6} and steps[1]["ms"] == 1500
    assert ui.get("/ui/jobs/cli-2").json()["verdict"] == "not_assessed"
    late = runner.invoke(
        cli, ["agent-log", "step", task_id, "--kind", "tool", "--text", "x"], env=env
    )
    assert late.exit_code == 2  # a finished task refuses steps


# ---------------------------------------------------------------- 5. across interfaces


def test_one_agent_task_across_interfaces_links_runs(
    offline_profile: Profile, profile_yaml: Path, ui: TestClient
) -> None:
    _cli_run(POSE, profile_yaml, Path(offline_profile.runs_dir) / "cli-3")

    created = ui.post("/ui/agent/tasks", json={"goal": "Pose claim across interfaces"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    _invoke(
        [
            "agent-log", "step", task_id, "--kind", "tool", "--text", "pah run (CLI)",
            "--data", json.dumps({"runId": "cli-3"}), "--profile", str(profile_yaml),
        ]
    )  # fmt: skip

    async def mcp_step() -> dict[str, Any]:
        async with Client(build_server(offline_profile)) as client:
            run = _payload(await client.call_tool("pah_run", {"manifest_path": str(POSE)}))
            step = {"kind": "tool", "text": "pah_run (MCP)", "data": {"runId": run["run_id"]}}
            await client.call_tool("agent_step", {"task_id": task_id, **step})
            return run  # type: ignore[no-any-return]

    mcp_run = asyncio.run(mcp_step())
    step = ui.post(
        f"/ui/agent/tasks/{task_id}/steps",
        json={"kind": "conclusion", "text": "both runs narrowed", "data": {"progress": 0.9}},
    )
    assert step.status_code == 201 and step.json()["seq"] == 3
    finish = ui.post(
        f"/ui/agent/tasks/{task_id}/finish",
        json={"status": "done", "outcome": {"label": "Completed", "detail": "2 runs", "runs": 2}},
    )
    assert finish.status_code == 200

    steps = ui.get(f"/ui/agent/tasks/{task_id}/steps", params={"format": "json"}).json()
    assert [s["text"] for s in steps] == ["pah run (CLI)", "pah_run (MCP)", "both runs narrowed"]
    linked = [s["data"]["runId"] for s in steps if "runId" in (s["data"] or {})]
    assert linked == ["cli-3", mcp_run["run_id"]]
    jobs = {j["id"] for j in ui.get("/ui/jobs").json()}
    for run_id in linked:  # the Agent view links data.runId to /jobs/<id> and /reports/<id>
        assert run_id in jobs
        assert ui.get(f"/ui/jobs/{run_id}").json()["verdict"] == "not_assessed"
        assert ui.get(f"/ui/runs/{run_id}/record").json()["id"] == run_id
    task = ui.get(f"/ui/agent/tasks/{task_id}").json()
    assert task["status"] == "done" and task["steps"] == 3 and task["outcome"]["runs"] == 2
    assert not any(j.startswith("agent-") for j in jobs)  # agent tasks are not jobs
