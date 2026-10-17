"""A synthetic finished run with layer 2, 4 and 5 findings carrying the evidence contract that
`pah.api.stats` reads. Used by the adapter, HTML report, figure and API tests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pah.core.engine import RunRecord
from pah.core.models import (
    Artifact,
    ArtifactKind,
    Event,
    EventKind,
    EvidenceLevel,
    Finding,
    Gate,
    Layer,
    Measurement,
    Provenance,
    Threshold,
    ToolRef,
)
from pah.core.policy import decide

T0 = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
POSES = ["boltz2/seed0/sample0", "boltz2/seed1/sample0", "boltz2/seed2/sample0", "gnina/mode1"]

EVIDENCE: dict[str, dict[str, Any]] = {
    "l2.docking.box": {
        "center": [12.5, 4.0, -3.25],
        "size": [24, 22, 26],
        "origin": "crystal ligand + 4 Å",
        "settings": {"exhaustiveness": 16, "num_modes": 9},
        "executor": "gnina",
    },
    "l4.posebusters": {
        "tests": [
            {"test": "bond_lengths", "pass": True, "value": "0 outliers"},
            {"test": "minimum_distance_to_protein", "pass": True, "value": "2.9 Å"},
            {"test": "volume_overlap_with_protein", "pass": False, "value": "0.12"},
        ],
        "poses": [
            {"pose": POSES[0], "passed": 20, "total": 20, "failed": []},
            {
                "pose": POSES[1],
                "passed": 19,
                "total": 20,
                "failed": ["volume_overlap_with_protein"],
            },
            {"pose": POSES[2], "passed": 20, "total": 20, "failed": []},
            {
                "pose": POSES[3],
                "passed": 18,
                "total": 20,
                "failed": ["volume_overlap_with_protein", "bond_lengths"],
            },
        ],
        "unknown_key": 1,
    },
    "l4.torsion_strain": {
        "poses": [
            {"pose": p, "unlikely_torsions": i % 2, "torsions": 7} for i, p in enumerate(POSES)
        ]
    },
    "l4.minimisation_drift": {
        "poses": [
            {"pose": p, "drift_A": d, "converged": True}
            for p, d in zip(POSES, [0.41, 0.62, 2.35, 0.8], strict=True)
        ]
    },
    "l4.structure.clashes": {
        "poses": [{"pose": p, "clashes": 0, "clashscore": 3.1} for p in POSES]
    },
    "l4.interactions.unsatisfied_polars": {
        "poses": [{"pose": p, "unsatisfied": 1, "buried_charged": 0} for p in POSES]
    },
    "l4.interactions.fingerprint": {
        "interactions": [
            {"type": "H-bond", "residue": "ASP189", "poses": 4, "of": 4, "distance_A": 2.9},
            {"type": "salt bridge", "residue": "ASP189", "poses": 3, "of": 4, "distance_A": 3.1},
            {"type": "hydrophobic", "residue": "TRP215", "poses": 2, "of": 4, "distance_A": 3.8},
        ],
        "representative": POSES[0],
    },
    "l5.sampling.clusters": {
        "poses": [
            {
                "pose": POSES[0],
                "executor": "boltz2",
                "seed": 0,
                "sample": 0,
                "cluster": 1,
                "rmsd_to_medoid_A": 0.0,
                "confidence": 0.91,
            },
            {
                "pose": POSES[1],
                "executor": "boltz2",
                "seed": 1,
                "sample": 0,
                "cluster": 1,
                "rmsd_to_medoid_A": 0.74,
                "confidence": 0.88,
            },
            {
                "pose": POSES[2],
                "executor": "boltz2",
                "seed": 2,
                "sample": 0,
                "cluster": 2,
                "rmsd_to_medoid_A": 3.12,
                "confidence": 0.71,
            },
            {
                "pose": POSES[3],
                "executor": "gnina",
                "seed": None,
                "sample": 1,
                "cluster": 1,
                "rmsd_to_medoid_A": 1.1,
                "confidence": None,
            },
        ],
        "clusters": [
            {"id": 1, "size": 3, "medoid": POSES[0]},
            {"id": 2, "size": 1, "medoid": POSES[2]},
        ],
        "medoid": POSES[0],
        "pairwise_rmsd_A": {"median": 0.92, "q1": 0.5, "q3": 2.1, "n": 6},
        "site_placement": "3 of 3 seeds in the crystal pocket",
        "pose_accuracy": "2 of 3 seeds within 2 Å of the medoid",
    },
    "l5.confidence.local": {
        "poses": [
            {
                "pose": POSES[0],
                "pocket_plddt": 91.2,
                "global_plddt": 88.0,
                "iptm": 0.88,
                "ptm": 0.93,
            },
            {
                "pose": POSES[1],
                "pocket_plddt": 89.5,
                "global_plddt": 87.1,
                "iptm": 0.86,
                "ptm": 0.92,
            },
        ],
        "metrics": [
            {
                "name": "ipTM",
                "value": "0.88",
                "read": "Interface confidence",
                "tool": "Boltz-2",
                "separate": False,
            },
            {
                "name": "Boltz-2 affinity",
                "value": "6.9 log",
                "read": "Ranking within this run",
                "tool": "Boltz-2",
                "separate": True,
            },
        ],
        "pae": {"pose": POSES[0], "path": "artifacts/pae/seed0.npy"},
    },
    "l5.agreement.cross_family": {
        "comparisons": [
            {"method": "Boltz-2", "vs": "Gnina", "value": 1.1, "unit": "Å", "weight": "high"},
            {"method": "Boltz-2", "vs": "Crystal", "value": 0.9, "unit": "Å", "weight": "decisive"},
            {"method": "Gnina", "vs": "Boltz-2", "value": 1.1, "unit": "Å", "weight": "high"},
            {"method": "Gnina", "vs": "Crystal", "value": 1.4, "unit": "Å", "weight": "decisive"},
        ]
    },
    "l5.controls.redocking": {"rmsd_A": 0.8, "pose": "gnina/redock1", "reference": "3PTB"},
    "l5.rmsd_to_crystal": {"poses": [{"pose": POSES[0], "rmsd_A": 0.9}]},
}

LAYER_OF = {"l2": Layer.ADEQUACY, "l4": Layer.VALIDITY, "l5": Layer.SUPPORT}


def _finding(cid: str, gate: Gate = Gate.PASS, **kw: Any) -> Finding:
    layer = Layer.PROVENANCE if cid.startswith("l0") else LAYER_OF.get(cid[:2], Layer.INTEGRITY)
    return Finding(check_id=cid, layer=layer, gate=gate, message=kw.pop("message", "ok"), **kw)


def findings(with_stats: bool = True) -> list[Finding]:
    out = [
        _finding(
            "l0.sources.resolved",
            message="2 identifiers resolved to 2 records",
            measurements=(Measurement(name="records", value=2),),
            duration_s=0.012,
        ),
        _finding(
            "l1.ligand.stereo_defined",
            Gate.WARN,
            message="1 stereo elements undefined",
            measurements=(
                Measurement(name="stereo_elements", value=1),
                Measurement(name="undefined", value=1),
            ),
            thresholds=(
                Threshold(
                    name="undefined_stereo",
                    value=0,
                    comparator="==",
                    origin="Specification, Layer 1",
                    evidence_level=EvidenceLevel.PUBLISHED,
                ),
            ),
            duration_s=0.4,
        ),
        _finding(
            "l2.msa.depth",
            Gate.SKIP,
            message="no MSA declared",
            evidence={"skip_reason": "not_applicable"},
        ),
    ]
    for cid, ev in EVIDENCE.items():
        if not with_stats:
            continue
        extra: dict[str, Any] = {}
        if cid == "l4.minimisation_drift":
            extra = {
                "measurements": (Measurement(name="max_drift", value=2.35, unit="Å"),),
                "thresholds": (
                    Threshold(name="max_drift", value=2.0, comparator="<=", origin="PoseBench"),
                ),
            }
        gate = Gate.WARN if cid == "l4.minimisation_drift" else Gate.PASS
        out.append(
            _finding(cid, gate, message=f"{cid} evidence", evidence=ev, duration_s=1.25, **extra)
        )
    out.append(
        _finding(
            "l4.interactions.known_binders",
            Gate.SKIP,
            message="no known binders",
            evidence={"skip_reason": "not_applicable"},
            tool=ToolRef(name="plip", version="2.3"),
        )
    )
    return out


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def write_synthetic_run(run_dir: Path, *, with_stats: bool = True) -> Path:
    """Writes record.json, provenance.json, events.jsonl, an mmCIF, renders and a PAE matrix."""
    run_dir.mkdir(parents=True, exist_ok=True)
    fs = findings(with_stats)
    model = run_dir / "artifacts" / "pred" / "seed0.cif"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_text("data_seed0\n")
    renders = run_dir / "renders"
    renders.mkdir(exist_ok=True)
    for view in ("overview", "pocket"):
        (renders / f"seed0_{view}.png").write_bytes(b"\x89PNG fake")
    (renders / "seed0.pse").write_bytes(b"pse")
    if with_stats:
        import numpy as np

        pae = run_dir / "artifacts" / "pae" / "seed0.npy"
        pae.parent.mkdir(parents=True, exist_ok=True)
        grid = np.add.outer(np.arange(12.0), np.arange(12.0)) / 1.5
        np.save(pae, grid)
    prov = [
        Provenance(
            source_id="uniprot",
            accession="P00760",
            url="https://rest.uniprot.org/uniprotkb/P00760.json",
            sha256=_sha("uniprot"),
            size_bytes=1200,
            retrieved_at=T0,
            release="2026_03",
            extra={"cache": "hit"},
        ),
        Provenance(
            source_id="rcsb",
            accession="3PTB",
            url="https://data.rcsb.org/rest/v1/core/entry/3PTB",
            sha256=_sha("rcsb"),
            size_bytes=900,
            retrieved_at=T0,
            extra={"cache": "miss"},
        ),
    ]
    layers = (0, 1, 2, 4, 5)
    record = RunRecord(
        run_id="ligand_pose-synthetic",
        task="ligand_pose",
        claim="Pose within stated uncertainty",
        layers=layers,
        manifest={
            "task": "ligand_pose",
            "ph": 7.4,
            "proteins": [{"id": "trypsin", "uniprot": "P00760", "pdb_id": "3PTB"}],
            "ligands": [{"id": "benzamidine", "smiles": "NC(=N)c1ccccc1", "ccd": "BEN"}],
            "receptor": {"pdb_id": "3PTB", "chains": ["A"]},
            "reference": {"pdb_id": "3PTB", "ligand": "BEN"},
            "model": {"executor": "boltz2", "version": "2.2.1", "seeds": [0, 1, 2]},
            "predictions": [
                {"executor": "boltz2", "path": "pred/boltz2", "version": "2.2.1"},
                {"executor": "gnina", "path": "pred/gnina", "version": "1.3"},
            ],
        },
        started_at=T0,
        finished_at=T0 + timedelta(seconds=14),
        tool_versions={"rdkit": "2026.09.1"},
        findings=fs,
        provenance=prov,
        artifacts=[
            Artifact(
                path="artifacts/pred/seed0.cif",
                kind=ArtifactKind.PREDICTION_STRUCTURE,
                sha256=_sha("data_seed0\n"),
                size_bytes=11,
                label=POSES[0],
            )
        ],
        verdict=decide("Pose within stated uncertainty", "layers 0,1,2,4,5", fs),
    )
    (run_dir / "record.json").write_text(record.model_dump_json(indent=2))
    (run_dir / "provenance.json").write_text(
        json.dumps([p.model_dump(mode="json") for p in prov], indent=2)
    )
    write_events(run_dir, record)
    return run_dir


def write_events(run_dir: Path, record: RunRecord, *, stop_after: int | None = None) -> None:
    """events.jsonl as the engine writes it. `stop_after` cuts the stream mid-run."""
    rows: list[Event] = []
    seq = 0
    clock = record.started_at

    def add(kind: EventKind, stage: str, message: str, **data: Any) -> None:
        nonlocal seq, clock
        seq += 1
        clock += timedelta(milliseconds=250)
        rows.append(
            Event(
                run_id=record.run_id, seq=seq, kind=kind, stage=stage, message=message, ts=clock,
                data=data,
            )
        )  # fmt: skip

    add(
        EventKind.RUN_START,
        "run",
        f"task={record.task}",
        task=record.task,
        layers=list(record.layers),
        claim=record.claim,
        manifest=record.manifest,
    )
    add(EventKind.LOG, "L0", "fetch uniprot P00760", cache="miss")
    for layer in record.layers:
        fs = [f for f in record.findings if int(f.layer) == layer]
        add(
            EventKind.STAGE_START,
            f"L{layer}",
            f"layer: {len(fs)} checks",
            checks=[f.check_id for f in fs],
        )
        for f in fs:
            add(EventKind.FINDING, f"L{layer}", f"{f.check_id}: {f.message}", gate=f.gate.value,
                finding=f.model_dump(mode="json"))  # fmt: skip
            if stop_after is not None and seq >= stop_after:
                break
        if stop_after is not None and seq >= stop_after:
            break
        add(EventKind.STAGE_END, f"L{layer}", "layer done", counts={})
    else:
        assert record.verdict is not None
        add(EventKind.RUN_END, "run", "verdict", verdict=record.verdict.model_dump(mode="json"))
    with (run_dir / "events.jsonl").open("w") as fh:
        for e in rows:
            fh.write(e.model_dump_json() + "\n")
