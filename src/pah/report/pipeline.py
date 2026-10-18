"""Writes reports into run and batch directories, announcing each file as it is written."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from pah.api.adapter import ui_outcome, ui_record
from pah.core.engine import RunRecord
from pah.core.models import Artifact, ArtifactKind
from pah.report import figures as figs
from pah.report.builder import build_batch_report, build_run_report
from pah.report.graph import write_graph
from pah.report.html import render_batch_html, render_html, visible_text
from pah.report.markdown import batch_markdown, run_markdown
from pah.report.model import BatchReport, BatchTargetRow, RunReport
from pah.report.renders import (
    Renderer,
    RenderResult,
    figure_entries,
    render_structures,
    require_renders,
)
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

    def announce(r: RenderResult) -> None:
        for png in r.pngs.values():
            note(png, ArtifactKind.RENDER, r.structure.label)
        if r.session:
            note(r.session, ArtifactKind.SESSION, r.structure.label)

    # Each structure's files are announced as soon as it is rendered: a run with many poses
    # spends minutes here, and a client following events.jsonl sees progress throughout.
    results = render_structures(record, run_dir, renderer, on_result=announce) if render else []
    require_renders(record, results)
    figure = figs.gates_by_layer(record, run_dir / "figures", run_dir)
    note(run_dir / figure.path, ArtifactKind.FIGURE, figure.id)
    if figure.data_path:
        note(run_dir / figure.data_path, ArtifactKind.DATA, figure.id)
    ui = ui_record(run_dir)
    stats_figs, figure_errors = figs.stats_figures(ui["stats"], run_dir / "figures", run_dir)
    for f in stats_figs:
        note(run_dir / f.path, ArtifactKind.FIGURE, f.id)
        if f.data_path:
            note(run_dir / f.data_path, ArtifactKind.DATA, f.id)
    graph = write_graph(record, run_dir)
    for p in graph.values():
        note(p, ArtifactKind.GRAPH, "provenance graph")
    try:
        title = load_task(record.task).title
    except (OSError, ValueError):
        title = record.task
    ui_path = run_dir / "ui_record.json"
    ui_path.write_text(json.dumps(ui, indent=2))
    emit(ui_path, ArtifactKind.REPORT, "ui record")
    report = build_run_report(
        record,
        task_title=title,
        figures=[figure, *stats_figs, *figure_entries(results, run_dir)],
        graph={k: str(p.relative_to(run_dir)) for k, p in graph.items()},
        extra_artifacts=produced,
        render_errors=[
            *(f"{r.structure.path}: {r.error}" for r in results if r.error),
            *figure_errors,
        ],
    )
    md = run_markdown(report, ui)
    (run_dir / "report.md").write_text(md)
    emit(run_dir / "report.md", ArtifactKind.REPORT, "markdown")
    page = render_html(
        ui,
        figures=report.figures,
        files=report.artifacts,
        limitations=report.limitations,
        errors=report.render_errors,
    )
    (run_dir / "report.html").write_text(page)
    emit(run_dir / "report.html", ArtifactKind.REPORT, "html")
    (run_dir / "report.json").write_text(report.model_dump_json(indent=2))
    emit(run_dir / "report.json", ArtifactKind.REPORT, "json")
    return report, [*lint(md), *lint(visible_text(page))]


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
    outcomes = {t.name: ui_outcome(t.verdict) for t in report.targets if t.verdict}
    links = {
        t.name: f"{t.name}/report.html"
        for t in report.targets
        if (batch_dir / t.name / "report.html").is_file()
    }
    page = render_batch_html(report, outcomes=outcomes, links=links, figures=figures)
    (batch_dir / "batch_report.html").write_text(page)
    emit(batch_dir / "batch_report.html", ArtifactKind.REPORT, "html")
    (batch_dir / "batch_report.json").write_text(report.model_dump_json(indent=2))
    emit(batch_dir / "batch_report.json", ArtifactKind.REPORT, "json")
    return report, [*lint(md), *lint(visible_text(page))]


def load_batch_targets(batch_dir: Path) -> list[BatchTargetRow]:
    data = json.loads((batch_dir / "batch_report.json").read_text())
    return [BatchTargetRow.model_validate(t) for t in data["targets"]]
