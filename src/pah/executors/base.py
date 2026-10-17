"""Executor output model and parser registry.

A parser reads one tool's output directory (layout in docs/EXECUTORS.md) and returns a
`PredictionSet`: one `Pose` per structure the tool wrote, with the tool's native scores. Every pose
carries a complex structure file, so renders and layer 4 checks work the same for every tool, and,
when a ligand was predicted, an SDF of the ligand alone with bond orders from the declared SMILES.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pah.core.manifest import Manifest, PredictionInput


class Family(StrEnum):
    COFOLDING = "cofolding"
    DOCKING = "docking"


class ParseError(ValueError):
    """The output directory does not match the tool's documented layout."""


@dataclass(frozen=True)
class Pose:
    """One predicted structure.

    `id` is unique within a run, e.g. `boltz2/seed0/sample1`. `seed` is the independent random
    seed when the tool records one; `sample` is the diffusion sample, model index or docking mode
    within that seed; `rank` is the tool's own ranking within the set (0 = best). Scores keep the
    tool's own key names (`confidence_score`, `iptm`, `vina_affinity`, `CNNscore`, ...), so values
    are never relabelled across tools. `plddt` is per residue or token, on a 0 to 100 scale.
    """

    id: str
    executor: str
    family: Family
    structure: Path
    seed: int | None = None
    sample: int = 0
    rank: int = 0
    ligand: Path | None = None
    ligand_id: str | None = None
    scores: Mapping[str, float] = field(default_factory=dict)
    plddt: tuple[float, ...] | None = None
    plddt_residues: tuple[tuple[str, int], ...] | None = None
    pae: Path | None = None
    files: tuple[Path, ...] = ()


@dataclass(frozen=True)
class PredictionSet:
    """All poses one executor produced for one manifest entry."""

    executor: str
    family: Family
    role: str
    source: Path
    poses: tuple[Pose, ...]
    version: str | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)
    issues: tuple[str, ...] = ()

    def ranked(self) -> list[Pose]:
        return sorted(self.poses, key=lambda p: (p.rank, p.seed or 0, p.sample))

    @property
    def seeds(self) -> list[int]:
        return sorted({p.seed for p in self.poses if p.seed is not None})


class Parser(Protocol):
    def __call__(
        self, spec: PredictionInput, manifest: Manifest, workdir: Path
    ) -> PredictionSet: ...


PARSERS: dict[str, Parser] = {}
FAMILIES: dict[str, Family] = {}


def parser(*executor_ids: str, family: Family) -> Callable[[Parser], Parser]:
    """Registers a parser for one or more executor ids from configs/executors.yaml."""

    def wrap(fn: Parser) -> Parser:
        for eid in executor_ids:
            if eid in PARSERS and PARSERS[eid] is not fn:
                raise ValueError(f"duplicate parser for {eid}")
            PARSERS[eid] = fn
            FAMILIES[eid] = family
        return fn

    return wrap


def parse_prediction(spec: PredictionInput, manifest: Manifest, workdir: Path) -> PredictionSet:
    import pah.executors.parsers  # noqa: F401 - registers the parsers

    fn = PARSERS.get(spec.executor)
    if fn is None:
        raise ParseError(f"no parser for executor {spec.executor!r}; known: {sorted(PARSERS)}")
    workdir.mkdir(parents=True, exist_ok=True)
    return fn(spec, manifest, workdir)
