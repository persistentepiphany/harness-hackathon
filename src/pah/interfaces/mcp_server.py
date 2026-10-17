"""MCP server: the harness as tools and resources for agents.

    pah mcp                 # stdio, for Claude Code, agent SDKs and benchmark runners
    pah mcp --http --port 8766

Long tools (run, batch, doctor) stream one progress notification per finding or probe while
they run; the message carries the stage, gate and finding text.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from pah.config import Profile
from pah.core.events import CallbackSink, Sink
from pah.core.models import Event, EventKind
from pah.service import (
    InputError,
    RunOptions,
    check_rows,
    load_run,
    run_dir_for,
    run_doctor,
    run_manifest,
    task_rows,
)

INSTRUCTIONS = """\
Prediction assurance harness. Checks whether a co-folding or docking input or result can
support a declared claim, layer by layer (0 provenance, 1 input integrity, 2 adequacy,
3 applicability, 4 output validity, 5 output support). Layers 0 and 1 are implemented.

Typical flow: pah_list_tasks -> pah_run(manifest=...) -> read verdict, stops and warnings ->
pah_get_report(run_id) for the full Markdown report. Verdicts: pass, pass_with_warnings,
stop (the claim is not supported by these inputs), incomplete (a check could not run).
A manifest names task, proteins (uniprot, pdb_id, chain, sequence, mutations, msa), ligands
(smiles, ccd, pubchem_cid, file), receptor (pdb_id or file, chains) and model (executor,
version, checkpoint, database_snapshot, seeds). JSON Schema: resource pah://schemas/manifest.
"""

Job = Callable[[Sequence[Sink]], Any]


async def _stream(ctx: Context | None, job: Job, total: int | None) -> Any:
    """Runs a blocking harness job in a worker thread and forwards its events to the client."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Event] = asyncio.Queue()

    def forward(event: Event) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    sink = CallbackSink(forward)
    future = loop.run_in_executor(None, job, [sink])
    done = 0
    while not (future.done() and queue.empty()):
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.2)
        except TimeoutError:
            continue
        if ctx is not None and event.kind in (EventKind.FINDING, EventKind.RESULT):
            done += 1
            gate = event.data.get("gate") or event.data.get("status") or ""
            await ctx.report_progress(done, total, f"{event.stage} {gate}: {event.message}")
    return await future


def build_server(profile: Profile) -> MCPServer:
    server = MCPServer(name="pah", title="Prediction assurance harness", instructions=INSTRUCTIONS)

    @server.tool(description="List task specifications with their claims and implemented checks.")
    def pah_list_tasks() -> list[dict[str, Any]]:
        return task_rows()

    @server.tool(description="List registered checks with layer, title and required modules.")
    def pah_list_checks() -> list[dict[str, Any]]:
        return check_rows()

    @server.tool(
        description="Run a task's checks on a manifest (inline object or path). Streams one "
        "progress notification per finding. Returns verdict, stops, warnings and report paths."
    )
    async def pah_run(
        ctx: Context,
        manifest: dict[str, Any] | None = None,
        manifest_path: str | None = None,
        layers: list[int] | None = None,
        offline: bool | None = None,
        report: bool = True,
    ) -> dict[str, Any]:
        source: Any = manifest if manifest is not None else manifest_path
        if source is None:
            raise ValueError("give manifest or manifest_path")
        options = RunOptions(layers=tuple(layers or (0, 1)), offline=offline, report=report)
        total = _check_total(source, options.layers)
        result = await _stream(
            ctx, lambda sinks: run_manifest(source, profile, options, sinks), total
        )
        return result.summary()  # type: ignore[no-any-return]

    @server.tool(
        description="Run several manifests (a batch spec path or a list of manifest paths) and "
        "write a comparative batch report. Streams progress per finding."
    )
    async def pah_batch(
        ctx: Context,
        batch_path: str | None = None,
        manifest_paths: list[str] | None = None,
        name: str = "batch",
        layers: list[int] | None = None,
        halt: bool = True,
    ) -> dict[str, Any]:
        from pah.batch import BatchSpec, load_batch_spec, run_batch

        if batch_path:
            spec = load_batch_spec(Path(batch_path))
        elif manifest_paths:
            spec = BatchSpec(
                name=name,
                targets=[Path(p) for p in manifest_paths],
                layers=tuple(layers or (0, 1)),
                halt=halt,
            )
        else:
            raise ValueError("give batch_path or manifest_paths")
        result = await _stream(ctx, lambda sinks: run_batch(spec, profile, sinks), None)
        return result.summary()  # type: ignore[no-any-return]

    @server.tool(
        description="Check reachability of data sources, tools, executor weights and skills."
    )
    async def pah_doctor(ctx: Context, categories: list[str] | None = None) -> dict[str, Any]:
        report = await _stream(ctx, lambda sinks: run_doctor(profile, categories, sinks), None)
        not_ok = [r.model_dump(mode="json") for r in report.results if r.status.value != "ok"]
        return {"run_id": report.run_id, "counts": report.counts(), "not_ok": not_ok}

    @server.tool(description="Return the Markdown or JSON report of a run or batch by id.")
    def pah_get_report(run_id: str, format: str = "md") -> str:
        return _read_report(profile, run_id, format)

    @server.tool(description="Return findings of a run, optionally filtered by layer and gate.")
    def pah_get_findings(
        run_id: str, layer: int | None = None, gate: str | None = None
    ) -> list[dict[str, Any]]:
        record = load_run(profile, run_id)
        return [
            f.model_dump(mode="json")
            for f in record.findings
            if (layer is None or int(f.layer) == layer) and (gate is None or f.gate.value == gate)
        ]

    @server.resource("pah://runs/{run_id}/report.md", mime_type="text/markdown")
    def run_report_md(run_id: str) -> str:
        return _read_report(profile, run_id, "md")

    @server.resource("pah://runs/{run_id}/record.json", mime_type="application/json")
    def run_record(run_id: str) -> str:
        return load_run(profile, run_id).model_dump_json(indent=2)

    @server.resource("pah://tasks/{task_id}", mime_type="application/json")
    def task_spec(task_id: str) -> str:
        rows = {r["id"]: r for r in task_rows()}
        if task_id not in rows:
            raise ValueError(f"unknown task {task_id!r}")
        return json.dumps(rows[task_id], indent=2)

    @server.resource("pah://schemas/{name}", mime_type="application/schema+json")
    def schema(name: str) -> str:
        from pah.schemas import MODELS
        from pah.schemas import schema as build

        if name not in MODELS:
            raise ValueError(f"unknown schema {name!r}; one of {sorted(MODELS)}")
        return json.dumps(build(name), indent=2)

    return server


def _check_total(source: Any, layers: tuple[int, ...]) -> int | None:
    from pah.core.task import load_task
    from pah.service import manifest_from

    try:
        task = load_task(manifest_from(source).task)
    except (InputError, OSError, ValueError):
        return None
    return len(task.checks(layers))


def _read_report(profile: Profile, run_id: str, fmt: str) -> str:
    if fmt not in ("md", "json"):
        raise ValueError("format must be md or json")
    d = run_dir_for(profile, run_id)
    for name in (f"report.{fmt}", f"batch_report.{fmt}"):
        if (d / name).is_file():
            return (d / name).read_text()
    raise InputError(f"no report for {run_id!r}; run with report=True or call `pah report`")
