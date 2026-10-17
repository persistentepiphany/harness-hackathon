"""Read side of the web UI: adapter mappings, run store, live tail, /ui routes, tools, CORS."""

import asyncio
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from pah.config import Profile
from tests.conftest import ROOT

pytest.importorskip("fastapi")
pytest.importorskip("sse_starlette")
from fastapi.testclient import TestClient

from pah.interfaces.api import create_app
from pah.webui import adapter
from pah.webui.adapter import event_to_logline, load_state, loglines, to_job, to_ui_record
from pah.webui.store import RunStore, UnsafePathError, read_events, tail_jsonl

CLEAN = ROOT / "examples/3ptb_ligand_pose/manifest.yaml"
FAULTY = ROOT / "examples/3ptb_faulty_inputs/manifest.yaml"


OUTCOMES = {
    "pass": "supported",
    "pass_with_warnings": "narrowed",
    "stop": "refused",
    "incomplete": "incomplete",
}


def _run(profile: Profile, manifest: Path, run_id: str, layers: tuple[int, ...]) -> Path:
    from pah.service import RunOptions, run_manifest

    result = run_manifest(manifest, profile, RunOptions(layers=layers, halt=False), run_id=run_id)
    events = result.run_dir / "events.jsonl"
    old = time.time() - 60  # a finished run: the tail does not wait for more lines
    os.utime(events, (old, old))
    return result.run_dir


@pytest.fixture
def runs(offline_profile: Profile) -> dict[str, Path]:
    return {
        "clean": _run(offline_profile, CLEAN, "clean-01", (0, 1)),
        "deep": _run(offline_profile, CLEAN, "clean-02", (0, 1, 2)),
        "faulty": _run(offline_profile, FAULTY, "faulty-01", (0, 1)),
    }


def _checks(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for layer in record["layers"] for c in layer["checks"]}


# ---------------------------------------------------------------- adapter


def test_record_outcomes_results_and_gates(runs: dict[str, Path]) -> None:
    clean = to_ui_record(runs["clean"])
    # the claim's output layers gave no result: the engine's narrowed is scoped to not_assessed
    assert clean["verdict"]["outcome"] == "not_assessed"
    assert clean["verdict"]["engineOutcome"] == "narrowed"
    assert clean["verdict"]["warnings"] == ["l1.ligand.stereo_defined"]
    assert clean["task"] == "ligand_pose" and clean["source"] == "pah"
    assert set(clean["stats"]) <= {"status", "provenance"}  # nothing computed, only why
    deep_raw = json.loads((runs["deep"] / "record.json").read_text())["verdict"]["outcome"]
    deep = to_ui_record(runs["deep"])["verdict"]
    assert deep["engineOutcome"] == OUTCOMES[deep_raw]
    assert deep["outcome"] in {OUTCOMES[deep_raw], "not_assessed"}
    faulty = to_ui_record(runs["faulty"])
    assert faulty["verdict"]["outcome"] == "refused"
    assert "l1.ligand.identity" in faulty["verdict"]["stops"]
    assert "is not supported" in faulty["verdict"]["statement"]

    checks = _checks(clean)
    stereo = checks["l1.ligand.stereo_defined"]
    assert (stereo["result"], stereo["gate"]) == ("warn", "Warn")
    assert stereo["threshold"]["value"] == "== 0"
    assert stereo["threshold"]["origin"] and stereo["threshold"]["evidenceLevel"]
    assert stereo["evidence"].startswith(stereo["message"]) and "undefined=1" in stereo["evidence"]
    assert stereo["tool"] == "rdkit" and isinstance(stereo["ms"], int)
    identity = checks["l1.ligand.identity"]
    assert (identity["result"], identity["gate"]) == ("pass", "Stop")
    assert checks["l1.receptor.altlocs"]["gate"] == "Warn"


