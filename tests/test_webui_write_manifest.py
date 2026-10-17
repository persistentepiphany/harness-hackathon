"""Run settings become manifests without invented values."""

from pathlib import Path

import httpx
import pytest

from pah.core.manifest import Manifest, load_manifest
from pah.sources import CachedHttp, ContentCache, Sources
from pah.webui.manifest_builder import (
    RunSettings,
    SettingsError,
    complete_manifest,
    parse_settings,
    plan_run,
)
from tests.conftest import ROOT
from tests.fakeweb import FakeWeb

EXAMPLES = ROOT / "examples"


def _plan(**kw: object):  # type: ignore[no-untyped-def]
    return plan_run(
        parse_settings(kw), server_profile="local", examples_dir=EXAMPLES,
        known_profiles=("local", "modal", "csf3"),
    )  # fmt: skip


def _trypsin(**extra: object):  # type: ignore[no-untyped-def]
    return _plan(
        task="ligand_pose", tools=["boltz2", "gnina"], target="P00760", reference="3PTB",
        ligand="NC(=N)c1ccccc1", seeds=5, ph=7.4, **extra,
    )  # fmt: skip


def test_settings_validation() -> None:
    s = parse_settings({"target": " p00760 ", "reference": "3ptb", "partner": "", "seeds": 3})
    assert (s.target, s.reference, s.partner, s.seeds) == ("P00760", "3PTB", None, 3)
    assert s.layers == [0, 1, 2, 3, 4, 5] and s.halt is False
    for bad in ({"target": "not-an-accession"}, {"reference": "XX"}, {"layers": [7]},
                {"seeds": -1}, {"ph": 20}):  # fmt: skip
        with pytest.raises(SettingsError):
            parse_settings(bad)


def test_skeleton_maps_task_tools_ligand_and_seeds() -> None:
    plan = _trypsin()
    m = plan.manifest
    assert m is not None
    assert (plan.pah_task, plan.ui_task, plan.tools, plan.executor) == (
        "ligand_pose", "ligand_pose", ("boltz2", "gnina"), "boltz2",
    )  # fmt: skip
    assert m["proteins"] == [{"id": "trypsin", "uniprot": "P00760", "pdb_id": "3PTB"}]
    assert m["ligands"] == [
        {"id": "benzamidine", "smiles": "NC(=N)c1ccccc1", "ccd": "BEN", "pubchem_cid": 2332}
    ]
    assert m["model"]["executor"] == "boltz2" and m["model"]["seeds"] == [0, 1, 2, 3, 4]
    assert m["model"]["version"] == "2.2.1"  # configs/runtimes.yaml pin, noted
    assert "checkpoint" not in m["model"]
    assert m["receptor"] == {"pdb_id": "3PTB", "chains": []} and m["ph"] == 7.4
    assert any("configs/runtimes.yaml" in n for n in plan.notes)
    Manifest.model_validate(m)
    assert plan.name == "Trypsin · ligand pose"


def test_task_ids_and_tool_aliases() -> None:
    assert _plan(task="pose_known_pocket", target="P00760", tools=["gnina"]).pah_task == (
        "ligand_pose"
    )
    mono = _plan(task="monomer", target="P69905", tools=["af3", "afdb"], ligand="CCO")
    assert mono.pah_task == "monomer_structure"
    assert mono.tools == ("alphafold3", "afdb") and mono.lookups == ("afdb",)
    assert mono.manifest is not None and "ligands" not in mono.manifest
    assert any("ligand ignored" in n for n in mono.notes)
    default = _plan(task="known_complex", target="P01116", partner="P04049", reference="6VJJ")
    assert default.tools == ("boltz2", "protenix")


def test_unknown_values_are_refused() -> None:
    with pytest.raises(SettingsError, match="unknown tool id"):
        _plan(target="P00760", tools=["nosuchtool"])
    with pytest.raises(SettingsError, match="is not an executor"):
        _plan(target="P00760", tools=["afdb", "boltz2"])
    with pytest.raises(SettingsError, match="unknown task"):
        _plan(task="nosuchtask", target="P00760")
    with pytest.raises(SettingsError, match="target"):
        _plan(task="ligand_pose")
    with pytest.raises(SettingsError, match="unknown profile"):
        _plan(target="P00760", profile="nowhere")
    with pytest.raises(SettingsError, match="not a manifest under"):
        _plan(manifest="../pyproject.toml")


def test_profile_is_recorded() -> None:
    assert _plan(target="P00760").profile == "local"
    plan = _plan(target="P00760", profile="modal")
    assert plan.profile == "modal" and any("profile modal recorded" in n for n in plan.notes)


def test_example_manifest_runs_as_is() -> None:
    plan = _plan(manifest="examples/3ptb_ligand_pose/manifest.yaml", tools=["gnina"])
    assert plan.manifest is None
    assert plan.manifest_path == (EXAMPLES / "3ptb_ligand_pose/manifest.yaml").resolve()
    assert plan.tools == ("boltz2", "gnina") and plan.seeds == 5
    assert _plan(manifest="3ptb_ligand_pose").manifest_path == plan.manifest_path


def test_complete_manifest_resolves_chain_and_sequence(tmp_path: Path) -> None:
    sources = Sources(CachedHttp(FakeWeb().client(), ContentCache(tmp_path / "c")))
    notes: list[str] = []
    plan = _trypsin()
    assert plan.manifest is not None
    built = complete_manifest(plan.manifest, sources, notes.append)
    protein = built["proteins"][0]
    example = load_manifest(EXAMPLES / "3ptb_ligand_pose/manifest.yaml").proteins[0]
    assert protein["chain"] == "A" and built["receptor"]["chains"] == ["A"]
    assert protein["sequence"] == example.sequence  # UniProt 24-246, the SIFTS range of chain A
    assert any("via SIFTS" in n for n in notes) and any("residues 24-246" in n for n in notes)
    assert "chain" not in plan.manifest["proteins"][0]  # skeleton unchanged


def test_failed_lookups_are_noted_not_filled(tmp_path: Path) -> None:
    offline = Sources(CachedHttp(httpx.Client(), ContentCache(tmp_path / "c"), offline=True))
    notes: list[str] = []
    plan = _trypsin()
    assert plan.manifest is not None
    built = complete_manifest(plan.manifest, offline, notes.append)
    protein = built["proteins"][0]
    assert protein["chain"] == "A" and "sequence" not in protein
    assert any("chain A assumed" in n for n in notes)
    assert any("sequence for P00760 not set" in n and "offline_miss" in n for n in notes)


def test_run_settings_accept_camel_case() -> None:
    s = RunSettings.model_validate({"task": "ligand_pose", "target": "P00760", "halt": True})
    assert s.halt is True and s.model_dump(by_alias=True)["target"] == "P00760"
