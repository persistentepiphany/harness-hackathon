import json
from pathlib import Path
from typing import Any

import pytest

from pah.config import Profile, resolve_path
from tests.synthetic import write_events, write_synthetic_run

pytest.importorskip("fastapi")
pytest.importorskip("sse_starlette")
pytest.importorskip("numpy")
from fastapi.testclient import TestClient

from pah.interfaces.api import create_app


@pytest.fixture
def runs(profile: Profile) -> Path:
    root = resolve_path(profile.runs_dir)
    write_synthetic_run(root / "synthetic")
    return root


def _sse(
    client: TestClient, url: str, headers: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    with client.stream("GET", url, headers=headers or {}) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if not line.strip():
                if current:
                    frames.append(current)
                current = {}
            elif line.startswith(":"):
                continue
            else:
                key, _, value = line.partition(":")
                current[key] = value.strip()
    if current:
        frames.append(current)
    return frames


def test_jobs_and_record(profile: Profile, runs: Path) -> None:
    from pah.core.engine import RunRecord

    second = write_synthetic_run(runs / "older")
    rec = RunRecord.model_validate_json((second / "record.json").read_text())
    rec = rec.model_copy(update={"started_at": rec.started_at.replace(year=2025)})
    (second / "record.json").write_text(rec.model_dump_json())
    (runs / "no-events").mkdir()
    client = TestClient(create_app(profile))
    health = client.get("/health").json()
    assert health["ok"] is True and health["mode"] == "live" and health["status"] == "ok"
    jobs = client.get("/jobs").json()
    assert [j["id"] for j in jobs] == ["synthetic", "older"]
    assert jobs[0]["status"] == "done" and jobs[0]["verdict"] == "narrowed"
    one = client.get("/jobs/synthetic").json()
    assert one == jobs[0]
    record = client.get("/runs/synthetic/record").json()
    assert record["source"] == "pah" and record["stats"]["pairwise"]["median"] == 0.92
    missing = client.get("/jobs/nope")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
    bad = client.get("/runs/bad id/record")
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_id"
    assert client.get("/runs/nope/record").json()["error"]["code"] == "not_found"


def test_log_json_and_sse(profile: Profile, runs: Path) -> None:
    client = TestClient(create_app(profile))
    lines = client.get("/jobs/synthetic/log", params={"format": "json"}).json()
    assert lines[0]["kind"] == "run" and lines[-1]["plain"].startswith("Run finished")
    frames = _sse(client, "/jobs/synthetic/log")
    assert [f["event"] for f in frames[:-1]] == ["line"] * len(lines)
    assert frames[-1]["event"] == "end"
    assert [int(f["id"]) for f in frames[:-1]] == [x["seq"] for x in lines]
    assert json.loads(frames[0]["data"]) == lines[0]
    resumed = _sse(client, "/jobs/synthetic/log", {"Last-Event-ID": "10"})
    assert int(resumed[0]["id"]) == 11 and resumed[-1]["event"] == "end"
    assert client.get("/jobs/synthetic/log", params={"format": "xml"}).status_code == 400


def test_log_of_running_job_ends_when_idle(profile: Profile, runs: Path) -> None:
    from pah.core.engine import RunRecord

    d = runs / "synthetic"
    rec = RunRecord.model_validate_json((d / "record.json").read_text())
    (d / "record.json").unlink()
    write_events(d, rec, stop_after=6)
    client = TestClient(create_app(profile, log_idle_s=0.3))
    assert client.get("/jobs/synthetic").json()["status"] == "running"
    frames = _sse(client, "/jobs/synthetic/log")
    assert frames[-1]["event"] == "end" and len(frames) > 2
    record = client.get("/runs/synthetic/record").json()
    assert "verdict" not in record


def test_report_html_endpoint(profile: Profile, runs: Path) -> None:
    from pah.report import write_run_report
    from tests.conftest import FakeRenderer

    pytest.importorskip("matplotlib")
    write_run_report(runs / "synthetic", renderer=FakeRenderer())
    client = TestClient(create_app(profile))
    resp = client.get("/runs/synthetic/report", params={"format": "html"})
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/html")
    assert 'data-testid="verdict"' in resp.text
