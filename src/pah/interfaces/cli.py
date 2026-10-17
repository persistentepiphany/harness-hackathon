"""`pah` command line. Streams events to the console or as JSON lines for agents.

Exit codes: 0 completed, 1 completed with failures under --strict, 2 could not run
(bad profile, unreadable configuration). Errors are reported as one line, not a traceback.
"""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from pydantic import ValidationError

from pah import __version__
from pah.config import Profile, available_profiles, load_profile, resolve_path
from pah.core.events import ConsoleSink, EventBus, JsonlSink, Sink, StdoutJsonlSink, new_run_id
from pah.core.models import EventKind

app = typer.Typer(
    name="pah",
    help="Prediction assurance harness.",
    no_args_is_help=True,
    add_completion=False,
)


class OutputFormat(StrEnum):
    console = "console"
    jsonl = "jsonl"


def _profiles_help() -> str:
    try:
        return f"Deployment profile: {', '.join(available_profiles())}"
    except OSError:
        return "Deployment profile name or path to a profile YAML"


def _bus(run_id: str, fmt: OutputFormat, events_file: Path | None) -> EventBus:
    sinks: list[Sink] = [ConsoleSink() if fmt is OutputFormat.console else StdoutJsonlSink()]
    if events_file is not None:
        sinks.append(JsonlSink(events_file))
    return EventBus(run_id, sinks)


def _fail(message: str, fmt: OutputFormat) -> typer.Exit:
    if fmt is OutputFormat.jsonl:
        sys.stdout.write(json.dumps({"kind": "error", "message": message}) + "\n")
    else:
        typer.echo(f"error: {message}", err=True)
    return typer.Exit(code=2)


def _profile(name: str, fmt: OutputFormat) -> Profile:
    try:
        return load_profile(name)
    except (OSError, ValueError, ValidationError) as exc:
        raise _fail(f"profile {name!r}: {exc}", fmt) from exc


ProfileOpt = Annotated[str, typer.Option(help=_profiles_help())]
FormatOpt = Annotated[OutputFormat, typer.Option("--format", help="Stream format")]


@app.command()
def version() -> None:
    """Print the harness version."""
    typer.echo(__version__)


@app.command()
def doctor(
    profile: ProfileOpt = "local",
    only: Annotated[
        list[str] | None,
        typer.Option(
            help="Restrict to categories: sources, tools, executors, skills, infrastructure"
        ),
    ] = None,
    out: Annotated[
        Path | None, typer.Option(help="Report directory (default: <runs_dir>/<id>)")
    ] = None,
    fmt: FormatOpt = OutputFormat.console,
    timeout: Annotated[float, typer.Option(help="HTTP timeout per probe, seconds")] = 20.0,
    dry_run: Annotated[
        bool, typer.Option(help="Validate the profile and list probes only")
    ] = False,
    strict: Annotated[bool, typer.Option(help="Exit 1 if any probe is not ok")] = False,
) -> None:
    """Check reachability of sources, tools, executor code and weights, and skills."""
    from pah.doctor import Doctor, ProbeContext, build_catalog, write_report

    prof = _profile(profile, fmt)
    run_id = new_run_id("doctor")
    out_dir = out or (resolve_path(prof.runs_dir) / run_id)
    with (
        httpx.Client(follow_redirects=True, timeout=timeout) as client,
        _bus(run_id, fmt, None if dry_run else out_dir / "events.jsonl") as bus,
    ):
        catalog = build_catalog(ProbeContext(client=client, profile=prof), only)
        if dry_run:
            for category, probes in catalog.items():
                for p in probes:
                    bus.emit(EventKind.LOG, category, f"{p.id} [{p.kind}] {p.target}")
            bus.emit(
                EventKind.RUN_END,
                "doctor",
                f"dry run: profile={prof.name} backend={prof.backend} "
                f"probes={sum(len(v) for v in catalog.values())}",
            )
            return
        report = Doctor(bus).run(catalog, prof.name)
        try:
            json_path, md_path = write_report(report, out_dir)
        except OSError as exc:
            raise _fail(f"cannot write report to {out_dir}: {exc}", fmt) from exc
        bus.emit(EventKind.ARTIFACT, "doctor", str(json_path), path=str(json_path))
        bus.emit(EventKind.ARTIFACT, "doctor", str(md_path), path=str(md_path))
    if strict and not report.ok:
        raise typer.Exit(code=1)


