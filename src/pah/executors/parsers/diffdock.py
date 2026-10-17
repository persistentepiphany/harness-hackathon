"""DiffDock / DiffDock-L output (docs/EXECUTORS.md section 8).

Layout: `OUT/<complex_name>/rank<k>_confidence<c>.sdf`, sorted by confidence (`c` may be
negative). `rank1.sdf` is a copy of the top pose and is skipped. Rank and confidence come only from
the file name; the score key is `diffdock_confidence`.
"""

from __future__ import annotations

import re
from pathlib import Path

from pah.core.manifest import Manifest, PredictionInput
from pah.executors.base import Family, ParseError, Pose, PredictionSet, parser
from pah.executors.parsers._common import ParseContext, pose_id

_POSE = re.compile(r"^rank(\d+)_confidence(-?\d+(?:\.\d+)?)\.sdf$")
_GLOB = "<complex_name>/rank<k>_confidence<c>.sdf"


def _has_poses(d: Path) -> bool:
    return any(_POSE.match(p.name) for p in d.iterdir() if p.is_file())


def _complex_dir(ctx: ParseContext, root: Path) -> Path:
    if _has_poses(root):
        return root
    dirs = sorted(d for d in root.iterdir() if d.is_dir() and _has_poses(d))
    if len(dirs) > 1 and ctx.spec.ligand is not None:
        named = [d for d in dirs if d.name == ctx.spec.ligand]
        if len(named) == 1:
            return named[0]
    if len(dirs) > 1:
        raise ParseError(
            f"diffdock: {root} holds several complexes {[d.name for d in dirs]}; "
            "point path at OUT/<complex_name>"
        )
    if not dirs:
        raise ParseError(f"diffdock: no {_GLOB} under {root}")
    return dirs[0]


@parser("diffdock", family=Family.DOCKING)
def parse_diffdock(spec: PredictionInput, manifest: Manifest, workdir: Path) -> PredictionSet:
    from rdkit import Chem

    ctx = ParseContext(spec, manifest, workdir, Family.DOCKING)
    root = ctx.require(ctx.source, "output directory")
    if not root.is_dir():
        raise ParseError(f"diffdock: {root} is not a directory; expected {_GLOB}")
    d = _complex_dir(ctx, root)
    receptor = ctx.receptor()
    seed = ctx.seeds_for(1)[0]
    found = sorted(
        (int(m.group(1)), float(m.group(2)), p) for p in d.iterdir() if (m := _POSE.match(p.name))
    )
    poses: list[Pose] = []
    for k, confidence, path in found:
        pid = pose_id(ctx.executor, seed, "mode", k - 1)
        mol = next(iter(Chem.SDMolSupplier(str(path), sanitize=False, removeHs=False)), None)
        if mol is None:
            ctx.issues.append(f"{pid}: RDKit could not read {path.name}")
            continue
        poses.append(
            ctx.docking_pose(
                pid=pid,
                mol=mol,
                receptor=receptor,
                seed=seed,
                sample=k - 1,
                rank=k - 1,
                scores={"diffdock_confidence": confidence},
                files=[path],
            )
        )
    return ctx.result(poses, {"complex_name": d.name})
