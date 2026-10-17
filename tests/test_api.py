import json
import time
from typing import Any

import pytest

from pah.config import Profile
from tests.conftest import ROOT

pytest.importorskip("fastapi")
pytest.importorskip("sse_starlette")
from fastapi.testclient import TestClient

from pah.interfaces.api import create_app


def _events(client: TestClient, run_id: str) -> list[dict[str, Any]]:
    rows = []
    with client.stream("GET", f"/runs/{run_id}/events") as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("data:"):
                rows.append(json.loads(line[5:].strip()))
    return rows


def _wait(client: TestClient, run_id: str, timeout: float = 60) -> dict[str, Any]:
    end = time.time() + timeout
    while time.time() < end:
        body = client.get(f"/runs/{run_id}").json()
        if body["status"] != "running":
            return body
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_run_lifecycle_over_http(offline_profile: Profile) -> None:
    client = TestClient(create_app(offline_profile))
    assert client.get("/health").json()["status"] == "ok"
    resp = client.post(
        "/runs", json={"manifest_path": str(ROOT / "examples/3ptb_ligand_pose/manifest.yaml")}
    )
    assert resp.status_code == 202
    run_id = resp.json()["id"]

    events = _events(client, run_id)
    kinds = [e.get("kind") for e in events]
    assert kinds.count("finding") == 13 and "run_end" in kinds
    assert events[-1]["status"] == "done"  # job_end payload

    body = _wait(client, run_id)
    assert body["summary"]["verdict"] == "pass_with_warnings"
    md = client.get(f"/runs/{run_id}/report?format=md")
    assert md.status_code == 200 and "## Summary" in md.text
    report = client.get(f"/runs/{run_id}/report?format=json").json()
    assert report["schema_version"] == "1"
    warn = client.get(f"/runs/{run_id}/findings", params={"gate": "warn"}).json()
    assert [f["check_id"] for f in warn] == ["l1.ligand.stereo_defined"]
    graph = client.get(f"/runs/{run_id}/files/graph.json")
    assert graph.status_code == 200 and "nodes" in graph.json()


def test_rejects_bad_input_and_traversal(offline_profile: Profile) -> None:
    client = TestClient(create_app(offline_profile))
    bad = client.post("/runs", json={"manifest": {"task": "ligand_pose", "ligands": [{"id": "x"}]}})
    assert bad.status_code == 422
    assert client.post("/runs", json={}).status_code == 422
    assert client.get("/runs/../../etc").status_code in (400, 404)
    assert client.get("/runs/nope/files/../../../etc/passwd").status_code in (400, 404)
    assert client.get("/runs/missing-run").status_code == 404


def test_batch_and_discovery_endpoints(offline_profile: Profile) -> None:
    client = TestClient(create_app(offline_profile))
    assert any(t["id"] == "ligand_pose" for t in client.get("/tasks").json())
    assert any(c["id"] == "l0.sources.resolved" for c in client.get("/checks").json())
    assert "properties" in client.get("/schemas/manifest").json()
    assert client.get("/schemas/nope").status_code == 404
    resp = client.post(
        "/batches",
        json={
            "name": "api",
            "manifest_paths": [str(ROOT / "examples/3ptb_ligand_pose/manifest.yaml")],
        },
    )
    batch_id = resp.json()["id"]
    body = _wait(client, batch_id)
    assert body["status"] == "done", body
    md = client.get(f"/runs/{batch_id}/report?format=md")
    assert md.status_code == 200 and "Batch assurance report" in md.text
