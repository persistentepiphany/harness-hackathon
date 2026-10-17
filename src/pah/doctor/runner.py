"""Runs probes category by category and streams each result as it completes."""

from __future__ import annotations

import platform
import socket
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from pah import __version__
from pah.core.events import EventBus
from pah.core.models import EventKind, utcnow
from pah.doctor.probes import Probe, ProbeResult, ProbeStatus


class HostInfo(BaseModel):
    hostname: str = Field(default_factory=socket.gethostname)
    platform: str = Field(default_factory=platform.platform)
    python: str = Field(default_factory=lambda: sys.version.split()[0])
    pah_version: str = __version__


class DoctorReport(BaseModel):
    run_id: str
    profile: str
    host: HostInfo = Field(default_factory=HostInfo)
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    results: list[ProbeResult] = Field(default_factory=list)

    def counts(self, category: str | None = None) -> dict[str, int]:
        rows = [r for r in self.results if category is None or r.category == category]
        return dict(Counter(r.status.value for r in rows))

    @property
    def ok(self) -> bool:
        return all(r.status in {ProbeStatus.OK, ProbeStatus.MANUAL} for r in self.results)


class Doctor:
    def __init__(self, bus: EventBus, max_workers: int = 16) -> None:
        self._bus = bus
        self._max_workers = max_workers

    def run(self, catalog: dict[str, list[Probe]], profile: str) -> DoctorReport:
        report = DoctorReport(run_id=self._bus.run_id, profile=profile)
        total = sum(len(v) for v in catalog.values())
        self._bus.emit(
            EventKind.RUN_START,
            "doctor",
            f"profile={profile} probes={total} host={report.host.hostname}",
            profile=profile,
            categories=list(catalog),
        )
        for category, probes in catalog.items():
            report.results.extend(self._run_category(category, probes))
            counts = report.counts(category)
            self._bus.emit(
                EventKind.STAGE_END,
                category,
                " ".join(f"{k}={v}" for k, v in sorted(counts.items())),
                counts=counts,
            )
        report.finished_at = utcnow()
        self._bus.emit(
            EventKind.RUN_END,
            "doctor",
            " ".join(f"{k}={v}" for k, v in sorted(report.counts().items())),
            counts=report.counts(),
        )
        return report

    def _run_category(self, category: str, probes: list[Probe]) -> list[ProbeResult]:
        self._bus.emit(EventKind.STAGE_START, category, f"{len(probes)} probes", count=len(probes))
        results: list[ProbeResult] = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(_safe_run, p): p for p in probes}
            for fut in as_completed(futures):
                result = fut.result()
                results.append(result)
                tail = f" [{result.version}]" if result.version else ""
                latency = f" {result.latency_ms:.0f}ms" if result.latency_ms is not None else ""
                self._bus.emit(
                    EventKind.RESULT,
                    category,
                    f"{result.id}: {result.detail}{tail}{latency}",
                    status=result.status.value,
                    result=result.model_dump(mode="json"),
                )
        order = {p.id: i for i, p in enumerate(probes)}
        return sorted(results, key=lambda r: order.get(r.id, 0))


def _safe_run(probe: Probe) -> ProbeResult:
    try:
        return probe.run()
    except Exception as exc:  # a probe bug must not abort the report
        return ProbeResult(
            id=probe.id,
            category=probe.category,
            kind=probe.kind,
            target=probe.target,
            status=ProbeStatus.ERROR,
            detail=f"{type(exc).__name__}: {exc}",
        )


def write_report(report: DoctorReport, out_dir: Path) -> tuple[Path, Path]:
    from pah.doctor.report import render_markdown

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "doctor_report.json"
    md_path = out_dir / "doctor_report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
