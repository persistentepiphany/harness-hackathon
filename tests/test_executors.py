"""Executor output parsers against synthetic trees built to the documented layouts."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("rdkit")
pytest.importorskip("gemmi")
pytest.importorskip("numpy")

from pah.core.manifest import LigandInput, Manifest, PredictionInput
from pah.executors import FAMILIES, PARSERS, Family, ParseError, PredictionSet
from pah.executors.base import parse_prediction
from pah.executors.structure import (
    ad_type_element,
    assemble_complex,
    extract_ligand,
    pdbqt_to_pdb_lines,
    residue_plddt,
)
from tests import executor_trees as trees


def _manifest(base: Path, *, smiles: str | None = trees.SMILES) -> Manifest:
    ligands = (
        LigandInput(id=trees.LIGAND_ID, smiles=smiles or None, ccd=None if smiles else "BEN"),
    )
    return Manifest(task="pose", ligands=ligands, base_dir=base)


def _parse(base: Path, executor: str, path: str, **kw: object) -> PredictionSet:
    spec = PredictionInput(executor=executor, path=Path(path), **kw)  # type: ignore[arg-type]
    return parse_prediction(spec, _manifest(base), base / "work")


def _ligand_key(path: Path | None) -> str:
    from rdkit import Chem

    assert path is not None and path.exists()
    mol = next(iter(Chem.SDMolSupplier(str(path))))
    assert mol is not None
    return str(Chem.MolToInchiKey(mol))


def _complex_counts(path: Path) -> tuple[int, int]:
    lines = path.read_text().splitlines()
    rec = sum(1 for ln in lines if ln.startswith("ATOM"))
    lig = sum(1 for ln in lines if ln.startswith("HETATM") and ln[17:20] == "LIG")
    return rec, lig


def test_registry_covers_documented_executors() -> None:
    import pah.executors.parsers  # noqa: F401

    expected = {
        "boltz2": Family.COFOLDING,
        "boltz1": Family.COFOLDING,
        "protenix": Family.COFOLDING,
        "alphafold3": Family.COFOLDING,
        "chai1": Family.COFOLDING,
        "colabfold": Family.COFOLDING,
        "vina": Family.DOCKING,
        "gnina": Family.DOCKING,
        "diffdock": Family.DOCKING,
        "haddock3": Family.DOCKING,
    }
    assert {k: FAMILIES[k] for k in expected} == expected
    assert set(expected) <= set(PARSERS)


# Structure helpers ------------------------------------------------------------------------------


def test_extract_ligand_assigns_bond_orders(tmp_path: Path) -> None:
    cif = trees.write_cif(tmp_path / "m.cif")
    issues: list[str] = []
    out = extract_ligand(cif, trees.SMILES, tmp_path / "lig.sdf", issues=issues)
    assert issues == []
    assert _ligand_key(out) == trees.inchikey()


def test_extract_ligand_without_smiles_records_issue(tmp_path: Path) -> None:
    cif = trees.write_cif(tmp_path / "m.cif")
    issues: list[str] = []
    out = extract_ligand(cif, None, tmp_path / "lig.sdf", issues=issues)
    assert out is not None and out.exists()
    assert any("no declared SMILES" in i for i in issues)


def test_extract_ligand_none_without_ligand(tmp_path: Path) -> None:
    pdb = trees.write_pdb(tmp_path / "p.pdb", with_ligand=False)
    issues: list[str] = []
    assert extract_ligand(pdb, trees.SMILES, tmp_path / "lig.sdf", issues=issues) is None
    assert issues


def test_residue_plddt_from_bfactors(tmp_path: Path) -> None:
    values, residues = residue_plddt(trees.write_cif(tmp_path / "m.cif"))
    assert residues == (("A", 1), ("A", 2), ("A", 3))
    assert values == (80.0, 70.0, 90.0)


def test_pdbqt_columns_become_elements(tmp_path: Path) -> None:
    lines = pdbqt_to_pdb_lines(trees.receptor_pdbqt(tmp_path / "r.pdbqt").read_text().splitlines())
    assert len(lines) == 16
    assert {ln[76:78].strip() for ln in lines} == {"N", "C", "O"}
    assert ad_type_element("OA") == "O" and ad_type_element("A") == "C"


def test_assemble_complex_from_pdbqt_receptor(tmp_path: Path) -> None:
    from rdkit import Chem

    sdf = tmp_path / "l.sdf"
    w = Chem.SDWriter(str(sdf))
    w.write(trees.ligand_mol())
    w.close()
    out = assemble_complex(trees.receptor_pdbqt(tmp_path / "r.pdbqt"), sdf, tmp_path / "c.pdb")
    assert _complex_counts(out) == (16, 9)


# Co-folding -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sub", ["out", "out/boltz_results_job", "out/boltz_results_job/predictions/job"]
)
def test_boltz(tmp_path: Path, sub: str) -> None:
    trees.boltz_tree(tmp_path / "out")
    ps = _parse(tmp_path, "boltz2", sub, seeds=(7,))
    assert ps.family is Family.COFOLDING
    assert [p.id for p in ps.ranked()] == ["boltz2/seed7/sample0", "boltz2/seed7/sample1"]
    best = ps.ranked()[0]
    assert best.seed == 7 and best.rank == 0
    assert best.scores["confidence_score"] == pytest.approx(0.9)
    assert best.scores["complex_plddt"] == pytest.approx(0.75)
    assert "affinity_pred_value" not in best.scores
    assert ps.settings["affinity"]["affinity_pred_value"] == pytest.approx(-1.2)
    assert ps.settings["affinity"]["affinity_probability_binary"] == pytest.approx(0.81)
    assert best.plddt == pytest.approx((80.0, 70.0, 90.0), abs=1e-3)
    assert best.plddt_residues == (("A", 1), ("A", 2), ("A", 3))
    assert best.pae is not None and best.pae.suffix == ".npy"
    assert _ligand_key(best.ligand) == trees.inchikey()
    assert best.ligand_id == trees.LIGAND_ID
    assert any(f.name == "affinity_job.json" for f in best.files)
    assert any(f.name.startswith("plddt_") for f in best.files)


def test_boltz_seed_dirs_and_missing_pae(tmp_path: Path) -> None:
    for seed in (0, 1):
        trees.boltz_tree(tmp_path / "runs" / f"seed_{seed}", n_models=1, pae=False, affinity=False)
    ps = _parse(tmp_path, "boltz1", "runs")
    assert ps.seeds == [0, 1]
    assert {p.id for p in ps.poses} == {"boltz1/seed0/sample0", "boltz1/seed1/sample0"}
    assert any("pae_job_model_0.npz missing" in i for i in ps.issues)
    assert any("affinity" in i for i in ps.issues)
    assert all(p.pae is None for p in ps.poses)


def test_boltz_wrong_layout(tmp_path: Path) -> None:
    (tmp_path / "out" / "something").mkdir(parents=True)
    with pytest.raises(ParseError, match=r"_model_<k>\.cif"):
        _parse(tmp_path, "boltz2", "out")


def test_protenix(tmp_path: Path) -> None:
    trees.protenix_tree(tmp_path / "out")
    for sub in ("out", "out/job", "out/job/seed_101"):
        ps = _parse(tmp_path, "protenix", sub)
        assert all(p.seed in (101, 102) for p in ps.poses)
    ps = _parse(tmp_path, "protenix", "out")
    assert ps.seeds == [101, 102]
    assert len(ps.poses) == 4
    p = next(p for p in ps.poses if p.id == "protenix/seed102/sample1")
    assert p.rank == 1 and p.sample == 1
    assert p.scores["plddt"] == pytest.approx(77.5)
    assert p.plddt == (80.0, 70.0, 90.0)
    assert _ligand_key(p.ligand) == trees.inchikey()


def test_protenix_wrong_layout(tmp_path: Path) -> None:
    trees.write_cif(tmp_path / "out" / "job" / "job_sample_0.cif")
    with pytest.raises(ParseError, match="seed_<seed>/predictions"):
        _parse(tmp_path, "protenix", "out")


def test_alphafold3(tmp_path: Path) -> None:
    trees.alphafold3_tree(tmp_path / "out")
    ps = _parse(tmp_path, "alphafold3", "out")
    ranked = ps.ranked()
    assert [p.id for p in ranked] == ["alphafold3/seed1/sample1", "alphafold3/seed1/sample0"]
    best = ranked[0]
    assert best.rank == 0 and best.seed == 1
    assert best.scores["ranking_score"] == pytest.approx(0.83)
    assert best.plddt == pytest.approx((80.0, 70.0, 90.0))
    assert best.plddt_residues == (("A", 1), ("A", 2), ("A", 3))
    assert best.pae is not None
    import numpy as np

    assert np.load(best.pae).shape == (trees.token_count(), trees.token_count())
    assert _ligand_key(best.ligand) == trees.inchikey()
    assert any(f.name == "job_ranking_scores.csv" for f in best.files)


def test_alphafold3_wrong_layout(tmp_path: Path) -> None:
    (tmp_path / "out" / "job" / "sample_0").mkdir(parents=True)
    with pytest.raises(ParseError, match="seed-<seed>_sample-<i>"):
        _parse(tmp_path, "alphafold3", "out")


def test_chai_reranks_by_aggregate_score(tmp_path: Path) -> None:
    trees.chai_tree(tmp_path / "chai")
    ps = _parse(tmp_path, "chai1", "chai", seeds=(3,))
    assert [p.sample for p in ps.ranked()] == [1, 2, 0]
    assert [p.rank for p in sorted(ps.poses, key=lambda p: p.sample)] == [2, 0, 1]
    best = ps.ranked()[0]
    assert best.id == "chai1/seed3/sample1"
    assert best.scores["aggregate_score"] == pytest.approx(0.92)
    assert best.scores["has_inter_chain_clashes"] == 0.0
    assert best.plddt == (80.0, 70.0, 90.0)
    assert _ligand_key(best.ligand) == trees.inchikey()


def test_chai_wrong_layout(tmp_path: Path) -> None:
    trees.write_cif(tmp_path / "chai" / "model_0.cif")
    with pytest.raises(ParseError, match=r"pred\.model_idx_<i>\.cif"):
        _parse(tmp_path, "chai1", "chai")


def test_colabfold_ranks_zero_based(tmp_path: Path) -> None:
    trees.colabfold_tree(tmp_path / "cf")
    ps = _parse(tmp_path, "colabfold", "cf")
    ranked = ps.ranked()
    assert [p.rank for p in ranked] == [0, 1]
    assert ranked[0].id == "colabfold/seed0/sample2"
    assert ranked[0].seed == 0
    assert ranked[0].scores["iptm"] == pytest.approx(0.55)
    assert ranked[0].scores["pdockq.A-B"] == pytest.approx(0.3)
    assert ranked[0].plddt == (80.0, 70.0, 90.0)
    assert ranked[0].pae is not None
    assert ranked[0].ligand is None
    assert any("no non-polymer" in i for i in ps.issues)


def test_colabfold_missing_pae_is_an_issue(tmp_path: Path) -> None:
    trees.colabfold_tree(tmp_path / "cf", pae=False)
    ps = _parse(tmp_path, "colabfold", "cf")
    assert all(p.pae is None for p in ps.poses)
    assert any("has no pae" in i for i in ps.issues)


def test_colabfold_wrong_layout(tmp_path: Path) -> None:
    trees.write_pdb(tmp_path / "cf" / "job_rank_1.pdb")
    with pytest.raises(ParseError, match="_unrelaxed_rank_<NNN>"):
        _parse(tmp_path, "colabfold", "cf")


# Docking ----------------------------------------------------------------------------------------


def test_vina(tmp_path: Path) -> None:
    trees.vina_out(tmp_path / "dock" / "ben_out.pdbqt")
    trees.write_pdb(tmp_path / "rec.pdb", with_ligand=False)
    ps = _parse(tmp_path, "vina", "dock/ben_out.pdbqt", receptor=Path("rec.pdb"), seeds=(5,))
    assert ps.family is Family.DOCKING
    assert [p.id for p in ps.ranked()] == ["vina/seed5/mode0", "vina/seed5/mode1"]
    first, second = ps.ranked()
    assert first.scores == {"vina_affinity": -6.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0}
    assert second.scores["vina_affinity"] == pytest.approx(-5.9)
    assert second.scores["rmsd_ub"] == pytest.approx(1.732)
    for p in (first, second):
        assert _ligand_key(p.ligand) == trees.inchikey()
        assert _complex_counts(p.structure) == (16, 9)
        assert tmp_path / "rec.pdb" in p.files
    assert not any("meeko" in i for i in ps.issues)


def test_vina_directory_of_seed_runs_with_pdbqt_receptor(tmp_path: Path) -> None:
    for seed in (11, 12):
        trees.vina_out(tmp_path / "dock" / f"ben_seed{seed}_out.pdbqt", energies=(-6.0,))
    trees.receptor_pdbqt(tmp_path / "rec.pdbqt")
    ps = _parse(tmp_path, "vina", "dock", receptor=Path("rec.pdbqt"))
    assert ps.seeds == [11, 12]
    assert {p.id for p in ps.poses} == {"vina/seed11/mode0", "vina/seed12/mode0"}
    assert all(_complex_counts(p.structure) == (16, 9) for p in ps.poses)


def test_vina_without_meeko_remarks_uses_smiles(tmp_path: Path) -> None:
    out = trees.vina_out(tmp_path / "ben_out.pdbqt")
    text = "\n".join(
        ln for ln in out.read_text().splitlines() if not ln.startswith("REMARK SMILES")
    )
    out.write_text(text + "\n")
    trees.write_pdb(tmp_path / "rec.pdb", with_ligand=False)
    ps = _parse(tmp_path, "vina", "ben_out.pdbqt", receptor=Path("rec.pdb"))
    assert len(ps.poses) == 2
    assert all(_ligand_key(p.ligand) == trees.inchikey() for p in ps.poses)
    assert any("meeko" in i for i in ps.issues)


def test_vina_needs_receptor(tmp_path: Path) -> None:
    trees.vina_out(tmp_path / "ben_out.pdbqt")
    with pytest.raises(ParseError, match="receptor"):
        _parse(tmp_path, "vina", "ben_out.pdbqt")


@pytest.mark.parametrize("gz", [False, True])
def test_gnina(tmp_path: Path, gz: bool) -> None:
    name = "docked.sdf.gz" if gz else "docked.sdf"
    trees.gnina_sdf(tmp_path / name, gz=gz)
    trees.write_pdb(tmp_path / "rec.pdb", with_ligand=False)
    ps = _parse(tmp_path, "gnina", name, receptor=Path("rec.pdb"))
    first, second = ps.ranked()
    assert first.id == "gnina/mode0" and first.seed is None
    assert first.scores["minimizedAffinity"] == pytest.approx(-7.1)
    assert first.scores["CNNscore"] == pytest.approx(0.91)
    assert first.scores["CNNaffinity"] == pytest.approx(5.2)
    assert first.scores["CNN_VS"] == pytest.approx(0.91 * 5.2, abs=1e-3)
    assert second.scores["minimizedRMSD"] == pytest.approx(0.5)
    assert _ligand_key(first.ligand) == trees.inchikey()
    assert _complex_counts(first.structure) == (16, 9)


def test_gnina_wrong_layout(tmp_path: Path) -> None:
    (tmp_path / "dir").mkdir()
    trees.write_pdb(tmp_path / "rec.pdb", with_ligand=False)
    with pytest.raises(ParseError, match=r"\.sdf"):
        _parse(tmp_path, "gnina", "dir", receptor=Path("rec.pdb"))


def test_diffdock(tmp_path: Path) -> None:
    trees.diffdock_tree(tmp_path / "dd")
    trees.write_pdb(tmp_path / "rec.pdb", with_ligand=False)
    for sub in ("dd", "dd/complex_0"):
        ps = _parse(tmp_path, "diffdock", sub, receptor=Path("rec.pdb"))
        assert [p.id for p in ps.ranked()] == ["diffdock/mode0", "diffdock/mode1"]
    first, second = ps.ranked()
    assert first.scores == {"diffdock_confidence": 0.53}
    assert second.scores == {"diffdock_confidence": -1.27}
    assert all(f.name != "rank1.sdf" for p in ps.poses for f in p.files)
    assert _ligand_key(second.ligand) == trees.inchikey()
    assert _complex_counts(second.structure) == (16, 9)


def test_diffdock_wrong_layout(tmp_path: Path) -> None:
    trees.diffdock_tree(tmp_path / "dd")
    (tmp_path / "dd" / "complex_0" / "rank1_confidence0.53.sdf").unlink()
    (tmp_path / "dd" / "complex_0" / "rank2_confidence-1.27.sdf").unlink()
    trees.write_pdb(tmp_path / "rec.pdb", with_ligand=False)
    with pytest.raises(ParseError, match="rank<k>_confidence<c>"):
        _parse(tmp_path, "diffdock", "dd", receptor=Path("rec.pdb"))


def test_haddock(tmp_path: Path) -> None:
    trees.haddock_tree(tmp_path / "run1")
    for sub in ("run1", "run1/2_caprieval", "run1/2_caprieval/capri_ss.tsv"):
        ps = _parse(tmp_path, "haddock3", sub)
        assert [p.id for p in ps.ranked()] == ["haddock3/mode0", "haddock3/mode1"]
    first, second = ps.ranked()
    assert first.scores == {"score": -45.2, "irmsd": 1.1, "fnat": 0.62, "dockq": 0.71}
    assert "irmsd" not in second.scores
    assert first.structure.suffix == ".pdb" and first.structure.exists()
    assert any(f.name == "rigidbody_1.pdb.gz" for f in first.files)
    assert first.ligand is None
    assert ps.settings["caprieval_step"] == "2_caprieval"


def test_haddock_wrong_layout(tmp_path: Path) -> None:
    (tmp_path / "run1" / "1_rigidbody").mkdir(parents=True)
    with pytest.raises(ParseError, match=r"capri_ss\.tsv"):
        _parse(tmp_path, "haddock3", "run1")


def test_unknown_executor(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="no parser"):
        _parse(tmp_path, "nope", "x")
