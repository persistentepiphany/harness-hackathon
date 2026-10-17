"""Web UI fixes from QA: gate kinds, threshold links, figures, job layers, live manifests, the
log tail and job.json, CORS `*`, non-run directories, agent log JSON and request body limits."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sse_starlette")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pah.config import Profile


def _profile(tmp_path: Path) -> Profile:
    return Profile(name="t", backend="local", cache_dir=tmp_path / "c", runs_dir=tmp_path / "r")


# ---------------------------------------------------------------- check metadata


def test_checks_that_never_stop_do_not_declare_stop() -> None:
    from pah.core.check import GateKind
    from pah.webui.adapter import checks_registry, failure_gate

    reg = checks_registry()
    warn = (
        "l3.exposure.ligand_prevalence",
        "l3.exposure.pocket",
        "l3.regime.modality",
        "l3.exposure.chemotype",
        "l2.receptor.state",
        "l2.receptor.protonation",
        "l2.ligand.protonation",
    )
    for cid in warn:
        assert reg[cid].gate_kind is GateKind.WARN, cid
        assert failure_gate(cid, None) == "Warn"
    assert reg["l3.exposure.sequence"].gate_kind is GateKind.REPORTED
    assert failure_gate("l3.exposure.sequence", None) == "Reported"


def test_threshold_names_its_measurement_and_the_adapter_copies_it() -> None:
    from pah.checks import resolve
    from pah.webui.adapter import ui_check

    t = resolve.threshold("undefined_stereo", 0, "==", "spec", "published", measurement="undefined")
    assert t.measurement == "undefined"
    assert resolve.threshold("x", 1, "<", "spec").measurement is None
    finding = {
        "check_id": "l1.ligand.stereo_defined",
        "gate": "warn",
        "message": "1 stereo elements undefined",
        "measurements": [{"name": "undefined", "value": 1, "unit": None}],
        "thresholds": [t.model_dump(mode="json")],
    }
    row = ui_check(finding, None)
    assert row["thresholds"][0]["measurement"] == "undefined"
    plain = dict(finding, thresholds=[resolve.threshold("x", 1, "<", "s").model_dump(mode="json")])
    assert "measurement" not in ui_check(plain, None)["thresholds"][0]


def test_layer_figures_skip_missing_values_and_take_units_from_names() -> None:
    from pah.webui.adapter import _figures

    findings = [
        {"gate": "warn", "measurements": [{"name": "ph", "value": None}]},
        {"gate": "pass", "measurements": [{"name": "volume_A3", "value": 1477.9}]},
        {"gate": "pass", "measurements": [{"name": "rmsd_A", "value": 0.416}]},
        {"gate": "pass", "measurements": [{"name": "score", "value": -6.1, "unit": "kcal/mol"}]},
        {"gate": "pass", "measurements": [{"name": "tagged", "value": True}]},
    ]
    assert _figures(findings) == [
        ["volume", "1477.9\N{THIN SPACE}Å³"],
        ["rmsd", "0.416\N{THIN SPACE}Å"],
        ["score", "\N{MINUS SIGN}6.1\N{THIN SPACE}kcal/mol"],
        ["tagged", "true"],
    ]


# ---------------------------------------------------------------- run state


def _events(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "events.jsonl").open("w") as fh:
        for i, row in enumerate(rows, 1):
            base = {"seq": i, "ts": "2026-10-17T12:00:00Z", "stage": "run", "message": ""}
            fh.write(json.dumps({**base, **row}) + "\n")


def test_live_run_takes_its_manifest_from_run_start(tmp_path: Path) -> None:
    from pah.webui.adapter import load_state

    manifest = {
        "task": "ligand_pose",
        "proteins": [{"id": "trypsin", "uniprot": "P00760"}],
        "ligands": [{"id": "BEN", "ccd": "BEN"}],
    }
    run = tmp_path / "cli-run"
    _events(run, [{"kind": "run_start", "data": {"task": "ligand_pose", "manifest": manifest}}])
    state = load_state(run)
    assert state.manifest is not None
    assert [p["id"] for p in state.manifest["proteins"]] == ["trypsin"]


def test_job_layer_lists_checks_that_leave_the_verdict_incomplete(tmp_path: Path) -> None:
    from pah.webui.adapter import to_job

    run = tmp_path / "skip-run"
    finding = {
        "check_id": "l4.minimisation_drift",
        "layer": 4,
        "gate": "skip",
        "evidence": {"skip_reason": "tool_missing"},
    }
    passed = {"check_id": "l4.posebusters", "layer": 4, "gate": "pass", "evidence": {}}
    _events(
        run,
        [
            {"kind": "run_start", "data": {"task": "ligand_pose", "layers": [4]}},
            {"kind": "finding", "stage": "L4", "data": {"finding": passed}},
            {"kind": "finding", "stage": "L4", "data": {"finding": finding}},
        ],
    )
    job = to_job(run)
    layer4 = next(layer for layer in job["layers"] if layer["i"] == 4)
    assert layer4["incomplete"] == ["l4.minimisation_drift"]
    assert all("incomplete" not in layer for layer in job["layers"] if layer["i"] != 4)


def test_report_stage_of_a_failed_job_is_failed(tmp_path: Path) -> None:
    from pah.webui.adapter import _report_status

    events = [{"kind": "stage_start", "stage": "report"}]
    assert _report_status(events, None) == ("running", None)
    failed = {"status": "failed", "error": "RuntimeError: render"}
    assert _report_status(events, None, failed) == ("failed", "RuntimeError: render")


# ---------------------------------------------------------------- log tail


def _tail(path: Path, status: list[str | None], **kw: Any) -> tuple[list[int], float]:
    from pah.webui.store import tail_jsonl

    async def consume() -> list[int]:
        return [
            int(e["seq"])
            async for e in tail_jsonl(
                path, poll=0.02, wait_for_file=0.5, job_status=lambda: status[0], **kw
            )
        ]

    started = time.monotonic()
    out = asyncio.run(consume())
    return out, time.monotonic() - started


def test_tail_ends_for_a_failed_job_and_waits_for_a_queued_one(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps({"seq": 1, "kind": "log", "stage": "run"}) + "\n")
    seqs, took = _tail(path, ["failed"], end_grace=0.1, stale_after=30.0)
    assert seqs == [1] and took < 5.0
    empty = tmp_path / "queued.jsonl"
    empty.write_text("")
    status: list[str | None] = ["queued"]

    def start_later() -> None:
        time.sleep(1.5)
        status[0] = "failed"

    import threading

    thread = threading.Thread(target=start_later)
    thread.start()
    seqs, took = _tail(empty, status, end_grace=0.1, stale_after=0.2)
    thread.join()
    # stale_after passed many times over while queued; the tail ended only once the job failed
    assert seqs == [] and took >= 1.4


# ---------------------------------------------------------------- routes


def test_cors_star_allows_every_origin() -> None:
    from pah.webui.settings import add_cors, cors_config

    assert cors_config(["*"]) == (("*",), None)
    assert cors_config(["http://a", "*"]) == (("*",), None)
    app = FastAPI()

    @app.get("/x")
    def x() -> dict[str, bool]:
        return {"ok": True}

    assert add_cors(app, ["*"])
    r = TestClient(app).get("/x", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "*"


def test_non_run_directories_are_not_runs(tmp_path: Path) -> None:
    from pah.interfaces.api import create_app

    profile = _profile(tmp_path)
    client = TestClient(create_app(profile))
    uploads = tmp_path / "r" / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / "68c4cc8984f4-secret.sdf").write_text("x")
    (tmp_path / "r" / "agent-abc").mkdir()
    assert client.get("/ui/runs/uploads/record").status_code == 404
    assert client.get("/ui/jobs/uploads").status_code == 404
    assert client.get("/ui/jobs/agent-abc").status_code == 404
    assert client.get("/runs/uploads/files/68c4cc8984f4-secret.sdf").status_code == 404


def test_agent_log_refuses_nan_and_infinity(tmp_path: Path) -> None:
    from pah.webui import routes_agent

    app = FastAPI()
    app.include_router(routes_agent.build_router(_profile(tmp_path), None), prefix="/ui")
    client = TestClient(app)
    tid = client.post("/ui/agent/tasks", json={"goal": "g"}).json()["id"]
    headers = {"content-type": "application/json"}
    bad = '{"kind": "result", "text": "x", "data": {"rmsd": NaN}}'
    r = client.post(f"/ui/agent/tasks/{tid}/steps", content=bad, headers=headers)
    assert r.status_code == 422
    for ms in ("NaN", "1e999"):
        body = '{"kind": "result", "text": "x", "ms": ' + ms + "}"
        r = client.post(f"/ui/agent/tasks/{tid}/steps", content=body, headers=headers)
        assert r.status_code == 422, ms
    r = client.post(
        f"/ui/agent/tasks/{tid}/finish",
        content='{"status": "done", "outcome": {"score": NaN}}',
        headers=headers,
    )
    assert r.status_code == 422
    # nothing was written: the task still reads and accepts a valid step
    assert client.get(f"/ui/agent/tasks/{tid}").status_code == 200
    assert client.get(f"/ui/agent/tasks/{tid}/steps", params={"format": "json"}).json() == []
    ok = client.post(f"/ui/agent/tasks/{tid}/steps", json={"kind": "result", "text": "x"})
    assert ok.status_code == 201


def test_body_limits_answer_413(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pah.interfaces.api import create_app
    from pah.webui import body_limit

    monkeypatch.setattr(body_limit, "JSON_LIMIT", 1000)
    monkeypatch.setattr(body_limit, "upload_limit", lambda: 2000)
    client = TestClient(create_app(_profile(tmp_path)))
    r = client.post("/ui/interpret", content=b"{" + b" " * 5000 + b"}")
    assert r.status_code == 413 and r.json()["error"]["code"] == "too_large"

    def chunks() -> Any:  # no Content-Length: the byte counter applies
        for _ in range(10):
            yield b"x" * 500

    r = client.post(
        "/ui/uploads",
        content=chunks(),
        headers={"content-type": "multipart/form-data; boundary=b"},
    )
    assert r.status_code == 413
    small = client.post("/ui/uploads", files={"f": ("a.smi", b"CCO\n")})
    assert small.status_code == 200
    # native routes have no /ui limit
    assert body_limit.limit_for("/runs") is None


def test_pae_matrix_is_embedded_and_binned(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    from pah.webui import stats

    small = tmp_path / "pae.npy"
    np.save(small, np.array([[0.123, 4.0], [4.0, 0.5]]))
    out = stats._pae_matrix(small)
    assert out["matrix"] == [[0.12, 4.0], [4.0, 0.5]] and out["tokens"] == 2
    assert "binned" not in out
    big = tmp_path / "big.npy"
    np.save(big, np.ones((stats.MAX_PAE_TOKENS + 10, stats.MAX_PAE_TOKENS + 10)))
    out = stats._pae_matrix(big)
    assert out["binned"] == 2 and len(out["matrix"]) <= stats.MAX_PAE_TOKENS
    assert out["lines"][0].startswith(f"{stats.MAX_PAE_TOKENS + 10} tokens")
    bad = tmp_path / "bad.npy"
    np.save(bad, np.ones((2, 3)))
    assert stats._pae_matrix(bad) == {}
