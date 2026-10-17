import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "script", ["scripts/setup_env.sh", "deploy/csf3/env.sh", "deploy/csf3/doctor.sbatch"]
)
def test_shell_syntax(script: str) -> None:
    subprocess.run(["bash", "-n", str(ROOT / script)], check=True)


def test_sbatch_runs_csf3_profile() -> None:
    text = (ROOT / "deploy/csf3/doctor.sbatch").read_text()
    assert "#SBATCH --job-name=pah-doctor" in text
    assert "pah doctor --profile csf3" in text


def test_modal_app_definition() -> None:
    pytest.importorskip("modal")
    spec = importlib.util.spec_from_file_location("doctor_app", ROOT / "deploy/modal/doctor_app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.app.name == "pah-doctor"
    reqs = module._pip_requirements()
    assert any(r.startswith("posebusters") for r in reqs)
    assert any(r.startswith("pymol-open-source-whl") for r in reqs)
