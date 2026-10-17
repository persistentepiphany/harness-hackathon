import json
from pathlib import Path

import pytest

from pah.api.adapter import log_lines, ui_job, ui_record
from tests.synthetic import EVIDENCE, POSES, write_events, write_synthetic_run


@pytest.fixture
def synthetic(tmp_path: Path) -> Path:
    pytest.importorskip("numpy")
    return write_synthetic_run(tmp_path / "synthetic")


def test_clean_run_record(clean_run: Path) -> None:
    ui = ui_record(clean_run)
    assert ui["source"] == "pah" and ui["task"] == "ligand_pose"
    assert ui["verdict"]["outcome"] == "narrowed"
    assert ui["verdict"]["warnings"] == ["l1.ligand.stereo_defined"]
    assert [layer["i"] for layer in ui["layers"]] == [0, 1, 2, 3, 4, 5]
    assert [layer["status"] for layer in ui["layers"]] == ["done", "done"] + ["not_run"] * 4
    l1 = ui["layers"][1]
    assert l1["counts"] == {"pass": 9, "warn": 1, "stop": 0, "skip": 0}
    stereo = next(c for c in l1["checks"] if c["id"] == "l1.ligand.stereo_defined")
    assert stereo["gate"] == "Warn" and stereo["result"] == "warn"
    assert stereo["threshold"]["value"] == "== 0"
    assert stereo["evidence"].startswith("1 stereo elements undefined")
    assert ui["stats"] == {}
    assert ui["inputs"] == {
        "target": "P00760",
        "ligand": "NC(=N)c1ccccc1",
        "reference": "3PTB",
        "ph": 7.4,
        "seeds": 5,
    }
    assert ui["tools"] == [
        {"id": "boltz2", "name": "Boltz-2", "version": "2.2.1", "family": "co-folding"}
    ]
    assert len(ui["sources"]) == 7 and all(len(s["sha256"]) == 64 for s in ui["sources"])
    assert ui["structures"][0]["format"] == "mmcif" and ui["structures"][0]["kind"] == "crystal"
    assert ui["structures"][0]["url"] == "/runs/run/files/artifacts/sources/3PTB.cif"
    assert {c["status"] for c in ui["controls"]} == {"missing"}
    json.dumps(ui)


def test_unknown_checks_are_skips(clean_run: Path) -> None:
    import pah.checks  # noqa: F401
    from pah.core.check import CheckContext
    from pah.core.engine import Engine
    from pah.core.events import EventBus, JsonlSink
    from pah.core.manifest import load_manifest
    from pah.core.task import load_task
    from pah.sources import CachedHttp, ContentCache, Sources
    from tests.conftest import ROOT
    from tests.fakeweb import FakeWeb

    manifest = load_manifest(ROOT / "examples/3ptb_ligand_pose/manifest.yaml")
    sources = Sources(CachedHttp(FakeWeb().client(), ContentCache(clean_run.parent / "c2")))
    run_dir = clean_run.parent / "full"
    ctx = CheckContext(manifest, load_task(manifest.task), sources, run_dir)
    with EventBus("full", [JsonlSink(run_dir / "events.jsonl")]) as bus:
        Engine(bus, ctx).run((0, 1, 2))
    ui = ui_record(run_dir)
    l2 = ui["layers"][2]
    assert l2["status"] == "done" and l2["counts"]["skip"] == len(l2["checks"]) > 0
    assert {c["skipReason"] for c in l2["checks"]} == {"unknown_check"}
    assert ui["verdict"]["outcome"] == "incomplete"
    assert "durationMs" in l2


