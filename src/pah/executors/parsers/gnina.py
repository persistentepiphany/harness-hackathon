"""Gnina output (docs/EXECUTORS.md section 7).

`path` is the single SDF written by `-o` (optionally `.sdf.gz`), poses in Gnina's sort order
(`--pose_sort_order`, default CNNscore). SD tags `minimizedAffinity`, `CNNscore`, `CNNaffinity`,
`CNN_VS`, `minimizedRMSD` and `CNNaffinity_variance` become scores when present.
"""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import Any

from pah.core.manifest import Manifest, PredictionInput
from pah.executors.base import Family, ParseError, Pose, PredictionSet, parser
from pah.executors.parsers._common import ParseContext, pose_id, seed_from_name

_TAGS = (
    "minimizedAffinity",
    "minimizedRMSD",
    "CNNscore",
    "CNNaffinity",
    "CNN_VS",
    "CNNaffinity_variance",
)


def _molecules(path: Path) -> list[Any]:
    from rdkit import Chem

    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rb") as fh:
        return list(Chem.ForwardSDMolSupplier(fh, sanitize=False, removeHs=False))


def _scores(mol: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    for tag in _TAGS:
        if mol.HasProp(tag):
            try:
                out[tag] = float(mol.GetProp(tag))
            except ValueError:
                continue
    return out


@parser("gnina", family=Family.DOCKING)
def parse_gnina(spec: PredictionInput, manifest: Manifest, workdir: Path) -> PredictionSet:
    ctx = ParseContext(spec, manifest, workdir, Family.DOCKING)
    path = ctx.require(ctx.source, "Gnina output SDF")
    if not path.is_file() or not path.name.lower().endswith((".sdf", ".sdf.gz")):
        raise ParseError(f"gnina: expected one docked .sdf or .sdf.gz file, got {path}")
    receptor = ctx.receptor()
    seed = seed_from_name(path.name)
    if seed is None:
        seed = ctx.seeds_for(1)[0]
    poses: list[Pose] = []
    for i, mol in enumerate(_molecules(path)):
        pid = pose_id(ctx.executor, seed, "mode", i)
        if mol is None:
            ctx.issues.append(f"{pid}: RDKit could not read SDF record {i + 1}")
            continue
        scores = _scores(mol)
        if "minimizedAffinity" not in scores:
            ctx.issues.append(f"{pid}: SD tag minimizedAffinity missing")
        poses.append(
            ctx.docking_pose(
                pid=pid,
                mol=mol,
                receptor=receptor,
                seed=seed,
                sample=i,
                rank=i,
                scores=scores,
                files=[path],
            )
        )
    return ctx.result(poses)
