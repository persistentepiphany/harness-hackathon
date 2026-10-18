"""What the UI may claim about a run: scope of the verdict, pending vs not applicable, exercised
tools, execution progress, absent blocks, endpoint-compatible suggestions and the /ui read routes
that describe tools, tasks, prompts and scores."""

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from pah.config import Profile
from pah.webui import assessment
from pah.webui.adapter import (
    compatible_tools,
    load_state,
    loglines,
    model_endpoints,
    task_endpoint,
    to_job,
    to_ui_record,
    tool_register,
)
from pah.webui.catalog import load_catalog
from pah.webui.interpret import interpret_request

PRE_RUN = "no predictions declared (pre-run assessment)"
TS = "2026-10-17T10:00:00Z"


def _finding(
    cid: str,
    layer: int,
    gate: str,
    message: str = "ok",
    *,
    tool: str | None = None,
    skip_reason: str | None = None,
    thresholds: list[dict[str, Any]] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ev = dict(evidence or {})
    if skip_reason:
        ev["skip_reason"] = skip_reason
    out: dict[str, Any] = {
        "check_id": cid,
        "layer": layer,
        "gate": gate,
        "message": message,
        "measurements": [],
        "thresholds": thresholds or [],
        "evidence": ev,
    }
    if tool:
        out["tool"] = {"name": tool, "version": "1.0"}
    return out


def _write_run(
    root: Path,
    run_id: str,
    findings: list[dict[str, Any]],
    verdict: dict[str, Any],
    *,
    manifest: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
    task: str = "ligand_pose",
    tool_versions: dict[str, str] | None = None,
) -> Path:
    run = root / run_id
    run.mkdir(parents=True)
    man = manifest or {
        "task": task,
        "proteins": [{"id": "trypsin", "uniprot": "P00760", "pdb_id": "3PTB"}],
        "model": {"executor": "vina", "version": "1.2.5", "seeds": [0, 1]},
    }
    record = {
        "run_id": run_id,
        "task": task,
        "claim": "Pose within stated uncertainty",
        "layers": [0, 1, 2, 3, 4, 5],
        "manifest": man,
        "findings": findings,
        "verdict": {"claim": "Pose within stated uncertainty", **verdict},
        "tool_versions": tool_versions or {},
        "started_at": TS,
        "finished_at": TS,
    }
    (run / "record.json").write_text(json.dumps(record))
    lines = [
        {"seq": 0, "run_id": run_id, "ts": TS, "kind": "run_start", "stage": "run",
         "message": "start", "data": {"task": task, "layers": [0, 1, 2, 3, 4, 5]}},
        *(events or []),
    ]  # fmt: skip
    (run / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in lines))
    old = time.time() - 60
    os.utime(run / "events.jsonl", (old, old))
    return run


def _pre_run_findings() -> list[dict[str, Any]]:
    return [
        _finding("l0.sources.resolved", 0, "pass", "8 identifiers resolved to 7 records"),
        _finding("l1.ligand.sanitization", 1, "pass", tool="rdkit"),
        _finding("l1.msa.integrity", 1, "skip", "no MSA declared", skip_reason="not_applicable"),
        _finding("l2.ligand.protonation", 2, "warn", "2 states", tool="dimorphite_dl"),
        _finding("l3.metric.endpoint", 3, "pass", "endpoint pose produced by vina"),
        _finding("l4.posebusters", 4, "skip", PRE_RUN, skip_reason="not_applicable"),
        _finding("l5.sampling.seeds", 5, "skip", PRE_RUN, skip_reason="not_applicable"),
    ]


def _checks(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for layer in record["layers"] for c in layer["checks"]}


# ---------------------------------------------------------------- scope of the verdict


