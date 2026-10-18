"""Protenix output (docs/EXECUTORS.md section 2).

Layout: `OUT/<name>/seed_<seed>/predictions/<name>_sample_<rank>.cif` with
`<name>_summary_confidence_sample_<rank>.json`. `<rank>` orders samples by `ranking_score` within a
seed. The CIF B-factor is atom pLDDT x 100; the summary `plddt` is on the same 0 to 100 scale.
"""

from __future__ import annotations

import re
from pathlib import Path

from pah.core.manifest import Manifest, PredictionInput
from pah.executors.base import Family, ParseError, Pose, PredictionSet, parser
from pah.executors.parsers._common import ParseContext, floats, pose_id, read_json

_SAMPLE = re.compile(r"^(?P<name>.+)_sample_(?P<rank>\d+)\.cif$")
_SEED = re.compile(r"^seed_(\d+)$")
_GLOB = "<name>/seed_<seed>/predictions/<name>_sample_<rank>.cif"


def _direct(root: Path) -> list[tuple[int, Path]]:
    return sorted(
        (int(m.group(1)), d)
        for d in root.iterdir()
        if d.is_dir() and (m := _SEED.match(d.name)) and (d / "predictions").is_dir()
    )


def _seed_folders(root: Path) -> list[tuple[int, Path]]:
    """`(seed, seed_<seed>)` folders whether `root` is OUT, OUT/<name> or a seed folder."""
    m = _SEED.match(root.name)
    if m and (root / "predictions").is_dir():
        return [(int(m.group(1)), root)]
    direct = _direct(root)
    if direct:
        return direct
    jobs = {d.name: s for d in root.iterdir() if d.is_dir() and (s := _direct(d))}
    if len(jobs) > 1:
        raise ParseError(
            f"protenix: {root} holds several jobs {sorted(jobs)}; point path at OUT/<name>"
        )
    return next(iter(jobs.values()), [])


@parser("protenix", family=Family.COFOLDING)
def parse_protenix(spec: PredictionInput, manifest: Manifest, workdir: Path) -> PredictionSet:
    ctx = ParseContext(spec, manifest, workdir, Family.COFOLDING)
    root = ctx.require(ctx.source, "output directory")
    if not root.is_dir():
        raise ParseError(f"protenix: {root} is not a directory; expected {_GLOB}")
    poses: list[Pose] = []
    for seed, d in _seed_folders(root):
        preds = d / "predictions"
        for structure in sorted(preds.glob("*_sample_*.cif")):
            m = _SAMPLE.match(structure.name)
            if not m:
                continue
            name, rank = m.group("name"), int(m.group("rank"))
            pid = pose_id(ctx.executor, seed, "sample", rank)
            summary = ctx.require(
                preds / f"{name}_summary_confidence_sample_{rank}.json", "summary confidence JSON"
            )
            data = read_json(summary)
            files = [structure, summary]
            full = preds / f"{name}_full_data_sample_{rank}.json"
            if full.exists():
                files.append(full)
            poses.append(
                ctx.cofolding_pose(
                    pid=pid,
                    structure=structure,
                    seed=seed,
                    sample=rank,
                    rank=rank,
                    scores=floats(data) if isinstance(data, dict) else {},
                    files=files,
                )
            )
    if not poses:
        raise ParseError(f"protenix: no {_GLOB} under {root}")
    return ctx.result(poses)
