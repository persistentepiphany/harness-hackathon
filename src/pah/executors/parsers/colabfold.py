"""ColabFold output (docs/EXECUTORS.md section 5).

Layout, flat in RESULTS_DIR: `<job>_unrelaxed_rank_<NNN>_<tag>_seed_<SSS>.pdb` with
`<job>_scores_rank_<NNN>_<tag>_seed_<SSS>.json`. Ranks are 1-based in the file names and stored
0-based here. The scores JSON holds per-residue `plddt` (0 to 100) and, when written, `pae`.
"""

from __future__ import annotations

import re
from pathlib import Path

from pah.core.manifest import Manifest, PredictionInput
from pah.executors.base import Family, ParseError, Pose, PredictionSet, parser
from pah.executors.parsers._common import ParseContext, floats, pose_id, read_json
from pah.executors.structure import polymer_residues

_MODEL = re.compile(
    r"^(?P<job>.+)_unrelaxed_rank_(?P<rank>\d{3})_(?P<tag>.+)_seed_(?P<seed>\d{3})\.pdb$"
)
_GLOB = "<job>_unrelaxed_rank_<NNN>_<tag>_seed_<SSS>.pdb"
_MODEL_NO = re.compile(r"model_(\d+)")
_SCALARS = ("ptm", "iptm", "max_pae", "actifptm")


@parser("colabfold", family=Family.COFOLDING)
def parse_colabfold(spec: PredictionInput, manifest: Manifest, workdir: Path) -> PredictionSet:
    ctx = ParseContext(spec, manifest, workdir, Family.COFOLDING)
    root = ctx.require(ctx.source, "results directory")
    if not root.is_dir():
        raise ParseError(f"colabfold: {root} is not a directory; expected {_GLOB}")
    matches = [
        (p, m) for p in sorted(root.glob("*_unrelaxed_rank_*.pdb")) if (m := _MODEL.match(p.name))
    ]
    jobs = {m.group("job") for _, m in matches}
    if len(jobs) > 1:
        raise ParseError(f"colabfold: {root} holds several jobs {sorted(jobs)}; expected one")
    poses: list[Pose] = []
    for structure, m in matches:
        job, rank, tag, seed = (
            m.group("job"),
            int(m.group("rank")),
            m.group("tag"),
            int(m.group("seed")),
        )
        suffix = f"rank_{m.group('rank')}_{tag}_seed_{m.group('seed')}"
        scores_json = ctx.require(root / f"{job}_scores_{suffix}.json", "scores JSON")
        data = read_json(scores_json)
        if not isinstance(data, dict):
            raise ParseError(f"colabfold: {scores_json} is not a JSON object")
        model_no = _MODEL_NO.search(tag)
        sample = int(model_no.group(1)) - 1 if model_no else rank - 1
        pid = pose_id(ctx.executor, seed, "sample", sample)
        scores = floats(data, _SCALARS)
        for key in ("ipsae", "pdockq", "pdockq2"):
            scores.update(floats({key: data[key]}) if isinstance(data.get(key), dict) else {})
        plddt: tuple[tuple[float, ...], tuple[tuple[str, int], ...]] | None = None
        values = data.get("plddt")
        residues = [key for key, _, _ in polymer_residues(structure)]
        if isinstance(values, list) and len(values) == len(residues):
            plddt = (tuple(float(v) for v in values), tuple(residues))
        else:
            n = len(values) if isinstance(values, list) else 0
            ctx.issues.append(
                f"{pid}: scores plddt has {n} values, model has {len(residues)} residues; "
                "pLDDT from B-factors"
            )
        pae: Path | None = None
        if "pae" in data:
            pae = ctx.save_pae(pid, data["pae"])
        else:
            ctx.issues.append(f"{pid}: {scores_json.name} has no pae")
        poses.append(
            ctx.cofolding_pose(
                pid=pid,
                structure=structure,
                seed=seed,
                sample=sample,
                rank=rank - 1,
                scores=scores,
                files=[structure, scores_json],
                plddt=plddt,
                pae=pae,
            )
        )
    if not poses:
        raise ParseError(f"colabfold: no {_GLOB} under {root}")
    return ctx.result(poses, {"model_tag": sorted({m.group("tag") for _, m in matches})})