def test_pre_run_is_not_assessed_with_scoped_statement(tmp_path: Path) -> None:
    run = _write_run(
        tmp_path,
        "pre-01",
        _pre_run_findings(),
        {"outcome": "pass_with_warnings", "stops": [], "warnings": ["l2.ligand.protonation"],
         "not_applicable": ["l1.msa.integrity", "l4.posebusters", "l5.sampling.seeds"]},
        tool_versions={"rdkit": "2026.9.1", "posebusters": "0.6.5"},
    )  # fmt: skip
    record = to_ui_record(run)
    v = record["verdict"]
    assert record["assessment"] == "pre-run"
    assert record["evaluatedLayers"] == [0, 1, 2, 3]
    assert v["outcome"] == "not_assessed" and v["engineOutcome"] == "narrowed"
    assert v["scope"] == "layers 0-3"
    assert v["statement"].startswith(
        "Pre-run check: layers 0-3 evaluated; layers 4-5 pending predictions."
    )
    assert "1 check warned in layer 2: l2.ligand.protonation." in v["statement"]
    assert v["assessedClaim"] == "Inputs fit to run"
    assert "l4.posebusters" in v["pending"] and "l5.sampling.seeds" in v["pending"]
    assert v["notApplicable"] == ["l1.msa.integrity"]
    checks = _checks(record)
    assert checks["l4.posebusters"]["skipReason"] == "pending_input"
    assert checks["l1.msa.integrity"]["skipReason"] == "not_applicable"
    job = to_job(run)
    assert job["verdict"] == "not_assessed" and job["assessment"] == "pre-run"
    assert job["layers"][4]["result"] == "pending"
    assert job["layers"][4]["pending"] == ["l4.posebusters"]
    end = [line for line in loglines(load_state(run).events, run) if line["kind"] == "run"]
    assert end[0]["kind"] == "run"


def test_pre_run_stop_stays_refused(tmp_path: Path) -> None:
    findings = _pre_run_findings()
    findings[4] = _finding("l3.metric.endpoint", 3, "stop", "vina does not produce affinity")
    run = _write_run(
        tmp_path,
        "pre-02",
        findings,
        {"outcome": "stop", "stops": ["l3.metric.endpoint"], "warnings": []},
    )
    v = to_ui_record(run)["verdict"]
    assert v["outcome"] == "refused"
    assert "1 check stopped in layer 3: l3.metric.endpoint." in v["statement"]
    assert v["statement"].endswith("is not supported.")
    assert to_job(run)["verdict"] == "refused"


def test_full_run_keeps_the_engine_outcome(tmp_path: Path) -> None:
    findings = [
        *_pre_run_findings()[:5],
        _finding("l4.posebusters", 4, "pass", "20 of 20", tool="posebusters"),
        _finding("l5.sampling.seeds", 5, "pass", "2 seeds"),
    ]
    manifest = {
        "task": "ligand_pose",
        "proteins": [{"id": "trypsin", "uniprot": "P00760"}],
        "model": {"executor": "vina", "seeds": [0, 1]},
        "predictions": [{"executor": "vina", "path": "predictions/vina"}],
    }
    run = _write_run(
        tmp_path,
        "full-01",
        findings,
        {"outcome": "pass_with_warnings", "stops": [], "warnings": ["l2.ligand.protonation"]},
        manifest=manifest,
        tool_versions={"posebusters": "0.6.5", "numpy": "1.26.4"},
    )
    record = to_ui_record(run)
    assert record["assessment"] == "full"
    assert record["verdict"]["outcome"] == "narrowed"
    assert record["verdict"]["assessedClaim"] is None
    assert record["evaluatedLayers"] == [0, 1, 2, 3, 4, 5]
    versions = {t["name"]: t for t in record["toolVersions"]}
    assert versions["posebusters"]["exercised"] is True
    assert versions["posebusters"]["checks"] == ["l4.posebusters"]
    assert versions["numpy"]["exercised"] is False  # declared only


def test_layer_span_and_phrase() -> None:
    assert assessment.layer_span([0, 1, 2, 3]) == "0-3"
    assert assessment.layer_span([0, 1, 3]) == "0-1,3"
    assert assessment.layers_phrase([1]) == "layer 1"
    assert assessment.layers_phrase([]) == "no layer"


# ---------------------------------------------------------------- execution events


def _exec(seq: int, phase: str, **data: Any) -> dict[str, Any]:
    return {
        "seq": seq,
        "run_id": "exec-01",
        "ts": f"2026-10-17T10:00:{seq:02d}Z",
        "kind": "log",
        "stage": "execute",
        "message": data.pop("message", f"boltz2 {phase}"),
        "data": {"stage": "execute", "executor": "boltz2", "phase": phase, **data},
    }


