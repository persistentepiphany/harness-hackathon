"""Layers 2 to 5 on the committed 3PTB Vina outputs, offline against recorded sources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.conftest import ROOT

pytest.importorskip("rdkit")
pytest.importorskip("gemmi")
pytest.importorskip("spyrmsd")

VINA = ROOT / "examples/3ptb_vina/manifest.yaml"


def _context(tmp_path: Path, manifest: Any, web: Any = None) -> Any:
    import pah.checks  # noqa: F401
    from pah.core.check import CheckContext
    from pah.core.task import load_task
    from pah.sources import CachedHttp, ContentCache, Sources
    from tests.fakeweb import FakeWeb

    web = web or FakeWeb()
    sources = Sources(CachedHttp(web.client(), ContentCache(tmp_path / "cache")))
    return CheckContext(manifest, load_task(manifest.task), sources, tmp_path / "run")


def _run(ctx: Any, layers: tuple[int, ...]) -> dict[str, Any]:
    from pah.core.engine import Engine
    from pah.core.events import EventBus

    record = Engine(EventBus("t", []), ctx, halt_on_stop=False).run(layers)
    return {f.check_id: f for f in record.findings}


@pytest.fixture(scope="module")
def vina_findings(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    from pah.core.manifest import load_manifest

    mp = pytest.MonkeyPatch()
    mp.setenv("PAH_CONDA_PREFIX", str(tmp_path_factory.mktemp("noconda")))
    try:
        tmp = tmp_path_factory.mktemp("vina")
        ctx = _context(tmp, load_manifest(VINA))
        return _run(ctx, (2, 3, 4, 5))
    finally:
        mp.undo()


def test_docking_box_encloses_contacts(vina_findings: dict[str, Any]) -> None:
    f = vina_findings["l2.docking.box"]
    assert f.gate.value == "pass"
    m = {x.name: x.value for x in f.measurements}
    assert m["contact_residues_outside"] == 0
    assert f.evidence["center"] == pytest.approx([-1.856, 14.366, 16.748])


def test_pocket_and_state(vina_findings: dict[str, Any]) -> None:
    assert vina_findings["l2.pocket.resolved"].gate.value == "pass"
    assert vina_findings["l2.receptor.state"].evidence["ligands"] == ["BEN"]
    assert vina_findings["l2.msa.depth"].gate.value == "skip"  # MSA unused by docking


def test_training_cutoff_not_learned(vina_findings: dict[str, Any]) -> None:
    f = vina_findings["l3.model.training_cutoff"]
    assert f.gate.value == "pass"
    assert "vina not learned" in f.message
    assert vina_findings["l3.exposure.pocket"].gate.value == "skip"
    assert vina_findings["l3.metric.endpoint"].gate.value == "pass"


def test_posebusters_and_interactions(vina_findings: dict[str, Any]) -> None:
    pytest.importorskip("posebusters")
    pb = vina_findings["l4.posebusters"]
    assert pb.gate.value == "pass"
    assert {t["test"] for t in pb.evidence["tests"]} >= {
        "bond_lengths",
        "volume_overlap_with_protein",
    }
    assert all(t["pass"] for t in pb.evidence["tests"])
    tors = vina_findings["l4.torsion_strain"]
    assert tors.gate.value == "pass"
    assert {x.name: x.value for x in tors.measurements}["strain_kcal"] < 5


def test_known_binder_interaction(vina_findings: dict[str, Any]) -> None:
    pytest.importorskip("plip")
    pytest.importorskip("openbabel")
    f = vina_findings["l4.interactions.known_binders"]
    assert f.gate.value == "pass"
    assert "hbond ASP189A" in f.evidence["reproduced"]
    fp = vina_findings["l4.interactions.fingerprint"]
    assert any(r["residue"] == "ASP189A" for r in fp.evidence["interactions"])


def test_drift_skips_without_conda(vina_findings: dict[str, Any]) -> None:
    f = vina_findings["l4.minimisation_drift"]
    assert f.gate.value == "skip"
    assert f.evidence["skip_reason"] == "tool_missing"


def test_ensemble_and_controls(vina_findings: dict[str, Any]) -> None:
    seeds = vina_findings["l5.sampling.seeds"]
    assert {x.name: x.value for x in seeds.measurements}["independent_seeds"] == 5
    cl = vina_findings["l5.sampling.clusters"]
    assert cl.gate.value == "pass"
    assert cl.evidence["medoid"].startswith("vina/seed")
    assert cl.evidence["pairwise_rmsd_A"]["n"] == 10
    assert "5 of 5" in cl.evidence["site_placement"]
    agree = vina_findings["l5.agreement.cross_family"]
    crystal = [c for c in agree.evidence["comparisons"] if c["weight"] == "decisive"]
    assert crystal and crystal[0]["value"] < 2.0
    redock = vina_findings["l5.controls.redocking"]
    assert redock.gate.value == "pass"
    assert redock.evidence["rmsd_A"] < 2.0


def test_prediction_artifacts_tagged(tmp_path: Path) -> None:
    from pah.checks import outputs
    from pah.core.manifest import load_manifest
    from pah.core.models import ArtifactKind

    ctx = _context(tmp_path, load_manifest(VINA))
    sets = outputs.prediction_sets(ctx)
    assert [s.role for s in sets] == ["primary", "control:redocking"]
    kinds = {a.kind for a in ctx.artifacts}
    assert ArtifactKind.PREDICTION_STRUCTURE in kinds
    assert len(outputs.ensemble_poses(ctx)) == 5


def test_redocking_missing_is_stop(tmp_path: Path) -> None:
    from pah.core.manifest import ControlsInput, load_manifest

    m = load_manifest(VINA).model_copy(update={"controls": ControlsInput()})
    f = _run(_context(tmp_path, m), (5,))["l5.controls.redocking"]
    assert f.gate.value == "stop"
    assert "not supplied" in f.message


def test_parse_failure_is_incomplete(tmp_path: Path) -> None:
    from pah.core.manifest import PredictionInput, load_manifest

    m = load_manifest(VINA)
    bad = PredictionInput(executor="vina", path=Path("does/not/exist"), receptor=Path("x.pdb"))
    m = m.model_copy(update={"predictions": (bad,)})
    f = _run(_context(tmp_path, m), (5,))["l5.sampling.seeds"]
    assert f.gate.value == "skip"
    assert f.evidence["skip_reason"] == "error"
    assert "no prediction could be parsed" in f.message


def test_endpoint_stops_affinity_claim(tmp_path: Path) -> None:
    from pah.core.manifest import load_manifest

    m = load_manifest(VINA).model_copy(update={"claim": "Kd below 1 µM"})
    f = _run(_context(tmp_path, m), (3,))["l3.metric.endpoint"]
    assert f.gate.value == "stop"


def test_msa_stats_neff() -> None:
    from pah.checks.layer2_adequacy import msa_stats

    records = [("q", "ACDEFGHIKL"), ("a", "ACDEFGHIKL"), ("b", "AC-EFGHIKM"), ("c", "WWWWWWWWWW")]
    s = msa_stats(records)
    assert s["sequences"] == 4
    assert s["distinct"] == 3
    # q, a, b cluster at 80 percent identity; c is alone: Neff = 3 * 1/3 + 1 = 2
    assert s["neff"] == pytest.approx(2.0)


def test_cluster_and_symmetry() -> None:
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import AllChem

    from pah.checks.outputs import cluster, heavy_coords, symmetric_rmsd

    mat = np.array([[0, 1, 5], [1, 0, 5], [5, 5, 0]], dtype=float)
    assert cluster(mat, 2.0) == [[0, 1], [2]]
    mol = Chem.AddHs(Chem.MolFromSmiles("c1ccccc1C(=O)[O-]"))
    AllChem.EmbedMolecule(mol, randomSeed=1)
    mol = Chem.RemoveHs(mol)
    xyz = heavy_coords(mol)
    order = [5, 4, 3, 2, 1, 0, 6, 8, 7]  # ring flipped, carboxylate oxygens swapped
    perm = Chem.RenumberAtoms(mol, order)
    assert symmetric_rmsd(mol, xyz, perm, heavy_coords(perm)) == pytest.approx(0.0, abs=1e-6)


def test_configured_threshold_has_origin() -> None:
    from pah.checks.outputs import configured, model_entry

    th = configured("l5.controls.redocking", "rmsd")
    # published origin (user's threshold list, 17 Oct 2026): Runs N' Poses, not the specification
    assert th.value == 2.0 and "Škrinjar et al. 2025" in th.origin
    assert model_entry("boltz2")["training_cutoff"] == "2023-06-01"
    assert model_entry("vina")["learned"] is False


def test_ligand_prevalence_counts_pre_cutoff_entries(tmp_path: Path) -> None:
    from pah.core.manifest import ModelInfo, load_manifest
    from tests.fakeweb import FakeWeb

    class SearchWeb(FakeWeb):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            if request.url.path == "/rcsbsearch/v2/query":
                q = json.loads(request.url.params["json"])
                if q["return_type"] == "mol_definition":
                    rows = [{"identifier": "BEN"}, {"identifier": "PBZ"}]
                    return httpx.Response(200, json={"total_count": 2, "result_set": rows})
                rows = [{"identifier": f"E{i:03d}"} for i in range(150)]
                return httpx.Response(200, json={"total_count": 150, "result_set": rows})
            return super().__call__(request)

    m = load_manifest(ROOT / "examples/3ptb_ligand_pose/manifest.yaml")
    m = m.model_copy(update={"model": ModelInfo(executor="boltz2", version="2.2.1")})
    f = _run(_context(tmp_path, m, SearchWeb()), (3,))["l3.exposure.ligand_prevalence"]
    # published definition used as exposure context only (configs/standing.yaml role context)
    assert f.gate.value == "pass" and f.evidence["prevalent"] == ["benzamidine"]
    assert f.evidence["gating"] is False
    m_ = {x.name: x.value for x in f.measurements}
    assert m_["systems"] == 150 and m_["cutoff"] == "2023-06-01"
    assert [c["code"] for c in f.evidence["ligands"][0]["components"]] == ["BEN"]
