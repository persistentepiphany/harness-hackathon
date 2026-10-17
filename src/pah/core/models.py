"""Data models shared by every layer, interface and report."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class Gate(StrEnum):
    """Outcome of a single check."""

    PASS = "pass"
    WARN = "warn"
    STOP = "stop"
    SKIP = "skip"


class Layer(IntEnum):
    PROVENANCE = 0
    INTEGRITY = 1
    ADEQUACY = 2
    APPLICABILITY = 3
    VALIDITY = 4
    SUPPORT = 5


class EvidenceLevel(StrEnum):
    """Strength of the evidence behind a threshold or failure mode."""

    REPRODUCED = "reproduced"
    PUBLISHED = "published"
    SUSPECTED = "suspected"
    UNCALIBRATED = "uncalibrated"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolRef(_Frozen):
    name: str
    version: str | None = None


class Threshold(_Frozen):
    name: str
    value: float | int | str | bool
    comparator: str = Field(description="One of <, <=, >, >=, ==, !=, in")
    origin: str = Field(description="Citation or calibration run the value comes from")
    evidence_level: EvidenceLevel = EvidenceLevel.UNCALIBRATED
    measurement: str | None = Field(
        default=None,
        description="Name of the measurement compared with this threshold, when it differs "
        "from the threshold name",
    )


class Measurement(_Frozen):
    name: str
    value: float | int | str | bool | None
    unit: str | None = None


class Provenance(_Frozen):
    """Where a payload came from, down to the exact bytes."""

    source_id: str
    accession: str
    url: str
    sha256: str
    size_bytes: int
    retrieved_at: datetime = Field(default_factory=utcnow)
    release: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


class Finding(_Frozen):
    """Result of one check, with the values and thresholds that produced the gate."""

    check_id: str
    layer: Layer
    gate: Gate
    message: str
    measurements: tuple[Measurement, ...] = ()
    thresholds: tuple[Threshold, ...] = ()
    evidence: dict[str, Any] = Field(default_factory=dict)
    artifacts: tuple[str, ...] = ()
    tool: ToolRef | None = None
    duration_s: float | None = None


class EventKind(StrEnum):
    RUN_START = "run_start"
    STAGE_START = "stage_start"
    PROGRESS = "progress"
    RESULT = "result"
    FINDING = "finding"
    ARTIFACT = "artifact"
    STAGE_END = "stage_end"
    RUN_END = "run_end"
    LOG = "log"


class Event(_Frozen):
    """One unit of streamed output. Sinks render or forward events as they arrive."""

    run_id: str
    seq: int
    kind: EventKind
    stage: str
    message: str
    ts: datetime = Field(default_factory=utcnow)
    data: dict[str, Any] = Field(default_factory=dict)


def provenance_id(p: Provenance) -> str:
    """Stable short identifier for a source record within a run."""
    return f"{p.source_id}:{p.accession}:{p.sha256[:12]}"


class ArtifactKind(StrEnum):
    INPUT_STRUCTURE = "input_structure"
    INPUT_LIGAND = "input_ligand"
    INPUT_MSA = "input_msa"
    SOURCE_STRUCTURE = "source_structure"
    PREDICTION_STRUCTURE = "prediction_structure"
    RENDER = "render"
    SESSION = "session"
    FIGURE = "figure"
    DATA = "data"
    GRAPH = "graph"
    REPORT = "report"


class Artifact(_Frozen):
    """A file used or produced by a run. Paths inside the run directory are relative to it."""

    path: str
    kind: ArtifactKind
    sha256: str
    size_bytes: int
    label: str = ""
    derived_from: tuple[str, ...] = ()
