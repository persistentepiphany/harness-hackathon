"""Builds report models from run records. Pure functions: no I/O, no new assertions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from pah.core.check import CHECKS
from pah.core.engine import LAYER_NAMES, RunRecord
from pah.core.models import Artifact, Finding, Gate, Layer, provenance_id
from pah.report.model import (
    BatchReport,
    BatchTargetRow,
    CheckSummary,
    FigureEntry,
    FindingRow,
    InputSummary,
    LayerSection,
    ProvenanceRow,
    RunReport,
)

GATES = ("pass", "warn", "stop", "skip")

RUN_LIMITATIONS = (
    "The harness establishes when a result should not be trusted. Passing checks are not "
    "evidence that a prediction is correct.",
    "Thresholds marked uncalibrated come from the specification or harness defaults and have "
    "not been recalibrated on the harness benchmark.",
)


def _title(check_id: str) -> str:
    cls = CHECKS.get(check_id)
    return cls.title if cls else check_id


def _counts(findings: Sequence[Finding]) -> dict[str, int]:
    c = Counter(f.gate.value for f in findings)
    return {g: c.get(g, 0) for g in GATES}


def _row(f: Finding, usage: dict[str, list[str]]) -> FindingRow:
    return FindingRow(
        check_id=f.check_id,
        title=_title(f.check_id),
        layer=int(f.layer),
        gate=f.gate.value,
        message=f.message,
        measurements=f.measurements,
        thresholds=f.thresholds,
        skip_reason=f.evidence.get("skip_reason"),
        duration_s=f.duration_s,
        tool=f.tool,
        sources_used=tuple(usage.get(f.check_id, ())),
    )


def _inputs(manifest: dict[str, object]) -> InputSummary:
    def rows(key: str) -> tuple[dict[str, object], ...]:
        value = manifest.get(key) or []
        assert isinstance(value, list)
        out = []
        for item in value:
            assert isinstance(item, dict)
            row = {k: v for k, v in item.items() if v not in (None, [], ())}
            if isinstance(row.get("sequence"), str):
                row["sequence_length"] = len(str(row.pop("sequence")))
            out.append(row)
        return tuple(out)

    receptor = manifest.get("receptor")
    model = manifest.get("model")
    return InputSummary(
        proteins=rows("proteins"),
        ligands=rows("ligands"),
        receptor=receptor if isinstance(receptor, dict) else None,
        model=model if isinstance(model, dict) else None,
    )


def build_run_report(
    record: RunRecord,
    *,
    task_title: str,
    figures: Sequence[FigureEntry] = (),
    graph: dict[str, str] | None = None,
    extra_artifacts: Sequence[Artifact] = (),
    render_errors: Sequence[str] = (),
) -> RunReport:
    if record.verdict is None:
        raise ValueError(f"run {record.run_id} has no verdict; the run did not finish")
    sections = []
    for layer in record.layers:
        fs = [f for f in record.findings if int(f.layer) == layer]
        sections.append(
            LayerSection(
                layer=layer,
                name=LAYER_NAMES.get(Layer(layer), str(layer)),
                counts=_counts(fs),
                findings=tuple(_row(f, record.usage) for f in fs),
            )
        )
    used_by: dict[str, list[str]] = {}
    for check_id, ids in record.usage.items():
        for pid in ids:
            used_by.setdefault(pid, []).append(check_id)
    provenance = tuple(
        ProvenanceRow(
            id=provenance_id(p),
            source=p.source_id,
            accession=p.accession,
            release=p.release,
            retrieved_at=p.retrieved_at,
            size_bytes=p.size_bytes,
            sha256=p.sha256,
            url=p.url,
            cache=p.extra.get("cache"),
            used_by=tuple(used_by.get(provenance_id(p), ())),
        )
        for p in record.provenance
    )
    not_run = tuple(x for x in range(6) if x not in record.layers)
    limitations = (
        f"This report covers layers {', '.join(map(str, record.layers))}."
        + (f" Layers not run: {', '.join(map(str, not_run))}." if not_run else ""),
        *RUN_LIMITATIONS,
    )
    return RunReport(
        run_id=record.run_id,
        task=record.task,
        task_title=task_title,
        claim=record.claim,
        layers=record.layers,
        layers_not_run=not_run,
        started_at=record.started_at,
        finished_at=record.finished_at,
        pah_version=record.pah_version,
        verdict=record.verdict,
        counts=_counts(record.findings),
        inputs=_inputs(record.manifest),
        sections=tuple(sections),
        provenance=provenance,
        tool_versions=record.tool_versions,
        artifacts=(*record.artifacts, *extra_artifacts),
        figures=tuple(figures),
        graph=graph or {},
        render_errors=tuple(render_errors),
        limitations=limitations,
    )


def gate_matrix(records: dict[str, RunRecord]) -> tuple[list[str], dict[str, dict[str, str]]]:
    """Ordered check ids (by layer, first appearance) and target -> check -> gate."""
    order: list[str] = []
    layer_of: dict[str, int] = {}
    for rec in records.values():
        for f in rec.findings:
            if f.check_id not in layer_of:
                layer_of[f.check_id] = int(f.layer)
                order.append(f.check_id)
    first = {c: i for i, c in enumerate(order)}
    order.sort(key=lambda c: (layer_of[c], first[c]))
    matrix = {
        name: {f.check_id: f.gate.value for f in rec.findings} for name, rec in records.items()
    }
    return order, matrix


def build_batch_report(
    *,
    batch_id: str,
    name: str,
    started_at: object,
    finished_at: object,
    pah_version: str,
    targets: Sequence[BatchTargetRow],
    records: dict[str, RunRecord],
    figures: Sequence[FigureEntry] = (),
) -> BatchReport:
    checks, matrix = gate_matrix(records)
    summaries = []
    for cid in checks:
        gates = {t: row[cid] for t, row in matrix.items() if cid in row}
        c = Counter(gates.values())
        layer = next(
            int(f.layer) for r in records.values() for f in r.findings if f.check_id == cid
        )
        summaries.append(
            CheckSummary(
                check_id=cid,
                title=_title(cid),
                layer=layer,
                counts={g: c.get(g, 0) for g in GATES},
                targets_stop=tuple(t for t, g in gates.items() if g == Gate.STOP.value),
                targets_warn=tuple(t for t, g in gates.items() if g == Gate.WARN.value),
            )
        )
    verdicts = Counter(t.verdict or "not_run" for t in targets)
    limitations = (
        "Each target row is the verdict for that target's declared claim over the layers run.",
        *RUN_LIMITATIONS,
    )
    return BatchReport.model_validate(
        {
            "batch_id": batch_id,
            "name": name,
            "started_at": started_at,
            "finished_at": finished_at,
            "pah_version": pah_version,
            "targets": targets,
            "checks": checks,
            "matrix": matrix,
            "check_summary": summaries,
            "verdict_counts": dict(verdicts),
            "figures": figures,
            "limitations": limitations,
        }
    )