def test_synthetic_stats_pass_through(synthetic: Path) -> None:
    ui = ui_record(synthetic)
    s = ui["stats"]
    assert s["posebusters"] == [
        {k: t[k] for k in ("test", "pass", "value")} for t in EVIDENCE["l4.posebusters"]["tests"]
    ]
    physics = {row["pose"]: row for row in s["physics"]}
    assert physics[POSES[1]] == {
        "pose": POSES[1],
        "pbPassed": 19,
        "pbTotal": 20,
        "pbFailed": ["volume_overlap"],
        "torsions": 1,
        "torsionsTotal": 7,
        "drift": 0.62,
        "converged": True,
        "clashes": 0,
        "clashscore": 3.1,
        "unsatisfied": 1,
        "buriedCharged": 0,
        "seed": 1,
    }
    assert "seed" not in physics[POSES[3]]
    assert s["seeds"][2] == {
        "seed": 2, "rmsdToMedoid": 3.12, "cluster": 2, "confidence": 0.71, "pose": POSES[2]
    }  # fmt: skip
    assert s["pairwise"] == {"median": 0.92, "n": 6, "iqr": [0.5, 2.1]}
    assert s["sitePlacement"] == EVIDENCE["l5.sampling.clusters"]["site_placement"]
    assert s["poseAccuracy"] == EVIDENCE["l5.sampling.clusters"]["pose_accuracy"]
    ens = {e["id"]: e for e in s["ensemble"]}
    assert ens[POSES[0]] == {
        "id": POSES[0], "label": POSES[0], "kind": "medoid", "source": "boltz2",
        "rmsdToMedoid": 0.0, "cluster": 1, "pocketPlddt": 91.2, "iptm": 0.88,
    }  # fmt: skip
    assert ens[POSES[3]]["kind"] == "docking" and "pocketPlddt" not in ens[POSES[3]]
    assert ens[POSES[2]]["kind"] == "seed"
    assert s["metrics"][1]["separate"] is True
    assert s["agreement"] == [
        {"method": "Boltz-2", "cells": [
            {"vs": "Gnina", "value": 1.1, "unit": "Å", "weight": "high"},
            {"vs": "Crystal", "value": 0.9, "unit": "Å", "weight": "decisive"}]},
        {"method": "Gnina", "cells": [
            {"vs": "Boltz-2", "value": 1.1, "unit": "Å", "weight": "high"},
            {"vs": "Crystal", "value": 1.4, "unit": "Å", "weight": "decisive"}]},
    ]  # fmt: skip
    assert s["interactions"][0] == {
        "residue": "ASP189", "type": "H-bond", "distance": 2.9, "poses": 4, "of": 4
    }  # fmt: skip
    assert s["interactionsPose"] == POSES[0]
    assert s["reference"] == {
        "redocking": {"rmsd": 0.8, "pose": "gnina/redock1", "reference": "3PTB"},
        "rmsdToCrystal": [{"pose": POSES[0], "rmsd": 0.9}],
    }
    assert s["docking"]["tool"] == "gnina"
    assert s["docking"]["rows"][1] == ["size", "24 \u00d7 22 \u00d7 26\u2009Å"]
    assert ["exhaustiveness", "16"] in s["docking"]["rows"]
    assert s["pae"] == {"pose": POSES[0], "path": "artifacts/pae/seed0.npy"}
    assert ui["verdict"]["outcome"] == "narrowed"
    assert ui["layers"][3]["status"] == "not_run" and ui["layers"][3]["counts"] == {}
    assert ui["layers"][4]["durationMs"] > 0
    drift = next(c for c in ui["layers"][4]["checks"] if c["id"] == "l4.minimisation_drift")
    assert drift["result"] == "warn" and drift["ms"] == 1250
    assert drift["thresholds"][0]["origin"] == "PoseBench"
    assert ui["structures"][0]["kind"] == "medoid"
    assert ui["renders"] == [
        {"structure": "seed0", "png": "/runs/synthetic/files/renders/seed0_overview.png",
         "pse": "/runs/synthetic/files/renders/seed0.pse", "view": "overview"},
        {"structure": "seed0", "png": "/runs/synthetic/files/renders/seed0_pocket.png",
         "pse": "/runs/synthetic/files/renders/seed0.pse", "view": "pocket"},
    ]  # fmt: skip
    assert [t["id"] for t in ui["tools"]] == ["boltz2", "gnina"]
    assert ui["tools"][1]["family"] == "docking"
    assert ui["controls"] == [
        {"name": "redocking", "status": "sound", "note": "l5.controls.redocking evidence"}
    ]


def test_absent_blocks_are_absent(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    run = write_synthetic_run(tmp_path / "bare", with_stats=False)
    assert ui_record(run)["stats"] == {}


def test_skipped_finding_gives_no_block(synthetic: Path) -> None:
    from pah.core.engine import RunRecord
    from pah.core.models import Gate

    rec = RunRecord.model_validate_json((synthetic / "record.json").read_text())
    findings = [
        f.model_copy(update={"gate": Gate.SKIP}) if f.check_id == "l5.agreement.cross_family" else f
        for f in rec.findings
    ]
    (synthetic / "record.json").write_text(
        rec.model_copy(update={"findings": findings}).model_dump_json()
    )
    stats = ui_record(synthetic)["stats"]
    assert "agreement" not in stats and "seeds" in stats


def test_running_from_events(synthetic: Path) -> None:
    from pah.core.engine import RunRecord

    rec = RunRecord.model_validate_json((synthetic / "record.json").read_text())
    (synthetic / "record.json").unlink()
    (synthetic / "provenance.json").unlink()
    write_events(synthetic, rec, stop_after=8)
    ui = ui_record(synthetic)
    assert "verdict" not in ui and ui["claim"] == rec.claim
    assert ui["inputs"]["target"] == "P00760"
    statuses = [layer["status"] for layer in ui["layers"]]
    assert statuses == ["done", "done", "running", "not_run", "pending", "pending"]
    pending = [c for c in ui["layers"][4]["checks"] if c["result"] == "pending"]
    assert pending and ui["layers"][4]["counts"]["pending"] == len(pending)
    job = ui_job(synthetic)
    assert job["status"] == "running" and job["layerIdx"] == 2 and job["verdict"] is None
    assert job["layers"][1] == {"i": 1, "result": "warn", "done": True}
    assert job["layers"][4] == {"i": 4, "result": None, "done": False}
    assert 0 < job["progress"] <= 1


def test_job_and_log_lines(synthetic: Path) -> None:
    job = ui_job(synthetic)
    assert job["id"] == "synthetic" and job["runId"] == "ligand_pose-synthetic"
    assert job["status"] == "done" and job["layerIdx"] == 6 and job["verdict"] == "narrowed"
    assert job["name"] == "trypsin · benzamidine" and job["seeds"] == 3
    assert job["tools"] == ["Boltz-2", "Gnina"] and job["elapsedMs"] > 0
    lines = log_lines(synthetic)
    assert [x["seq"] for x in lines] == list(range(1, len(lines) + 1))
    kinds = {x["kind"] for x in lines}
    assert kinds == {"run", "fetch", "layer", "check"}
    check = next(x for x in lines if x["kind"] == "check")
    assert check["result"] == "pass" and check["layer"] == 0 and check["t"].endswith("s")
    assert all(x["plain"].endswith(".") and ".." not in x["plain"] for x in lines)
    assert lines[-1]["plain"] == "Run finished with verdict narrowed."
