"""`/ui` write routes over HTTP: runs through the upstream JobStore, interpret, entities,
uploads, examples."""

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
from pah.interfaces.api import JobStore, create_app
from pah.webui import persistence, routes_write
from tests.conftest import ROOT
from tests.fakeweb import FakeWeb

EXAMPLE = "examples/3ptb_ligand_pose/manifest.yaml"
TRYPSIN = {
    "task": "ligand_pose",
    "tools": ["boltz2", "gnina"],
    "target": "P00760",
    "reference": "3PTB",
    "ligand": "NC(=N)c1ccccc1",
    "seeds": 5,
    "ph": 7.4,
}


class _Offline:
    """Dispatcher for tests that do not exercise execution: nothing leaves the process."""

    def run(self, job: Any, progress: Any) -> dict[str, Any]:
        from pah.webui.execute import DispatchUnavailableError

        raise DispatchUnavailableError("test: no dispatch")


def _client(profile: Profile, **kw: Any) -> TestClient:
    kw.setdefault("dispatchers", {"modal": _Offline(), "local": _Offline()})
    app = FastAPI()
    app.include_router(routes_write.build_router(profile, JobStore(), **kw), prefix="/ui")
    return TestClient(app)


def _job(profile: Profile, run_id: str) -> dict[str, Any]:
    return json.loads((Path(profile.runs_dir) / run_id / "job.json").read_text())  # type: ignore[no-any-return]


def _wait(profile: Profile, run_id: str, timeout: float = 180) -> dict[str, Any]:
    end = time.time() + timeout
    while time.time() < end:
        job = _job(profile, run_id)
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.2)
    raise AssertionError(f"job {run_id} did not finish")


def _events(profile: Profile, run_id: str) -> list[dict[str, Any]]:
    path = Path(profile.runs_dir) / run_id / "events.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_example_manifest_run(offline_profile: Profile) -> None:
    calls: list[int] = []
    remove = persistence.on_persist(lambda: calls.append(1))
    try:
        client = _client(offline_profile)
        r = client.post("/ui/runs", json={"manifest": EXAMPLE, "layers": [0, 1]})
        assert r.status_code == 202, r.text
        ids = r.json()
        assert ids["jobId"] == ids["runId"]
        run_dir = Path(offline_profile.runs_dir) / ids["runId"]
        assert (run_dir / "events.jsonl").is_file() and (run_dir / "job.json").is_file()
        job = _wait(offline_profile, ids["runId"])
    finally:
        remove()
    assert job["status"] == "done", job
    assert job["verdict"] == "pass_with_warnings" and job["manifest"] == EXAMPLE
    assert job["executors"] == "not run (checks only)" and job["tools"] == ["boltz2"]
    assert job["profile"] == "offline" and job["startedAt"] and job["finishedAt"]
    assert (run_dir / "record.json").is_file() and (run_dir / "report.md").is_file()
    events = _events(offline_profile, ids["runId"])
    assert events[0]["seq"] == 0 and events[0]["stage"] == "job"
    assert events[0]["data"]["executors"] == "not run (checks only)"
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert "run_end" in [e["kind"] for e in events]
    assert len(calls) >= 4  # queued, running, done, run ended


