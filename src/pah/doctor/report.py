"""Markdown rendering of a doctor report."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pah.doctor.runner import DoctorReport


def _cell(text: str | None) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def render_markdown(report: DoctorReport) -> str:
    finished = report.finished_at.isoformat(timespec="seconds") if report.finished_at else "n/a"
    lines = [
        f"# Doctor report `{report.run_id}`",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Profile | {report.profile} |",
        f"| Host | {report.host.hostname} |",
        f"| Platform | {_cell(report.host.platform)} |",
        f"| Python | {report.host.python} |",
        f"| pah | {report.host.pah_version} |",
        f"| Started (UTC) | {report.started_at.isoformat(timespec='seconds')} |",
        f"| Finished (UTC) | {finished} |",
        "",
        "## Summary",
        "",
        "| Category | " + " | ".join(s for s in _statuses(report)) + " |",
        "| --- | " + " | ".join("---" for _ in _statuses(report)) + " |",
    ]
    for category in _categories(report):
        counts = report.counts(category)
        lines.append(
            f"| {category} | " + " | ".join(str(counts.get(s, 0)) for s in _statuses(report)) + " |"
        )
    for category in _categories(report):
        lines += [
            "",
            f"## {category}",
            "",
            "| Probe | Status | Kind | Target | Detail | Version | ms |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for r in (r for r in report.results if r.category == category):
            ms = f"{r.latency_ms:.0f}" if r.latency_ms is not None else ""
            lines.append(
                f"| {r.id} | {r.status.value} | {r.kind} | {_cell(r.target)} | "
                f"{_cell(r.detail)} | {_cell(r.version)} | {ms} |"
            )
    return "\n".join(lines) + "\n"


def _categories(report: DoctorReport) -> list[str]:
    return list(dict.fromkeys(r.category for r in report.results))


def _statuses(report: DoctorReport) -> list[str]:
    return sorted({r.status.value for r in report.results})
