"""Regression tests from multi-target runs: metal ligands, declared mutations, missing files."""

import json
from pathlib import Path

import pytest
import yaml

import pah.checks  # noqa: F401 - registers checks
from pah.core.check import CheckContext
from pah.core.engine import Engine, RunRecord
from pah.core.events import EventBus
from pah.core.manifest import Manifest, load_manifest
from pah.core.models import Gate
from pah.core.task import load_task
from pah.sources import CachedHttp, ContentCache, Sources
from tests.fakeweb import FIXTURES, FakeWeb

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("rdkit")
pytest.importorskip("gemmi")


def _run(manifest: Manifest, tmp_path: Path) -> RunRecord:
    sources = Sources(CachedHttp(FakeWeb().client(), ContentCache(tmp_path / "cache")))
    ctx = CheckContext(manifest, load_task(manifest.task), sources, tmp_path / "run")
    return Engine(EventBus("t", []), ctx, halt_on_stop=False).run((0, 1))


def _gate(record: RunRecord, cid: str) -> Gate:
    return next(f.gate for f in record.findings if f.check_id == cid)


def _finding(record: RunRecord, cid: str):  # type: ignore[no-untyped-def]
    return next(f for f in record.findings if f.check_id == cid)


def _clean(tmp_path: Path, **protein_updates: object) -> Manifest:
    raw = yaml.safe_load((ROOT / "examples/3ptb_ligand_pose/manifest.yaml").read_text())
    raw["proteins"][0].update(protein_updates)
    path = tmp_path / "m" / "manifest.yaml"
    path.parent.mkdir(parents=True)
    for name in ("chain_A.a3m", "ligand_BEN.sdf"):
        (path.parent / name).write_bytes((ROOT / "examples/3ptb_ligand_pose" / name).read_bytes())
    path.write_text(yaml.safe_dump(raw))
    return load_manifest(path)


def _uniprot_seq() -> str:
    return json.loads((FIXTURES / "uniprot_P00760.json").read_text())["sequence"]["value"]


def test_declared_mutation_absent_from_seqres_passes(tmp_path: Path) -> None:
    seq = _uniprot_seq()[23:246]
    mutant = "V" + seq[1:]  # I24V in UniProt numbering, first residue of the construct
    record = _run(_clean(tmp_path, sequence=mutant, mutations=["I24V"]), tmp_path)
    assert _gate(record, "l0.cross.uniprot_seqres") is Gate.PASS
    assert _gate(record, "l1.sequence.matches_record") is Gate.PASS
    assert _gate(record, "l1.sequence.no_truncation_substitution") is Gate.PASS


def test_declared_mutation_with_wrong_wild_type_stops(tmp_path: Path) -> None:
    record = _run(_clean(tmp_path, mutations=["V24I"]), tmp_path)
    f = _finding(record, "l0.cross.uniprot_seqres")
    assert f.gate is Gate.STOP and "V24I: P00760 has I at 24" in f.message
    assert _gate(record, "l1.sequence.matches_record") is Gate.STOP


def test_undeclared_substitution_still_stops(tmp_path: Path) -> None:
    seq = _uniprot_seq()[23:246]
    record = _run(_clean(tmp_path, sequence="V" + seq[1:]), tmp_path)
    assert _gate(record, "l1.sequence.no_truncation_substitution") is Gate.STOP


def test_mutation_format_is_validated(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mutations must look like"):
        _clean(tmp_path, mutations=["99A"])


def test_missing_ligand_file_is_a_stop_not_an_error(tmp_path: Path) -> None:
    manifest = _clean(tmp_path)
    (manifest.base_dir / "ligand_BEN.sdf").unlink()
    record = _run(manifest, tmp_path)
    f = _finding(record, "l1.ligand.sanitization")
    assert f.gate is Gate.STOP and "file not found" in json.dumps(f.evidence)
    assert record.verdict and not record.verdict.incomplete


def test_metal_ligand_sanitises_and_matches_on_skeleton(tmp_path: Path) -> None:
    (tmp_path / "HEM.sdf").write_bytes((FIXTURES / "4HHB_HEM.sdf").read_bytes())
    smiles = json.loads((FIXTURES / "chemcomp_HEM.json").read_text())["rcsb_chem_comp_descriptor"]
    manifest = Manifest(
        task="virtual_screening",
        ligands=[{"id": "hem", "ccd": "HEM", "smiles": smiles["SMILES_stereo"], "file": "HEM.sdf"}],
        base_dir=tmp_path,
    )
    record = _run(manifest, tmp_path)
    san = _finding(record, "l1.ligand.sanitization")
    assert san.gate is Gate.PASS
    assert {m.name: m.value for m in san.measurements}["metal_disconnected"] == 1
    assert _gate(record, "l0.cross.ligand_inchikey") is Gate.WARN
    assert _gate(record, "l1.ligand.identity") is Gate.WARN


def test_compare_inchikey_rules() -> None:
    from pah.checks.resolve import compare_inchikey

    ref = "KABFMIBPWCXCRK-RGGAHWMASA-L"
    assert compare_inchikey(ref, ref, metal=False)[0] is Gate.PASS
    assert compare_inchikey("KABFMIBPWCXCRK-UHFFFAOYSA-L", ref, metal=True)[0] is Gate.WARN
    assert compare_inchikey("KABFMIBPWCXCRK-UHFFFAOYSA-L", ref, metal=False)[0] is Gate.STOP
    assert compare_inchikey("XXXXXXXXXXXXXX-UHFFFAOYSA-L", ref, metal=True)[0] is Gate.STOP
    assert compare_inchikey(None, ref, metal=True)[0] is Gate.STOP


def test_non_metal_valence_error_is_not_disconnected() -> None:
    from rdkit import Chem

    from pah.checks.resolve import prepare

    mol = Chem.MolFromSmiles("C[N](C)(C)(C)C", sanitize=False)  # pentavalent N, no metal
    prep = prepare(mol, "test")
    assert prep.mol is None and not prep.metal_disconnected and prep.problems
