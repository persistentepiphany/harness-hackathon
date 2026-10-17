import json

from typer.testing import CliRunner

from pah import __version__
from pah.interfaces.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0 and __version__ in result.stdout


def test_doctor_dry_run_jsonl() -> None:
    result = runner.invoke(app, ["doctor", "--dry-run", "--only", "skills", "--format", "jsonl"])
    assert result.exit_code == 0, result.output
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert events[-1]["kind"] == "run_end"
    assert any("humanizer.remote" in e["message"] for e in events)


def test_doctor_dry_run_profiles() -> None:
    for profile in ("csf3", "modal"):
        result = runner.invoke(app, ["doctor", "--dry-run", "--profile", profile])
        assert result.exit_code == 0, result.output


def test_bad_profile_exits_2_without_traceback() -> None:
    result = runner.invoke(app, ["doctor", "--profile", "no-such-profile"])
    assert result.exit_code == 2
    assert "Traceback" not in result.output


def test_fetch_dry_run_lists_assets() -> None:
    result = runner.invoke(
        app,
        ["fetch", "--dry-run", "--all", "--only", "mmseqs", "--only", "ghost", "--format", "jsonl"],
    )
    assert result.exit_code == 0, result.output
    events = [json.loads(line) for line in result.stdout.splitlines()]
    messages = " ".join(e["message"] for e in events)
    assert "unknown asset id: ghost" in messages and "mmseqs" in messages


def _offline_profile(tmp_path):  # type: ignore[no-untyped-def]
    import pytest

    pytest.importorskip("rdkit")
    pytest.importorskip("gemmi")
    from pah.sources import CachedHttp, ContentCache, Sources
    from tests.fakeweb import FakeWeb

    cache = tmp_path / "cache"
    s = Sources(CachedHttp(FakeWeb().client(), ContentCache(cache)))
    s.uniprot.entry("P00760")
    s.rcsb.entry("3PTB")
    s.rcsb.mmcif("3PTB")
    s.rcsb.chemcomp("BEN")
    s.pdbe.molecules("3ptb")
    s.pdbe.sifts("3ptb")
    s.pubchem.compound(2332)
    profile = tmp_path / "offline.yaml"
    runs = tmp_path / "runs"
    profile.write_text(
        f"name: offline\nbackend: local\ncache_dir: {cache}\nruns_dir: {runs}\noffline: true\n"
    )
    return profile


def test_run_example_offline_jsonl(tmp_path) -> None:  # type: ignore[no-untyped-def]
    profile = _offline_profile(tmp_path)
    out = tmp_path / "run"
    result = runner.invoke(
        app,
        [
            "run",
            "examples/3ptb_ligand_pose/manifest.yaml",
            "--profile",
            str(profile),
            "--out",
            str(out),
            "--format",
            "jsonl",
            "--strict",
        ],
    )
    assert result.exit_code == 0, result.output
    events = [json.loads(line) for line in result.stdout.splitlines()]
    findings = [e for e in events if e["kind"] == "finding"]
    assert len(findings) == 13
    run_end = next(e for e in events if e["kind"] == "run_end")
    assert run_end["data"]["verdict"]["outcome"] == "pass_with_warnings"
    assert (out / "record.json").is_file() and len(list((out / "findings").iterdir())) == 13
    artifacts = [e["data"]["path"] for e in events if e["kind"] == "artifact"]
    assert any(a.endswith("report.md") for a in artifacts)
    assert events.index(run_end) < max(i for i, e in enumerate(events) if e["kind"] == "artifact")
    assert (out / "report.json").is_file() and (out / "graph.mmd").is_file()


def test_run_faulty_example_strict_exits_1(tmp_path) -> None:  # type: ignore[no-untyped-def]
    profile = _offline_profile(tmp_path)
    result = runner.invoke(
        app,
        ["run", "examples/3ptb_faulty_inputs/manifest.yaml", "--profile", str(profile), "--strict"],
    )
    assert result.exit_code == 1


def test_run_bad_manifest_exits_2(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bad = tmp_path / "m.yaml"
    bad.write_text("task: ligand_pose\nligands:\n  - id: x\n")
    result = runner.invoke(app, ["run", str(bad)])
    assert result.exit_code == 2 and "Traceback" not in result.output


def test_tasks_and_checks_listing() -> None:
    tasks = runner.invoke(app, ["tasks", "--format", "jsonl"])
    rows = [json.loads(line) for line in tasks.stdout.splitlines()]
    assert any(r["id"] == "ligand_pose" and r["implemented"] >= 13 for r in rows)
    checks = runner.invoke(app, ["checks"])
    assert "l0.sources.resolved" in checks.stdout and "l1.msa.integrity" in checks.stdout


def test_report_command_regenerates(tmp_path) -> None:  # type: ignore[no-untyped-def]
    profile = _offline_profile(tmp_path)
    out = tmp_path / "run"
    runner.invoke(
        app,
        [
            "run",
            "examples/3ptb_ligand_pose/manifest.yaml",
            "--profile",
            str(profile),
            "--out",
            str(out),
            "--no-report",
        ],
    )
    assert not (out / "report.md").exists()
    result = runner.invoke(app, ["report", str(out), "--format", "jsonl"])
    assert result.exit_code == 0, result.output
    assert (out / "report.md").is_file()


def test_report_command_bad_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["report", str(tmp_path)])
    assert result.exit_code == 2


def test_schema_command(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["schema", "--out", str(tmp_path)])
    assert result.exit_code == 0
    data = json.loads((tmp_path / "run_report.json").read_text())
    assert "verdict" in data["properties"]
