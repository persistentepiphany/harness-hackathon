"""HADDOCK3 output (docs/EXECUTORS.md section 9).

`capri_ss.tsv` in a `<N>_caprieval` step folder lists one model per row, sorted by `score`. Model
paths are relative to that folder and may have gained a `.gz` suffix once the run was cleaned.
`path` may be the run directory (the last caprieval step is read), the step folder or the TSV.
"""

from __future__ import annotations

import csv
import gzip
import re
import shutil
from pathlib import Path

from pah.core.manifest import Manifest, PredictionInput
from pah.executors.base import Family, ParseError, Pose, PredictionSet, parser
from pah.executors.parsers._common import ParseContext, pose_id

_STEP = re.compile(r"^(\d+)_caprieval$")
_SCORES = ("score", "irmsd", "fnat", "dockq")
_GLOB = "<run_dir>/<N>_caprieval/capri_ss.tsv"


def _table(root: Path) -> Path:
    if root.is_file():
        return root
    if (root / "capri_ss.tsv").exists():
        return root / "capri_ss.tsv"
    steps = sorted(
        (int(m.group(1)), d)
        for d in root.iterdir()
        if d.is_dir() and (m := _STEP.match(d.name)) and (d / "capri_ss.tsv").exists()
    )
    if not steps:
        raise ParseError(f"haddock3: no {_GLOB} under {root}")
    return steps[-1][1] / "capri_ss.tsv"


def _model_file(ctx: ParseContext, step: Path, rel: str, pid: str) -> Path | None:
    path = (step / rel).resolve()
    if path.exists():
        return path
    gz = path.with_name(path.name + ".gz")
    if gz.exists():
        return gz
    ctx.issues.append(f"{pid}: model {rel} not found (nor {gz.name})")
    return None


def _plain(ctx: ParseContext, pid: str, path: Path) -> Path:
    """Gzipped models are written out uncompressed so every renderer can read them."""
    if not path.name.endswith(".gz"):
        return path
    out = ctx.pose_dir(pid) / path.name[: -len(".gz")]
    with gzip.open(path, "rb") as src, out.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    return out


@parser("haddock3", family=Family.DOCKING)
def parse_haddock(spec: PredictionInput, manifest: Manifest, workdir: Path) -> PredictionSet:
    ctx = ParseContext(spec, manifest, workdir, Family.DOCKING, with_ligand=False)
    root = ctx.require(ctx.source, "HADDOCK3 run")
    table = _table(root)
    step = table.parent
    with table.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader((ln for ln in fh if not ln.startswith("#")), delimiter="\t"))
    if not rows or "model" not in rows[0]:
        raise ParseError(f"haddock3: {table} has no rows or no model column")
    poses: list[Pose] = []
    for i, row in enumerate(rows):
        pid = pose_id(ctx.executor, None, "mode", i)
        source = _model_file(ctx, step, row["model"], pid)
        if source is None:
            continue
        scores: dict[str, float] = {}
        for key in _SCORES:
            value = row.get(key)
            if value not in (None, "", "-"):
                try:
                    scores[key] = float(value)
                except ValueError:
                    ctx.issues.append(f"{pid}: {key}={value!r} is not a number")
        rank = i
        rank_text = row.get("caprieval_rank")
        if rank_text and rank_text.isdigit():
            rank = int(rank_text) - 1
        poses.append(
            Pose(
                id=pid,
                executor=ctx.executor,
                family=ctx.family,
                structure=_plain(ctx, pid, source),
                sample=i,
                rank=rank,
                scores=scores,
                files=(table, source),
            )
        )
    return ctx.result(poses, {"caprieval_step": step.name})
