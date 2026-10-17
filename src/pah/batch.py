"""Multi-target batches: run several manifests, then write one comparative report."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pah import __version__
from pah.config import Profile, resolve_path
from pah.core.events import EventBus, Sink, new_run_id
from pah.core.models import ArtifactKind, EventKind, utcnow
from pah.report.model import BatchTargetRow
from pah.service import InputError, RunOptions, RunResult, run_manifest

SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


class BatchSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "batch"
    targets: list[Path]
    layers: tuple[int, ...] = (0, 1)
    offline: bool | None = None
    halt: bool = True
    report: bool = True
    base_dir: Path = Field(Path(), exclude=True)

    def target_paths(self) -> list[Path]:
        return [p if p.is_absolute() else self.base_dir / p for p in self.targets]


def load_batch_spec(path: Path) -> BatchSpec:
    try:
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict):
            raise ValueError("expected a mapping")
        raw["base_dir"] = path.resolve().parent
        return BatchSpec.model_validate(raw)
    except (OSError, ValueError, ValidationError) as exc:
        raise InputError(f"batch spec {path}: {exc}") from exc


def target_name(manifest: Path, taken: set[str]) -> str:
    """Directory name for a target: the manifest's folder (or stem), unique within the batch."""
    base = SAFE.sub(
        "_", manifest.parent.name if manifest.name == "manifest.yaml" else manifest.stem
    )
    name, i = base or "target", 2
    while name in taken:
        name, i = f"{base}_{i}", i + 1
    taken.add(name)
    return name


@dataclass(frozen=True)
class BatchResult:
    batch_id: str
    batch_dir: Path
    targets: tuple[BatchTargetRow, ...]
    results: tuple[RunResult, ...]
    report_files: tuple[Path, ...]

    def summary(self) -> dict[str, object]:
        return {
            "batch_id": self.batch_id,
            "batch_dir": str(self.batch_dir),
            "targets": [t.model_dump(mode="json") for t in self.targets],
            "report_md": str(self.batch_dir / "batch_report.md") if self.report_files else None,
            "report_json": str(self.batch_dir / "batch_report.json") if self.report_files else None,
        }


def run_batch(
    spec: BatchSpec,
    profile: Profile,
    sinks: Sequence[Sink] = (),
    *,
    batch_id: str | None = None,
    timeout: float = 30.0,
) -> BatchResult:
    batch_id = batch_id or new_run_id(f"batch-{SAFE.sub('_', spec.name)}")
    batch_dir = resolve_path(profile.runs_dir) / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    started = utcnow()
    options = RunOptions(
        layers=spec.layers,
        offline=spec.offline,
        halt=spec.halt,
        report=spec.report,
        timeout=timeout,
    )
    rows: list[BatchTargetRow] = []
    results: list[RunResult] = []
    taken: set[str] = set()
    paths = spec.target_paths()
    with EventBus(batch_id, list(sinks)) as bus:
        bus.emit(
            EventKind.RUN_START, "batch", f"{spec.name}: {len(paths)} targets", targets=len(paths)
        )
        for i, manifest in enumerate(paths, start=1):
            name = target_name(manifest, taken)
            bus.emit(EventKind.STAGE_START, name, f"target {i}/{len(paths)}: {manifest}")
            try:
                result = run_manifest(manifest, profile, options, sinks, run_dir=batch_dir / name)
            except Exception as exc:  # one broken target never stops the batch
                rows.append(
                    BatchTargetRow(name=name, manifest=str(manifest), run_id=None, task=None,
                                   verdict=None, error=f"{type(exc).__name__}: {exc}")
                )  # fmt: skip
                bus.emit(EventKind.STAGE_END, name, f"not run: {exc}", status="error")
                continue
            results.append(result)
            summary = result.summary()
            rows.append(
                BatchTargetRow(
                    name=name,
                    manifest=str(manifest),
                    run_id=result.run_id,
                    task=result.record.task,
                    verdict=summary["verdict"],
                    counts=summary["counts"],
                    report_path=f"{name}/report.md" if result.report_files else None,
                )
            )
            bus.emit(
                EventKind.STAGE_END,
                name,
                f"verdict={summary['verdict']}",
                status=summary["verdict"],
            )
        files = _write(batch_dir, batch_id, spec.name, started, rows, bus)
        bus.emit(EventKind.RUN_END, "batch", f"{len(results)}/{len(paths)} targets ran")
    return BatchResult(batch_id, batch_dir, tuple(rows), tuple(results), tuple(files))


def _write(
    batch_dir: Path,
    batch_id: str,
    name: str,
    started: object,
    rows: Sequence[BatchTargetRow],
    bus: EventBus,
) -> list[Path]:
    from pah.report import write_batch_report

    files: list[Path] = []

    def emit(path: Path, kind: ArtifactKind, label: str) -> None:
        files.append(path)
        bus.emit(EventKind.ARTIFACT, "batch", str(path), path=str(path), artifact_kind=kind.value)

    _, issues = write_batch_report(
        batch_dir,
        batch_id=batch_id,
        name=name,
        started_at=started,  # type: ignore[arg-type]
        finished_at=utcnow(),
        pah_version=__version__,
        targets=rows,
        emit=emit,
    )
    for i in issues:
        bus.emit(EventKind.LOG, "batch", f"style: line {i.line}: {i.rule}", status="warn")
    return files


def rewrite_batch_report(batch_dir: Path, sinks: Sequence[Sink] = ()) -> list[Path]:
    import json

    from pah.report.pipeline import load_batch_targets

    data = json.loads((batch_dir / "batch_report.json").read_text())
    rows = load_batch_targets(batch_dir)
    with EventBus(data["batch_id"], list(sinks)) as bus:
        return _write(batch_dir, data["batch_id"], data["name"], data["started_at"], rows, bus)
