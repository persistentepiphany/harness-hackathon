"""AlphaFold3 output (docs/EXECUTORS.md section 3).

Layout: `OUT/<job>/seed-<seed>_sample-<i>/<job>_seed-<seed>_sample-<i>_model.cif` with
`_summary_confidences.json` and `_confidences.json` beside it, and `<job>_ranking_scores.csv`
(`seed,sample,ranking_score`) in the job folder. The job folder may carry a timestamp suffix, so
file names are matched by glob, not rebuilt from the folder name.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from pah.core.manifest import Manifest, PredictionInput
from pah.executors.base import Family, ParseError, Pose, PredictionSet, parser
from pah.executors.parsers._common import ParseContext, floats, pose_id, read_json
from pah.executors.structure import atom_table

_SAMPLE_DIR = re.compile(r"^seed-(?P<seed>\d+)_sample-(?P<i>\d+)$")
_GLOB = "<job>/seed-<seed>_sample-<i>/<job>_seed-<seed>_sample-<i>_model.cif"


def _job_dir(root: Path) -> Path:
    if any(_SAMPLE_DIR.match(d.name) for d in root.iterdir() if d.is_dir()):
        return root
    jobs = [
        d
        for d in root.iterdir()
        if d.is_dir() and any(_SAMPLE_DIR.match(s.name) for s in d.iterdir() if s.is_dir())
    ]
    if len(jobs) > 1:
        raise ParseError(
            f"alphafold3: {root} holds several jobs {sorted(d.name for d in jobs)}; "
            "point path at OUT/<job>"
        )
    if not jobs:
        raise ParseError(f"alphafold3: no {_GLOB} under {root}")
    return jobs[0]


def _ranking(ctx: ParseContext, path: Path | None) -> dict[tuple[int, int], float] | None:
    if path is None:
        ctx.issues.append("<job>_ranking_scores.csv missing; ranked by summary ranking_score")
        return None
    out: dict[tuple[int, int], float] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                out[(int(row["seed"]), int(row["sample"]))] = float(row["ranking_score"])
            except (KeyError, TypeError, ValueError):
                ctx.issues.append(f"{path.name}: unreadable row {row}")
    return out


def _plddt(
    ctx: ParseContext, pid: str, structure: Path, conf: dict[str, Any]
) -> tuple[tuple[float, ...], tuple[tuple[str, int], ...]]:
    values = conf.get("atom_plddts")
    chains = conf.get("atom_chain_ids")
    if not isinstance(values, list):
        ctx.issues.append(f"{pid}: confidences JSON has no atom_plddts")
        return (), ()
    atoms = [a for a in atom_table(structure) if not a[3]]
    if len(atoms) != len(values) or (
        isinstance(chains, list) and [a[0] for a in atoms] != [str(c) for c in chains]
    ):
        ctx.issues.append(
            f"{pid}: atom_plddts ({len(values)}) do not line up with the {len(atoms)} heavy "
            "atoms of the model; per-residue pLDDT not mapped"
        )
        return (), ()
    sums: dict[tuple[str, int], list[float]] = defaultdict(list)
    order: list[tuple[str, int]] = []
    for (_, key, polymer, _), v in zip(atoms, values, strict=True):
        if not polymer:
            continue
        if key not in sums:
            order.append(key)
        sums[key].append(float(v))
    return tuple(round(sum(sums[k]) / len(sums[k]), 3) for k in order), tuple(order)


@parser("alphafold3", family=Family.COFOLDING)
def parse_alphafold3(spec: PredictionInput, manifest: Manifest, workdir: Path) -> PredictionSet:
    ctx = ParseContext(spec, manifest, workdir, Family.COFOLDING)
    root = ctx.require(ctx.source, "output directory")
    if not root.is_dir():
        raise ParseError(f"alphafold3: {root} is not a directory; expected {_GLOB}")
    job = _job_dir(root)
    csv_path = next(iter(sorted(job.glob("*_ranking_scores.csv"))), None)
    ranking = _ranking(ctx, csv_path)
    entries: list[tuple[int, int, Path, Path, dict[str, Any]]] = []
    for d in sorted(job.iterdir()):
        m = _SAMPLE_DIR.match(d.name)
        if not m or not d.is_dir():
            continue
        seed, i = int(m.group("seed")), int(m.group("i"))
        stem = f"seed-{seed}_sample-{i}"
        models = sorted(d.glob(f"*_{stem}_model.cif"))
        if not models:
            if list(d.glob(f"*_{stem}_model.cif.zst")):
                ctx.issues.append(f"{d.name}: zstd-compressed model not read; decompress first")
            else:
                ctx.issues.append(f"{d.name}: no *_{stem}_model.cif")
            continue
        summary = ctx.require(
            models[0].with_name(models[0].name.replace("_model.cif", "_summary_confidences.json")),
            "summary confidences JSON",
        )
        data = read_json(summary)
        entries.append((seed, i, models[0], summary, data if isinstance(data, dict) else {}))
    if not entries:
        raise ParseError(f"alphafold3: no {_GLOB} under {job}")

    def score(e: tuple[int, int, Path, Path, dict[str, Any]]) -> float:
        if ranking is not None and (e[0], e[1]) in ranking:
            return ranking[(e[0], e[1])]
        value = e[4].get("ranking_score")
        return float(value) if isinstance(value, int | float) else float("-inf")

    order = sorted(entries, key=lambda e: (-score(e), e[0], e[1]))
    rank_of = {(e[0], e[1]): r for r, e in enumerate(order)}
    poses: list[Pose] = []
    for seed, i, model, summary, data in entries:
        pid = pose_id(ctx.executor, seed, "sample", i)
        files = [model, summary, *([csv_path] if csv_path else [])]
        plddt: tuple[tuple[float, ...], tuple[tuple[str, int], ...]] | None = None
        pae: Path | None = None
        full = model.with_name(model.name.replace("_model.cif", "_confidences.json"))
        if full.exists():
            conf = read_json(full)
            files.append(full)
            if isinstance(conf, dict):
                plddt = _plddt(ctx, pid, model, conf)
                if "pae" in conf:
                    pae = ctx.save_pae(pid, conf["pae"])
                else:
                    ctx.issues.append(f"{pid}: {full.name} has no pae")
        else:
            ctx.issues.append(f"{pid}: {full.name} missing; pLDDT from B-factors, no PAE")
        poses.append(
            ctx.cofolding_pose(
                pid=pid,
                structure=model,
                seed=seed,
                sample=i,
                rank=rank_of[(seed, i)],
                scores=floats(data),
                files=files,
                plddt=plddt,
                pae=pae,
            )
        )
    return ctx.result(poses, {"job_dir": str(job)})
