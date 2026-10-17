from pathlib import Path

import pytest

import pah.checks  # noqa: F401 - registers checks
from pah.checks.layer1_integrity import _diff, _read_a3m
from pah.core.check import CheckContext
from pah.core.engine import Engine, RunRecord
from pah.core.events import EventBus
from pah.core.manifest import load_manifest
from pah.core.models import Gate
from pah.core.policy import Outcome
from pah.core.task import list_tasks, load_task
from pah.sources import CachedHttp, ContentCache, Sources
from tests.fakeweb import FakeWeb

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=False)
def science() -> None:
    pytest.importorskip("rdkit")
    pytest.importorskip("gemmi")


def _run(example: str, tmp_path: Path, **kw: bool) -> RunRecord:
    manifest = load_manifest(ROOT / "examples" / example / "manifest.yaml")
    task = load_task(manifest.task)
    sources = Sources(CachedHttp(FakeWeb().client(), ContentCache(tmp_path / "cache"), **kw))
    ctx = CheckContext(manifest, task, sources, tmp_path / "run")
    return Engine(EventBus("t", []), ctx, halt_on_stop=False).run((0, 1))


def _gates(record: RunRecord) -> dict[str, Gate]:
    return {f.check_id: f.gate for f in record.findings}


def test_clean_example_passes(tmp_path: Path, science: None) -> None:
    record = _run("3ptb_ligand_pose", tmp_path)
    gates = _gates(record)
    assert gates.pop("l1.ligand.stereo_defined") is Gate.WARN
    assert set(gates.values()) == {Gate.PASS}, gates
    assert record.verdict and record.verdict.outcome is Outcome.PASS_WITH_WARNINGS
    sources = {p.source_id for p in record.provenance}
    assert {"uniprot", "rcsb", "pdbe", "sifts", "ccd", "pubchem", "rcsb_files"} <= sources
    assert all(len(p.sha256) == 64 for p in record.provenance)
    assert record.tool_versions.get("rdkit") and record.tool_versions.get("gemmi")
    assert (tmp_path / "run" / "artifacts" / "sources" / "3PTB.cif").is_file()


def test_faulty_example_stops_on_each_fault(tmp_path: Path, science: None) -> None:
    record = _run("3ptb_faulty_inputs", tmp_path)
    gates = _gates(record)
    for cid in (
        "l0.cross.ligand_inchikey",
        "l1.sequence.matches_record",
        "l1.sequence.no_truncation_substitution",
        "l1.msa.integrity",
        "l1.ligand.identity",
        "l1.receptor.chains",
        "l1.provenance.model_config",
    ):
        assert gates[cid] is Gate.STOP, cid
    trunc = next(
        f for f in record.findings if f.check_id == "l1.sequence.no_truncation_substitution"
    )
    values = {m.name: m.value for m in trunc.measurements}
    assert values["n_truncation"] == 5 and values["substitutions"] == 3
    assert record.verdict and record.verdict.outcome is Outcome.STOP


def test_offline_without_cache_stops_at_provenance(tmp_path: Path, science: None) -> None:
    manifest = load_manifest(ROOT / "examples" / "3ptb_ligand_pose" / "manifest.yaml")
    sources = Sources(
        CachedHttp(FakeWeb().client(), ContentCache(tmp_path / "empty"), offline=True)
    )
    ctx = CheckContext(manifest, load_task("ligand_pose"), sources, tmp_path / "run")
    record = Engine(EventBus("t", []), ctx).run((0, 1))
    first = record.findings[0]
    assert first.check_id == "l0.sources.resolved" and first.gate is Gate.STOP
    assert "offline_miss" in str(first.evidence["failed"])
    assert all(f.gate is Gate.SKIP for f in record.findings[1:] if f.layer == 1)


def test_cached_then_offline_rerun_matches(tmp_path: Path, science: None) -> None:
    first = _run("3ptb_ligand_pose", tmp_path)
    second = _run("3ptb_ligand_pose", tmp_path, offline=True)
    assert _gates(first) == _gates(second)
    assert {p.sha256 for p in first.provenance} == {p.sha256 for p in second.provenance}


def test_sequence_diff_classifies_changes() -> None:
    ref = "ABCDEFGHIJ"
    assert _diff(ref, ref)["substitutions"] == []
    d = _diff(ref, "CDEFGXIJ")
    assert d["n_truncation"] == 2 and d["substitutions"] == ["H8X"]
    assert _diff(ref, "ABCDEFGH")["c_truncation"] == 2
    assert _diff(ref, "ABCFGHIJ")["internal_deletions"] == 2


def test_read_a3m(tmp_path: Path) -> None:
    f = tmp_path / "x.a3m"
    f.write_text("#comment\n>q\nACD\nEF\n>h1\nA-DefEF\n")
    assert _read_a3m(f) == [("q", "ACDEF"), ("h1", "A-DefEF")]


def test_every_task_spec_loads() -> None:
    tasks = list_tasks()
    assert {"ligand_pose", "interaction_discovery", "virtual_screening"} <= set(tasks)
    for t in tasks:
        spec = load_task(t)
        assert spec.claim and spec.layers
