import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    "deploy/csf3/executor.sbatch",
    "deploy/csf3/executor_array.sbatch",
    "deploy/csf3/prepare_executor.sh",
]


@pytest.mark.parametrize("script", SCRIPTS)
def test_shell_syntax(script: str) -> None:
    subprocess.run(["bash", "-n", str(ROOT / script)], check=True)


@pytest.mark.parametrize("script", SCRIPTS[:2])
def test_sbatch_uses_runtimes_on_csf3(script: str) -> None:
    text = (ROOT / script).read_text()
    assert "#SBATCH --gres=gpu:1" in text
    assert "pah runtimes run" in text and "--profile csf3" in text


def _load_modal_app(executor: str, monkeypatch: pytest.MonkeyPatch) -> object:
    pytest.importorskip("modal")
    monkeypatch.setenv("PAH_EXECUTOR", executor)
    name = f"executors_app_{executor}"
    spec = importlib.util.spec_from_file_location(name, ROOT / "deploy/modal/executors_app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_modal_app_native_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_modal_app("vina", monkeypatch)
    assert module.app.name == "pah-vina"  # type: ignore[attr-defined]
    assert module.ROUTE == "native"  # type: ignore[attr-defined]


def test_modal_app_defaults_to_kit_image(monkeypatch: pytest.MonkeyPatch) -> None:
    if not (ROOT / ".tools/accel/boltz2/environment/Dockerfile").is_file():
        pytest.skip("kits checkout absent (pah runtimes kits fetch)")
    module = _load_modal_app("boltz2", monkeypatch)
    assert module.ROUTE == "kit"  # type: ignore[attr-defined]