def test_settings_run_builds_manifest(offline_profile: Profile) -> None:
    client = _client(offline_profile)
    r = client.post("/ui/runs", json={**TRYPSIN, "name": "trypsin settings"})
    assert r.status_code == 202, r.text
    run_id = r.json()["runId"]
    queued = _job(offline_profile, run_id)
    assert queued["name"] == "trypsin settings" and queued["tools"] == ["boltz2", "gnina"]
    assert queued["settings"]["target"] == "P00760" and queued["seeds"] == 5
    job = _wait(offline_profile, run_id)
    assert job["status"] == "done", job
    record = json.loads((Path(offline_profile.runs_dir) / run_id / "record.json").read_text())
    protein = record["manifest"]["proteins"][0]
    assert protein["chain"] == "A" and protein["sequence"].startswith("IVGGYTCGANTVPYQVSLNSGYHFCGG")
    assert record["manifest"]["model"] == {
        "executor": "boltz2", "version": "2.2.1", "checkpoint": "boltz2_conf.ckpt",
        "database_snapshot": None, "seeds": [0, 1, 2, 3, 4],
    }  # fmt: skip
    assert record["manifest"]["ligands"][0]["ccd"] == "BEN"
    # The executor's default checkpoint is declared, so layer 1 records the model config.
    assert "l1.provenance.model_config" not in record["verdict"]["stops"]
    assert any("via SIFTS" in n for n in job["notes"])
    first = _events(offline_profile, run_id)[0]
    assert first["seq"] == 0 and "boltz2, gnina" in first["message"]


