import json
from pathlib import Path

import pytest

from pah.batch import BatchSpec, load_batch_spec, run_batch, target_name
from pah.core.events import MemorySink
from pah.core.models import EventKind
from pah.service import InputError, regenerate_report
from tests.conftest import ROOT

pytest.importorskip("matplotlib")


def _spec(tmp_path: Path) -> BatchSpec:
    bad = tmp_path / "bad" / "manifest.yaml"
    bad.parent.mkdir()
    bad.write_text("task: ligand_pose\nligands:\n  - id: x\n")
    return BatchSpec(
        name="t",
        halt=False,
        targets=[
            ROOT / "examples/3ptb_ligand_pose/manifest.yaml",
            ROOT / "examples/3ptb_faulty_inputs/manifest.yaml",
            tmp_path / "missing" / "manifest.yaml",
            bad,
        ],
    )


def test_batch_runs_every_target_and_reports(tmp_path: Path, offline_profile) -> None:  # type: ignore[no-untyped-def]
    mem = MemorySink()
    result = run_batch(_spec(tmp_path), offline_profile, [mem], batch_id="batch-test")
    names = [t.name for t in result.targets]
    assert names == ["3ptb_ligand_pose", "3ptb_faulty_inputs", "missing", "bad"]
    verdicts = {t.name: t.verdict for t in result.targets}
    assert verdicts["3ptb_ligand_pose"] == "pass_with_warnings"
    assert verdicts["3ptb_faulty_inputs"] == "stop"
    assert verdicts["missing"] is None and verdicts["bad"] is None
    assert all(t.error for t in result.targets[2:])

    d = result.batch_dir
    for name in (
        "batch_report.md",
        "batch_report.json",
        "figures/gate_matrix.svg",
        "figures/verdict_counts.svg",
    ):
        assert (d / name).is_file(), name
    assert (d / "3ptb_ligand_pose" / "report.md").is_file()
    report = json.loads((d / "batch_report.json").read_text())
    assert report["verdict_counts"] == {"pass_with_warnings": 1, "stop": 1, "not_run": 2}
    stops = {c["check_id"]: c["targets_stop"] for c in report["check_summary"]}
    assert stops["l1.msa.integrity"] == ["3ptb_faulty_inputs"]
    md = (d / "batch_report.md").read_text()
    assert "## Checks that stopped or warned" in md and "[report](3ptb_ligand_pose/report.md)" in md

    kinds = [e.kind for e in mem.events if e.run_id == "batch-test"]
    assert kinds[0] is EventKind.RUN_START and kinds[-1] is EventKind.RUN_END
    assert any(e.kind is EventKind.FINDING for e in mem.events if e.run_id != "batch-test")

    regenerated = regenerate_report(d)
    assert any(p.name == "batch_report.md" for p in regenerated)


def test_target_names_are_unique() -> None:
    taken: set[str] = set()
    a = target_name(Path("x/1ABC/manifest.yaml"), taken)
    b = target_name(Path("y/1ABC/manifest.yaml"), taken)
    c = target_name(Path("z/run one.yaml"), taken)
    assert (a, b, c) == ("1ABC", "1ABC_2", "run_one")


def test_load_batch_spec_resolves_relative_paths() -> None:
    spec = load_batch_spec(ROOT / "examples/batches/validation.yaml")
    paths = spec.target_paths()
    assert len(paths) == 10 and all(p.is_file() for p in paths)


def test_load_batch_spec_errors(tmp_path: Path) -> None:
    bad = tmp_path / "b.yaml"
    bad.write_text("targets: 3\n")
    with pytest.raises(InputError):
        load_batch_spec(bad)
