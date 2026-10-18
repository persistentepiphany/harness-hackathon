"""Boltz-1 / Boltz-2 output (docs/EXECUTORS.md section 1).

Layout: `OUT/boltz_results_<stem>/predictions/<name>/<name>_model_<k>.cif`, with
`confidence_<name>_model_<k>.json`, `plddt_<name>_model_<k>.npz` (key `plddt`, 0 to 1),
optional `pae_<name>_model_<k>.npz` (key `pae`) and optional `affinity_<name>.json`. `<k>` is the
rank by `confidence_score`. One seed per invocation; several runs may sit in `seed_<n>/` folders.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pah.core.manifest import Manifest, PredictionInput
from pah.executors.base import Family, ParseError, Pose, PredictionSet, parser
from pah.executors.parsers._common import ParseContext, floats, pose_id, read_json, seed_dirs
from pah.executors.structure import token_residues

_MODEL = re.compile(r"^(?P<name>.+)_model_(?P<k>\d+)\.(?:cif|pdb)$")
_GLOB = "boltz_results_<stem>/predictions/<name>/<name>_model_<k>.cif"
_AFFINITY_KEYS = (
    "affinity_pred_value",
    "affinity_probability_binary",
    "affinity_pred_value1",
    "affinity_probability_binary1",
    "affinity_pred_value2",
    "affinity_probability_binary2",
)


def _is_prediction_dir(d: Path) -> bool:
    return any(_MODEL.match(p.name) for p in d.iterdir() if p.is_file())


def _prediction_dirs(root: Path) -> list[Path]:
    """`predictions/<name>` folders under OUT, `boltz_results_<stem>` or the folder itself."""
    if not root.is_dir():
        return []
    if _is_prediction_dir(root):
        return [root]
    found: list[Path] = []
    preds = root / "predictions"
    if preds.is_dir():
        found.extend(sorted(d for d in preds.iterdir() if d.is_dir() and _is_prediction_dir(d)))
    for res in sorted(root.glob("boltz_results_*")):
        if res.is_dir():
            found.extend(_prediction_dirs(res))
    return found


def _runs(ctx: ParseContext, root: Path) -> list[tuple[int | None, Path]]:
    by_seed = seed_dirs(root)
    if by_seed:
        runs: list[tuple[int | None, Path]] = []
        for seed, d in by_seed:
            dirs = _prediction_dirs(d)
            if len(dirs) > 1:
                raise ParseError(
                    f"boltz: {d} holds {len(dirs)} predictions/<name> folders; expected one"
                )
            runs.extend((seed, p) for p in dirs)
        return runs
    dirs = _prediction_dirs(root)
    names = {p.name for p in dirs}
    if len(names) > 1:
        raise ParseError(
            f"boltz: {root} holds predictions for several records {sorted(names)}; "
            "point path at one predictions/<name> folder"
        )
    return list(zip(ctx.seeds_for(len(dirs)), dirs, strict=True))


def _plddt(
    ctx: ParseContext, pid: str, structure: Path, npz: Path
) -> tuple[tuple[float, ...], tuple[tuple[str, int], ...]]:
    import numpy as np

    with np.load(npz) as data:
        if "plddt" not in data:
            ctx.issues.append(f"{pid}: {npz.name} has no key plddt")
            return (), ()
        values = np.asarray(data["plddt"], dtype=float).ravel()
    tokens = token_residues(structure)
    if len(tokens) != len(values):
        ctx.issues.append(
            f"{pid}: {npz.name} has {len(values)} tokens, structure has {len(tokens)}; "
            "per-residue pLDDT not mapped"
        )
        return (), ()
    pairs = [(round(float(v) * 100.0, 3), t) for v, t in zip(values, tokens, strict=True) if t]
    return tuple(v for v, _ in pairs), tuple(t for _, t in pairs)


def _affinity(ctx: ParseContext, d: Path, name: str, seed: int | None) -> dict[str, Any] | None:
    path = d / f"affinity_{name}.json"
    if not path.exists():
        return None
    data = read_json(path)
    if not isinstance(data, dict):
        ctx.issues.append(f"{path.name}: not a JSON object")
        return None
    out: dict[str, Any] = dict(floats(data, _AFFINITY_KEYS))
    out["seed"] = seed
    out["file"] = str(path)
    return out


def _run_poses(ctx: ParseContext, seed: int | None, d: Path) -> list[Pose]:
    import numpy as np

    poses: list[Pose] = []
    for structure in sorted(d.iterdir()):
        m = _MODEL.match(structure.name)
        if not m:
            continue
        name, k = m.group("name"), int(m.group("k"))
        pid = pose_id(ctx.executor, seed, "sample", k)
        conf = ctx.require(d / f"confidence_{name}_model_{k}.json", "confidence JSON")
        data = read_json(conf)
        scores = floats(data) if isinstance(data, dict) else {}
        files = [structure, conf]
        plddt_npz = d / f"plddt_{name}_model_{k}.npz"
        plddt: tuple[tuple[float, ...], tuple[tuple[str, int], ...]] = ((), ())
        if plddt_npz.exists():
            plddt = _plddt(ctx, pid, structure, plddt_npz)
            files.append(plddt_npz)
        else:
            ctx.issues.append(f"{pid}: {plddt_npz.name} missing; no per-residue pLDDT")
        pae: Path | None = None
        pae_npz = d / f"pae_{name}_model_{k}.npz"
        if pae_npz.exists():
            with np.load(pae_npz) as arr:
                if "pae" in arr:
                    pae = ctx.save_pae(pid, arr["pae"])
                    files.append(pae_npz)
                else:
                    ctx.issues.append(f"{pid}: {pae_npz.name} has no key pae")
        else:
            ctx.issues.append(f"{pid}: {pae_npz.name} missing (written only with --write_full_pae)")
        affinity = d / f"affinity_{d.name}.json"
        if affinity.exists():
            files.append(affinity)
        poses.append(
            ctx.cofolding_pose(
                pid=pid,
                structure=structure,
                seed=seed,
                sample=k,
                rank=k,
                scores=scores,
                files=files,
                plddt=plddt,
                pae=pae,
            )
        )
    return poses


@parser("boltz2", "boltz1", family=Family.COFOLDING)
def parse_boltz(spec: PredictionInput, manifest: Manifest, workdir: Path) -> PredictionSet:
    ctx = ParseContext(spec, manifest, workdir, Family.COFOLDING)
    root = ctx.require(ctx.source, "output directory")
    runs = _runs(ctx, root)
    if not runs:
        raise ParseError(f"boltz: no {_GLOB} under {root}")
    poses: list[Pose] = []
    affinities: list[dict[str, Any]] = []
    for seed, d in runs:
        poses.extend(_run_poses(ctx, seed, d))
        aff = _affinity(ctx, d, d.name, seed)
        if aff is not None:
            affinities.append(aff)
    settings: dict[str, Any] = {}
    if len(affinities) == 1:
        settings["affinity"] = affinities[0]
    elif affinities:
        settings["affinity"] = affinities
    elif ctx.ligand is not None:
        ctx.issues.append("affinity_<name>.json missing (written only with properties.affinity)")
    return ctx.result(poses, settings)
