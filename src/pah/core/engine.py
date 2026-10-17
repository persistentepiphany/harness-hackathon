"""Runs a task's checks layer by layer, streaming each finding and writing it at once."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import time
from collections import Counter
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from pah import __version__
from pah.core.check import CHECKS, CheckContext, SkipReason
from pah.core.events import EventBus
from pah.core.models import EventKind, Finding, Gate, Layer, Provenance, utcnow
from pah.core.policy import Verdict, decide
from pah.core.task import PRE_RUN_LAYERS

LAYER_NAMES = {
    Layer.PROVENANCE: "provenance",
    Layer.INTEGRITY: "input integrity",
    Layer.ADEQUACY: "input adequacy",
    Layer.APPLICABILITY: "applicability",
    Layer.VALIDITY: "output validity",
    Layer.SUPPORT: "output support",
}


class RunRecord(BaseModel):
    """Machine-readable record every report is generated from."""

    run_id: str
    task: str
    claim: str
    layers: tuple[int, ...]
    manifest: dict[str, Any]
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    pah_version: str = __version__
    tool_versions: dict[str, str] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    verdict: Verdict | None = None


def _module_version(module: str) -> str | None:
    root = module.split(".")[0]
    for dist in (root, root.replace("_", "-")):
        try:
            return importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def _missing_modules(modules: tuple[str, ...]) -> list[str]:
    missing = []
    for m in modules:
        try:
            if importlib.util.find_spec(m) is None:
                missing.append(m)
        except (ImportError, ValueError):
            missing.append(m)
    return missing


class Engine:
    def __init__(self, bus: EventBus, ctx: CheckContext, *, halt_on_stop: bool = True) -> None:
        self._bus = bus
        self._ctx = ctx
        self._halt_on_stop = halt_on_stop

    def run(self, layers: tuple[int, ...]) -> RunRecord:
        ctx = self._ctx
        task = ctx.task
        claim = ctx.manifest.claim or task.claim
        record = RunRecord(
            run_id=self._bus.run_id,
            task=task.id,
            claim=claim,
            layers=layers,
            manifest=ctx.manifest.model_dump(mode="json"),
        )
        ctx.run_dir.mkdir(parents=True, exist_ok=True)
        self._bus.emit(
            EventKind.RUN_START,
            "run",
            f"task={task.id} layers={','.join(map(str, layers))} claim={claim!r}",
            task=task.id,
            layers=list(layers),
        )
        halted_by: str | None = None
        for layer in layers:
            ids = task.layers.get(layer, ())
            name = LAYER_NAMES.get(Layer(layer), str(layer))
            stage = f"L{layer}"
            self._bus.emit(EventKind.STAGE_START, stage, f"{name}: {len(ids)} checks")
            layer_findings: list[Finding] = []
            for cid in ids:
                if halted_by:
                    finding = _skipped(
                        cid, layer, SkipReason.UPSTREAM_STOP, f"halted by {halted_by}"
                    )
                else:
                    finding = self._run_check(cid, layer)
                finding = self._escalate(finding)
                layer_findings.append(finding)
                record.findings.append(finding)
                self._write(finding)
                self._emit_finding(stage, finding)
            counts = Counter(f.gate.value for f in layer_findings)
            self._bus.emit(
                EventKind.STAGE_END,
                stage,
                f"{name}: " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())),
                counts=dict(counts),
            )
            stops = [f.check_id for f in layer_findings if f.gate is Gate.STOP]
            if stops and self._halt_on_stop and layer in PRE_RUN_LAYERS and not halted_by:
                halted_by = stops[0]
        record.provenance = list(ctx.provenance)
        record.tool_versions = self._tool_versions(record.findings)
        scope = f"layers {','.join(map(str, layers))}"
        record.verdict = decide(claim, scope, record.findings)
        record.finished_at = utcnow()
        self._write_record(record)
        v = record.verdict
        self._bus.emit(
            EventKind.RUN_END,
            "run",
            f"verdict={v.outcome.value} stops={len(v.stops)} warnings={len(v.warnings)} "
            f"incomplete={len(v.incomplete)}",
            verdict=v.model_dump(mode="json"),
        )
        return record

    def _run_check(self, cid: str, layer: int) -> Finding:
        cls = CHECKS.get(cid)
        if cls is None:
            return _skipped(cid, layer, SkipReason.UNKNOWN_CHECK, "check not registered")
        check = cls()
        missing = _missing_modules(cls.requires_modules)
        if missing:
            return check.skip(SkipReason.TOOL_MISSING, f"missing modules: {', '.join(missing)}")
        reason = check.applies(self._ctx)
        if reason:
            return check.skip(SkipReason.NOT_APPLICABLE, reason)
        started = time.perf_counter()
        try:
            finding = check.run(self._ctx)
        except Exception as exc:  # a check bug is recorded, never fatal to the run
            finding = check.skip(SkipReason.ERROR, f"{type(exc).__name__}: {exc}")
        return finding.model_copy(update={"duration_s": round(time.perf_counter() - started, 3)})

    def _escalate(self, finding: Finding) -> Finding:
        if finding.gate is Gate.WARN and finding.check_id in self._ctx.task.escalate:
            evidence = {**finding.evidence, "escalated_by_task": self._ctx.task.id}
            return finding.model_copy(update={"gate": Gate.STOP, "evidence": evidence})
        return finding

    def _emit_finding(self, stage: str, f: Finding) -> None:
        values = ", ".join(f"{m.name}={m.value}{m.unit or ''}" for m in f.measurements[:6])
        tail = f" [{values}]" if values else ""
        self._bus.emit(
            EventKind.FINDING,
            stage,
            f"{f.check_id}: {f.message}{tail}",
            gate=f.gate.value,
            finding=f.model_dump(mode="json"),
        )

    def _write(self, f: Finding) -> None:
        path = self._ctx.run_dir / "findings" / f"L{int(f.layer)}_{f.check_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f.model_dump_json(indent=2))

    def _write_record(self, record: RunRecord) -> None:
        run_dir = self._ctx.run_dir
        (run_dir / "record.json").write_text(record.model_dump_json(indent=2))
        prov = [p.model_dump(mode="json") for p in record.provenance]
        (run_dir / "provenance.json").write_text(json.dumps(prov, indent=2))

    def _tool_versions(self, findings: list[Finding]) -> dict[str, str]:
        versions: dict[str, str] = {}
        for f in findings:
            cls = CHECKS.get(f.check_id)
            for m in cls.requires_modules if cls else ():
                v = _module_version(m)
                if v:
                    versions[m.split(".")[0]] = v
            if f.tool and f.tool.version:
                versions[f.tool.name] = f.tool.version
        return versions


def _skipped(cid: str, layer: int, reason: SkipReason, message: str) -> Finding:
    return Finding(
        check_id=cid,
        layer=Layer(layer),
        gate=Gate.SKIP,
        message=message,
        evidence={"skip_reason": reason.value},
    )