def test_execution_events_aggregate_per_executor(tmp_path: Path) -> None:
    events = [
        _exec(1, "queued"),
        _exec(2, "building", gpu="A100", route="kit"),
        _exec(3, "running", seed=0),
        _exec(4, "done", seed=0, elapsedMs=4200),
        _exec(5, "done", elapsedMs=9000, message="2 structures written"),
    ]
    run = _write_run(tmp_path, "exec-01", _pre_run_findings(), {"outcome": "pass"}, events=events)
    record = to_ui_record(run)
    (row,) = record["execution"]
    assert (row["executor"], row["name"], row["phase"]) == ("boltz2", "Boltz-2", "done")
    assert (row["gpu"], row["route"], row["elapsedMs"]) == ("A100", "kit", 9000)
    assert row["seeds"] == [{"seed": 0, "phase": "done", "ms": 4200}]
    assert row["message"] == "2 structures written"
    assert record["assessment"] == "full"  # outputs are being produced
    assert to_job(run)["execution"] == record["execution"]
    lines = [line for line in loglines(load_state(run).events, run) if line["kind"] == "exec"]
    assert len(lines) == 5 and lines[-1]["result"] == "pass"
    assert "seed 0" in lines[2]["text"]


# ---------------------------------------------------------------- absent blocks


def test_stats_status_explains_absent_blocks(tmp_path: Path) -> None:
    run = _write_run(tmp_path, "na-01", _pre_run_findings(), {"outcome": "pass"})
    stats = to_ui_record(run)["stats"]
    assert "pae" not in stats and "agreement" not in stats
    assert stats["status"]["pae"]["status"] == "na"
    assert "AutoDock Vina declares no PAE output" in stats["status"]["pae"]["reason"]
    assert stats["status"]["agreement"]["status"] == "na"
    assert stats["status"]["posebusters"] == {"status": "pending", "reason": "pending predictions"}


def test_check_rows_carry_the_sources_they_used(tmp_path: Path) -> None:
    run = _write_run(tmp_path, "src-01", _pre_run_findings(), {"outcome": "pass"})
    rec = json.loads((run / "record.json").read_text())
    rec["provenance"] = [
        {"source_id": "uniprot", "accession": "P00760", "sha256": "ab" * 32, "release": "2026_03"}
    ]
    rec["usage"] = {"l0.sources.resolved": [f"uniprot:P00760:{'ab' * 6}"]}
    (run / "record.json").write_text(json.dumps(rec))
    checks = _checks(to_ui_record(run))
    assert checks["l0.sources.resolved"]["sources"] == [f"uniprot:P00760:{'ab' * 6}"]
    assert checks["l1.ligand.sanitization"]["sources"] == []


# ---------------------------------------------------------------- standing and dimensions


TABLE = assessment.standing_table(
    {
        "standings": [{"id": s} for s in assessment.STANDINGS],
        "categories": [
            {"id": "provenance_identity", "dimension": "inputs"},
            {"id": "applicability", "dimension": "exposure"},
            {"id": "physical_validity", "dimension": "physical_validity"},
        ],
        "dimensions": [
            {"id": "inputs", "label": "Inputs", "categories": ["provenance_identity"]},
            {"id": "exposure", "label": "Exposure", "categories": ["applicability"]},
            {"id": "physical_validity", "label": "Physical validity",
             "categories": ["physical_validity"]},
        ],
        "checks": {
            "l0.a": {"category": "provenance_identity", "standing": "definitional",
                     "decisive": True},
            "l0.b": {"category": "provenance_identity", "standing": "uncalibrated",
                     "decisive": False},
            "l3.metric.endpoint": {"category": "applicability", "standing": "definitional",
                                   "decisive": True},
            "l4.p": {"category": "physical_validity", "standing": "published", "decisive": True},
        },
    }
)  # fmt: skip


def test_dimensions_follow_categories_and_weakest_standing() -> None:
    checks = [
        {"id": c, "result": r, **assessment.check_labels(None, c, TABLE)}
        for c, r in (
            ("l0.a", "pass"),
            ("l0.b", "warn"),
            ("l3.metric.endpoint", "stop"),
            ("l4.p", "skip"),
        )
    ]
    checks[3]["skipReason"] = "pending_input"
    dims = {d["id"]: d for d in assessment.dimensions(checks, TABLE)}
    assert dims["inputs"]["result"] == "warn" and dims["inputs"]["certainty"] == "uncalibrated"
    assert dims["inputs"]["decisive"] == ["l0.a"]
    assert dims["exposure"]["result"] == "stop" and dims["exposure"]["certainty"] == "definitional"
    assert dims["physical_validity"]["result"] == "pending"
    assert dims["physical_validity"]["certainty"] == "none"


