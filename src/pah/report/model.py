"""Report models. `report.json` serialises these; Markdown and any frontend read the same data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pah.core.models import Artifact, Measurement, Threshold, ToolRef
from pah.core.policy import Verdict

REPORT_SCHEMA_VERSION = "1"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class FigureEntry(_Model):
    id: str
    kind: str = Field(description="figure | render")
    path: str
    caption: str
    alt: str
    data_path: str | None = None
    session_path: str | None = None


class FindingRow(_Model):
    check_id: str
    title: str
    layer: int
    gate: str
    message: str
    measurements: tuple[Measurement, ...] = ()
    thresholds: tuple[Threshold, ...] = ()
    skip_reason: str | None = None
    duration_s: float | None = None
    tool: ToolRef | None = None
    sources_used: tuple[str, ...] = ()


class LayerSection(_Model):
    layer: int
    name: str
    counts: dict[str, int]
    findings: tuple[FindingRow, ...]


class ProvenanceRow(_Model):
    id: str
    source: str
    accession: str
    release: str | None
    retrieved_at: datetime
    size_bytes: int
    sha256: str
    url: str
    cache: str | None
    used_by: tuple[str, ...] = ()


class InputSummary(_Model):
    proteins: tuple[dict[str, Any], ...] = ()
    ligands: tuple[dict[str, Any], ...] = ()
    receptor: dict[str, Any] | None = None
    model: dict[str, Any] | None = None


class RunReport(_Model):
    schema_version: str = REPORT_SCHEMA_VERSION
    run_id: str
    task: str
    task_title: str
    claim: str
    layers: tuple[int, ...]
    layers_not_run: tuple[int, ...]
    started_at: datetime
    finished_at: datetime | None
    pah_version: str
    verdict: Verdict
    counts: dict[str, int]
    inputs: InputSummary
    sections: tuple[LayerSection, ...]
    provenance: tuple[ProvenanceRow, ...]
    tool_versions: dict[str, str]
    artifacts: tuple[Artifact, ...]
    figures: tuple[FigureEntry, ...]
    graph: dict[str, str]
    render_errors: tuple[str, ...] = ()
    limitations: tuple[str, ...]


class BatchTargetRow(_Model):
    name: str
    manifest: str
    run_id: str | None
    task: str | None
    verdict: str | None
    counts: dict[str, int] = Field(default_factory=dict)
    report_path: str | None = None
    error: str | None = None


class CheckSummary(_Model):
    check_id: str
    title: str
    layer: int
    counts: dict[str, int]
    targets_stop: tuple[str, ...] = ()
    targets_warn: tuple[str, ...] = ()


class BatchReport(_Model):
    schema_version: str = REPORT_SCHEMA_VERSION
    batch_id: str
    name: str
    started_at: datetime
    finished_at: datetime | None
    pah_version: str
    targets: tuple[BatchTargetRow, ...]
    checks: tuple[str, ...]
    matrix: dict[str, dict[str, str]] = Field(description="target -> check -> gate")
    check_summary: tuple[CheckSummary, ...]
    verdict_counts: dict[str, int]
    figures: tuple[FigureEntry, ...]
    limitations: tuple[str, ...]