def test_layers_counts_durations_and_unknown_checks(
    offline_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pah.core.check import CHECKS

    # A task check with no registered implementation is a skip with unknown_check.
    monkeypatch.delitem(CHECKS, "l2.context.cofactors")
    record = to_ui_record(_run(offline_profile, CLEAN, "clean-03", (0, 1, 2)))
    layers = record["layers"]
    assert [layer["i"] for layer in layers] == [0, 1, 2, 3, 4, 5]
    assert [layer["key"] for layer in layers][:2] == ["provenance", "integrity"]
    assert [layer["status"] for layer in layers] == ["done"] * 3 + ["not_run"] * 3
    assert layers[1]["counts"] == {"pass": 9, "warn": 1, "stop": 0, "skip": 0}
    assert all(isinstance(layer["durationMs"], int) for layer in layers[:3])
    assert all("durationMs" not in layer and layer["counts"] == {} for layer in layers[3:])
    l2 = layers[2]
    assert sum(l2["counts"].values()) == len(l2["checks"])
    cofactors = _checks(record)["l2.context.cofactors"]
    assert (cofactors["result"], cofactors["skipReason"]) == ("skip", "unknown_check")
    # an escalated check keeps Stop as its failure gate even when not implemented
    assert cofactors["gate"] == "Stop"
    assert any("1 not implemented" in line for line in record["narrative"])
    assert record["verdict"]["engineOutcome"] == "incomplete"
    assert record["narrative"][-1].startswith(f"Verdict: {record['verdict']['outcome']}.")
    assert layers[0]["summary"][0] == "7 objects"


def test_sources_structures_renders_and_tools(runs: dict[str, Path]) -> None:
    record = to_ui_record(runs["clean"])
    sources = {s["sourceId"]: s for s in record["sources"]}
    assert {"uniprot", "rcsb", "pdbe", "sifts", "ccd", "pubchem", "rcsb_files"} <= set(sources)
    assert all(len(s["sha256"]) == 64 and s["retrievedAt"] for s in record["sources"])
    assert sources["uniprot"]["source"] == "UniProt" and sources["pdbe"]["release"] == "n/a"
    assert sources["rcsb"]["source"] == "RCSB PDB data API"
    assert sources["uniprot"]["cached"] is True  # the offline profile reads a pre-filled cache
    assert "l0.sources.resolved" in sources["uniprot"]["usedBy"]

    (structure,) = record["structures"]
    assert structure["kind"] == "crystal" and structure["format"] == "mmcif"
    assert structure["url"] == "/runs/clean-01/files/artifacts/sources/3PTB.cif"
    views = {r["view"]: r for r in record["renders"]}
    assert set(views) == {"overview", "pocket"}
    assert views["overview"]["png"] == "/runs/clean-01/files/renders/3PTB_overview.png"
    assert views["overview"]["pse"] == "/runs/clean-01/files/renders/3PTB.pse"
    assert views["overview"]["structure"] == structure["id"]
    assert record["report"]["status"] == "done"
    assert record["report"]["graph"]["json"] == "/runs/clean-01/files/graph.json"
    inputs = [a for a in record["artifacts"] if a["kind"] == "input_ligand"]
    assert inputs and inputs[0]["url"] is None  # outside the run directory: not served

    (tool,) = record["tools"]
    assert tool["id"] == "boltz2" and tool["family"] == "co-folding" and tool["ran"] is False
    ranking = [o["key"] for o in tool["outputs"] if o.get("rankingOnly")]
    assert ranking == ["affinity_pred_value", "affinity_probability_binary"]
    assert record["inputs"] == {
        "partner": None,
        "ligand": "NC(=N)c1ccccc1",
        "target": "P00760",
        "reference": "3PTB",
        "ph": 7.4,
        "seeds": 5,
    }


def test_structures_leave_out_check_files(runs: dict[str, Path]) -> None:
    run = runs["clean"]
    # receptor-only PDB a check derived from a pose, and a check scratch file
    for rel in ("derived/pose_0_ab12cd34_protein.pdb", "artifacts/work/plip/x.pdb"):
        (run / rel).parent.mkdir(parents=True, exist_ok=True)
        (run / rel).write_text("END\n")
    for name in ("record.json", "report.json"):
        path = run / name
        if not path.is_file():
            continue
        doc = json.loads(path.read_text())
        if not isinstance(doc.get("artifacts"), list):
            continue
        doc["artifacts"].append(
            {"path": str(run / "derived/pose_0_ab12cd34_protein.pdb"), "kind": "input_structure"}
        )
        path.write_text(json.dumps(doc))
    paths = [s["path"] for s in to_ui_record(run)["structures"]]
    assert paths == ["artifacts/sources/3PTB.cif"]


def test_job_card(runs: dict[str, Path]) -> None:
    job = to_job(runs["faulty"])
    assert job["name"] == "trypsin · benzamidine" and job["tools"] == ["boltz2"]
    assert (job["status"], job["verdict"], job["layerIdx"], job["progress"]) == (
        "done",
        "refused",
        6,
        1.0,
    )
    assert [layer["result"] for layer in job["layers"]] == ["stop", "stop", None, None, None, None]
    assert job["checksDone"] == job["checksTotal"] == 13 and job["reportStatus"] == "done"


def _partial(src: Path, dst: Path, upto: int) -> list[dict[str, Any]]:
    """Copies the first `upto` events of a finished run into a new live run directory."""
    events = read_events(src / "events.jsonl")[:upto]
    dst.mkdir(parents=True)
    (dst / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    return events


def test_record_and_job_while_running(runs: dict[str, Path], tmp_path: Path) -> None:
    live = tmp_path / "live" / "live-01"
    events = _partial(runs["clean"], live, 5)  # log, run_start, stage_start L0, two findings
    assert [e["kind"] for e in events][-2:] == ["finding", "finding"]
    record = to_ui_record(live)
    assert record["status"] == "running" and record["verdict"]["outcome"] is None
    assert record["verdict"]["statement"].startswith("Run in progress")
    l0, l1, l2 = record["layers"][:3]
    assert l0["status"] == "running" and l0["counts"]["pass"] == 2 and l0["counts"]["pending"] == 1
    assert l1["status"] == "pending" and l1["counts"]["pending"] == 10
    assert l2["status"] == "not_run"
    assert record["sources"] and "retrievedAt" not in record["sources"][0]
    job = to_job(live)
    assert (job["status"], job["layerIdx"], job["progress"]) == ("running", 0, 0.667)
    assert job["verdict"] is None and job["layers"][0] == {"i": 0, "result": "pass", "done": False}
    stale = to_job(live, now=(live / "events.jsonl").stat().st_mtime + 700)
    assert stale["status"] == "failed"


# ---------------------------------------------------------------- log lines


def test_loglines_map_every_event_kind(runs: dict[str, Path]) -> None:
    run_dir = runs["clean"]
    lines = loglines(read_events(run_dir / "events.jsonl"), run_dir)
    kinds = {line["kind"] for line in lines}
    assert {"log", "run", "layer", "check", "artifact"} <= kinds
    by_text = {line["text"].split("  ")[1]: line for line in lines if line["kind"] == "check"}
    identity = by_text["l1.ligand.identity"]
    assert identity["result"] == "pass" and identity["layer"] == 1
    assert identity["text"].startswith("L1  l1.ligand.identity  pass  ")
    assert identity["plain"].endswith("(pass).") and identity["t"].endswith("s")
    end = next(line for line in lines if line["kind"] == "run" and "end" in line["text"])
    assert end["result"] == "warn" and "narrowed" in end["plain"]
    layer_end = next(line for line in lines if line["text"].startswith("L1  end"))
    assert layer_end["result"] == "warn" and "finished in" in layer_end["plain"]
    art = next(line for line in lines if line.get("path") == "record.json")
    assert art["url"] == "/runs/clean-01/files/record.json"
    assert [line["seq"] for line in lines] == sorted(line["seq"] for line in lines)


def test_logline_for_unknown_check_and_relative_time() -> None:
    from datetime import UTC, datetime

    start = datetime(2026, 1, 1, tzinfo=UTC)
    event = {
        "seq": 9,
        "kind": "finding",
        "stage": "L2",
        "message": "l2.msa.depth: check not registered",
        "ts": "2026-01-01T00:00:03.400000Z",
        "data": {
            "gate": "skip",
            "finding": {
                "check_id": "l2.msa.depth",
                "layer": 2,
                "gate": "skip",
                "message": "check not registered",
                "evidence": {"skip_reason": "unknown_check"},
            },
        },
    }
    line = event_to_logline(event, start)
    assert line["t"] == "3.4s" and line["result"] == "skip" and line["layer"] == 2
    assert line["plain"] == "l2.msa.depth is not implemented in this harness; skipped."


# ---------------------------------------------------------------- store


def test_resolve_file_rejects_traversal_and_symlinks(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    (runs / "r1" / "artifacts").mkdir(parents=True)
    (runs / "r1" / "artifacts" / "a.cif").write_text("data_x\n")
    (tmp_path / "secret.txt").write_text("secret")
    (runs / "r1" / "leak.txt").symlink_to(tmp_path / "secret.txt")
    store = RunStore(runs)
    assert store.resolve_file("r1", "artifacts/a.cif").name == "a.cif"
    for bad in ("../secret.txt", "/etc/passwd", "artifacts/../../secret.txt", "a\\b", "", "x//y"):
        with pytest.raises(UnsafePathError):
            store.resolve_file("r1", bad)
    with pytest.raises(UnsafePathError):
        store.resolve_file("r1", "leak.txt")
    for bad_id in ("..", ".", "a/b", "r 1"):
        with pytest.raises(UnsafePathError):
            store.path_for(bad_id)
    with pytest.raises(FileNotFoundError):
        store.resolve_file("r1", "artifacts")


def test_list_runs_skips_non_runs_and_sorts_newest_first(tmp_path: Path) -> None:
    def make(name: str, ts: str, extra: str | None = None) -> None:
        d = tmp_path / name
        d.mkdir()
        (d / "events.jsonl").write_text(json.dumps({"seq": 1, "kind": "log", "ts": ts}) + "\n")
        if extra:
            (d / extra).write_text("{}")

    make("old", "2026-01-01T00:00:00Z")
    make("new", "2026-02-01T00:00:00Z")
    make("agent-01", "2026-03-01T00:00:00Z")
    make("batch-x-01", "2026-03-01T00:00:00Z")
    make("named-batch", "2026-03-01T00:00:00Z", "batch_report.json")
    (tmp_path / "uploads").mkdir()
    (tmp_path / "empty").mkdir()
    assert [p.name for p in RunStore(tmp_path).list_runs()] == ["new", "old"]


def _line(seq: int, kind: str, stage: str = "run") -> str:
    return json.dumps({"seq": seq, "kind": kind, "stage": stage, "message": "", "ts": ""}) + "\n"


def test_tail_follows_appends_until_run_end_and_report(tmp_path: Path) -> None:
    path = tmp_path / "late" / "events.jsonl"

    def writer() -> None:
        time.sleep(0.15)  # the file does not exist when the tail starts
        path.parent.mkdir()
        with path.open("a") as fh:
            for seq, kind, stage in [
                (1, "run_start", "run"),
                (2, "finding", "L0"),
                (3, "run_end", "run"),
                (4, "stage_start", "report"),
            ]:
                fh.write(_line(seq, kind, stage))
                fh.flush()
                time.sleep(0.05)
            fh.write('{"seq": 5, "kind": "artifact"')  # partial line, completed later
            fh.flush()
            time.sleep(0.4)  # longer than end_grace: the open report stage keeps the tail
            fh.write(', "stage": "report", "message": "", "ts": ""}\n')
            fh.write(_line(6, "stage_end", "report"))

    async def consume() -> list[int]:
        return [
            int(e["seq"])
            async for e in tail_jsonl(path, poll=0.02, wait_for_file=2.0, end_grace=0.2)
        ]

    thread = threading.Thread(target=writer)
    thread.start()
    started = time.monotonic()
    seqs = asyncio.run(consume())
    thread.join()
    assert seqs == [1, 2, 3, 4, 5, 6]
    assert time.monotonic() - started < 3.0


def test_tail_gives_up_on_missing_file_and_stop(tmp_path: Path) -> None:
    async def consume(path: Path, **kw: Any) -> list[dict[str, Any]]:
        return [e async for e in tail_jsonl(path, poll=0.02, **kw)]

    assert asyncio.run(consume(tmp_path / "none.jsonl", wait_for_file=0.1)) == []
    path = tmp_path / "events.jsonl"
    path.write_text(_line(1, "run_start"))

    async def stop() -> bool:
        return True

    assert [e["seq"] for e in asyncio.run(consume(path, stop=stop))] == [1]


# ---------------------------------------------------------------- routes


@pytest.fixture
def client(offline_profile: Profile, runs: dict[str, Path]) -> TestClient:
    return TestClient(create_app(offline_profile))


def _sse(client: TestClient, url: str, **kw: Any) -> list[tuple[str, str | None, Any]]:
    frames: list[tuple[str, str | None, Any]] = []
    event, ident = "message", None
    with client.stream("GET", url, **kw) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        for raw in resp.iter_lines():
            if raw.startswith("event:"):
                event = raw[6:].strip()
            elif raw.startswith("id:"):
                ident = raw[3:].strip()
            elif raw.startswith("data:"):
                frames.append((event, ident, json.loads(raw[5:].strip())))
                event, ident = "message", None
    return frames


def test_jobs_and_record_routes(client: TestClient) -> None:
    jobs = client.get("/ui/jobs").json()
    assert {j["id"] for j in jobs} == {"clean-01", "clean-02", "faulty-01"}
    assert client.get("/ui/jobs/faulty-01").json()["verdict"] == "refused"
    record = client.get("/ui/runs/clean-01/record").json()
    assert record["id"] == "clean-01" and len(record["layers"]) == 6
    missing = client.get("/ui/runs/nope/record")
    assert missing.status_code == 404
    assert missing.json() == {"error": {"code": "run_not_found", "message": "no run 'nope'"}}
    assert client.get("/ui/jobs/a%20b").json()["error"]["code"] == "invalid_run_id"
    # native routes keep their own error body
    assert client.get("/runs/missing-run").json() == {"detail": "no run 'missing-run'"}
    bad = client.get("/ui/jobs/clean-01/log", params={"after": "x"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"


def test_log_sse_replays_resumes_and_json(client: TestClient, runs: dict[str, Path]) -> None:
    n = len(read_events(runs["clean"] / "events.jsonl"))
    frames = _sse(client, "/ui/jobs/clean-01/log")
    lines = [f for f in frames if f[0] == "line"]
    assert len(lines) == n and lines[0][1] == "1" and lines[0][2]["seq"] == 1
    assert frames[-1][0] == "end" and frames[-1][2] == {"reason": "run_end", "lastSeq": n}
    resumed = _sse(client, "/ui/jobs/clean-01/log", headers={"Last-Event-ID": str(n - 3)})
    assert [f[2]["seq"] for f in resumed if f[0] == "line"] == [n - 2, n - 1, n]
    as_json = client.get("/ui/jobs/clean-01/log", params={"format": "json"}).json()
    assert len(as_json) == n and as_json[-1]["seq"] == n
    assert client.get("/ui/jobs/nope/log", params={"format": "json"}).status_code == 404
    missing = _sse(client, "/ui/jobs/not-started/log", params={"wait": 0})
    # nothing sent yet: -1, so a reconnect still receives a seq-0 line
    assert missing == [("end", "-1", {"reason": "missing", "lastSeq": -1})]


def test_sse_streams_a_run_that_is_still_being_written(
    client: TestClient, runs: dict[str, Path], offline_profile: Profile
) -> None:
    events = read_events(runs["clean"] / "events.jsonl")
    live = Path(offline_profile.runs_dir) / "live-02"

    def writer() -> None:
        time.sleep(0.3)  # the stream starts before the run directory exists
        live.mkdir()
        with (live / "events.jsonl").open("a") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
                fh.flush()
                time.sleep(0.01)

    thread = threading.Thread(target=writer)
    thread.start()
    frames = _sse(client, "/ui/jobs/live-02/log", params={"wait": 5})
    thread.join()
    assert [f[2]["seq"] for f in frames if f[0] == "line"] == [e["seq"] for e in events]
    assert frames[-1][2]["reason"] == "run_end"


def test_native_files_route_is_hardened(client: TestClient, runs: dict[str, Path]) -> None:
    cif = client.get("/runs/clean-01/files/artifacts/sources/3PTB.cif")
    assert cif.status_code == 200 and cif.headers["content-type"].startswith("text/plain")
    assert cif.headers["x-content-type-options"] == "nosniff"
    svg = client.get("/runs/clean-01/files/graph.svg")
    assert svg.status_code == 200 and svg.headers["content-security-policy"] == "sandbox"
    (runs["clean"] / "out.txt").symlink_to(ROOT / "pyproject.toml")
    assert client.get("/runs/clean-01/files/out.txt").status_code == 404
    assert client.get("/runs/clean-01/files/..%2F..%2Fsecret").status_code == 404
    assert client.get("/runs/clean-01/files/%2Fetc%2Fpasswd").status_code == 404


def test_tools_tasks_and_catalog_routes(client: TestClient) -> None:
    tools = {t["id"]: t for t in client.get("/ui/tools").json()}
    assert {"boltz2", "protenix", "vina", "gnina", "diffdock", "pydock"} <= set(tools)
    for t in tools.values():
        assert t["family"] in {"co-folding", "docking"} and isinstance(t["available"], bool)
        assert t["name"] and t["role"] and "note" in t and isinstance(t["outputs"], list)
        for o in t["outputs"]:
            assert o["key"] and o["label"] and o["kind"] and o["scope"]
    gnina = tools["gnina"]
    assert {o["key"]: o.get("rankingOnly", False) for o in gnina["outputs"]}["CNNaffinity"]
    assert any(p["key"] == "exhaustiveness" for p in gnina["dockingParams"])
    assert tools["boltz2"]["runtime"]["gpu"] == "required" and tools["boltz2"]["version"]
    assert tools["pydock"]["outputs"] == [] and "UNVERIFIED" in tools["pydock"]["outputsNote"]
    assert tools["alphafold3"]["aliases"] == ["af3"]
    assert all(t["available"] is False for t in tools.values())  # no executor here

    tasks = {t["id"]: t for t in client.get("/ui/tasks").json()}
    assert tasks["pose_known_pocket"]["pah"] == "ligand_pose"
    assert tasks["pose_known_pocket"]["group"] == "docking"
    assert tasks["monomer"]["pah"] == "monomer_structure"
    lp = tasks["ligand_pose"]
    assert lp["implemented"] == sum(layer["implemented"] for layer in lp["layers"])
    assert lp["checks"] == sum(layer["checks"] for layer in lp["layers"]) >= lp["implemented"]

    catalog = client.get("/ui/catalog").json()
    assert catalog["proteins"] and catalog["ligands"]


def test_catalog_missing_gives_empty_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    from pah.webui import catalog, routes_read

    def missing() -> Any:
        raise FileNotFoundError("configs/catalog.yaml")

    monkeypatch.setattr(catalog, "load_catalog", missing)
    assert routes_read.ui_catalog() == {"proteins": [], "ligands": []}


def test_executor_outputs_present_missing_or_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    cfg = tmp_path / "configs"
    shutil.copytree(ROOT / "configs", cfg)
    (cfg / "executors.yaml").write_text(
        "version: 1\nexecutors:\n"
        "  - {id: plain, name: Plain, family: docking}\n"
        "  - id: rich\n    name: Rich\n    family: cofolding\n    outputs:\n"
        "      - {key: s, label: S, kind: score, scope: pose, rankingOnly: true}\n"
        "      - {key: bad, label: Bad, kind: nonsense, scope: pose}\n"
    )
    monkeypatch.setenv("PAH_CONFIG_DIR", str(cfg))
    rows = adapter.executor_rows()
    assert [r["id"] for r in rows] == ["plain", "rich"]
    assert adapter.tool_outputs(rows[0]) == []
    assert adapter.tool_outputs(rows[1]) == [
        {"key": "s", "label": "S", "kind": "score", "scope": "pose", "rankingOnly": True}
    ]
    unknown = adapter.record_tool("nope", rows)
    assert unknown == {"id": "nope", "name": "nope", "version": None, "outputs": []}
    register = adapter.tool_register("local")
    assert [t["family"] for t in register] == ["docking", "co-folding"]
    assert register[0]["available"] is False and "runtimes.yaml" in register[0]["note"]


# ---------------------------------------------------------------- app wiring and CORS


def test_ui_router_skips_missing_modules(
    offline_profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pah.webui as webui

    monkeypatch.setattr(webui, "ROUTER_MODULES", ("routes_read", "routes_does_not_exist"))
    client = TestClient(create_app(offline_profile))
    assert client.get("/ui/tools").status_code == 200


def test_cors_patterns_and_single_middleware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import re

    from fastapi.middleware.cors import CORSMiddleware

    from pah.webui.settings import add_cors, cors_config, create_app_from_env

    plain, regex = cors_config(["http://localhost:3000", "https://*.vercel.app"])
    assert plain == ("http://localhost:3000",) and regex is not None
    assert re.fullmatch(regex, "https://pah-git-main.vercel.app")
    assert not re.fullmatch(regex, "https://evil.example/x.vercel.app")
    assert not re.fullmatch(regex, "https://vercel.app")
    assert cors_config(["http://a"]) == (("http://a",), None)

    profile = tmp_path / "p.yaml"
    profile.write_text(
        f"name: t\nbackend: local\ncache_dir: {tmp_path / 'c'}\nruns_dir: {tmp_path / 'r'}\n"
    )
    monkeypatch.setenv("PAH_PROFILE", str(profile))
    monkeypatch.setenv("PAH_CORS_ORIGINS", "http://localhost:3000, https://*.vercel.app")
    app = create_app_from_env()
    assert (tmp_path / "r").is_dir() and (tmp_path / "c").is_dir()
    assert sum(m.cls is CORSMiddleware for m in app.user_middleware) == 1
    assert add_cors(app, ["http://other"]) is False  # never a second CORS layer
    client = TestClient(app)
    ok = client.get("/health", headers={"Origin": "https://pr-12.vercel.app"})
    assert ok.headers["access-control-allow-origin"] == "https://pr-12.vercel.app"
    no = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in no.headers
    assert client.get("/ui/jobs").json() == []


def test_load_state_of_empty_run_dir_is_queued(tmp_path: Path) -> None:
    run = tmp_path / "queued-01"
    run.mkdir()
    (run / "job.json").write_text(json.dumps({"name": "queued job", "status": "queued"}))
    state = load_state(run)
    assert state.status == "queued"
    job = to_job(run, state=state)
    assert job["name"] == "queued job" and job["layerIdx"] == 0 and job["verdict"] is None
    assert to_ui_record(run)["layers"][0]["status"] == "pending"


def test_log_includes_seq_zero_line(client: TestClient, offline_profile: Profile) -> None:
    run_dir = Path(offline_profile.runs_dir) / "seq0-01"
    run_dir.mkdir(parents=True)
    rows = [
        {"run_id": "seq0-01", "seq": 0, "kind": "log", "stage": "job", "message": "executors "
         "not run (checks only): boltz2", "ts": "2026-10-17T10:00:00Z", "data": {}},
        {"run_id": "seq0-01", "seq": 1, "kind": "run_start", "stage": "run", "message": "start",
         "ts": "2026-10-17T10:00:01Z", "data": {}},
    ]  # fmt: skip
    events = run_dir / "events.jsonl"
    events.write_text("".join(json.dumps(r) + "\n" for r in rows))
    old = time.time() - 60
    os.utime(events, (old, old))
    lines = client.get("/ui/jobs/seq0-01/log", params={"format": "json"}).json()
    assert [line["seq"] for line in lines] == [0, 1]
    after = client.get("/ui/jobs/seq0-01/log", params={"format": "json", "after": 0}).json()
    assert [line["seq"] for line in after] == [1]


def test_tasks_carry_inputs_and_kind(client: TestClient) -> None:
    from pah.webui.routes_read import task_kind

    assert task_kind(["target", "partner", "seeds"]) == "complex"
    assert task_kind(["target", "series", "ph"]) == "ligand"
    assert task_kind(["target", "seeds"]) == "monomer"
    tasks = {t["id"]: t for t in client.get("/ui/tasks").json()}
    assert tasks["ligand_pose"]["kind"] == "ligand" and "ligand" in tasks["ligand_pose"]["inputs"]
