"""Writes reports into run and batch directories, announcing each file as it is written."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from pah.core.engine import RunRecord
from pah.core.models import Artifact, ArtifactKind
from pah.report import figures as figs
from pah.report.builder import build_batch_report, build_run_report
from pah.report.graph import write_graph
from pah.report.markdown import batch_markdown, run_markdown
from pah.report.model import BatchReport, BatchTargetRow, RunReport
from pah.report.renders import Renderer, figure_entries, render_structures, require_renders
from pah.report.style import StyleIssue, lint

Emit = Callable[[Path, ArtifactKind, str], None]


def _noop(path: Path, kind: ArtifactKind, label: str) -> None:
    return None


def load_record(run_dir: Path) -> RunRecord:
    return RunRecord.model_validate_json((run_dir / "record.json").read_text())


def _artifact(path: Path, kind: ArtifactKind, run_dir: Path, label: str = "") -> Artifact:
    data = path.read_bytes()
    return Artifact(
        path=str(path.relative_to(run_dir)),
        kind=kind,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        label=label,
    )


def write_run_report(
    run_dir: Path,
    *,
    emit: Emit = _noop,
    renderer: Renderer | None = None,
    render: bool = True,
) -> tuple[RunReport, list[StyleIssue]]:
    """Reads only record.json and the files it lists.

    Raises ReportError when a mandatory rule (renders for predictions) fails.
    """
    import pah.checks  # noqa: F401 - check titles
    from pah.core.task import load_task

    record = load_record(run_dir)
    produced: list[Artifact] = []

    def note(path: Path, kind: ArtifactKind, label: str = "") -> None:
        produced.append(_artifact(path, kind, run_dir, label))
        emit(path, kind, label)

    results = render_structures(record, run_dir, renderer) if render else []
    require_renders(record, results)
    for r in results:
        for png in r.pngs.values():
            note(png, ArtifactKind.RENDER, r.structure.label)
        if r.session:
            note(r.session, ArtifactKind.SESSION, r.structure.label)
    figure = figs.gates_by_layer(record, run_dir / "figures", run_dir)
    note(run_dir / figure.path, ArtifactKind.FIGURE, figure.id)
    if figure.data_path:
        note(run_dir / figure.data_path, ArtifactKind.DATA, figure.id)
    graph = write_graph(record, run_dir)
    for p in graph.values():
        note(p, ArtifactKind.GRAPH, "provenance graph")
    try:
        title = load_task(record.task).title
    except (OSError, ValueError):
        title = record.task
    report = build_run_report(
        record,
        task_title=title,
        figures=[figure, *figure_entries(results, run_dir)],
        graph={k: str(p.relative_to(run_dir)) for k, p in graph.items()},
        extra_artifacts=produced,
        render_errors=[f"{r.structure.path}: {r.error}" for r in results if r.error],
    )
    md = run_markdown(report)
    (run_dir / "report.md").write_text(md)
    emit(run_dir / "report.md", ArtifactKind.REPORT, "markdown")
    (run_dir / "report.json").write_text(report.model_dump_json(indent=2))
    emit(run_dir / "report.json", ArtifactKind.REPORT, "json")
    return report, lint(md)


def write_batch_report(
    batch_dir: Path,
    *,
    batch_id: str,
    name: str,
    started_at: datetime,
    finished_at: datetime,
    pah_version: str,
    targets: Sequence[BatchTargetRow],
    emit: Emit = _noop,
) -> tuple[BatchReport, list[StyleIssue]]:
    records = {
        t.name: load_record(batch_dir / t.name)
        for t in targets
        if t.run_id and (batch_dir / t.name / "record.json").is_file()
    }
    base = build_batch_report(
        batch_id=batch_id,
        name=name,
        started_at=started_at,
        finished_at=finished_at,
        pah_version=pah_version,
        targets=targets,
        records=records,
    )
    fig_dir = batch_dir / "figures"
    figures = [
        figs.gate_matrix(base, fig_dir, batch_dir),
        figs.verdict_counts(base, fig_dir, batch_dir),
    ]
    for f in figures:
        emit(batch_dir / f.path, ArtifactKind.FIGURE, f.id)
    report = base.model_copy(update={"figures": tuple(figures)})
    md = batch_markdown(report)
    (batch_dir / "batch_report.md").write_text(md)
    emit(batch_dir / "batch_report.md", ArtifactKind.REPORT, "markdown")
    (batch_dir / "batch_report.json").write_text(report.model_dump_json(indent=2))
    emit(batch_dir / "batch_report.json", ArtifactKind.REPORT, "json")
    return report, lint(md)


def load_batch_targets(batch_dir: Path) -> list[BatchTargetRow]:
    data = json.loads((batch_dir / "batch_report.json").read_text())
    return [BatchTargetRow.model_validate(t) for t in data["targets"]]
