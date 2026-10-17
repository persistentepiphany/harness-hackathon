"""Chai-1 output (docs/EXECUTORS.md section 4).

Layout: `OUTPUT_DIR/pred.model_idx_<i>.cif` with `scores.model_idx_<i>.npz`. `<i>` is the diffusion
sample index and is not rank ordered, so poses are ranked here by `aggregate_score`, highest first.
pLDDT comes from the CIF B-factors (100 x pLDDT). One seed per run; several runs may sit in
`seed_<n>/` folders.
"""

from __future__ import annotations

import re
from pathlib import Path

from pah.core.manifest import Manifest, PredictionInput
from pah.executors.base import Family, ParseError, Pose, PredictionSet, parser
from pah.executors.parsers._common import ParseContext, pose_id, seed_dirs

_MODEL = re.compile(r"^pred\.model_idx_(\d+)\.cif$")
_GLOB = "pred.model_idx_<i>.cif"
_SCALARS = ("aggregate_score", "ptm", "iptm", "has_inter_chain_clashes")


def _scores(npz: Path) -> dict[str, float]:
    import numpy as np

    out: dict[str, float] = {}
    with np.load(npz) as data:
        for key in _SCALARS:
            if key in data:
                arr = np.asarray(data[key]).ravel()
                if arr.size == 1:
                    out[key] = float(arr[0])
    return out


def _run_poses(ctx: ParseContext, seed: int | None, d: Path) -> list[Pose]:
    found: list[tuple[int, Path, Path, dict[str, float]]] = []
    for structure in sorted(d.glob("pred.model_idx_*.cif")):
        m = _MODEL.match(structure.name)
        if not m:
            continue
        i = int(m.group(1))
        npz = ctx.require(d / f"scores.model_idx_{i}.npz", "scores npz")
        found.append((i, structure, npz, _scores(npz)))
    order = sorted(found, key=lambda f: (-f[3].get("aggregate_score", float("-inf")), f[0]))
    rank_of = {f[0]: r for r, f in enumerate(order)}
    missing = [f[0] for f in found if "aggregate_score" not in f[3]]
    if missing:
        ctx.issues.append(f"{d.name}: aggregate_score missing for model_idx {missing}")
    return [
        ctx.cofolding_pose(
            pid=pose_id(ctx.executor, seed, "sample", i),
            structure=structure,
            seed=seed,
            sample=i,
            rank=rank_of[i],
            scores=scores,
            files=[structure, npz],
        )
        for i, structure, npz, scores in found
    ]


@parser("chai1", family=Family.COFOLDING)
def parse_chai(spec: PredictionInput, manifest: Manifest, workdir: Path) -> PredictionSet:
    ctx = ParseContext(spec, manifest, workdir, Family.COFOLDING)
    root = ctx.require(ctx.source, "output directory")
    if not root.is_dir():
        raise ParseError(f"chai1: {root} is not a directory; expected {_GLOB}")
    runs: list[tuple[int | None, Path]] = list(seed_dirs(root))
    if not runs:
        runs = [(ctx.seeds_for(1)[0], root)]
    poses = [p for seed, d in runs for p in _run_poses(ctx, seed, d)]
    if not poses:
        raise ParseError(f"chai1: no {_GLOB} under {root}")
    if any(d.is_dir() and d.name.startswith("trunk_") for d in root.iterdir()):
        ctx.issues.append(f"{root.name}: trunk_<t> folders present and not read")
    return ctx.result(poses)
