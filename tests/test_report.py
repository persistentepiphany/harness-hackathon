import json
from pathlib import Path

import pytest

from pah.core.engine import RunRecord
from pah.core.models import Artifact, ArtifactKind
from pah.report import ReportError, lint, write_run_report
from pah.report.graph import build_graph, to_mermaid
from pah.report.renders import require_renders
from tests.conftest import FakeRenderer

pytest.importorskip("matplotlib")
pytest.importorskip("networkx")


def test_run_report_files_and_content(clean_run: Path) -> None:
    emitted: list[tuple[str, str]] = []
    report, issues = write_run_report(
        clean_run,
        renderer=FakeRenderer(),
        emit=lambda p, k, _label: emitted.append((p.name, k.value)),
    )
    assert issues == []
    for name in ("report.md", "report.json", "graph.json", "graph.mmd", "graph.svg"):
        assert (clean_run / name).is_file(), name
    assert (clean_run / "figures" / "gates_by_layer.svg").is_file()
    assert (clean_run / "figures" / "gates_by_layer.csv").read_text().startswith("layer,pass")
    assert ("report.md", "report") in emitted and ("3PTB_overview.png", "render") in emitted

    record = RunRecord.model_validate_json((clean_run / "record.json").read_text())
    in_report = {f.check_id for s in report.sections for f in s.findings}
    assert in_report == {f.check_id for f in record.findings}
    assert {f.id for f in report.figures} >= {
        "gates_by_layer",
        "render_3PTB_overview",
        "render_3PTB_pocket",
    }
    data = json.loads((clean_run / "report.json").read_text())
    assert data["schema_version"] == "1" and data["verdict"]["outcome"] == "pass_with_warnings"

    md = (clean_run / "report.md").read_text()
    for heading in (
        "## Summary",
        "## Inputs",
        "## Results by layer",
        "## Figures",
        "## Provenance",
        "## Limitations",
        "## Files",
        "### Thresholds",
    ):
        assert heading in md, heading
    assert "l1.ligand.stereo_defined" in md and "P00760" in md


def test_report_is_deterministic_apart_from_files(clean_run: Path) -> None:
    first, _ = write_run_report(clean_run, renderer=FakeRenderer())
    second, _ = write_run_report(clean_run, renderer=FakeRenderer())
    assert first.sections == second.sections and first.provenance == second.provenance


def test_graph_has_every_source_and_finding(clean_run: Path) -> None:
    record = RunRecord.model_validate_json((clean_run / "record.json").read_text())
    g = build_graph(record)
    kinds = [n["kind"] for n in g.nodes.values()]
    assert kinds.count("source") == len(record.provenance)
    assert kinds.count("check") == len(record.findings)
    assert any(r == "used" for _, _, r in g.edges) and any(r == "produced" for _, _, r in g.edges)
    mmd = to_mermaid(g, "t")
    assert mmd.startswith("flowchart LR") and "accTitle" in mmd


def test_prediction_without_render_fails_report(clean_run: Path) -> None:
    record = RunRecord.model_validate_json((clean_run / "record.json").read_text())
    pred = Artifact(
        path="pred/model_0.cif",
        kind=ArtifactKind.PREDICTION_STRUCTURE,
        sha256="0" * 64,
        size_bytes=1,
    )
    record = record.model_copy(update={"artifacts": [*record.artifacts, pred]})
    with pytest.raises(ReportError, match="without PyMOL renders"):
        require_renders(record, [])


def test_render_failure_is_recorded_not_fatal(clean_run: Path) -> None:
    class Broken:
        def render(self, structure, ligands, out_stem):  # type: ignore[no-untyped-def]
            raise RuntimeError("pymol crashed")

    report, _ = write_run_report(clean_run, renderer=Broken())
    assert report.render_errors and "pymol crashed" in report.render_errors[0]
    assert (clean_run / "report.md").is_file()


def test_real_pymol_render(clean_run: Path) -> None:
    pytest.importorskip("pymol")
    report, _ = write_run_report(clean_run)
    assert not report.render_errors
    png = clean_run / "renders" / "3PTB_pocket.png"
    assert png.stat().st_size > 10_000 and (clean_run / "renders" / "3PTB.pse").is_file()


def test_style_lint_rules() -> None:
    bad = "Additionally the result is crucial — see.\n- **Label**: text\n```\ndelve\n```\n`crucial`"
    rules = {i.rule for i in lint(bad)}
    assert rules == {"word:additionally", "dash", "bold_label"}


def test_readme_passes_style_lint() -> None:
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    assert lint(readme) == []