def test_failed_run_is_recorded(offline_profile: Profile, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("source client broke")

    monkeypatch.setattr(routes_write, "complete_manifest", boom)
    client = _client(offline_profile)
    run_id = client.post("/ui/runs", json=TRYPSIN).json()["runId"]
    job = _wait(offline_profile, run_id)
    assert job["status"] == "failed" and "source client broke" in job["error"]
    last = _events(offline_profile, run_id)[-1]
    assert last["data"]["status"] == "error" and "source client broke" in last["message"]


def test_run_settings_errors(offline_profile: Profile) -> None:
    client = _client(offline_profile)
    bad = client.post("/ui/runs", json={**TRYPSIN, "tools": ["boltz2", "nosuch"]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_settings"
    assert "nosuch" in bad.json()["error"]["message"]
    assert client.post("/ui/runs", json={**TRYPSIN, "target": "x"}).status_code == 422
    assert client.post("/ui/runs", json={"manifest": "../pyproject.toml"}).status_code == 422
    assert client.post("/ui/runs", content=b"[]").status_code == 422
    assert not any(Path(offline_profile.runs_dir).glob("*/job.json"))


def test_interpret_examples_and_tools(offline_profile: Profile) -> None:
    client = _client(offline_profile)
    r = client.post("/ui/interpret", json={"text": "Dock benzamidine into trypsin, 3 seeds"})
    body = r.json()
    assert body["settings"]["target"] == "P00760" and body["settings"]["seeds"] == 3
    assert body["settings"]["ligand"] == "NC(=N)c1ccccc1"
    assert body["steps"][0]["field"] == "task" and body["interpreter"] == "rule-based"
    assert client.post("/ui/interpret", json={}).status_code == 422
    examples = {e["path"]: e for e in client.get("/ui/examples").json()}
    assert examples[EXAMPLE]["task"] == "ligand_pose"
    assert examples[EXAMPLE]["claim"] == "Pose within stated uncertainty"
    r = client.post("/ui/tools", json={"id": "x"})
    assert r.status_code == 501 and r.json()["error"]["code"] == "not_implemented"


def test_entities(profile: Profile) -> None:
    client = _client(profile, client_factory=FakeWeb().client)
    groups = client.get("/ui/entities", params={"q": "benzamidine in trypsin, also Q9Y6K9"}).json()
    by = {g["key"]: g for g in groups}
    assert list(by)[:3] == ["uniprot:P00760", "rcsb:3PTB", "afdb:P00760"]
    uni = dict(map(tuple, by["uniprot:P00760"]["rows"]))
    assert uni["TRY1_BOVIN"] == "246 aa" and uni["Organism"] == "Bos taurus"
    assert uni["Release"] == "2026_03"
    assert dict(map(tuple, by["rcsb:3PTB"]["rows"]))["SIFTS"] == "P00760 → chains A"
    assert by["ccd:BEN"]["status"] == "ok" and by["pubchem:2332"]["status"] == "ok"
    assert dict(map(tuple, by["pubchem:2332"]["rows"]))["InChIKey"] == (
        "PXXJHWLDUBFPOL-UHFFFAOYSA-N"
    )
    missing = by["uniprot:Q9Y6K9"]
    assert missing["status"] == "error" and "not_found" in missing["message"]
    assert all(isinstance(g["ms"], int) for g in groups)
    assert client.get("/ui/entities", params={"q": "nothing known"}).json() == []


def test_uploads(profile: Profile) -> None:
    client = _client(profile)
    sdf = (ROOT / "tests/fixtures/sources/3PTB_BEN.sdf").read_bytes()
    r = client.post(
        "/ui/uploads",
        files=[("files", ("ben.sdf", sdf)), ("files", ("seq.fasta", b">a\nMKV\n"))],
    )
    rows = r.json()["files"]
    assert [x["kind"] for x in rows] == ["ligand", "sequence"]
    assert all(x["status"] == "parsed" for x in rows), rows
    stored = Path(profile.runs_dir) / rows[0]["path"]
    assert stored.read_bytes() == sdf and stored.name.startswith(rows[0]["sha256"][:12])
    assert client.post("/ui/uploads", data={"x": "1"}).status_code == 422


def test_mounted_on_upstream_app(offline_profile: Profile) -> None:
    client = TestClient(create_app(offline_profile))
    r = client.post("/ui/runs", json={"manifest": EXAMPLE, "layers": [0, 1]})
    assert r.status_code == 202, r.text
    run_id = r.json()["runId"]
    assert _wait(offline_profile, run_id)["status"] == "done"
    assert client.get(f"/runs/{run_id}").json()["status"] == "done"  # upstream job view
    assert client.post("/ui/tools").status_code == 501


def test_execute_run_dispatches_and_assesses_predictions(offline_profile: Profile) -> None:
    from tests.test_webui_execute import FakeBoltz

    fake = FakeBoltz()
    client = _client(offline_profile, dispatchers={"modal": fake})
    body = {**TRYPSIN, "tools": ["boltz2"], "seeds": 2, "execute": True, "layers": [0, 1, 4, 5]}
    r = client.post("/ui/runs", json=body)
    assert r.status_code == 202, r.text
    run_id = r.json()["runId"]
    queued = _job(offline_profile, run_id)
    assert queued["execute"] is True and queued["executors"] == "run (configs/dispatch.yaml)"
    job = _wait(offline_profile, run_id)
    assert job["status"] == "done", job
    (row,) = job["execution"]
    assert row["executor"] == "boltz2" and row["phase"] == "done" and row["route"] == "kit"
    assert [s["seed"] for s in row["seeds"]] == [0, 1]
    events = _events(offline_profile, run_id)
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    execute = [e for e in events if e["stage"] == "execute"]
    assert execute[0]["data"]["phase"] == "queued" and execute[-1]["data"]["phase"] == "done"
    assert all(e["data"]["executor"] == "boltz2" for e in execute)
    assert max(e["seq"] for e in execute) < min(e["seq"] for e in events if e["stage"] == "run")
    record = json.loads((Path(offline_profile.runs_dir) / run_id / "record.json").read_text())
    (pred,) = record["manifest"]["predictions"]
    assert pred["path"] == "predictions/boltz2" and pred["seeds"] == [0, 1]
    l4 = [f for f in record["findings"] if f["layer"] in (4, "L4") and f["gate"] != "skip"]
    assert l4, "layer 4 evaluated the dispatched poses"


def test_execute_without_token_skips_executors(
    offline_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_webui_execute import FakeBoltz

    monkeypatch.setenv("PAH_EXEC_TOKEN", "s3cret")
    fake = FakeBoltz()
    client = _client(offline_profile, dispatchers={"modal": fake})
    body = {**TRYPSIN, "tools": ["boltz2"], "seeds": 1, "execute": True, "layers": [0, 1]}
    run_id = client.post("/ui/runs", json=body).json()["runId"]
    job = _wait(offline_profile, run_id)
    assert job["status"] == "done" and "X-Pah-Exec-Token" in job["executionDenied"]
    assert job["executors"] == "not run (checks only)" and not fake.jobs
    (row,) = job["execution"]
    assert row["phase"] == "skipped"
    skipped = [e for e in _events(offline_profile, run_id) if e["stage"] == "execute"]
    assert [e["data"]["phase"] for e in skipped] == ["skipped"]
    ok = client.post("/ui/runs", json=body, headers={"X-Pah-Exec-Token": "s3cret"})
    assert _wait(offline_profile, ok.json()["runId"])["executionDenied"] is None
    assert len(fake.jobs) == 1


def test_execute_run_returns_estimate_and_stores_calls(offline_profile: Profile) -> None:
    from tests.test_webui_execute import FakeSpawner

    fake = FakeSpawner()
    client = _client(offline_profile, dispatchers={"modal": fake})
    body = {**TRYPSIN, "tools": ["boltz2"], "seeds": 2, "execute": True, "layers": [0, 1]}
    r = client.post("/ui/runs", json=body)
    assert r.status_code == 202, r.text
    run_id = r.json()["runId"]
    est = r.json()["eta"]
    assert r.json()["etaMs"] == est["etaMs"] > 0 and est["executors"][0]["executor"] == "boltz2"
    assert est["executors"][0]["basis"] in ("measured", "estimate")
    queued = _job(offline_profile, run_id)
    assert queued["etaMs"] == est["etaMs"] and queued["eta"] == est
    job = _wait(offline_profile, run_id)
    assert job["status"] == "done", job
    calls = routes_write.read_calls(Path(offline_profile.runs_dir) / run_id)
    assert calls["boltz2"]["callId"] == "fc-1" and calls["boltz2"]["status"] == "done"
    execute = [e for e in _events(offline_profile, run_id) if e["stage"] == "execute"]
    assert all(e["data"]["runEtaMs"] == est["etaMs"] for e in execute)
    assert any(e["data"]["callId"] == "fc-1" for e in execute)


def test_spawned_calls_resume_after_restart(offline_profile: Profile) -> None:
    from tests.test_webui_execute import MANIFEST, FakeSpawner

    run_id = "ligand_pose-resume0001"
    run_dir = Path(offline_profile.runs_dir) / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text("")
    manifest = {k: v for k, v in MANIFEST.items()}
    manifest["model"] = {"executor": "boltz2", "seeds": [0]}
    (run_dir / "manifest.yaml").write_text(json.dumps(manifest))
    (run_dir / "job.json").write_text(
        json.dumps({"id": run_id, "runId": run_id, "status": "running", "layers": [0, 1, 4]})
    )
    call = {"callId": "fc-7", "app": "pah-gpu-boltz2", "function": "predict",
            "status": "spawned", "seeds": [0], "name": "trypsin_benzamidine",
            "ligand": "benzamidine", "params": {}}  # fmt: skip
    routes_write.write_calls(run_dir, {"boltz2": call})
    fake = FakeSpawner()
    jobs = JobStore()
    submitter = routes_write.RunSubmitter(offline_profile, jobs, None, {"modal": fake})
    assert submitter.resume_pending() == [run_id]
    job = _wait(offline_profile, run_id)
    assert job["status"] == "done", job
    assert fake.spawned == [] and fake.waited == ["fc-7"]
    assert routes_write.read_calls(run_dir)["boltz2"]["status"] == "done"
    messages = [e["message"] for e in _events(offline_profile, run_id)]
    assert any("server restarted: following 1 spawned call" in m for m in messages)
    record = json.loads((run_dir / "record.json").read_text())
    assert record["manifest"]["predictions"][0]["executor"] == "boltz2"
    assert submitter.resume_pending() == []  # a finished run is not taken up again
