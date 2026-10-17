"""`pah runtimes`: install, build, plan and run executors on GPU hosts."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from pah.core.events import ConsoleSink, EventBus, JsonlSink, Sink, StdoutJsonlSink, new_run_id
from pah.core.models import EventKind
from pah.runtimes.accel import AccelUnavailableError, RuntimeUnavailableError
from pah.runtimes.hardware import detect_gpus
from pah.runtimes.images import (
    Recipe,
    RecipeError,
    build_image,
    fetch_kits,
    install_native_host,
)
from pah.runtimes.launch import make_launcher
from pah.runtimes.models import Policy, Route, RuntimeProfile, RuntimeRegistry
from pah.runtimes.registry import MissingParameterError, fill, fill_env, load_accel, load_runtimes
from pah.runtimes.runner import ExecutorRunner, RunRequest

app = typer.Typer(
    name="runtimes",
    help="Install, build, plan and run co-folding and docking executors.",
    no_args_is_help=True,
    add_completion=False,
)
kits_app = typer.Typer(help="Anthropic optimisation kits checkout.", no_args_is_help=True)
app.add_typer(kits_app, name="kits")


class Fmt(StrEnum):
    console = "console"
    jsonl = "jsonl"


class Target(StrEnum):
    docker = "docker"
    apptainer = "apptainer"


ProfileOpt = Annotated[
    str, typer.Option(help="Runtime profile in runtimes.yaml: local, csf3, modal")
]
LauncherOpt = Annotated[
    str | None, typer.Option(help="host, docker or apptainer (default: the profile's)")
]
DryRunOpt = Annotated[bool, typer.Option(help="Print the commands without running them")]
ParamOpt = Annotated[
    list[str] | None, typer.Option("--param", "-p", help="Template value, key=value (repeatable)")
]


def _setup(profile: str) -> tuple[RuntimeRegistry, RuntimeProfile]:
    reg = load_runtimes()
    return reg, reg.profile(profile)


def _params(items: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise typer.BadParameter(f"expected key=value, got {item!r}")
        out[key] = value
    return out


def _bus(fmt: Fmt, events: Path | None) -> EventBus:
    sinks: list[Sink] = [ConsoleSink() if fmt is Fmt.console else StdoutJsonlSink()]
    if events is not None:
        sinks.append(JsonlSink(events))
    return EventBus(new_run_id("runtime"), sinks)


def _execute(recipe: Recipe, dry_run: bool) -> None:
    for path, text in recipe.files.items():
        if dry_run:
            typer.echo(f"# {path}\n{text}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            typer.echo(f"wrote {path}", err=True)
    for cmd in recipe.commands:
        typer.echo(shlex.join(cmd))
        if not dry_run:
            rc = subprocess.run(list(cmd), check=False).returncode
            if rc != 0:
                typer.echo(f"exit {rc}: {shlex.join(cmd)}", err=True)
                raise typer.Exit(code=rc)


@app.command("list")
def list_cmd(fmt: Annotated[Fmt, typer.Option("--format")] = Fmt.console) -> None:
    """Executors with their kit, stock route and what has been verified."""
    reg = load_runtimes()
    rows = [
        {
            "id": rt.id,
            "tool": rt.tool,
            "gpu": rt.gpu,
            "kit": rt.accel.kit if rt.accel else None,
            "stock": (rt.native.kind + " " + rt.native.version)
            if rt.native
            else "kit image, mode off",
            "verified": ",".join(rt.verified) or "-",
        }
        for rt in reg.executors
    ]
    if fmt is Fmt.jsonl:
        for r in rows:
            typer.echo(json.dumps(r))
        return
    for r in rows:
        typer.echo(
            f"{r['id']:<15} kit={r['kit'] or '-':<12} gpu={'yes' if r['gpu'] else 'no ':<3} "
            f"stock={r['stock']:<22} verified={r['verified']}  {r['tool']}"
        )


@app.command()
def hardware(
    profile: ProfileOpt = "local",
    launcher: LauncherOpt = None,
    fmt: Annotated[Fmt, typer.Option("--format")] = Fmt.console,
) -> None:
    """Visible GPUs and the route every executor would take on this host now."""
    reg, prof = _setup(profile)
    cfg = load_accel()
    gpus = detect_gpus()
    runner = ExecutorRunner(
        reg, cfg, prof, make_launcher(launcher or prof.launcher, reg, prof), gpus
    )
    out: dict[str, object] = {"gpus": [g.as_dict() for g in gpus], "executors": {}}
    routes: dict[str, object] = {}
    for rt in reg.executors:
        try:
            routes[rt.id] = runner.decide(rt, RunRequest(rt.id, Path())).as_dict()
        except (AccelUnavailableError, RuntimeUnavailableError, ValueError) as exc:
            routes[rt.id] = {"error": str(exc)}
    out["executors"] = routes
    if fmt is Fmt.jsonl:
        typer.echo(json.dumps(out))
        return
    typer.echo(f"gpus: {[g.as_dict() for g in gpus] or 'none'}")
    for eid, d in routes.items():
        assert isinstance(d, dict)
        if "error" in d:
            typer.echo(f"{eid:<15} unavailable: {d['error']}")
        else:
            reasons = "; ".join(d["reasons"]) or "-"
            mode, card = d["mode"] or "-", d["card"] or "-"
            typer.echo(f"{eid:<15} route={d['route']:<8} mode={mode:<5} card={card:<5} {reasons}")


def _runner(profile: str, launcher: str | None, bus: EventBus | None) -> ExecutorRunner:
    reg, prof = _setup(profile)
    return ExecutorRunner(
        reg,
        load_accel(),
        prof,
        make_launcher(launcher or prof.launcher, reg, prof),
        detect_gpus(),
        bus,
    )


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def plan(
    ctx: typer.Context,
    executor: str,
    out: Annotated[Path, typer.Option(help="Output directory")] = Path("runs/executor"),
    param: ParamOpt = None,
    accel: Annotated[
        Policy | None, typer.Option(help="auto, kit or stock (default: accel.yaml)")
    ] = None,
    mode: Annotated[str | None, typer.Option(help="Kit mode: off, exact, fast, big")] = None,
    profile: ProfileOpt = "local",
    launcher: LauncherOpt = None,
) -> None:
    """Show the route and the exact command a run would use. Extra args after -- pass through."""
    runner = _runner(profile, launcher, None)
    req = RunRequest(executor, out, _params(param), tuple(ctx.args), accel, mode)
    try:
        p = runner.plan(req)
    except (
        AccelUnavailableError,
        RuntimeUnavailableError,
        MissingParameterError,
        KeyError,
        ValueError,
    ) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        json.dumps(
            {
                "decision": p.decision.as_dict(),
                "argv": list(p.invocation.argv),
                "env": p.invocation.env,
                "check": list(p.check.argv) if p.check else None,
                "outputs": p.outputs,
                "weights": str(p.weights),
            },
            indent=2,
        )
    )


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    ctx: typer.Context,
    executor: str,
    out: Annotated[Path, typer.Option(help="Output directory")],
    param: ParamOpt = None,
    accel: Annotated[
        Policy | None, typer.Option(help="auto, kit or stock (default: accel.yaml)")
    ] = None,
    mode: Annotated[str | None, typer.Option(help="Kit mode: off, exact, fast, big")] = None,
    preflight: Annotated[
        bool, typer.Option(help="Run the kit's dry-run check before the kit run")
    ] = True,
    profile: ProfileOpt = "local",
    launcher: LauncherOpt = None,
    fmt: Annotated[Fmt, typer.Option("--format")] = Fmt.console,
) -> None:
    """Run an executor. Uses the optimisation kit when it can engage, otherwise stock."""
    req = RunRequest(executor, out, _params(param), tuple(ctx.args), accel, mode, preflight)
    out.mkdir(parents=True, exist_ok=True)
    with _bus(fmt, out / "events.jsonl") as bus:
        runner = _runner(profile, launcher, bus)
        try:
            result = runner.run(req)
        except (
            AccelUnavailableError,
            RuntimeUnavailableError,
            MissingParameterError,
            KeyError,
            ValueError,
        ) as exc:
            bus.emit(EventKind.LOG, "runtime", f"error: {exc}")
            raise typer.Exit(code=2) from exc
    raise typer.Exit(code=result.exit_code)


@app.command()
def install(
    executor: str,
    profile: ProfileOpt = "local",
    dry_run: DryRunOpt = False,
) -> None:
    """Install the stock tool on this GPU host (pip venv or binary under envs_root)."""
    reg, prof = _setup(profile)
    try:
        recipe = install_native_host(reg, reg.get(executor), prof)
    except RecipeError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    _execute(recipe, dry_run)


@app.command()
def build(
    executor: str,
    target: Annotated[Target, typer.Option(help="docker or apptainer")] = Target.docker,
    route: Annotated[
        str, typer.Option(help="kit (also serves stock as mode off) or native")
    ] = "kit",
    profile: ProfileOpt = "local",
    dry_run: DryRunOpt = False,
) -> None:
    """Build the image an executor runs in. Kit images need `pah runtimes kits fetch` first."""
    reg, prof = _setup(profile)
    try:
        recipe = build_image(reg, reg.get(executor), prof, Route(route), target.value)
    except (RecipeError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    _execute(recipe, dry_run)


@app.command()
def weights(
    executor: str,
    profile: ProfileOpt = "local",
    launcher: LauncherOpt = None,
    dry_run: DryRunOpt = False,
) -> None:
    """Fetch and digest-check weights: through the kit's installer when the kit is available,
    otherwise through the stock tool's own downloader."""
    reg, prof = _setup(profile)
    rt = reg.get(executor)
    lch = make_launcher(launcher or prof.launcher, reg, prof)
    runner = ExecutorRunner(reg, load_accel(), prof, lch, [])
    wdir = runner.weights_dir(rt)
    values: dict[str, object] = {"weights": str(wdir)}
    if rt.accel is not None and lch.kit_available(rt).ok:
        spec = rt.accel
        values.update(kit=spec.kit, kit_dir=lch.kit_dir(spec.kit), card=spec.configs[0])
        argv = fill(spec.install_weights or reg.kit_defaults.install_weights, values)
        inv = lch.wrap(rt, Route.KIT_OFF, argv, fill_env(spec.env, values), [wdir])
    elif (
        rt.native is not None
        and rt.native.fetch_weights is not None
        and lch.native_available(rt).ok
    ):
        argv = fill(rt.native.fetch_weights, values)
        inv = lch.wrap(rt, Route.NATIVE, argv, fill_env(rt.native.env, values), [wdir])
    else:
        note = (rt.native.fetch_note if rt.native else None) or "no fetch route available here"
        typer.echo(f"{rt.id}: {note}")
        raise typer.Exit(code=0 if rt.native and rt.native.fetch_note else 2)
    typer.echo(shlex.join(inv.argv))
    if dry_run:
        return
    wdir.mkdir(parents=True, exist_ok=True)
    rc = subprocess.run(list(inv.argv), env={**os.environ, **inv.env}, check=False).returncode
    raise typer.Exit(code=rc)


@kits_app.command("fetch")
def kits_fetch(profile: ProfileOpt = "local", dry_run: DryRunOpt = False) -> None:
    """Sparse checkout of the kits repository at the commit pinned in accel.yaml."""
    reg, prof = _setup(profile)
    root = prof.path("kits_root")
    if (root / ".git").exists():
        typer.echo(f"{root} exists; checking out the pinned commit")
        _execute(
            Recipe(
                commands=[
                    ("git", "-C", str(root), "fetch", "origin"),
                    ("git", "-C", str(root), "checkout", "--detach", load_accel().commit),
                ]
            ),
            dry_run,
        )
        return
    _execute(fetch_kits(load_accel(), reg, prof), dry_run)
