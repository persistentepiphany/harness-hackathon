"""Files computed from a pose go under <run>/derived/, never into the executor's output tree."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pah.checks import outputs

FIXTURE = Path(__file__).parent / "fixtures" / "sources" / "3PTB.cif"


def _ctx_pose(tmp_path: Path, pose_id: str) -> tuple[Any, Any, Path]:
    executor_out = tmp_path / "executor" / "seed_1"
    executor_out.mkdir(parents=True)
    structure = executor_out / "model_0.cif"
    shutil.copy(FIXTURE, structure)
    ctx = SimpleNamespace(run_dir=tmp_path / "run")
    return ctx, SimpleNamespace(id=pose_id, structure=structure), executor_out


def test_derived_path_is_under_run_and_unique_per_structure(tmp_path: Path) -> None:
    ctx, pose, _ = _ctx_pose(tmp_path, "boltz2/seed1/sample0")
    other = SimpleNamespace(id=pose.id, structure=tmp_path / "elsewhere" / "model_0.cif")
    a = outputs.derived_path(ctx, pose, "_minimised.json")
    b = outputs.derived_path(ctx, other, "_minimised.json")
    assert a.parent == ctx.run_dir / "derived"
    assert a.name.startswith("boltz2_seed1_sample0_") and a.name.endswith("_minimised.json")
    assert a != b


def test_receptor_of_writes_protein_only_pdb_under_run(tmp_path: Path) -> None:
    pytest.importorskip("gemmi")
    ctx, pose, executor_out = _ctx_pose(tmp_path, "boltz2/seed1/sample0")
    out = outputs.receptor_of(ctx, pose)
    assert out.is_file() and out.parent == ctx.run_dir / "derived"
    assert sorted(p.name for p in executor_out.iterdir()) == ["model_0.cif"]
    text = out.read_text()
    assert "BEN" not in text and "HOH" not in text
    assert outputs.receptor_of(ctx, pose) == out