def test_policy_downgrade_is_labelled() -> None:
    f = _finding(
        "l0.b",
        0,
        "warn",
        evidence={"policy": {"original_gate": "stop", "reason": "stop downgraded by policy"}},
    )
    labels = assessment.check_labels(f, "l0.b", TABLE)
    assert labels["downgraded"] is True and labels["originalGate"] == "stop"
    assert labels["decisive"] is False and labels["standing"] == "uncalibrated"


# ---------------------------------------------------------------- suggestions


def _executor(tool_id: str) -> str:
    entry = load_catalog().tool(tool_id)
    return entry.executor if entry and entry.executor else tool_id


def test_catalog_default_tools_have_the_task_endpoint() -> None:
    for task in load_catalog().tasks:
        endpoint = task_endpoint(task.pah)
        assert endpoint, task.id
        for tool in task.default_tools:
            assert endpoint in model_endpoints(_executor(tool)), (task.id, tool, endpoint)


def test_sample_prompts_map_to_quick_setup_tasks_with_compatible_tools() -> None:
    cat = load_catalog()
    assert cat.prompts
    quick = {t.id for t in cat.tasks if t.quick_setup}
    for prompt in cat.prompts:
        out = interpret_request(prompt)
        assert out["task"] in quick, prompt
        endpoint = task_endpoint(cat.task(out["task"]).pah)  # type: ignore[union-attr]
        for tool in out["tools"]:
            assert endpoint in model_endpoints(tool), (prompt, tool)
        assert not [w for w in out["warnings"] if "does not produce" in w], prompt
        if "partner" in cat.task(out["task"]).inputs:  # type: ignore[union-attr]
            assert out["partner"], prompt


def test_named_incompatible_tool_is_kept_with_a_warning() -> None:
    out = interpret_request("Screen the erlotinib library against EGFR with Vina and DiffDock-L")
    assert out["task"] == "virtual_screening"
    assert out["tools"] == ["vina", "diffdock"]
    assert any(w.startswith("diffdock does not produce score_within_run") for w in out["warnings"])
    assert any(s["field"] == "warning" for s in out["steps"])


def test_compatible_tools_follow_models_yaml() -> None:
    assert compatible_tools("affinity_ranking") == ["boltz2"]
    assert set(compatible_tools("protein_protein_docking")) >= {"haddock3", "pydock"}
    assert "diffdock" not in compatible_tools("virtual_screening")


# ---------------------------------------------------------------- read routes


@pytest.fixture
def client(offline_profile: Profile) -> Any:
    pytest.importorskip("fastapi")
    pytest.importorskip("sse_starlette")
    from fastapi.testclient import TestClient

    from pah.interfaces.api import create_app

    return TestClient(create_app(offline_profile))


def test_tools_carry_endpoints_and_dispatch(client: Any) -> None:
    tools = {t["id"]: t for t in client.get("/ui/tools").json()}
    assert "pose" in tools["vina"]["endpoints"]
    assert tools["vina"]["route"] == "local" and tools["vina"]["dispatchable"] is True
    assert tools["boltz2"]["route"] == "modal" and tools["boltz2"]["gpu"]
    assert tools["boltz2"]["available"] is True
    assert "not installed on this host" not in tools["boltz2"]["note"]
    assert tools["pydock"]["dispatchable"] is False and tools["pydock"]["available"] is False


def test_tool_register_matches_route(offline_profile: Profile) -> None:
    rows = {t["id"]: t for t in tool_register(offline_profile.name)}
    assert all(t["available"] for t in rows.values() if t["route"] == "modal")


def test_tasks_catalog_and_glossary_routes(client: Any) -> None:
    tasks = {t["id"]: t for t in client.get("/ui/tasks").json()}
    assert tasks["affinity_ranking"]["endpoint"] == "affinity_series"
    assert tasks["affinity_ranking"]["compatibleTools"] == ["boltz2"]
    assert tasks["affinity_ranking"]["quickSetup"] is False
    assert tasks["protein_protein_docking"]["group"] == "protein-protein"
    assert tasks["pose_known_pocket"]["quickSetup"] is True
    assert client.get("/ui/catalog").json()["prompts"] == list(load_catalog().prompts)
    scores = {s["key"]: s for s in client.get("/ui/glossary").json()["scores"]}
    assert "vina" in scores["vina_affinity"]["producedBy"]
    assert scores["vina_affinity"]["unit"] == "kcal/mol"
    strain = scores["l4.torsion_strain"]
    assert strain["kind"] == "check" and strain["measurements"] == ["torsion_energy"]
    assert strain["higherIsBetter"] is False
    assert all(s["what"] and s["inputs"] for s in scores.values())
