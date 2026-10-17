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

    def __call__(self, argv: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result
