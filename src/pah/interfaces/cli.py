"""`pah` command line. Streams events to the console or as JSON lines for agents."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import httpx
import typer

from pah import __version__
from pah.config import available_profiles, load_profile
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


def _bus(run_id: str, fmt: OutputFormat, events_file: Path | None) -> EventBus:
    sinks: list[Sink] = [ConsoleSink() if fmt is OutputFormat.console else StdoutJsonlSink()]
    if events_file is not None:
        sinks.append(JsonlSink(events_file))
    return EventBus(run_id, sinks)


@app.command()
def version() -> None:
    """Print the harness version."""
    typer.echo(__version__)


@app.command()
def doctor(
    profile: Annotated[
        str, typer.Option(help=f"Deployment profile: {', '.join(available_profiles())}")
    ] = "local",
    only: Annotated[
        list[str] | None,
        typer.Option(
            help="Restrict to categories: sources, tools, executors, skills, infrastructure"
        ),
    ] = None,
    out: Annotated[
        Path | None, typer.Option(help="Report directory (default: <runs_dir>/<id>)")
    ] = None,
    fmt: Annotated[
        OutputFormat, typer.Option("--format", help="Stream format")
    ] = OutputFormat.console,
    timeout: Annotated[float, typer.Option(help="HTTP timeout per probe, seconds")] = 20.0,
    dry_run: Annotated[
        bool, typer.Option(help="Validate the profile and list probes only")
    ] = False,
    strict: Annotated[bool, typer.Option(help="Exit 1 if any probe is not ok")] = False,
) -> None:
    """Check reachability of sources, tools, executor code and weights, and skills."""
    from pah.doctor import Doctor, ProbeContext, build_catalog, write_report

    prof = load_profile(profile)
    run_id = new_run_id("doctor")
    out_dir = out or (prof.runs_dir / run_id)
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
        json_path, md_path = write_report(report, out_dir)
        bus.emit(EventKind.ARTIFACT, "doctor", str(json_path), path=str(json_path))
        bus.emit(EventKind.ARTIFACT, "doctor", str(md_path), path=str(md_path))
    if strict and not report.ok:
        raise typer.Exit(code=1)


def _register_subcommands() -> None:
    from pah.interfaces.cli_runtimes import app as runtimes_app

    app.add_typer(runtimes_app, name="runtimes")


_register_subcommands()


if __name__ == "__main__":
    app()