@app.command()
def fetch(
    profile: ProfileOpt = "local",
    only: Annotated[list[str] | None, typer.Option(help="Asset ids to fetch")] = None,
    include_all: Annotated[
        bool, typer.Option("--all", help="Include non-default assets (weights, databases)")
    ] = False,
    force: Annotated[bool, typer.Option(help="Re-fetch assets that are already present")] = False,
    fmt: FormatOpt = OutputFormat.console,
    timeout: Annotated[float, typer.Option(help="HTTP read timeout, seconds")] = 60.0,
    dry_run: Annotated[bool, typer.Option(help="List the selected assets only")] = False,
    strict: Annotated[
        bool, typer.Option(help="Exit 1 if any asset is not installed or present")
    ] = False,
) -> None:
    """Fetch binaries, weights and datasets declared in configs/externals.yaml.

    Each asset is fetched on its own: a blocked host, a failed download or a missing
    prerequisite is recorded and the next asset proceeds.
    """
    from pah.externals import Fetcher, InstallContext, load_registry, select

    prof = _profile(profile, fmt)
    run_id = new_run_id("fetch")
    out_dir = resolve_path(prof.runs_dir) / run_id
    tools_dir = resolve_path(prof.tools_dir)
    registry = load_registry()
    chosen, unknown = select(registry.assets, only, include_all)
    http_timeout = httpx.Timeout(timeout, connect=20.0)
    with (
        httpx.Client(follow_redirects=True, timeout=http_timeout) as client,
        _bus(run_id, fmt, None if dry_run else out_dir / "events.jsonl") as bus,
    ):
        for problem in registry.errors:
            bus.emit(EventKind.LOG, "fetch", f"registry entry skipped: {problem}", status="error")
        for asset_id in unknown:
            bus.emit(EventKind.LOG, "fetch", f"unknown asset id: {asset_id}", status="error")
        if dry_run:
            for a in chosen:
                size = f" ({a.size_hint})" if a.size_hint else ""
                where = f"${a.env_var}" if a.env_var else str(tools_dir / a.dest)
                bus.emit(EventKind.LOG, a.id, f"{a.kind.value} -> {where}{size}")
            bus.emit(EventKind.RUN_END, "fetch", f"dry run: {len(chosen)} assets")
            return
        extra = (resolve_path(prof.conda_prefix) / "bin",) if prof.conda_prefix else ()
        ctx = InstallContext(client=client, tools_dir=tools_dir, force=force, extra_path=extra)
        results = Fetcher(bus, ctx).run(chosen)
        out_dir.mkdir(parents=True, exist_ok=True)
        report = out_dir / "fetch_report.json"
        report.write_text(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
        bus.emit(EventKind.ARTIFACT, "fetch", str(report), path=str(report))
    failed = [r for r in results if not r.usable]
    if strict and (failed or unknown or registry.errors):
        raise typer.Exit(code=1)


def _parse_layers(text: str) -> tuple[int, ...]:
    try:
        layers = tuple(sorted({int(x) for x in text.split(",") if x.strip()}))
    except ValueError as exc:
        raise typer.BadParameter(f"layers must be integers 0-5, got {text!r}") from exc
    if not layers or any(x < 0 or x > 5 for x in layers):
        raise typer.BadParameter(f"layers must be integers 0-5, got {text!r}")
    return layers


@app.command()
def run(
    manifest: Annotated[Path, typer.Argument(help="Run manifest (YAML)")],
    profile: ProfileOpt = "local",
    layers: Annotated[str, typer.Option(help="Comma-separated layers to run")] = "0,1",
    offline: Annotated[
        bool | None,
        typer.Option("--offline/--online", help="Override the profile's offline setting"),
    ] = None,
    refresh: Annotated[bool, typer.Option(help="Re-fetch sources even when cached")] = False,
    halt: Annotated[
        bool, typer.Option("--halt/--no-halt", help="Skip later layers after a stop")
    ] = True,
    out: Annotated[
        Path | None, typer.Option(help="Run directory (default: <runs_dir>/<id>)")
    ] = None,
    fmt: FormatOpt = OutputFormat.console,
    timeout: Annotated[float, typer.Option(help="HTTP timeout per request, seconds")] = 30.0,
    strict: Annotated[
        bool, typer.Option(help="Exit 1 unless the verdict is pass or pass_with_warnings")
    ] = False,
) -> None:
    """Run a task's checks on a manifest, streaming each finding as it is produced."""
    import pah.checks  # noqa: F401 - registers the check library
    from pah.core.check import CheckContext
    from pah.core.engine import Engine
    from pah.core.manifest import load_manifest
    from pah.core.policy import Outcome
    from pah.core.task import load_task
    from pah.sources import CachedHttp, ContentCache, Sources

    prof = _profile(profile, fmt)
    selected = _parse_layers(layers)
    try:
        man = load_manifest(manifest)
        task = load_task(man.task)
    except (OSError, ValueError, ValidationError) as exc:
        raise _fail(f"{manifest}: {exc}", fmt) from exc
    run_id = new_run_id(task.id)
    run_dir = out or (resolve_path(prof.runs_dir) / run_id)
    is_offline = prof.offline if offline is None else offline
    cache = ContentCache(resolve_path(prof.cache_dir))
    with (
        httpx.Client(follow_redirects=True, timeout=timeout) as client,
        _bus(run_id, fmt, run_dir / "events.jsonl") as bus,
    ):
        sources = Sources(CachedHttp(client, cache, offline=is_offline, refresh=refresh))
        ctx = CheckContext(man, task, sources, run_dir)
        bus.emit(
            EventKind.LOG,
            "run",
            f"manifest={manifest} profile={prof.name} offline={is_offline} cache={cache.root}",
        )
        record = Engine(bus, ctx, halt_on_stop=halt).run(selected)
        for name in ("record.json", "provenance.json", "events.jsonl"):
            bus.emit(EventKind.ARTIFACT, "run", str(run_dir / name), path=str(run_dir / name))
    ok = {Outcome.PASS, Outcome.PASS_WITH_WARNINGS}
    if strict and (record.verdict is None or record.verdict.outcome not in ok):
        raise typer.Exit(code=1)


@app.command()
def tasks(fmt: FormatOpt = OutputFormat.console) -> None:
    """List task specifications and how many of their checks are implemented."""
    import pah.checks  # noqa: F401
    from pah.core.check import CHECKS
    from pah.core.task import list_tasks, load_task

    rows: list[dict[str, Any]] = []
    for tid in list_tasks():
        spec = load_task(tid)
        ids = [c for layer in spec.layers.values() for c in layer]
        rows.append(
            {
                "id": tid,
                "status": spec.status,
                "families": list(spec.families),
                "claim": spec.claim,
                "checks": len(ids),
                "implemented": sum(c in CHECKS for c in ids),
            }
        )
    if fmt is OutputFormat.jsonl:
        for r in rows:
            sys.stdout.write(json.dumps(r) + "\n")
        return
    for r in rows:
        typer.echo(
            f"{r['id']:<30} {r['status']:<12} {','.join(r['families']):<18} "
            f"{r['implemented']}/{r['checks']} checks  {r['claim']}"
        )


@app.command()
def checks(fmt: FormatOpt = OutputFormat.console) -> None:
    """List registered checks by layer."""
    import pah.checks  # noqa: F401
    from pah.core.check import CHECKS

    rows = sorted(
        (
            {
                "id": c.id,
                "layer": int(c.layer),
                "title": c.title,
                "requires": list(c.requires_modules),
            }
            for c in CHECKS.values()
        ),
        key=lambda r: (r["layer"], r["id"]),
    )
    if fmt is OutputFormat.jsonl:
        for r in rows:
            sys.stdout.write(json.dumps(r) + "\n")
        return
    for r in rows:
        typer.echo(f"L{r['layer']}  {r['id']:<42} {r['title']}")


if __name__ == "__main__":
    app()
