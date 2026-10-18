import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pah.api.adapter import ui_record
from pah.report import lint, write_batch_report, write_run_report
from pah.report.figures import STATS_FIGURES, stats_figures
from pah.report.html import render_html, visible_text
from pah.report.model import BatchTargetRow
from tests.conftest import FakeRenderer
from tests.synthetic import write_synthetic_run

pytest.importorskip("matplotlib")
pytest.importorskip("networkx")

STATS_FIGURE_IDS = {"seed_spread", "posebusters_grid", "interactions", "agreement", "pae"}


@pytest.fixture
def synthetic(tmp_path: Path) -> Path:
    pytest.importorskip("numpy")
    return write_synthetic_run(tmp_path / "synthetic")


def test_html_report_for_synthetic_run(synthetic: Path) -> None:
    report, issues = write_run_report(synthetic, renderer=FakeRenderer())
    assert issues == []
    html = (synthetic / "report.html").read_text()
    ui = json.loads((synthetic / "ui_record.json").read_text())
    assert ui == json.loads(json.dumps(ui_record(synthetic)))
    assert html.startswith("<!doctype html>")
    assert 'data-testid="verdict" data-state="narrowed"' in html
    for layer in ui["layers"]:
        for check in layer["checks"]:
            assert f'data-check="{check["id"]}"' in html, check["id"]
            assert f'data-state="{check["result"]}"' in html
    for source in ui["sources"]:
        assert source["sha256"][:12] in html and f'title="{source["sha256"]}"' in html
    for testid in (
        "stats-posebusters",
        "stats-physics",
        "stats-interactions",
        "stats-seeds",
        "stats-ensemble",
        "stats-agreement",
        "stats-metrics",
        "stats-sampling",
        "stats-reference",
        "stats-docking",
        "key-numbers",
        "layer-strip",
        "provenance",
        "thresholds",
        "files",
        "renders",
    ):
        assert f'data-testid="{testid}"' in html, testid
    assert 'data-layer="3" data-state="not_run"' in html
    assert "undefined 1 == 0" in html
    assert "\u2014" not in html and "\u2013" not in html
    assert "<script" not in html
    assert "@page{size:A4" in html and "break-before:page" in html
    assert {f.id for f in report.figures} >= STATS_FIGURE_IDS | {"gates_by_layer"}
    for fid in STATS_FIGURE_IDS:
        assert f'data-figure="{fid}"' in html
        for ext in ("svg", "png", "csv"):
            assert (synthetic / "figures" / f"{fid}.{ext}").is_file(), (fid, ext)
    pae = next(f for f in report.figures if f.id == "pae")
    assert pae.layer == 5 and "12 by 12 tokens" in pae.caption
    assert 'src="figures/seed_spread.svg"' in html and 'href="renders/seed0.pse"' in html


def test_visible_text_passes_style_lint(synthetic: Path, clean_run: Path) -> None:
    for run in (synthetic, clean_run):
        write_run_report(run, renderer=FakeRenderer())
        text = visible_text((run / "report.html").read_text())
        assert "Narrowed" in text
        assert lint(text) == []
        assert lint((run / "report.md").read_text()) == []


def test_clean_run_html_has_no_stats_figures(clean_run: Path) -> None:
    report, _ = write_run_report(clean_run, renderer=FakeRenderer())
    assert not {f.id for f in report.figures} & STATS_FIGURE_IDS
    assert not any((clean_run / "figures" / f"{fid}.svg").exists() for fid in STATS_FIGURE_IDS)
    html = (clean_run / "report.html").read_text()
    assert not any(f'data-testid="stats-{b}"' in html for b in ("posebusters", "seeds", "physics"))
    assert 'data-check="l1.ligand.stereo_defined" data-state="warn"' in html


def test_figures_only_for_present_blocks(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    assert stats_figures({}, tmp_path / "f", tmp_path) == ([], [])
    assert not (tmp_path / "f").exists()
    stats = {"agreement": [{"method": "A", "cells": [{"vs": "B", "value": 1.5, "unit": "Å"}]}]}
    entries, errors = stats_figures(stats, tmp_path / "f", tmp_path)
    assert [e.id for e in entries] == ["agreement"] and errors == []
    assert {block for block, _ in STATS_FIGURES} == {
        "seeds",
        "posebusters",
        "interactions",
        "agreement",
        "pae",
    }
    entries, errors = stats_figures({"pae": {"path": "missing.npy"}}, tmp_path / "f", tmp_path)
    assert entries == [] and errors and "pae" in errors[0]


def test_text_is_escaped() -> None:
    ui = {
        "id": "r<1>",
        "claim": 'x "<b>"',
        "taskName": "t",
        "inputs": {"ligand": "<img src=x>"},
        "layers": [
            {
                "i": 0,
                "key": "provenance",
                "name": "Provenance",
                "status": "done",
                "counts": {"pass": 1},
                "checks": [
                    {
                        "id": "l0.x",
                        "name": "<script>alert(1)</script>",
                        "gate": "Stop",
                        "result": "pass",
                        "evidence": "a & b",
                    }
                ],
            }
        ],
        "verdict": {"claim": "c", "outcome": "supported", "statement": "<i>s</i>"},
    }
    html = render_html(ui)
    assert "<script>alert" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x>" not in html and "a &amp; b" in html and "<i>s</i>" not in html
    assert 'data-testid="verdict" data-state="supported"' in html


def test_batch_html(synthetic: Path) -> None:
    write_run_report(synthetic, renderer=FakeRenderer())
    batch = synthetic.parent
    targets = [
        BatchTargetRow(
            name="synthetic",
            manifest="m.yaml",
            run_id="ligand_pose-synthetic",
            task="ligand_pose",
            verdict="pass_with_warnings",
            counts={"pass": 12, "warn": 2, "stop": 0, "skip": 2},
            report_path="synthetic/report.md",
        ),
        BatchTargetRow(
            name="broken", manifest="b.yaml", run_id=None, task=None, verdict=None, error="bad"
        ),
    ]
    now = datetime(2026, 10, 1, tzinfo=UTC)
    emitted: list[str] = []
    _, issues = write_batch_report(
        batch,
        batch_id="batch-1",
        name="demo",
        started_at=now,
        finished_at=now,
        pah_version="0",
        targets=targets,
        emit=lambda p, k, label: emitted.append(p.name),
    )
    assert issues == [] and "batch_report.html" in emitted
    html = (batch / "batch_report.html").read_text()
    assert 'data-target="synthetic" data-state="narrowed"' in html
    assert 'href="synthetic/report.html"' in html
    assert 'data-target="broken" data-state="not_run"' in html
    assert 'data-figure="gate_matrix"' in html
    assert lint(visible_text(html)) == []
