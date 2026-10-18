"""`pah agent-log`: an agent under test reports its steps from bash. Registered by
`pah.interfaces.cli`. Writes the same files as the `/ui/agent/...` HTTP routes, so the UI's
Agent view shows the steps live.

    id=$(pah agent-log start --goal "Check the 3PTB benzamidine pose")
    pah agent-log step "$id" --kind tool --text "pah run examples/3ptb_ligand_pose" --ms 900
    pah agent-log finish "$id" --status done --label Completed --detail "verdict pass_with_warnings"

Exit codes: 0 written, 2 unusable profile or runs directory, unknown task, finished task or
invalid argument.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

import typer

agent_app = typer.Typer(
    name="agent-log",
    help="Report agent steps to the harness UI (runs/agent-<id>/).",
    no_args_is_help=True,
    add_completion=False,
)

RunsDirOpt = Annotated[
    Path | None, typer.Option("--runs-dir", help="Runs directory (default: the profile's)")
]
ProfileOpt = Annotated[
    str | None, typer.Option(help="Profile for the runs directory (default: $PAH_PROFILE or local)")
]
JsonOpt = Annotated[bool, typer.Option("--json", help="Print the full object as JSON")]


def _fail(message: str) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(code=2)


def _log(runs_dir: Path | None, profile: str | None) -> Any:
    from pah.config import load_profile, resolve_path
    from pah.webui.agent_log import AgentLog

    if runs_dir is None:
        name = profile or os.environ.get("PAH_PROFILE") or "local"
        try:
            runs_dir = resolve_path(load_profile(name).runs_dir)
        except (OSError, ValueError) as exc:
            raise _fail(f"profile {name!r}: {exc}") from exc
    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _fail(f"runs directory {runs_dir}: {exc}") from exc
    return AgentLog(runs_dir)


def _call(fn: Any, *args: Any) -> Any:
    from pah.webui.agent_log import AgentLogError, AgentTaskFinishedError, AgentTaskNotFoundError

    try:
        return fn(*args)
    except (AgentLogError, AgentTaskNotFoundError, AgentTaskFinishedError, OSError) as exc:
        raise _fail(str(exc)) from exc


@agent_app.command()
def start(
    goal: Annotated[str, typer.Option(help="What the agent is trying to establish")],
    runs_dir: RunsDirOpt = None,
    profile: ProfileOpt = None,
    as_json: JsonOpt = False,
) -> None:
    """Start a task; prints its id."""
    task = _call(_log(runs_dir, profile).create, goal)
    typer.echo(json.dumps(task) if as_json else task["id"])


@agent_app.command()
def step(
    task_id: Annotated[str, typer.Argument(help="Task id from `start`")],
    kind: Annotated[str, typer.Option(help="thought, tool, result, report or conclusion")],
    text: Annotated[str, typer.Option(help="One line describing the step")],
    ms: Annotated[int | None, typer.Option(help="Duration of the step in ms")] = None,
    data: Annotated[
        str | None, typer.Option(help="JSON object; data.progress (0..1) sets progress")
    ] = None,
    runs_dir: RunsDirOpt = None,
    profile: ProfileOpt = None,
    as_json: JsonOpt = False,
) -> None:
    """Append a step; prints its sequence number."""
    parsed: dict[str, Any] | None = None
    if data is not None:
        try:
            value = json.loads(data)
        except ValueError as exc:
            raise _fail(f"--data is not JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise _fail("--data must be a JSON object")
        parsed = value
    result = _call(_log(runs_dir, profile).append, task_id, kind, text, ms, parsed)
    typer.echo(json.dumps(result) if as_json else str(result["seq"]))


@agent_app.command()
def finish(
    task_id: Annotated[str, typer.Argument(help="Task id from `start`")],
    status: Annotated[str, typer.Option(help="done or failed")] = "done",
    label: Annotated[str, typer.Option(help="Outcome label, e.g. Completed")] = "Completed",
    detail: Annotated[str, typer.Option(help="One-line outcome detail")] = "",
    runs: Annotated[int | None, typer.Option(help="Number of harness runs")] = None,
    reports: Annotated[int | None, typer.Option(help="Number of reports")] = None,
    runs_dir: RunsDirOpt = None,
    profile: ProfileOpt = None,
    as_json: JsonOpt = False,
) -> None:
    """Finish a task with an outcome."""
    outcome: dict[str, Any] = {"label": label, "detail": detail}
    if runs is not None:
        outcome["runs"] = runs
    if reports is not None:
        outcome["reports"] = reports
    task = _call(_log(runs_dir, profile).finish, task_id, status, outcome)
    typer.echo(json.dumps(task) if as_json else f"{task['id']} {task['status']}")


@agent_app.command()
def show(
    task_id: Annotated[str, typer.Argument(help="Task id")],
    runs_dir: RunsDirOpt = None,
    profile: ProfileOpt = None,
) -> None:
    """Print the task and its steps as JSON."""
    log = _log(runs_dir, profile)
    task = _call(log.get, task_id)
    typer.echo(json.dumps({**task, "stepList": _call(log.steps, task_id)}, indent=2))


def register(app: typer.Typer) -> None:
    """Adds `pah agent-log` to the top-level app."""
    app.add_typer(agent_app, name="agent-log")
