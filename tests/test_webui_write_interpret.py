"""The rule-based interpreter returns what interpretRun() in runs.js returns."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pah.webui.interpret import interpret_request
from tests.conftest import ROOT

RUNS_JS = ROOT / "web/design/prototype/data/runs.js"
# Expected values produced by `node` running interpretRun() from runs.js (tool ids mapped to
# executor ids: af3 -> alphafold3, haddock -> haddock3).
CASES = [
    (
        "Dock imatinib into the ABL1 kinase pocket with Boltz-2 and Gnina, 5 seeds at pH 7.4, "
        "compare against 1IEP",
        "ligand_pose", ["boltz2", "gnina"], "P00519", "", 5, 7.4,
    ),
    (
        "Does KRAS interact with RAF1? Run Boltz-2 and Protenix with decoy partners",
        "virtual_screening", ["boltz2", "protenix"], "P01116", "", 5, 7.4,
    ),
    (
        "Rank the imatinib congeneric series against ABL1 by Boltz-2 affinity, corroborate with "
        "Gnina, 8 seeds",
        "affinity_ranking", ["boltz2", "gnina"], "P00519", "", 8, 7.4,
    ),
    (
        "Screen the erlotinib library against EGFR with Vina and DiffDock-L, property-matched "
        "decoys",
        "virtual_screening", ["vina", "diffdock"], "P00533", "", 5, 7.4,
    ),
    (
        "Protein\u2013protein dock KRAS with RAF1 using pyDock and HADDOCK, compare against 6VJJ",
        "protein_protein_docking", ["pydock", "haddock3"], "P01116", "", 5, 7.4,
    ),
    (
        "Does KRAS bind to RAF1 in a complex with GDP?",
        "interaction_discovery", ["boltz2", "protenix"], "P01116", "P04049", 5, 7.4,
    ),
    (
        "Redock the crystal ligand of HSP90 with vina at ph 6.5",
        "redocking", ["vina"], "P07900", "", 5, 6.5,
    ),
]  # fmt: skip


@pytest.mark.parametrize(("text", "task", "tools", "target", "partner", "seeds", "ph"), CASES)
def test_parity_with_prototype(
    text: str, task: str, tools: list[str], target: str, partner: str, seeds: int, ph: float
) -> None:
    out = interpret_request(text)
    assert (out["task"], out["tools"], out["target"], out["partner"]) == (
        task,
        tools,
        target,
        partner,
    )
    assert (out["seeds"], out["ph"]) == (seeds, ph)
    assert [s["field"] for s in out["steps"]][:3] == ["task", "tools", "target"]
    assert all(set(s) == {"field", "value", "because"} for s in out["steps"])


def test_steps_explain_each_decision() -> None:
    out = interpret_request("Is the imatinib pose in ABL1 valid? Boltz-2 and Gnina, 5 seeds")
    by = {s["field"]: s for s in out["steps"]}
    assert by["task"]["because"] == "matched “pose”"
    assert by["tools"]["because"] == "named in the request"
    assert by["target"]["because"] == "“ABL1 kinase” → UniProt P00519"
    assert by["ligand"]["because"] == "“imatinib” → CCD STI, PubChem 5291"
    assert by["claim"]["value"] == "Pose within stated uncertainty"
    assert out["reference"] == "2HYY"  # human Abl with imatinib; the prototype used mouse 1IEP


def test_defaults_and_explicit_values() -> None:
    out = interpret_request("Blind docking of CC(=O)Oc1ccccc1C(=O)O against Q9Y6K9, 40 seeds")
    assert out["task"] == "blind_docking"
    assert out["tools"] == ["diffdock", "gnina"]  # task default
    assert out["target"] == "Q9Y6K9"
    assert out["ligand"] == "CC(=O)Oc1ccccc1C(=O)O"
    assert out["seeds"] == 20  # clamped as in the prototype
    by = {s["field"]: s["because"] for s in out["steps"]}
    assert by["target"] == "accession given explicitly"
    assert by["ligand"].startswith("SMILES given explicitly")


def test_any_registered_executor_is_recognised() -> None:
    assert interpret_request("monomer structure of P69905 with colabfold")["tools"] == ["colabfold"]
    assert interpret_request("monomer structure of P69905 with AF3")["tools"] == ["alphafold3"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_matches_node_on_sample_prompts(tmp_path: Path) -> None:
    script = tmp_path / "interp.mjs"
    script.write_text(
        "import { readFileSync } from 'node:fs';\n"
        f"const src = readFileSync({json.dumps(str(RUNS_JS))}, 'utf8');\n"
        "const m = await import('data:text/javascript;base64,' + "
        "Buffer.from(src).toString('base64'));\n"
        "console.log(JSON.stringify(m.SAMPLE_PROMPTS.map(p => [p, m.interpretRun(p)])));\n"
    )
    proc = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    alias = {"af3": "alphafold3", "haddock": "haddock3"}
    for prompt, js in json.loads(proc.stdout):
        py = interpret_request(prompt)
        assert py["task"] == js["task"], prompt
        assert py["tools"] == [alias.get(t, t) for t in js["tools"]], prompt
        assert py["target"] == js["target"], prompt
        assert (py["partner"], py["seeds"], py["ph"]) == (js["partner"], js["seeds"], js["ph"])
        assert [s["field"] for s in py["steps"]] == [s["field"] for s in js["steps"]]
