import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from pah.config import Profile


@pytest.fixture
def profile(tmp_path: Path) -> Profile:
    return Profile(name="local", backend="local", cache_dir=tmp_path / "c", runs_dir=tmp_path / "r")


def completed(rc: int = 0, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=out, stderr=err)


class FakeRunner:
    def __init__(self, result: subprocess.CompletedProcess[str] | Exception) -> None:
        self.result = result
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: Sequence[str], timeout: float, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        self.env = env
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def clean_run(tmp_path: Path) -> Path:
    """Runs the clean 3PTB example offline against recorded fixtures; returns the run dir."""
    pytest.importorskip("rdkit")
    pytest.importorskip("gemmi")
    import pah.checks  # noqa: F401
    from pah.core.check import CheckContext
    from pah.core.engine import Engine
    from pah.core.events import EventBus
    from pah.core.manifest import load_manifest
    from pah.core.task import load_task
    from pah.sources import CachedHttp, ContentCache, Sources
    from tests.fakeweb import FakeWeb

    manifest = load_manifest(ROOT / "examples/3ptb_ligand_pose/manifest.yaml")
    sources = Sources(CachedHttp(FakeWeb().client(), ContentCache(tmp_path / "cache")))
    run_dir = tmp_path / "run"
    ctx = CheckContext(manifest, load_task(manifest.task), sources, run_dir)
    Engine(EventBus("ligand_pose-test", []), ctx).run((0, 1))
    return run_dir


class FakeRenderer:
    """Writes placeholder PNG and PSE files instead of calling PyMOL."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, list[Path]]] = []

    def render(self, structure: Path, ligands: list[Path], out_stem: Path) -> dict[str, object]:
        self.calls.append((structure, ligands))
        pngs = {}
        for view in ("overview", "pocket"):
            p = Path(f"{out_stem}_{view}.png")
            p.write_bytes(b"\x89PNG fake")
            pngs[view] = str(p)
        pse = Path(f"{out_stem}.pse")
        pse.write_bytes(b"pse")
        return {"pngs": pngs, "pse": str(pse), "organic": ["BEN"], "chains": ["A"]}
