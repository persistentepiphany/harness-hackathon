"""Step log of an agent under test, read by the UI's Agent view.

Layout per task, under the runs directory:
    agent-<id>/task.json     {id, goal, status, createdAt, updatedAt, finishedAt, progress,
                              steps, outcome}
    agent-<id>/steps.jsonl   one step per line: {seq, ts, kind, text, ms, data}

Writers in different processes (the HTTP API, `pah agent-log`, the MCP server) serialise on an
exclusive `flock` of `agent-<id>/.lock`; `task.json` is replaced atomically, so readers never see
a partial file. `steps` in task.json is the step count; `progress` is 0..1 (1 when done, or the
last `data.progress` an agent reported).
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import re
import tempfile
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pah.webui import persistence

KINDS = ("thought", "tool", "result", "report", "conclusion")
STATUSES = ("running", "done", "failed")
FINISH_STATUSES = ("done", "failed")
PREFIX = "agent-"
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class AgentLogError(ValueError):
    """Invalid input (unknown kind or status, bad id)."""


class AgentTaskNotFoundError(LookupError):
    pass


class AgentTaskFinishedError(RuntimeError):
    """A step or finish for a task that has already finished."""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _atomic_json(path: Path, obj: Any) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
            fh.write("\n")
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read_steps(path: Path) -> list[dict[str, Any]]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    complete, _, _ = data.rpartition(b"\n")
    out = []
    for raw in complete.split(b"\n"):
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


class AgentLog:
    """Agent tasks under one runs directory."""

    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir

    # ---- paths ----------------------------------------------------------------------------

    def task_dir(self, task_id: str) -> Path:
        if not _ID.fullmatch(task_id):
            raise AgentLogError(f"invalid agent task id {task_id!r}")
        return self.runs_dir / f"{PREFIX}{task_id}"

    def _existing(self, task_id: str) -> Path:
        d = self.task_dir(task_id)
        if not (d / "task.json").is_file():
            raise AgentTaskNotFoundError(f"no agent task {task_id!r}")
        return d

    @contextmanager
    def _locked(self, d: Path) -> Iterator[None]:
        with (d / ".lock").open("a") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _load(self, d: Path) -> dict[str, Any]:
        obj = json.loads((d / "task.json").read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise AgentTaskNotFoundError(f"{d / 'task.json'} is not an object")
        return obj

    def _view(self, task: dict[str, Any]) -> dict[str, Any]:
        start = _parse_ts(task.get("createdAt"))
        end = _parse_ts(task.get("finishedAt")) or datetime.now(UTC)
        elapsed = int((end - start).total_seconds() * 1000) if start else 0
        return {**task, "elapsedMs": max(0, elapsed)}

    # ---- writes ---------------------------------------------------------------------------

    def create(self, goal: str) -> dict[str, Any]:
        goal = goal.strip()
        if not goal:
            raise AgentLogError("goal must not be empty")
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        task_id = f"{stamp}-{uuid.uuid4().hex[:6]}"
        d = self.task_dir(task_id)
        d.mkdir(parents=True, exist_ok=False)
        now = _now()
        task: dict[str, Any] = {
            "id": task_id,
            "goal": goal,
            "status": "running",
            "createdAt": now,
            "updatedAt": now,
            "finishedAt": None,
            "progress": 0.0,
            "steps": 0,
            "outcome": None,
        }
        with self._locked(d):
            (d / "steps.jsonl").touch()
            _atomic_json(d / "task.json", task)
        persistence.persist("agent task created")
        return self._view(task)

    def append(
        self,
        task_id: str,
        kind: str,
        text: str,
        ms: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if kind not in KINDS:
            raise AgentLogError(f"kind must be one of {', '.join(KINDS)}; got {kind!r}")
        if ms is not None and ms < 0:
            raise AgentLogError("ms must be >= 0")
        if data is not None and not isinstance(data, dict):
            raise AgentLogError("data must be a JSON object")
        d = self._existing(task_id)
        with self._locked(d):
            task = self._load(d)
            if task.get("status") in FINISH_STATUSES:
                raise AgentTaskFinishedError(f"agent task {task_id} is {task['status']}")
            seq = len(_read_steps(d / "steps.jsonl")) + 1
            step = {"seq": seq, "ts": _now(), "kind": kind, "text": text, "ms": ms,
                    "data": data}  # fmt: skip
            with (d / "steps.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(step) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            task["steps"] = seq
            task["updatedAt"] = step["ts"]
            progress = (data or {}).get("progress")
            if isinstance(progress, (int, float)) and not isinstance(progress, bool):
                task["progress"] = min(1.0, max(0.0, float(progress)))
            _atomic_json(d / "task.json", task)
        persistence.persist("agent step")
        return step

    def finish(self, task_id: str, status: str, outcome: dict[str, Any] | None) -> dict[str, Any]:
        if status not in FINISH_STATUSES:
            raise AgentLogError(f"status must be done or failed; got {status!r}")
        if outcome is not None and not isinstance(outcome, dict):
            raise AgentLogError("outcome must be an object {label, detail, runs?, reports?}")
        d = self._existing(task_id)
        with self._locked(d):
            task = self._load(d)
            if task.get("status") in FINISH_STATUSES:
                raise AgentTaskFinishedError(f"agent task {task_id} is {task['status']}")
            now = _now()
            task.update(status=status, finishedAt=now, updatedAt=now, outcome=outcome or {})
            if status == "done":
                task["progress"] = 1.0
            _atomic_json(d / "task.json", task)
        persistence.persist("agent task finished")
        return self._view(task)

    # ---- reads ----------------------------------------------------------------------------

    def get(self, task_id: str) -> dict[str, Any]:
        return self._view(self._load(self._existing(task_id)))

    def steps(self, task_id: str, after: int = 0) -> list[dict[str, Any]]:
        d = self._existing(task_id)
        return [s for s in _read_steps(d / "steps.jsonl") if int(s.get("seq") or 0) > after]

    def list_tasks(self) -> list[dict[str, Any]]:
        out = []
        try:
            dirs = [p for p in self.runs_dir.iterdir() if p.name.startswith(PREFIX)]
        except OSError:
            return []
        for d in dirs:
            try:
                out.append(self._view(self._load(d)))
            except (OSError, ValueError, AgentTaskNotFoundError):
                continue
        return sorted(out, key=lambda t: str(t.get("createdAt") or ""), reverse=True)

    async def tail(
        self, task_id: str, after: int = 0, poll: float = 0.25
    ) -> AsyncIterator[dict[str, Any]]:
        """Yields steps after `after`, then new ones as they are appended. Ends once the task
        has finished and every step has been yielded."""
        d = self._existing(task_id)
        path = d / "steps.jsonl"
        last = after
        while True:
            finished = self._load(d).get("status") in FINISH_STATUSES
            for step in _read_steps(path):
                seq = int(step.get("seq") or 0)
                if seq > last:
                    last = seq
                    yield step
            if finished:
                return
            await asyncio.sleep(poll)


def register_mcp_tools(server: Any, runs_dir: Path) -> None:
    """Adds agent_start, agent_step and agent_finish to an MCP server, writing the same files as
    the HTTP routes and `pah agent-log`, so the UI's Agent view shows an MCP agent live."""
    log = AgentLog(runs_dir)

    @server.tool(  # type: ignore[untyped-decorator]
        description="Start an agent task log shown in the harness UI. Returns the task with its id."
    )
    def agent_start(goal: str) -> dict[str, Any]:
        return log.create(goal)

    @server.tool(  # type: ignore[untyped-decorator]
        description="Append a step to an agent task log. kind: thought, tool, result, report or "
        "conclusion; ms: duration; data: any JSON object (data.progress 0..1 sets progress)."
    )
    def agent_step(
        task_id: str,
        kind: str,
        text: str,
        ms: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return log.append(task_id, kind, text, ms, data)

    @server.tool(  # type: ignore[untyped-decorator]
        description="Finish an agent task log. status: done or failed; outcome: "
        "{label, detail, runs?, reports?}."
    )
    def agent_finish(
        task_id: str, status: str, label: str, detail: str = "",
        runs: int | None = None, reports: int | None = None,
    ) -> dict[str, Any]:  # fmt: skip
        outcome: dict[str, Any] = {"label": label, "detail": detail}
        if runs is not None:
            outcome["runs"] = runs
        if reports is not None:
            outcome["reports"] = reports
        return log.finish(task_id, status, outcome)
