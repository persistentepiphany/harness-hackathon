"""UI record `stats`: every block from findings, absent when its check skipped, tool-generic.

The docking case runs layers 2 to 5 on the committed 3PTB Vina outputs offline (as
tests/test_layers_2_5.py does) and writes the report with placeholder renders. The co-folding case
is a synthetic Boltz-2 finding set shaped like the layer 4 and 5 checks write it.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from pah.webui import stats as ui_stats
from pah.webui.adapter import load_state, stats_input, to_ui_record
from tests.conftest import ROOT, FakeRenderer

VINA = ROOT / "examples/3ptb_vina/manifest.yaml"


# ---------------------------------------------------------------- docking run (3PTB, Vina)


@pytest.fixture(scope="module")
def vina_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    pytest.importorskip("rdkit")
    pytest.importorskip("gemmi")
    pytest.importorskip("spyrmsd")
    pytest.importorskip("posebusters")
    import pah.checks  # noqa: F401
    from pah.core.check import CheckContext
    from pah.core.engine import Engine
    from pah.core.events import EventBus
    from pah.core.manifest import load_manifest
    from pah.core.task import load_task
    from pah.report import write_run_report
    from pah.sources import CachedHttp, ContentCache, Sources
    from tests.fakeweb import FakeWeb

    mp = pytest.MonkeyPatch()
    mp.setenv("PAH_CONDA_PREFIX", str(tmp_path_factory.mktemp("noconda")))  # drift skips
    try:
        tmp = tmp_path_factory.mktemp("vina")
        manifest = load_manifest(VINA)
        sources = Sources(CachedHttp(FakeWeb().client(), ContentCache(tmp / "cache")))
        run_dir = tmp / "run"
        ctx = CheckContext(manifest, load_task(manifest.task), sources, run_dir)
        Engine(EventBus("ligand_pose-vina", []), ctx, halt_on_stop=False).run((2, 3, 4, 5))
        write_run_report(run_dir, renderer=FakeRenderer())
    finally:
        mp.undo()
    return run_dir


@pytest.fixture(scope="module")
def vina(vina_run: Path) -> dict[str, Any]:
    return to_ui_record(vina_run)


def _findings(run_dir: Path) -> dict[str, dict[str, Any]]:
    record = json.loads((run_dir / "record.json").read_text())
    return {f["check_id"]: f for f in record["findings"]}


def _measures(f: dict[str, Any]) -> dict[str, Any]:
    return {m["name"]: m["value"] for m in f["measurements"]}


def test_seeds_pairwise_and_sampling_from_clusters(vina: dict[str, Any], vina_run: Path) -> None:
    st = vina["stats"]
    ev = _findings(vina_run)["l5.sampling.clusters"]["evidence"]
    assert [r["seed"] for r in st["seeds"]] == [0, 1, 2, 3, 4]
    for row, p in zip(st["seeds"], ev["poses"], strict=True):
        assert row["pose"] == p["pose"] and row["rmsdToMedoid"] == p["rmsd_to_medoid_A"]
        assert row["cluster"] == p["cluster"]
        # the Vina score is not a confidence output: it is kept as a score with its key
        assert "confidence" not in row and row["score"] == p["confidence"]
        assert row["scoreKey"] == "vina_affinity"
    pw = st["pairwise"]
    assert pw["median"] == ev["pairwise_rmsd_A"]["median"] and pw["n"] == 10
    assert pw["iqr"] == [ev["pairwise_rmsd_A"]["q1"], ev["pairwise_rmsd_A"]["q3"]]
    assert "ci95" not in pw  # not computed by the harness
    assert pw["unit"] == "Å" and pw["source"]["check"] == "l5.sampling.clusters"
    assert st["sitePlacement"] == ev["site_placement"]
    assert st["poseAccuracy"] == ev["pose_accuracy"]


def test_posebusters_physics_and_interactions(vina: dict[str, Any], vina_run: Path) -> None:
    st = vina["stats"]
    found = _findings(vina_run)
    assert st["posebusters"] == found["l4.posebusters"]["evidence"]["tests"]
    assert len(st["physics"]) == 5
    strain = {p["pose"]: p["strain_kcal"] for p in found["l4.torsion_strain"]["evidence"]["poses"]}
    assert {r["pose"]: r["strain"] for r in st["physics"]} == strain
    assert all("drift" not in r for r in st["physics"])  # l4.minimisation_drift skipped
    pb = {p["pose"]: p for p in found["l4.posebusters"]["evidence"]["poses"]}
    assert all(r["pbPassed"] == pb[r["pose"]]["passed"] for r in st["physics"])
    assert all(r["pbTotal"] == pb[r["pose"]]["total"] for r in st["physics"])
    prov = st["provenance"]
    assert prov["physics.strain"]["check"] == "l4.torsion_strain"
    assert prov["physics.strain"]["unit"] == "kcal/mol"
    assert "physics.drift" not in prov
    inter = {(r["residue"], r["type"]): r for r in st["interactions"]}
    asp = inter[("ASP189A", "H-bond")]
    assert asp["known"] is True and asp["plipType"] == "hbond" and asp["poses"] == 5
    assert prov["interactions"]["tool"] == "plip"


def test_site_pose_and_agreement_cards(vina: dict[str, Any], vina_run: Path) -> None:
    st = vina["stats"]
    found = _findings(vina_run)
    site = dict(st["site"])
    assert site["pocket residues"] == str(_measures(found["l2.pocket.resolved"])["pocket_residues"])
    assert site["receptor state"] == "holo"
    assert site["docking box volume"].endswith("\N{THIN SPACE}Å³")
    pose = dict(st["pose"])
    crystal = next(
        c
        for c in found["l5.agreement.cross_family"]["evidence"]["comparisons"]
        if c["weight"] == "decisive"
    )
    assert pose["RMSD to crystal"] == ui_stats.fmt(crystal["value"], "Å")
    assert pose["redocking control RMSD"] == ui_stats.fmt(
        _measures(found["l5.controls.redocking"])["rmsd_A"], "Å"
    )
    pb = _measures(found["l4.posebusters"])
    assert pose["PoseBusters"] == f"{pb['passed']}/{pb['total']}"
    assert "minimisation drift" not in pose
    assert st["provenance"]["pose.RMSD to crystal"]["check"] == "l5.agreement.cross_family"
    matrix = {r["method"]: {c["vs"]: c for c in r["cells"]} for r in st["agreement"]}
    assert matrix["vina"]["vina"]["self"] is True
    assert matrix["vina"][crystal["vs"]]["value"] == crystal["value"]
    assert matrix[crystal["vs"]]["vina"]["mirror"] is True


def test_metrics_follow_the_tool_register(vina: dict[str, Any], vina_run: Path) -> None:
    from pah.webui.adapter import executor_rows, record_tool

    outputs = {o["key"]: o for o in record_tool("vina", executor_rows())["outputs"]}
    found = _findings(vina_run)["l5.confidence.local"]["evidence"]
    rep = next(p for p in found["poses"] if p["pose"] == found["representative"])
    metrics = vina["stats"]["metrics"]
    assert {m["key"] for m in metrics} == set(ui_stats.tool_values(rep))
    for m in metrics:
        assert m["toolId"] == "vina" and m["check"] == "l5.confidence.local"
        assert m["number"] == rep[m["key"]] and m["pose"] == found["representative"]
        o = outputs.get(m["key"])
        assert m["declared"] is (o is not None)
        if o is not None:
            assert m["name"] == o["label"] and m["separate"] is bool(o.get("rankingOnly"))
        else:  # parsed but not declared in configs/executors.yaml: never shown as pose quality
            assert m["name"] == m["key"] and m["separate"] is True and "unit" not in m


def test_ensemble_rows_per_mode_with_files_and_renders(
    vina: dict[str, Any], vina_run: Path
) -> None:
    ens = vina["stats"]["ensemble"]
    structures = {s["id"]: s for s in vina["structures"]}
    roles = Counter(r.get("role", "reference") for r in ens)
    assert roles == {"primary": 45, "control:redocking": 9, "reference": 1}
    primary = [r for r in ens if r.get("role") == "primary"]
    assert len({(r["seed"], r["mode"]) for r in primary}) == 45
    assert Counter(r["kind"] for r in primary) == {"medoid": 1, "seed": 4, "docking": 40}
    with_values = [r for r in primary if "values" in r]
    assert len(with_values) == 5 and all(r["mode"] == 0 for r in with_values)
    assert all("vina_affinity" in r["values"] for r in with_values)
    pb = {
        p["pose"]: p["passed"] for p in _findings(vina_run)["l4.posebusters"]["evidence"]["poses"]
    }
    assert all(r["posebusters"] == pb[r["pose"]] for r in with_values)
    assert all("values" not in r and "rmsdToMedoid" not in r for r in primary if r["mode"] > 0)
    for r in ens:
        assert r["perResidueConfidence"] is False  # docking complexes, crystal reference
        assert r["structureId"] in structures
        assert structures[r["structureId"]]["kind"] == r["kind"]
    redock = [r for r in ens if r.get("role") == "control:redocking"]
    assert all(isinstance(r["rmsdToReference"], float) for r in redock)
    assert redock[0]["label"].startswith("redocking · ")
    crystal = next(r for r in ens if r["kind"] == "crystal")
    assert crystal["rmsdToMedoid"] < 2.0
    # each render file is linked to the structure whose sha256 its caption names; when two
    # structures were rendered to one file name, the file shows the last one rendered
    report = json.loads((vina_run / "report.json").read_text())
    figures = [f for f in report["figures"] if f["kind"] == "render"]
    last = {f["path"]: f for f in figures}
    renders = vina["renders"]
    assert len(renders) == len(last) and len({r["png"] for r in renders}) == len(renders)
    for r in renders:
        caption_sha = ui_stats.caption_sha(r["caption"])
        assert caption_sha and structures[r["structure"]]["sha256"].startswith(caption_sha)
    assert vina["report"]["rendersOverwritten"] == len(figures) - len(last)
    by_structure = {r["structure"]: r["png"] for r in renders if r["view"] == "overview"}
    for row in ens:
        assert row.get("render") == by_structure.get(row["structureId"])


def test_overwritten_render_belongs_to_the_last_structure(tmp_path: Path) -> None:
    from pah.webui.adapter import last_renders, ui_renders

    run = _boltz_run(tmp_path)
    report = {
        "figures": [
            {
                "id": "render_model_overview",
                "kind": "render",
                "path": "renders/model_overview.png",
                "caption": f"{pid} (prediction_structure), whole structure. sha256 {str(i) * 16}.",
                "session_path": "renders/model.pse",
            }
            for i, pid in enumerate(("boltz2/seed0/sample0", "boltz2/seed0/sample1"))
        ]
    }
    (run / "report.json").write_text(json.dumps(report))
    kept, overwritten = last_renders(report["figures"])
    assert overwritten == 1 and kept == [report["figures"][1]]
    record = to_ui_record(run)
    (render,) = record["renders"]
    assert render["structure"] == "predictions/00_boltz2/boltz2/seed0/sample1/model"
    rows = {r["pose"]: r for r in record["stats"]["ensemble"]}
    assert "render" not in rows["boltz2/seed0/sample0"]
    assert rows["boltz2/seed0/sample1"]["render"] == render["png"]
    assert record["report"]["rendersOverwritten"] == 1
    meta = {"executor", "seed", "rank", "pose", "score", "checks"}
    plain = {k: v for k, v in render.items() if k not in meta}
    assert ui_renders(load_state(run), []) == [{**plain, "structure": "model"}]
    assert render["executor"] == "boltz2" and isinstance(render["checks"], list)


def test_docking_card_from_manifest_settings(vina: dict[str, Any]) -> None:
    card = vina["docking"]
    assert card["toolId"] == "vina" and card["tool"] == "AutoDock Vina"
    rows = dict(card["rows"])
    assert rows["Box centre (x, y, z)"] == "\N{MINUS SIGN}1.856, 14.366, 16.748\N{THIN SPACE}Å"
    assert rows["Exhaustiveness"] == "8" and rows["Seed"] == "0, 1, 2, 3, 4"
    assert rows["poses parsed"] == "45"
    assert card["source"]["field"] == "manifest.predictions[0].settings"
    params = {p["key"]: p for p in card["params"]}
    assert params["box_origin"]["declared"] is False


def test_structures_take_member_labels_and_skip_work_files(vina: dict[str, Any]) -> None:
    paths = [s["path"] for s in vina["structures"]]
    assert not [p for p in paths if p.startswith("artifacts/work/")]
    labels = Counter(s["label"] for s in vina["structures"])
    assert max(labels.values()) == 1  # primary and control poses share ids, not labels


def test_every_block_has_provenance(vina: dict[str, Any]) -> None:
    st = vina["stats"]
    prov = st["provenance"]
    checks = set(_findings_ids(vina))
    for block in st:
        if block == "provenance":
            continue
        assert block in prov, block
    for key, src in prov.items():
        named = [src["check"]] if src.get("check") else src.get("checks", [])
        assert all(c in checks for c in named), key


def _findings_ids(record: dict[str, Any]) -> list[str]:
    return [c["id"] for layer in record["layers"] for c in layer["checks"]]


# ---------------------------------------------------------------- synthetic records


def _write_run(
    tmp_path: Path,
    manifest: dict[str, Any],
    findings: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> Path:
    run = tmp_path / "run"
    run.mkdir(parents=True, exist_ok=True)
    record = {
        "run_id": "synthetic",
        "task": manifest["task"],
        "claim": "Pose within stated uncertainty",
        "layers": [4, 5],
        "manifest": manifest,
        "started_at": "2026-10-17T10:00:00Z",
        "finished_at": "2026-10-17T10:00:05Z",
        "findings": findings,
        "artifacts": artifacts,
        "provenance": [],
        "verdict": {"outcome": "pass", "stops": [], "warnings": []},
    }
    (run / "record.json").write_text(json.dumps(record))
    return run


def _finding(
    cid: str,
    layer: int,
    gate: str,
    measurements: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    tool: str | None = None,
) -> dict[str, Any]:
    return {
        "check_id": cid,
        "layer": layer,
        "gate": gate,
        "message": cid,
        "measurements": [
            {"name": k, "value": v, "unit": None} for k, v in (measurements or {}).items()
        ],
        "thresholds": [],
        "evidence": evidence or {},
        "tool": {"name": tool, "version": None} if tool else None,
    }


def test_skipped_checks_leave_blocks_out(tmp_path: Path) -> None:
    manifest = {"task": "ligand_pose", "ligands": [{"id": "x", "smiles": "C"}], "predictions": []}
    skip = {"skip_reason": "not_applicable"}
    findings = [
        _finding(cid, int(cid[1]), "skip", evidence=skip)
        for cid in (
            "l4.posebusters",
            "l4.torsion_strain",
            "l4.interactions.fingerprint",
            "l5.sampling.clusters",
            "l5.confidence.local",
            "l5.agreement.cross_family",
            "l5.controls.redocking",
        )
    ]
    record = to_ui_record(_write_run(tmp_path, manifest, findings, []))
    assert record["stats"] == {}
    assert "docking" not in record


def test_partial_evidence_keeps_only_reported_fields(tmp_path: Path) -> None:
    manifest = {"task": "ligand_pose", "predictions": []}
    findings = [
        _finding(
            "l5.sampling.clusters",
            5,
            "pass",
            measurements={"poses": 2, "clusters": 1, "largest_cluster": 2},
            evidence={
                "poses": [{"pose": "t/seed0/sample0", "cluster": 1}],
                "medoid": "t/seed0/sample0",
            },
        ),
    ]
    st = to_ui_record(_write_run(tmp_path, manifest, findings, []))["stats"]
    assert st["seeds"] == [{"pose": "t/seed0/sample0", "cluster": 1}]
    assert "pairwise" not in st and "sitePlacement" not in st
    assert dict(st["pose"])["largest cluster"] == "2/2 poses"


def _boltz_run(tmp_path: Path) -> Path:
    outside = tmp_path / "boltz_out"
    outside.mkdir()
    (outside / "lig_model_1.cif").write_text("data_x\n")
    manifest = {
        "task": "ligand_pose",
        "ligands": [{"id": "lig", "smiles": "NC(=N)c1ccccc1"}],
        "model": {"executor": "boltz2", "version": "2.2.1", "seeds": [0, 1]},
        "predictions": [{"executor": "boltz2", "path": str(outside), "role": "primary"}],
        "controls": {"decoys": [], "actives": []},
    }
    run = tmp_path / "run"
    poses = ["boltz2/seed0/sample0", "boltz2/seed0/sample1", "boltz2/seed1/sample0"]
    artifacts: list[dict[str, Any]] = []
    for i, pid in enumerate(poses):
        d = run / "predictions" / "00_boltz2" / pid
        d.mkdir(parents=True)
        (d / "ligand.sdf").write_text("x\n$$$$\n")
        if i < 2:  # model files copied into the run; the third stays in the tool's folder
            (d / "model.cif").write_text("data_x\n")
            structure = f"predictions/00_boltz2/{pid}/model.cif"
        else:
            structure = str(outside / "lig_model_1.cif")
        artifacts += [
            {
                "path": structure,
                "kind": "prediction_structure",
                "sha256": str(i) * 64,
                "label": pid,
            },
            {
                "path": f"predictions/00_boltz2/{pid}/ligand.sdf",
                "kind": "data",
                "label": f"{pid} ligand",
            },
        ]
    conf_rows = [
        {
            "pose": pid,
            "confidence_score": c,
            "iptm": c - 0.05,
            "ptm": 0.9,
            "complex_plddt": 0.88,
            "global_plddt": 88.1,
            "pocket_plddt": 91.2,
            "pocket_residues": 22,
        }
        for pid, c in zip(poses, (0.91, 0.87, 0.85), strict=True)
    ]
    findings = [
        _finding(
            "l5.confidence.local",
            5,
            "pass",
            measurements={"poses": 3, "confidence_score": 0.91},
            evidence={
                "representative": poses[0],
                "poses": conf_rows,
                "metrics": [
                    {
                        "name": "affinity_pred_value",
                        "value": -1.2,
                        "tool": "boltz2",
                        "read": "ranking within a series, never pose quality",
                        "separate": True,
                    }
                ],
            },
        ),
        _finding(
            "l5.sampling.clusters",
            5,
            "pass",
            measurements={"poses": 3, "clusters": 2, "largest_cluster": 2},
            evidence={
                "medoid": poses[0],
                "poses": [
                    {
                        "pose": p,
                        "executor": "boltz2",
                        "seed": int(p[11]),
                        "sample": int(p[-1]),
                        "cluster": 1 if j < 2 else 2,
                        "rmsd_to_medoid_A": r,
                        "confidence": c,
                    }
                    for j, (p, r, c) in enumerate(
                        zip(poses, (0.0, 0.6, 3.1), (0.91, 0.87, 0.85), strict=True)
                    )
                ],
                "pairwise_rmsd_A": {"median": 0.6, "q1": 0.6, "q3": 3.1, "n": 3},
            },
            tool="spyrmsd",
        ),
        _finding(
            "l4.posebusters",
            4,
            "pass",
            measurements={"poses": 3, "passed": 19, "total": 20},
            evidence={
                "representative": poses[0],
                "tests": [{"test": "bond_lengths", "pass": True, "value": "0 outliers"}],
                "poses": [{"pose": p, "passed": 19, "total": 20, "failed": ["x"]} for p in poses],
            },
            tool="posebusters",
        ),
    ]
    return _write_run(tmp_path, manifest, findings, artifacts)


def test_cofolding_finding_set(tmp_path: Path) -> None:
    record = to_ui_record(_boltz_run(tmp_path))
    st = record["stats"]
    assert "docking" not in record  # no docking executor in the run
    assert [t["id"] for t in record["tools"]] == ["boltz2"]
    metrics = {m["key"]: m for m in st["metrics"]}
    assert metrics["confidence_score"]["name"] == "Confidence score"
    assert metrics["iptm"]["name"] == "ipTM" and metrics["iptm"]["separate"] is False
    aff = metrics["affinity_pred_value"]
    assert aff["name"] == "Boltz-2 affinity" and aff["unit"] == "log10(µM)"
    assert aff["separate"] is True and aff["read"].startswith("ranking")
    assert not {"global_plddt", "pocket_plddt", "pocket_residues"} & set(metrics)
    seeds = st["seeds"]
    assert [s["confidenceKey"] for s in seeds] == ["confidence_score"] * 3
    assert [s["confidence"] for s in seeds] == [0.91, 0.87, 0.85]
    ens = {r["pose"]: r for r in st["ensemble"]}
    first = ens["boltz2/seed0/sample0"]
    assert first["kind"] == "medoid" and first["perResidueConfidence"] is True
    assert first["perResidueConfidenceKey"] == "plddt"
    assert first["values"]["iptm"] == pytest.approx(0.86) and first["pocketPlddt"] == 91.2
    assert first["posebusters"] == 19 and first["posebustersTotal"] == 20
    assert "mode" not in first and first["sample"] == 0
    assert ens["boltz2/seed0/sample1"]["kind"] == "seed"
    ids = {s["id"] for s in record["structures"]}
    assert first["structureId"] in ids
    # the model file outside the run directory is not served
    outside = ens["boltz2/seed1/sample0"]
    assert "structureId" not in outside and outside["ligand"]["format"] == "sdf"
    assert outside["id"] == "predictions/00_boltz2/boltz2/seed1/sample0"


def test_members_resolve_sets_from_work_directories(tmp_path: Path) -> None:
    run = _boltz_run(tmp_path)
    inp = stats_input(load_state(run))
    members = ui_stats.members(inp)
    assert [m.role for m in members] == ["primary"] * 3
    assert [(m.seed, m.sample, m.sample_kind) for m in members] == [
        (0, 0, "sample"),
        (0, 1, "sample"),
        (1, 0, "sample"),
    ]


def test_spec_roles_follow_prediction_set_order() -> None:
    manifest = {
        "predictions": [{"executor": "boltz2"}, {"executor": "gnina", "role": "secondary"}],
        "controls": {
            "redocking": {"executor": "vina"},
            "decoys": [{"executor": "vina"}],
            "actives": [],
        },
    }
    assert ui_stats.spec_roles(manifest) == [
        ("boltz2", "primary"),
        ("gnina", "secondary"),
        ("vina", "control:redocking"),
        ("vina", "control:decoy"),
    ]
    assert ui_stats.primary_index(ui_stats.spec_roles(manifest), {1, 2}) == 1


def test_formatting_and_units() -> None:
    assert ui_stats.fmt(-6.131, "kcal/mol") == "\N{MINUS SIGN}6.131\N{THIN SPACE}kcal/mol"
    assert ui_stats.fmt(22) == "22" and ui_stats.fmt(4.0) == "4" and ui_stats.fmt(True) == "True"
    assert ui_stats.fraction(5, 5) == "5/5" and ui_stats.fraction(None, 5) is None
    assert ui_stats.unit_of("volume_A3") == "Å³" and ui_stats.unit_of("rmsd_A") == "Å"
    assert ui_stats.unit_of("strain_kcal") == "kcal/mol" and ui_stats.unit_of("poses") is None
    assert ui_stats.unit_of("x_A", "nm") == "nm"
    assert ui_stats.number(float("nan")) is None and ui_stats.number(True) is None
    assert (
        ui_stats.caption_sha("vina/seed0/mode0 (x), y. sha256 032df7660f625e99.")
        == "032df7660f625e99"
    )


def test_crystal_row_is_the_declared_reference(tmp_path: Path) -> None:
    run = _boltz_run(tmp_path)
    record = json.loads((run / "record.json").read_text())
    record["manifest"]["receptor"] = {"pdb_id": "3ptb"}
    (run / "record.json").write_text(json.dumps(record))
    sources = run / "artifacts" / "sources"
    sources.mkdir(parents=True)
    for pdb in ("3PTB", "1BTY"):  # 1BTY stands for an entry fetched by an exposure check
        (sources / f"{pdb}.cif").write_text("data_x\n")
    ens = to_ui_record(run)["stats"]["ensemble"]
    crystal = [r for r in ens if r["kind"] == "crystal"]
    assert [r["structureId"] for r in crystal] == ["artifacts/sources/3PTB"]
    assert "rmsdToMedoid" not in crystal[0]  # no agreement finding in this record


# ---------------------------------------------------------------- blocks ported from pah.api.stats


def test_cluster_reference_and_flag_blocks(vina: dict[str, Any], vina_run: Path) -> None:
    st = vina["stats"]
    found = _findings(vina_run)
    clusters = found["l5.sampling.clusters"]["evidence"]
    assert st["clusters"] == clusters["clusters"] and st["medoid"] == clusters["medoid"]
    assert (
        st["interactionsPose"] == found["l4.interactions.fingerprint"]["evidence"]["representative"]
    )
    redock = found["l5.controls.redocking"]["evidence"]
    assert st["reference"]["redocking"] == {
        "rmsd": redock["rmsd_A"],
        "pose": redock["pose"],
        "reference": redock["reference"],
        "unit": "Å",
    }
    assert "rmsdToCrystal" not in st["reference"]  # l5.rmsd_to_crystal is not in this task
    failed = {p["pose"]: p["failed"] for p in found["l4.posebusters"]["evidence"]["poses"]}
    assert {r["pose"]: r["pbFailed"] for r in st["physics"]} == failed
    assert all("converged" not in r for r in st["physics"])  # minimisation skipped
    assert "pae" not in st  # docking poses carry no PAE


def test_pae_and_global_plddt_for_cofolding(tmp_path: Path) -> None:
    run = _boltz_run(tmp_path)
    pae = run / "predictions" / "00_boltz2" / "boltz2" / "seed0" / "sample0" / "pae.npy"
    pae.write_bytes(b"\x93NUMPY")
    record = json.loads((run / "record.json").read_text())
    conf = next(f for f in record["findings"] if f["check_id"] == "l5.confidence.local")
    conf["evidence"]["pae"] = {"pose": "boltz2/seed0/sample0", "path": str(pae)}
    (run / "record.json").write_text(json.dumps(record))
    st = to_ui_record(run)["stats"]
    rel = "predictions/00_boltz2/boltz2/seed0/sample0/pae.npy"
    assert st["pae"] == {
        "path": rel,
        "url": f"/runs/run/files/{rel}",
        "format": "npy",
        "pose": "boltz2/seed0/sample0",
    }
    rows = {r["pose"]: r for r in st["ensemble"]}
    assert rows["boltz2/seed0/sample0"]["globalPlddt"] == 88.1
    assert st["provenance"]["ensemble.globalPlddt"]["check"] == "l5.confidence.local"


def test_docking_box_from_check_evidence_when_settings_lack_it(tmp_path: Path) -> None:
    manifest = {
        "task": "ligand_pose",
        "predictions": [
            {"executor": "vina", "path": "x", "seeds": [1], "settings": {"exhaustiveness": 8}}
        ],
    }
    box = {"center": [1.0, 2.0, 3.0], "size": [20, 20, 20], "origin": "BEN in 3PTB + 4 Å"}
    findings = [_finding("l2.docking.box", 2, "pass", evidence=box)]
    card = to_ui_record(_write_run(tmp_path, manifest, findings, []))["docking"]
    rows = dict(card["rows"])
    assert rows["Box centre (x, y, z)"] == "1, 2, 3\N{THIN SPACE}Å"
    assert rows["Box size (x, y, z)"] == "20, 20, 20\N{THIN SPACE}Å"
    assert rows["box origin"] == box["origin"] and rows["Exhaustiveness"] == "8"
    params = {p["key"]: p for p in card["params"]}
    assert params["center"]["check"] == "l2.docking.box" and "check" not in params["exhaustiveness"]


def test_map_outputs_resolve_to_their_declared_key(tmp_path: Path) -> None:
    manifest = {
        "task": "known_complex_assembly",
        "predictions": [{"executor": "colabfold", "path": "x"}],
    }
    rows = [{"pose": "colabfold/seed0/sample0", "iptm": 0.6, "pdockq.A-B": 0.3}]
    ev = {"representative": "colabfold/seed0/sample0", "poses": rows, "metrics": []}
    findings = [_finding("l5.confidence.local", 5, "pass", evidence=ev)]
    metrics = {
        m["key"]: m
        for m in to_ui_record(_write_run(tmp_path, manifest, findings, []))["stats"]["metrics"]
    }
    assert metrics["pdockq.A-B"]["name"] == "pDockQ A-B" and metrics["pdockq.A-B"]["declared"]
    assert metrics["iptm"]["name"] == "ipTM"


# ---------------------------------------------------------------- register keys against the parsers


def _parse_tree(base: Path, executor: str) -> Any:
    from pah.core.manifest import LigandInput, Manifest, PredictionInput
    from pah.executors.base import parse_prediction
    from tests import executor_trees as trees

    rec = {"receptor": Path("rec.pdb")}
    cases: dict[str, tuple[Any, str, dict[str, Any]]] = {
        "boltz2": (lambda: trees.boltz_tree(base / "out"), "out", {"seeds": (7,)}),
        "protenix": (lambda: trees.protenix_tree(base / "out"), "out", {}),
        "alphafold3": (lambda: trees.alphafold3_tree(base / "out"), "out", {}),
        "chai1": (lambda: trees.chai_tree(base / "chai"), "chai", {"seeds": (3,)}),
        "colabfold": (lambda: trees.colabfold_tree(base / "cf"), "cf", {}),
        "vina": (lambda: trees.vina_out(base / "d" / "ben_out.pdbqt"), "d/ben_out.pdbqt", rec),
        "gnina": (lambda: trees.gnina_sdf(base / "docked.sdf"), "docked.sdf", rec),
        "diffdock": (lambda: trees.diffdock_tree(base / "dd"), "dd", rec),
        "haddock3": (lambda: trees.haddock_tree(base / "run1"), "run1", {}),
    }
    build, path, kw = cases[executor]
    build()
    trees.write_pdb(base / "rec.pdb", with_ligand=False)
    ligands = (LigandInput(id=trees.LIGAND_ID, smiles=trees.SMILES),)
    manifest = Manifest(task="pose", ligands=ligands, base_dir=base)
    spec = PredictionInput(executor=executor, path=Path(path), **kw)
    return parse_prediction(spec, manifest, base / "work")


@pytest.mark.parametrize(
    "executor",
    [
        "boltz2",
        "protenix",
        "alphafold3",
        "chai1",
        "colabfold",
        "vina",
        "gnina",
        "diffdock",
        "haddock3",
    ],
)
def test_every_parsed_score_key_is_declared(tmp_path: Path, executor: str) -> None:
    pytest.importorskip("rdkit")
    pytest.importorskip("gemmi")
    from pah.webui.adapter import executor_rows, record_tool

    rows = executor_rows()
    tools = {str(r["id"]): record_tool(str(r["id"]), rows) for r in rows}
    inp = ui_stats.StatsInput("r", tmp_path, [], {}, [], tools)
    keys = {k for p in _parse_tree(tmp_path, executor).poses for k in p.scores}
    assert keys and not [k for k in keys if inp.output(executor, k) is None]


# ---------------------------------------------------------------- gates and executor provenance


def test_gate_comes_from_gate_kind_and_escalate(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from pah.core.check import CHECKS, GateKind
    from pah.webui.adapter import checks_registry, failure_gate

    checks_registry()
    assert failure_gate("l1.ligand.stereo_defined", None) == "Warn"  # declared GateKind.WARN
    assert failure_gate("l1.ligand.identity", None) == "Stop"  # default GateKind.STOP
    assert failure_gate("not.a.check", None) == "Stop"
    task = SimpleNamespace(escalate=("l1.ligand.stereo_defined",))
    assert failure_gate("l1.ligand.stereo_defined", task) == "Stop"  # type: ignore[arg-type]
    monkeypatch.setattr(CHECKS["l4.posebusters"], "gate_kind", GateKind.REPORTED)
    assert failure_gate("l4.posebusters", None) == "Reported"


def test_tools_ran_by(vina: dict[str, Any], tmp_path: Path) -> None:
    (tool,) = vina["tools"]
    assert (tool["id"], tool["ran"], tool["ranBy"]) == ("vina", True, "external")
    # declared model without outputs: nothing ran
    plain = {"task": "ligand_pose", "model": {"executor": "boltz2"}, "predictions": []}
    run = _write_run(tmp_path / "a", plain, [], [])
    assert [(t["ran"], t["ranBy"]) for t in to_ui_record(run)["tools"]] == [(False, None)]
    # started from settings: executors are not run, whatever the manifest names
    with_preds = {**plain, "predictions": [{"executor": "boltz2", "path": "x"}]}
    run = _write_run(tmp_path / "b", with_preds, [], [])
    (run / "job.json").write_text(json.dumps({"executors": "not run (checks only)"}))
    assert [(t["ran"], t["ranBy"]) for t in to_ui_record(run)["tools"]] == [(False, None)]
    # an exec stage of the run's own event stream names the executor
    run = _write_run(tmp_path / "c", plain, [], [])
    event = {
        "seq": 1,
        "kind": "log",
        "stage": "exec",
        "message": "boltz2",
        "ts": "2026-10-17T10:00:01Z",
        "data": {"executor": "boltz2"},
    }
    (run / "events.jsonl").write_text(json.dumps(event) + "\n")
    assert [(t["ran"], t["ranBy"]) for t in to_ui_record(run)["tools"]] == [(True, "harness")]


def test_identical_files_each_keep_a_render(tmp_path: Path) -> None:
    run = _boltz_run(tmp_path)
    record = json.loads((run / "record.json").read_text())
    for a in record["artifacts"]:
        if a["kind"] == "prediction_structure":
            a["sha256"] = "0" * 64  # byte-identical models render alike
    (run / "record.json").write_text(json.dumps(record))
    figures = [
        {
            "id": f"render_{stem}_overview",
            "kind": "render",
            "path": f"renders/{stem}_overview.png",
            "caption": f"model (prediction_structure), whole structure. sha256 {'0' * 16}.",
            "session_path": f"renders/{stem}.pse",
        }
        for stem in ("00_boltz2_a", "00_boltz2_b")
    ]
    (run / "report.json").write_text(json.dumps({"figures": figures}))
    record_ui = to_ui_record(run)
    linked = [r["structure"] for r in record_ui["renders"]]
    assert linked == [
        "predictions/00_boltz2/boltz2/seed0/sample0/model",
        "predictions/00_boltz2/boltz2/seed0/sample1/model",
    ]
    assert record_ui["report"]["rendersOverwritten"] == 0
