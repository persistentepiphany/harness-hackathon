import json
from pathlib import Path

import httpx
import pytest

from pah.config import Profile, config_dir, load_profile
from pah.core.events import EventBus, MemorySink
from pah.core.models import EventKind
from pah.doctor import Doctor, ProbeContext, build_catalog, write_report
from pah.doctor.catalog import CATEGORIES, build_probe
from pah.doctor.probes import FileProbe, ProbeStatus


def test_catalog_builds_every_category(profile: Profile) -> None:
    with httpx.Client() as client:
        catalog = build_catalog(ProbeContext(client=client, profile=profile), list(CATEGORIES))
    assert list(catalog) == list(CATEGORIES)
    ids = [p.id for probes in catalog.values() for p in probes]
    assert len(ids) == len(set(ids)), "probe ids must be unique"
    assert {"uniprot", "rdkit", "boltz2.weights", "humanizer.local"} <= set(ids)


def test_unknown_probe_kind(profile: Profile) -> None:
    with httpx.Client() as client, pytest.raises(ValueError, match="unknown probe kind"):
        build_probe("x", "s", {"kind": "telepathy"}, ProbeContext(client=client, profile=profile))


def test_infrastructure_filtered_by_profile() -> None:
    with httpx.Client() as client:
        csf3 = build_catalog(
            ProbeContext(client=client, profile=load_profile("csf3")), ["infrastructure"]
        )
        modal = build_catalog(
            ProbeContext(client=client, profile=load_profile("modal")), ["infrastructure"]
        )
    assert "sbatch" in {p.id for p in csf3["infrastructure"]}
    assert "modal_token" in {p.id for p in modal["infrastructure"]}
    assert "sbatch" not in {p.id for p in modal["infrastructure"]}


def test_profiles_load() -> None:
    for name in ("local", "csf3", "modal"):
        assert load_profile(name).name == name
    assert (config_dir() / "profiles" / "csf3.yaml").is_file()


def test_runner_streams_and_reports(tmp_path: Path) -> None:
    present = tmp_path / "a"
    present.write_text("x")
    catalog = {
        "skills": [
            FileProbe(id="a", category="skills", target=str(present)),
            FileProbe(id="b", category="skills", target=str(tmp_path / "missing")),
        ]
    }
    mem = MemorySink()
    report = Doctor(EventBus("doctor-t", [mem])).run(catalog, "local")
    kinds = [e.kind for e in mem.events]
    assert kinds[0] is EventKind.RUN_START and kinds[-1] is EventKind.RUN_END
    assert kinds.count(EventKind.RESULT) == 2
    assert [r.id for r in report.results] == ["a", "b"]
    assert report.counts() == {"ok": 1, "missing": 1}
    assert not report.ok

    json_path, md_path = write_report(report, tmp_path / "out")
    assert json.loads(json_path.read_text())["results"][1]["status"] == ProbeStatus.MISSING.value
    md = md_path.read_text()
    assert "| a | ok |" in md and "## skills" in md


def test_probe_exception_becomes_error(tmp_path: Path) -> None:
    class Boom(FileProbe):
        def run(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("bug")

    report = Doctor(EventBus("d", [])).run({"x": [Boom(id="z", category="x", target="t")]}, "local")
    assert report.results[0].status is ProbeStatus.ERROR


def test_catalog_tolerates_bad_entries(tmp_path: Path, profile: Profile) -> None:
    (tmp_path / "sources.yaml").write_text(
        "sources:\n"
        "  - {id: good, probe: {kind: http, url: 'https://h/'}}\n"
        "  - {id: noprobe}\n"
        "  - {id: badkind, probe: {kind: telepathy}}\n"
        "  - {id: nourl, probe: {kind: http}}\n"
    )
    with httpx.Client() as client:
        catalog = build_catalog(
            ProbeContext(client=client, profile=profile),
            ["sources", "tools", "nope"],
            base=tmp_path,
        )
    kinds = {p.id: p.kind for p in catalog["sources"]}
    assert kinds == {"good": "http", "noprobe": "config", "badkind": "config", "nourl": "config"}
    assert [p.kind for p in catalog["tools"]] == ["config"]  # tools.yaml missing in tmp_path
    assert [p.kind for p in catalog["nope"]] == ["config"]
    report = Doctor(EventBus("d", [])).run({"sources": catalog["sources"][1:]}, "local")
    assert {r.status for r in report.results} == {ProbeStatus.ERROR}


def test_binary_search_includes_tools_dir(profile: Profile) -> None:
    with httpx.Client() as client:
        ctx = ProbeContext(client=client, profile=profile)
    assert ctx.search_dirs[0].name == "bin" and ctx.search_dirs[0].parent.name == ".tools"


def test_fetchable_tool_missing_detail_names_command(profile: Profile) -> None:
    with httpx.Client() as client:
        tools = build_catalog(ProbeContext(client=client, profile=profile), ["tools"])["tools"]
    mmseqs = next(p for p in tools if p.id == "mmseqs")
    assert getattr(mmseqs, "hint", "") == "install with `pah fetch --only mmseqs`"
