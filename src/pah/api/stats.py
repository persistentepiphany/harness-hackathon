"""`UiRunRecord.stats` from the evidence of layer 2, 4 and 5 findings.

One reader per check id, registered with `@reads`. A reader copies the values it knows from the
finding's evidence into a `StatsDraft`; `StatsDraft.finish()` joins the per-pose rows into the
blocks the UI renders. A block appears only when the finding that supplies it exists and did not
skip. Values pass through unchanged; unknown evidence keys are ignored.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pah.core.models import Finding, Gate

Reader = Callable[[Mapping[str, Any], "StatsDraft"], None]
READERS: dict[str, Reader] = {}


def reads(check_id: str) -> Callable[[Reader], Reader]:
    def deco(fn: Reader) -> Reader:
        READERS[check_id] = fn
        return fn

    return deco


def _list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, Mapping)]


def _pick(row: Mapping[str, Any], mapping: Mapping[str, str]) -> dict[str, Any]:
    """Copies `row[src]` to `dst` for every key present."""
    return {dst: row[src] for src, dst in mapping.items() if src in row}


@dataclass
class StatsDraft:
    families: Mapping[str, str] = field(default_factory=dict)
    blocks: dict[str, Any] = field(default_factory=dict)
    physics: dict[str, dict[str, Any]] = field(default_factory=dict)
    confidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    poses: list[dict[str, Any]] = field(default_factory=list)
    medoid: str | None = None
    reference: dict[str, Any] = field(default_factory=dict)

    def pose_row(self, pose: str) -> dict[str, Any]:
        return self.physics.setdefault(pose, {"pose": pose})

    def finish(self) -> dict[str, Any]:
        out = dict(self.blocks)
        seeds = {p["pose"]: p.get("seed") for p in self.poses if "pose" in p}
        if self.physics:
            order = [p for p in seeds if p in self.physics]
            order += [p for p in self.physics if p not in seeds]
            rows = []
            for pose in order:
                row = dict(self.physics[pose])
                if seeds.get(pose) is not None:
                    row["seed"] = seeds[pose]
                rows.append(row)
            out["physics"] = rows
        if self.poses:
            out["ensemble"] = [self._ensemble_row(p) for p in self.poses]
        if self.reference:
            out["reference"] = dict(self.reference)
        return out

    def _ensemble_row(self, p: Mapping[str, Any]) -> dict[str, Any]:
        pose = str(p.get("pose"))
        executor = p.get("executor")
        if pose == self.medoid:
            kind = "medoid"
        elif executor is not None and self.families.get(str(executor)) == "docking":
            kind = "docking"
        else:
            kind = "seed"
        row: dict[str, Any] = {"id": pose, "label": pose, "kind": kind}
        if executor is not None:
            row["source"] = executor
        row.update(_pick(p, {"rmsd_to_medoid_A": "rmsdToMedoid", "cluster": "cluster"}))
        conf = self.confidence.get(pose, {})
        row.update(_pick(conf, {"pocketPlddt": "pocketPlddt", "iptm": "iptm"}))
        return row


@reads("l4.posebusters")
def _posebusters(ev: Mapping[str, Any], d: StatsDraft) -> None:
    tests = [
        _pick(t, {"test": "test", "pass": "pass", "value": "value"}) for t in _list(ev.get("tests"))
    ]
    if tests:
        d.blocks["posebusters"] = tests
    for p in _list(ev.get("poses")):
        if "pose" in p:
            d.pose_row(str(p["pose"])).update(
                _pick(p, {"passed": "pbPassed", "total": "pbTotal", "failed": "pbFailed"})
            )


def _per_pose(mapping: Mapping[str, str]) -> Reader:
    def read(ev: Mapping[str, Any], d: StatsDraft) -> None:
        for p in _list(ev.get("poses")):
            if "pose" in p:
                d.pose_row(str(p["pose"])).update(_pick(p, mapping))

    return read


reads("l4.torsion_strain")(
    _per_pose({"unlikely_torsions": "torsions", "torsions": "torsionsTotal"})
)
reads("l4.minimisation_drift")(_per_pose({"drift_A": "drift", "converged": "converged"}))
reads("l4.structure.clashes")(_per_pose({"clashes": "clashes", "clashscore": "clashscore"}))
reads("l4.interactions.unsatisfied_polars")(
    _per_pose({"unsatisfied": "unsatisfied", "buried_charged": "buriedCharged"})
)


@reads("l4.interactions.fingerprint")
def _fingerprint(ev: Mapping[str, Any], d: StatsDraft) -> None:
    rows = [
        _pick(
            i,
            {
                "residue": "residue",
                "type": "type",
                "distance_A": "distance",
                "poses": "poses",
                "of": "of",
            },
        )
        for i in _list(ev.get("interactions"))
    ]
    if rows:
        d.blocks["interactions"] = rows
    if "representative" in ev:
        d.blocks["interactionsPose"] = ev["representative"]


@reads("l5.sampling.clusters")
def _clusters(ev: Mapping[str, Any], d: StatsDraft) -> None:
    poses = [dict(p) for p in _list(ev.get("poses")) if "pose" in p]
    if poses:
        d.poses = poses
        d.blocks["seeds"] = [
            _pick(
                p,
                {
                    "seed": "seed",
                    "rmsd_to_medoid_A": "rmsdToMedoid",
                    "cluster": "cluster",
                    "confidence": "confidence",
                    "pose": "pose",
                },
            )
            for p in poses
        ]
    clusters = [
        _pick(c, {"id": "id", "size": "size", "medoid": "medoid"})
        for c in _list(ev.get("clusters"))
    ]
    if clusters:
        d.blocks["clusters"] = clusters
    if "medoid" in ev:
        d.medoid = str(ev["medoid"])
        d.blocks["medoid"] = ev["medoid"]
    pw = ev.get("pairwise_rmsd_A")
    if isinstance(pw, Mapping):
        block: dict[str, Any] = _pick(pw, {"median": "median", "n": "n"})
        if "q1" in pw and "q3" in pw:
            block["iqr"] = [pw["q1"], pw["q3"]]
        d.blocks["pairwise"] = block
    if "site_placement" in ev:
        d.blocks["sitePlacement"] = ev["site_placement"]
    if "pose_accuracy" in ev:
        d.blocks["poseAccuracy"] = ev["pose_accuracy"]


@reads("l5.confidence.local")
def _confidence(ev: Mapping[str, Any], d: StatsDraft) -> None:
    for p in _list(ev.get("poses")):
        if "pose" in p:
            d.confidence[str(p["pose"])] = _pick(
                p,
                {"pocket_plddt": "pocketPlddt", "global_plddt": "globalPlddt", "iptm": "iptm",
                 "ptm": "ptm"},
            )  # fmt: skip
    metrics = [
        _pick(m, {"name": "name", "value": "value", "read": "read", "tool": "tool",
                  "separate": "separate"})
        for m in _list(ev.get("metrics"))
    ]  # fmt: skip
    if metrics:
        d.blocks["metrics"] = metrics
    pae = ev.get("pae")
    if isinstance(pae, Mapping) and "path" in pae:
        d.blocks["pae"] = _pick(pae, {"pose": "pose", "path": "path"})


@reads("l5.agreement.cross_family")
def _agreement(ev: Mapping[str, Any], d: StatsDraft) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for c in _list(ev.get("comparisons")):
        if "method" in c:
            grouped.setdefault(str(c["method"]), []).append(
                _pick(c, {"vs": "vs", "value": "value", "unit": "unit", "weight": "weight"})
            )
    if grouped:
        d.blocks["agreement"] = [{"method": m, "cells": cells} for m, cells in grouped.items()]


@reads("l5.controls.redocking")
def _redocking(ev: Mapping[str, Any], d: StatsDraft) -> None:
    block = _pick(ev, {"rmsd_A": "rmsd", "pose": "pose", "reference": "reference"})
    if block:
        d.reference["redocking"] = block


@reads("l5.rmsd_to_crystal")
def _rmsd_to_crystal(ev: Mapping[str, Any], d: StatsDraft) -> None:
    rows = [_pick(p, {"pose": "pose", "rmsd_A": "rmsd"}) for p in _list(ev.get("poses"))]
    if rows:
        d.reference["rmsdToCrystal"] = rows


def _num(v: Any) -> str:
    return f"{v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)


@reads("l2.docking.box")
def _docking_box(ev: Mapping[str, Any], d: StatsDraft) -> None:
    rows: list[list[str]] = []
    center, size = ev.get("center"), ev.get("size")
    if isinstance(center, list) and center:
        rows.append(["center", ", ".join(_num(v) for v in center) + "\u2009Å"])
    if isinstance(size, list) and size:
        rows.append(["size", " \u00d7 ".join(_num(v) for v in size) + "\u2009Å"])
    if "origin" in ev:
        rows.append(["origin", str(ev["origin"])])
    settings = ev.get("settings")
    if isinstance(settings, Mapping):
        rows += [[str(k), _num(v)] for k, v in settings.items()]
    if not rows:
        return
    block: dict[str, Any] = {"rows": rows}
    if "executor" in ev:
        block["tool"] = ev["executor"]
    d.blocks["docking"] = block


def build_stats(
    findings: Iterable[Finding], families: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Stats blocks from the findings whose check has a reader and whose gate is not skip."""
    draft = StatsDraft(families=families or {})
    for f in findings:
        reader = READERS.get(f.check_id)
        if reader is None or f.gate is Gate.SKIP:
            continue
        reader(f.evidence, draft)
    return draft.finish()
