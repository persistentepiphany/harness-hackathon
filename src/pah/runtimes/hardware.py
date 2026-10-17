"""GPU discovery through nvidia-smi. No GPU, or no nvidia-smi, gives an empty list."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

QUERY = "index,name,compute_cap,memory.total,driver_version"


@dataclass(frozen=True)
class Gpu:
    index: int
    name: str
    compute_capability: float
    memory_mib: int
    driver: str

    @property
    def driver_major(self) -> int:
        head = self.driver.split(".", 1)[0]
        return int(head) if head.isdigit() else 0

    def as_dict(self) -> dict[str, str | int | float]:
        return {
            "index": self.index,
            "name": self.name,
            "compute_capability": self.compute_capability,
            "memory_mib": self.memory_mib,
            "driver": self.driver,
        }


def parse_nvidia_smi(text: str) -> list[Gpu]:
    """Parse `nvidia-smi --query-gpu=<QUERY> --format=csv,noheader,nounits` output."""
    gpus: list[Gpu] = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 5 or not parts[0].isdigit():
            continue
        try:
            cc = float(parts[2])
            mem = int(float(parts[3]))
        except ValueError:
            continue
        gpus.append(Gpu(int(parts[0]), parts[1], cc, mem, parts[4]))
    return gpus


Runner = Callable[[list[str]], str]


def _run(argv: list[str]) -> str:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    return proc.stdout if proc.returncode == 0 else ""


def detect_gpus(runner: Runner | None = None) -> list[Gpu]:
    """GPUs visible to this process, in nvidia-smi order."""
    if runner is None:
        if shutil.which("nvidia-smi") is None:
            return []
        runner = _run
    try:
        out = runner(["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"])
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_nvidia_smi(out)
