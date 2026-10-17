"""Application service. The CLI, the MCP server and the HTTP API all call these functions,
so every interface runs the same code and streams the same events."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from pah.config import Profile, resolve_path
from pah.core.engine import RunRecord
from pah.core.events import EventBus, JsonlSink, Sink, new_run_id
from pah.core.manifest import Manifest, load_manifest
from pah.core.models import ArtifactKind, EventKind
from pah.core.policy import Outcome

RUN_ID = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


class InputError(ValueError):
    """The manifest, task or run id cannot be used. Interfaces map this to exit 2 or HTTP 4xx."""


@dataclass(frozen=True)
class RunOptions:
    layers: tuple[int, ...] = (0, 1)
    offline: bool | None = None
    refresh: bool = False
    halt: bool = True
    timeout: float = 30.0
    report: bool = True


@dataclass(frozen=True)
class RunResult:
    run_id: str
    run_dir: Path
    record: RunRecord
    report_files: tuple[Path, ...] = ()
    report_error: str | None = None
    style_issues: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        v = self.record.verdict
        return v is not None and v.outcome in {Outcome.PASS, Outcome.PASS_WITH_WARNINGS}

    def summary(self) -> dict[str, Any]:
        """Compact result for agents: verdict, stops and warnings with messages, file paths."""
        v = self.record.verdict
        msgs = {f.check_id: f.message for f in self.record.findings}
        return {
            "run_id": self.run_id,
            "task": self.record.task,
            "claim": self.record.claim,
            "layers": list(self.record.layers),
            "verdict": v.outcome.value if v else None,
            "stops": [{"check": c, "message": msgs.get(c, "")} for c in (v.stops if v else ())],
            "warnings": [
                {"check": c, "message": msgs.get(c, "")} for c in (v.warnings if v else ())
            ],
            "incomplete": list(v.incomplete) if v else [],
            "counts": _counts(self.record),
            "run_dir": str(self.run_dir),
            "report_md": str(self.run_dir / "report.md") if self.report_files else None,
            "report_json": str(self.run_dir / "report.json") if self.report_files else None,
            "report_html": str(self.run_dir / "report.html") if self.report_files else None,
            "report_error": self.report_error,
        }


def _counts(record: RunRecord) -> dict[str, int]:
    out = {"pass": 0, "warn": 0, "stop": 0, "skip": 0}
    for f in record.findings:
        out[f.gate.value] += 1
    return out


def manifest_from(
    source: Manifest | Path | str | Mapping[str, Any], base_dir: Path | None = None
) -> Manifest:
    """Loads a manifest from a path, a mapping (MCP/HTTP payload) or passes one through."""
    try:
        if isinstance(source, Manifest):
            return source
        if isinstance(source, (str, Path)):
            return load_manifest(Path(source))
        data = dict(source)
        data["base_dir"] = Path(data.get("base_dir") or base_dir or Path.cwd())
        return Manifest.model_validate(data)
    except (OSError, ValueError, ValidationError) as exc:
        raise InputError(f"manifest: {exc}") from exc


def run_dir_for(profile: Profile, run_id: str) -> Path:
    if not RUN_ID.match(run_id):
        raise InputError(f"invalid run id {run_id!r}")
    return resolve_path(profile.runs_dir) / run_id


def run_manifest(
    source: Manifest | Path | str | Mapping[str, Any],
    profile: Profile,
    options: RunOptions | None = None,
    sinks: Sequence[Sink] = (),
    *,
    run_id: str | None = None,
    run_dir: Path | None = None,
    base_dir: Path | None = None,
    seq_start: int = 0,
) -> RunResult:
    import pah.checks  # noqa: F401 - registers the check library
    from pah.core.check import CheckContext
    from pah.core.engine import Engine
    from pah.core.task import load_task
    from pah.sources import CachedHttp, ContentCache, Sources

    options = options or RunOptions()
    manifest = manifest_from(source, base_dir)
    try:
        task = load_task(manifest.task)
    except (OSError, ValueError, ValidationError) as exc:
        raise InputError(f"task {manifest.task!r}: {exc}") from exc
    run_id = run_id or new_run_id(task.id)
    run_dir = run_dir or run_dir_for(profile, run_id)
    offline = profile.offline if options.offline is None else options.offline
    cache = ContentCache(resolve_path(profile.cache_dir))
    report_files: list[Path] = []
    report_error: str | None = None
    style: list[str] = []
    with (
        httpx.Client(follow_redirects=True, timeout=options.timeout) as client,
        EventBus(run_id, [*sinks, JsonlSink(run_dir / "events.jsonl")], seq_start) as bus,
    ):
        sources = Sources(CachedHttp(client, cache, offline=offline, refresh=options.refresh))
        ctx = CheckContext(manifest, task, sources, run_dir)
        bus.emit(
            EventKind.LOG, "run", f"profile={profile.name} offline={offline} cache={cache.root}"
        )
        record = Engine(bus, ctx, halt_on_stop=options.halt).run(options.layers)
        for name in ("record.json", "provenance.json"):
            bus.emit(EventKind.ARTIFACT, "run", str(run_dir / name), path=str(run_dir / name))
        if options.report:
            report_files, report_error, style = _report(run_dir, bus)
    return RunResult(run_id, run_dir, record, tuple(report_files), report_error, tuple(style))


def _report(run_dir: Path, bus: EventBus) -> tuple[list[Path], str | None, list[str]]:
    from pah.report import ReportError, write_run_report

    files: list[Path] = []

    def emit(path: Path, kind: ArtifactKind, label: str) -> None:
        files.append(path)
        bus.emit(EventKind.ARTIFACT, "report", str(path), path=str(path), artifact_kind=kind.value)

    bus.emit(EventKind.STAGE_START, "report", "renders, figures, provenance graph, markdown")
    try:
        _, issues = write_run_report(run_dir, emit=emit)
    except ReportError as exc:
        bus.emit(EventKind.STAGE_END, "report", str(exc), status="stop")
        return files, str(exc), []
    except ImportError as exc:
        bus.emit(EventKind.STAGE_END, "report", f"report extra not installed: {exc}", status="skip")
        return files, f"report extra not installed: {exc}", []
    style = [f"line {i.line}: {i.rule}: {i.text}" for i in issues]
    for s in style:
        bus.emit(EventKind.LOG, "report", f"style: {s}", status="warn")
    bus.emit(EventKind.STAGE_END, "report", f"{len(files)} files", status="ok")
    return files, None, style


def regenerate_report(path: Path, sinks: Sequence[Sink] = ()) -> list[Path]:
    """Rebuilds the report for a run or batch directory from its records only."""
    from pah.batch import rewrite_batch_report

    if (path / "batch_report.json").is_file():
        return rewrite_batch_report(path, sinks)
    if not (path / "record.json").is_file():
        raise InputError(f"{path}: no record.json or batch_report.json")
    with EventBus(f"report-{path.name}", list(sinks)) as bus:
        files, error, _ = _report(path, bus)
    if error:
        raise InputError(error)
    return files


def run_doctor(
    profile: Profile,
    categories: Sequence[str] | None = None,
    sinks: Sequence[Sink] = (),
    timeout: float = 20.0,
) -> Any:
    """Runs the reachability probes and writes doctor_report.{json,md}; returns the report."""
    from pah.doctor import Doctor, ProbeContext, build_catalog, write_report

    run_id = new_run_id("doctor")
    out_dir = resolve_path(profile.runs_dir) / run_id
    with (
        httpx.Client(follow_redirects=True, timeout=timeout) as client,
        EventBus(run_id, [*sinks, JsonlSink(out_dir / "events.jsonl")]) as bus,
    ):
        catalog = build_catalog(
            ProbeContext(client=client, profile=profile), list(categories or []) or None
        )
        report = Doctor(bus).run(catalog, profile.name)
        write_report(report, out_dir)
    return report


def task_rows() -> list[dict[str, Any]]:
    import pah.checks  # noqa: F401
    from pah.core.check import CHECKS
    from pah.core.task import list_tasks, load_task

    rows = []
    for tid in list_tasks():
        spec = load_task(tid)
        ids = [c for layer in spec.layers.values() for c in layer]
        rows.append(
            {
                "id": tid,
                "title": spec.title,
                "status": spec.status,
                "families": list(spec.families),
                "claim": spec.claim,
                "required_inputs": list(spec.required_inputs),
                "checks": len(ids),
                "implemented": sum(c in CHECKS for c in ids),
                "layers": {str(k): list(v) for k, v in spec.layers.items()},
            }
        )
    return rows


def check_rows() -> list[dict[str, Any]]:
    import pah.checks  # noqa: F401
    from pah.core.check import CHECKS

    return sorted(
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


def load_run(profile: Profile, run_id: str) -> RunRecord:
    path = run_dir_for(profile, run_id) / "record.json"
    if not path.is_file():
        raise InputError(f"no run {run_id!r} under {path.parent.parent}")
    return RunRecord.model_validate_json(path.read_text())


@dataclass
class EventLog:
    """In-memory event list used by the HTTP API and MCP to replay and follow a run."""

    events: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False


def dock_manifest(
    source: Path,
    profile: Profile,
    out_dir: Path,
    *,
    seeds: Sequence[int] = (0, 1, 2, 3, 4),
    exhaustiveness: int = 8,
    redock: bool = True,
    offline: bool | None = None,
    sinks: Sequence[Sink] = (),
) -> Path:
    """Docks the manifest ligand with local Vina and writes `<out_dir>/manifest.yaml` with the
    outputs declared as predictions (and, with `redock`, the crystal ligand redocked as the
    redocking control). Returns the path of the new manifest."""
    import os

    import yaml

    from pah.checks import outputs
    from pah.core.check import CheckContext
    from pah.core.task import load_task
    from pah.executors.vina_local import box_from_reference, run_vina
    from pah.sources import CachedHttp, ContentCache, Sources

    manifest = manifest_from(source)
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = ContentCache(resolve_path(profile.cache_dir))
    is_offline = profile.offline if offline is None else offline
    with (
        httpx.Client(follow_redirects=True, timeout=30.0) as client,
        EventBus(f"dock-{out_dir.name}", [*sinks, JsonlSink(out_dir / "events.jsonl")]) as bus,
    ):
        ctx = CheckContext(
            manifest,
            load_task(manifest.task),
            Sources(CachedHttp(client, cache, offline=is_offline)),
            out_dir,
        )
        receptor = outputs.receptor_path(ctx)
        if receptor is None:
            raise InputError("dock: no receptor file or reference entry in the manifest")
        ref = outputs.reference_ligand(ctx)
        if manifest.docking_box:
            center, size = list(manifest.docking_box.center), list(manifest.docking_box.size)
            origin = manifest.docking_box.origin
        elif ref is not None:
            center, size = box_from_reference(ref.coords)
            origin = f"{ref.code} in {ref.source} extent + 4 Å"
        else:
            raise InputError("dock: no docking box and no reference ligand to derive one")

        def log(msg: str) -> None:
            bus.emit(EventKind.LOG, "dock", msg)

        bus.emit(EventKind.STAGE_START, "dock", f"vina, {len(seeds)} seeds, box {origin}")
        run = run_vina(
            manifest,
            receptor,
            out_dir / "pose",
            center=center,
            size=size,
            box_origin=origin,
            seeds=seeds,
            exhaustiveness=exhaustiveness,
            log=log,
        )
        control = None
        if redock and ref is not None:
            cc = ctx.sources.rcsb.chemcomp(ref.code)
            smiles = cc.smiles_stereo or cc.smiles
            if smiles:
                control = run_vina(
                    manifest,
                    receptor,
                    out_dir / "redock",
                    smiles=smiles,
                    center=center,
                    size=size,
                    box_origin=origin,
                    seeds=seeds[:1],
                    exhaustiveness=exhaustiveness,
                    log=log,
                )
        bus.emit(EventKind.STAGE_END, "dock", f"{len(run.outputs)} pose files", status="ok")

    def rel(p: Path) -> str:
        return os.path.relpath(manifest.path(p) if not p.is_absolute() else p, out_dir)

    data = manifest.model_dump(mode="json", exclude_none=True)
    for lig in data.get("ligands", []):
        if "file" in lig:
            lig["file"] = rel(Path(lig["file"]))
    for prot in data.get("proteins", []):
        if "msa" in prot:
            prot["msa"] = rel(Path(prot["msa"]))
    if data.get("receptor", {}).get("file"):
        data["receptor"]["file"] = rel(Path(data["receptor"]["file"]))
    data["model"] = {
        "executor": "vina",
        "version": run.vina_version or "unknown",
        "seeds": list(seeds),
    }
    data["docking_box"] = {"center": run.center, "size": run.size, "origin": origin}
    data["predictions"] = [
        {
            "executor": "vina",
            "path": "pose",
            "role": "primary",
            "version": run.vina_version,
            "receptor": "pose/receptor_H.pdb",
            "seeds": list(seeds),
            "settings": run.settings(),
        }
    ]
    if control is not None:
        data.setdefault("controls", {})["redocking"] = {
            "executor": "vina",
            "path": "redock",
            "role": "control",
            "receptor": "redock/receptor_H.pdb",
            "seeds": list(seeds[:1]),
            "settings": control.settings(),
        }
        data.setdefault(
            "reference",
            {"pdb_id": outputs.reference_ids(ctx)[0], "ligand": ref.code if ref else None},
        )
    path = out_dir / "manifest.yaml"
    header = (
        f"# Written by `pah dock` from {source}. Vina {run.vina_version}, "
        f"exhaustiveness {exhaustiveness}, seeds {list(seeds)}.\n"
    )
    path.write_text(header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return path
