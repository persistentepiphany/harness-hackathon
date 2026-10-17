"""`/ui/agent/...` routes over HTTP, including the SSE step stream."""

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sse_starlette")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pah.config import Profile
from pah.webui import routes_agent


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    profile = Profile(name="t", backend="local", cache_dir=tmp_path / "c", runs_dir=tmp_path / "r")
    app = FastAPI()
    app.include_router(routes_agent.build_router(profile, None), prefix="/ui")
    return TestClient(app)


def _sse(client: TestClient, url: str, headers: dict[str, str] | None = None) -> list[Any]:
    frames: list[Any] = []
    event = None
    with client.stream("GET", url, headers=headers or {}) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                frames.append((event, json.loads(line[5:].strip())))
    return frames


def test_task_lifecycle(client: TestClient) -> None:
    r = client.post("/ui/agent/tasks", json={"goal": "Decide whether the 3PTB pose is valid"})
    assert r.status_code == 201
    tid = r.json()["id"]
    r = client.post(
        f"/ui/agent/tasks/{tid}/steps", json={"kind": "thought", "text": "plan", "ms": 1200}
    )
    assert r.status_code == 201 and r.json()["seq"] == 1
    r = client.post(
        f"/ui/agent/tasks/{tid}/steps",
        json={"kind": "tool", "text": "harness.submit", "data": {"runId": "x", "progress": 0.4}},
    )
    assert r.json()["seq"] == 2
    task = client.get(f"/ui/agent/tasks/{tid}").json()
    assert task["steps"] == 2 and task["progress"] == 0.4 and task["status"] == "running"
    assert [t["id"] for t in client.get("/ui/agent/tasks").json()] == [tid]
    steps = client.get(f"/ui/agent/tasks/{tid}/steps", params={"format": "json"}).json()
    assert [s["kind"] for s in steps] == ["thought", "tool"]
    r = client.post(
        f"/ui/agent/tasks/{tid}/finish",
        json={"status": "done", "outcome": {"label": "Completed", "detail": "1 run", "runs": 1}},
    )
    assert r.status_code == 200 and r.json()["status"] == "done"
    frames = _sse(client, f"/ui/agent/tasks/{tid}/steps")
    assert [e for e, _ in frames] == ["step", "step", "end"]
    assert frames[-1][1]["outcome"]["label"] == "Completed"
    resumed = _sse(client, f"/ui/agent/tasks/{tid}/steps", {"Last-Event-ID": "1"})
    assert [d.get("seq") for e, d in resumed if e == "step"] == [2]


def test_errors(client: TestClient) -> None:
    assert client.post("/ui/agent/tasks", json={}).status_code == 422
    assert client.post("/ui/agent/tasks", content=b"[1]").json()["error"]["code"] == "invalid"
    r = client.get("/ui/agent/tasks/missing")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    tid = client.post("/ui/agent/tasks", json={"goal": "g"}).json()["id"]
    bad = client.post(f"/ui/agent/tasks/{tid}/steps", json={"kind": "chat", "text": "x"})
    assert bad.status_code == 422
    assert client.post(f"/ui/agent/tasks/{tid}/finish", json={"status": "later"}).status_code == 422
    client.post(f"/ui/agent/tasks/{tid}/finish", json={"status": "failed", "outcome": None})
    late = client.post(f"/ui/agent/tasks/{tid}/steps", json={"kind": "tool", "text": "x"})
    assert late.status_code == 409 and late.json()["error"]["code"] == "task_finished"
