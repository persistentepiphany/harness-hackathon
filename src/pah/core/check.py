"""Check base class, shared context and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, TypeVar

from pah.core.manifest import Manifest
from pah.core.models import (
    Finding,
    Gate,
    Layer,
    Measurement,
    Provenance,
    Threshold,
    ToolRef,
)
from pah.core.task import TaskSpec
from pah.sources import Sources


class SkipReason(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    TOOL_MISSING = "tool_missing"
    ERROR = "error"
    UPSTREAM_STOP = "upstream_stop"
    UNKNOWN_CHECK = "unknown_check"


INCOMPLETE_REASONS = frozenset(
    {SkipReason.TOOL_MISSING, SkipReason.ERROR, SkipReason.UNKNOWN_CHECK}
)


@dataclass
class CheckContext:
    """Everything a check may read. Checks share resolved records through `state`."""

    manifest: Manifest
    task: TaskSpec
    sources: Sources
    run_dir: Path
    state: dict[str, Any] = field(default_factory=dict)
    provenance: list[Provenance] = field(default_factory=list)

    def record(self, *items: Provenance) -> None:
        for p in items:
            if all(
                (q.sha256, q.url, q.accession) != (p.sha256, p.url, p.accession)
                for q in self.provenance
            ):
                self.provenance.append(p)

    def artifact_path(self, name: str) -> Path:
        path = self.run_dir / "artifacts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def memo(self, key: str, fn: Callable[[], Any]) -> Any:
        """Computes a shared value once per run (for example a parsed structure)."""
        if key not in self.state:
            self.state[key] = fn()
        return self.state[key]


class Check(ABC):
    id: ClassVar[str]
    layer: ClassVar[Layer]
    title: ClassVar[str]
    requires_modules: ClassVar[tuple[str, ...]] = ()

    def applies(self, ctx: CheckContext) -> str | None:
        """None when the check applies; otherwise the reason it does not."""
        return None

    @abstractmethod
    def run(self, ctx: CheckContext) -> Finding: ...

    def finding(
        self,
        gate: Gate,
        message: str,
        *,
        measurements: dict[str, float | int | str | bool | None] | None = None,
        units: dict[str, str] | None = None,
        thresholds: tuple[Threshold, ...] = (),
        evidence: dict[str, Any] | None = None,
        tool: ToolRef | None = None,
        artifacts: tuple[str, ...] = (),
    ) -> Finding:
        units = units or {}
        return Finding(
            check_id=self.id,
            layer=self.layer,
            gate=gate,
            message=message,
            measurements=tuple(
                Measurement(name=k, value=v, unit=units.get(k))
                for k, v in (measurements or {}).items()
            ),
            thresholds=thresholds,
            evidence=evidence or {},
            tool=tool,
            artifacts=artifacts,
        )

    def skip(self, reason: SkipReason, message: str, **evidence: Any) -> Finding:
        return self.finding(Gate.SKIP, message, evidence={"skip_reason": reason.value, **evidence})


CHECKS: dict[str, type[Check]] = {}
C = TypeVar("C", bound=type[Check])


def register(cls: C) -> C:
    if cls.id in CHECKS and CHECKS[cls.id] is not cls:
        raise ValueError(f"duplicate check id {cls.id}")
    CHECKS[cls.id] = cls
    return cls
