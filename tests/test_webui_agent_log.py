"""Agent step log: files, concurrent writers, tailing, CLI and MCP tools."""

import asyncio
import json
import threading
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from pah.interfaces.cli import app
from pah.webui import persistence
from pah.webui.agent_log import (
    AgentLog,
    AgentLogError,
    AgentTaskFinishedError,
    AgentTaskNotFoundError,
)


def test_lifecycle(tmp_path: Path) -> None:
    log = AgentLog(tmp_path)
    task = log.create("Check the 3PTB pose")
    assert task["status"] == "running" and task["steps"] == 0 and task["outcome"] is None
    assert (tmp_path / f"agent-{task['id']}" / "task.json").is_file()
    s1 = log.append(task["id"], "thought", "Ligand pose task", ms=1400)
    s2 = log.append(task["id"], "tool", "pah run", data={"progress": 0.5})
    assert (s1["seq"], s2["seq"]) == (1, 2) and s1["ms"] == 1400 and s2["data"] == {"progress": 0.5}
    assert log.get(task["id"])["progress"] == 0.5 and log.get(task["id"])["steps"] == 2
    done = log.finish(task["id"], "done", {"label": "Completed", "detail": "1 run", "runs": 1})
    assert done["status"] == "done" and done["progress"] == 1.0 and done["finishedAt"]
    assert done["outcome"]["runs"] == 1 and done["elapsedMs"] >= 0
    assert [s["kind"] for s in log.steps(task["id"])] == ["thought", "tool"]
    assert [s["seq"] for s in log.steps(task["id"], after=1)] == [2]
    with pytest.raises(AgentTaskFinishedError):
        log.append(task["id"], "result", "late")
    assert [t["id"] for t in log.list_tasks()] == [task["id"]]


def test_validation(tmp_path: Path) -> None:
    log = AgentLog(tmp_path)
    tid = log.create("goal")["id"]
    with pytest.raises(AgentLogError):
        log.append(tid, "chatter", "x")
    with pytest.raises(AgentLogError):
        log.finish(tid, "maybe", None)
    with pytest.raises(AgentLogError):
        log.create("  ")
    with pytest.raises(AgentLogError):
        log.get("../etc")
    with pytest.raises(AgentTaskNotFoundError):
        log.get("missing")


def test_two_writers_append_concurrently(tmp_path: Path) -> None:
    tid = AgentLog(tmp_path).create("concurrency")["id"]

    def write(tag: str) -> None:
        log = AgentLog(tmp_path)  # separate instances, separate lock file handles
        for i in range(40):
            log.append(tid, "tool", f"{tag}-{i}")

    threads = [threading.Thread(target=write, args=(t,)) for t in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    steps = AgentLog(tmp_path).steps(tid)
    assert [s["seq"] for s in steps] == list(range(1, 81))
    assert len({s["text"] for s in steps}) == 80
    assert AgentLog(tmp_path).get(tid)["steps"] == 80


def test_tail_follows_until_finished(tmp_path: Path) -> None:
    log = AgentLog(tmp_path)
    tid = log.create("tail")["id"]
    log.append(tid, "thought", "first")

    async def go() -> list[int]:
        seen: list[int] = []

        async def writer() -> None:
            await asyncio.sleep(0.3)
            log.append(tid, "result", "second")
            await asyncio.sleep(0.3)
            log.finish(tid, "failed", {"label": "Failed", "detail": "x"})

        task = asyncio.create_task(writer())
        async for step in log.tail(tid, poll=0.05):
            seen.append(step["seq"])
        await task
        return seen

    assert asyncio.run(go()) == [1, 2]


def test_persist_hook_called(tmp_path: Path) -> None:
    calls: list[int] = []
    remove = persistence.on_persist(lambda: calls.append(1))
    persistence.on_persist(lambda: 1 / 0)  # a failing callback is logged, not raised
    try:
        log = AgentLog(tmp_path)
        tid = log.create("persist")["id"]
        log.append(tid, "tool", "x")
        log.finish(tid, "done", {"label": "ok", "detail": ""})
    finally:
        remove()
        persistence.clear()
    assert len(calls) == 3


def test_cli(tmp_path: Path) -> None:
    runner = CliRunner()
    base = ["agent-log"]
    rd = ["--runs-dir", str(tmp_path)]
    r = runner.invoke(app, [*base, "start", "--goal", "Check 3PTB", *rd])
    assert r.exit_code == 0, r.output
    tid = r.stdout.strip()
    r = runner.invoke(app, [*base, "step", tid, "--kind", "tool", "--text", "pah run", "--ms",
                            "900", "--data", '{"run": "x"}', *rd])  # fmt: skip
    assert r.exit_code == 0 and r.stdout.strip() == "1"
    r = runner.invoke(app, [*base, "step", tid, "--kind", "nope", "--text", "x", *rd])
    assert r.exit_code == 2 and "kind must be one of" in r.output
    r = runner.invoke(app, [*base, "step", tid, "--kind", "tool", "--text", "x", "--data", "[1]",
                            *rd])  # fmt: skip
    assert r.exit_code == 2
    r = runner.invoke(app, [*base, "finish", tid, "--status", "done", "--label", "Completed",
                            "--detail", "verdict pass", "--runs", "1", "--json", *rd])  # fmt: skip
    assert r.exit_code == 0 and json.loads(r.stdout)["outcome"]["runs"] == 1
    r = runner.invoke(app, [*base, "show", tid, *rd])
    shown = json.loads(r.stdout)
    assert shown["status"] == "done" and shown["stepList"][0]["data"] == {"run": "x"}
    r = runner.invoke(app, [*base, "step", "missing", "--kind", "tool", "--text", "x", *rd])
    assert r.exit_code == 2


def test_mcp_tools(tmp_path: Path) -> None:
    pytest.importorskip("mcp")
    from mcp.client.client import Client

    from pah.config import Profile
    from pah.interfaces.mcp_server import build_server

    profile = Profile(name="t", backend="local", cache_dir=tmp_path / "c", runs_dir=tmp_path / "r")
    server = build_server(profile)

    async def go() -> tuple[list[str], Any, Any]:
        async with Client(server) as client:
            names = [t.name for t in (await client.list_tools()).tools]
            started = await client.call_tool("agent_start", {"goal": "MCP agent"})
            tid = (started.structured_content or json.loads(started.content[0].text))["id"]
            await client.call_tool("agent_step", {"task_id": tid, "kind": "tool", "text": "x"})
            await client.call_tool(
                "agent_finish", {"task_id": tid, "status": "done", "label": "Completed"}
            )
            return names, tid, None

    names, tid, _ = asyncio.run(go())
    assert {"agent_start", "agent_step", "agent_finish", "pah_run"} <= set(names)
    task = AgentLog(tmp_path / "r").get(tid)
    assert task["status"] == "done" and task["steps"] == 1
