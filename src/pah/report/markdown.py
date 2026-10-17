"""Markdown from report models. Values and provenance only; no commentary.

Section order follows the scientific-writing skill: summary, inputs, results, figures,
limitations, record. The text is plain enough to be expanded into prose with that skill.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from pah.report.model import BatchReport, FigureEntry, LayerSection, RunReport

GATE_ORDER = ("pass", "warn", "stop", "skip")


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _table(header: Sequence[str], rows: Iterable[Sequence[object]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return lines


def _counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{counts.get(g, 0)} {g}" for g in GATE_ORDER)


def _measurements(ms: Iterable[object]) -> str:
    parts = []
    for m in ms:
        name, value, unit = m.name, m.value, m.unit  # type: ignore[attr-defined]
        parts.append(f"{name}={value}{unit or ''}")
    return "; ".join(parts)


def _figures(figures: Sequence[FigureEntry], start: int = 1) -> list[str]:
    lines: list[str] = []
    for i, f in enumerate(figures, start=start):
        lines += [f"![{f.alt}]({f.path})", "", f"Figure {i}. {f.caption}"]
        extras = []
        if f.data_path:
            extras.append(f"data: [{f.data_path}]({f.data_path})")
        if f.session_path:
            extras.append(f"PyMOL session: [{f.session_path}]({f.session_path})")
        if extras:
            lines.append(f"Files: {'; '.join(extras)}.")
        lines.append("")
    return lines


def _section(sec: LayerSection) -> list[str]:
    lines = [f"### Layer {sec.layer}: {sec.name}", "", f"Outcomes: {_counts(sec.counts)}.", ""]
    lines += _table(
        ["Check", "Gate", "Result", "Measurements"],
        ((f.check_id, f.gate, f.message, _measurements(f.measurements)) for f in sec.findings),
    )
    return [*lines, ""]


def _thresholds(report: RunReport) -> list[str]:
    rows = [
        (f.check_id, t.name, t.comparator, t.value, t.origin, t.evidence_level.value)
        for sec in report.sections
        for f in sec.findings
        for t in f.thresholds
    ]
    if not rows:
        return []
    return [
        "### Thresholds",
        "",
        *_table(["Check", "Threshold", "Comparator", "Value", "Origin", "Evidence level"], rows),
        "",
    ]


def _inputs(report: RunReport) -> list[str]:
    inp = report.inputs
    lines = ["## Inputs", ""]
    if inp.proteins:
        lines += _table(
            ["Protein", "UniProt", "PDB", "Chain", "Length", "Copies", "Declared mutations", "MSA"],
            (
                (
                    p.get("id"), p.get("uniprot"), p.get("pdb_id"), p.get("chain"),
                    p.get("sequence_length"), p.get("copies", 1),
                    ", ".join(p.get("mutations", []) or []) or "none", p.get("msa", ""),
                )
                for p in inp.proteins
            ),
        )  # fmt: skip
        lines.append("")
    if inp.ligands:
        lines += _table(
            ["Ligand", "SMILES", "CCD", "PubChem CID", "File"],
            (
                (
                    lig.get("id"),
                    lig.get("smiles"),
                    lig.get("ccd"),
                    lig.get("pubchem_cid"),
                    lig.get("file"),
                )
                for lig in inp.ligands
            ),
        )
        lines.append("")
    if inp.receptor:
        r = inp.receptor
        chains = ", ".join(r.get("chains", []) or [])
        lines += [
            f"Receptor: {r.get('pdb_id') or r.get('file')}, chains {chains or 'all'}, "
            f"altloc policy {r.get('altloc_policy') or 'not declared'}.",
            "",
        ]
    if inp.model:
        m = inp.model
        seeds = len(m.get("seeds", []) or [])
        fields = ", ".join(
            f"{k} {m[k]}"
            for k in ("executor", "version", "checkpoint", "database_snapshot")
            if m.get(k)
        )
        lines += [f"Model: {fields}; {seeds} seeds.", ""]
    return lines


def _provenance(report: RunReport) -> list[str]:
    lines = ["## Provenance", ""]
    lines += _table(
        ["Source", "Accession", "Release", "Retrieved (UTC)", "Bytes", "SHA-256", "Used by", "URL"],
        (
            (
                p.source, p.accession, p.release or "not reported",
                p.retrieved_at.strftime("%Y-%m-%d %H:%M:%S"), p.size_bytes, p.sha256[:16],
                ", ".join(p.used_by), p.url,
            )
            for p in report.provenance
        ),
    )  # fmt: skip
    lines.append("")
    if report.graph:
        lines.append(
            "Provenance graph: "
            + ", ".join(f"[{k}]({v})" for k, v in report.graph.items())
            + ". Nodes are source records, files, tools, checks and the verdict."
        )
        lines.append("")
    if report.tool_versions:
        versions = ", ".join(f"{k} {v}" for k, v in sorted(report.tool_versions.items()))
        lines += [f"Tool versions: {versions}.", ""]
    return lines


def run_markdown(report: RunReport) -> str:
    v = report.verdict
    finished = report.finished_at.isoformat(timespec="seconds") if report.finished_at else "n/a"
    lines = [
        f"# Assurance report: {report.task_title}, run {report.run_id}",
        "",
        *_table(
            ["Field", "Value"],
            [
                ("Task", report.task),
                ("Claim", report.claim),
                ("Layers run", ", ".join(map(str, report.layers))),
                ("Verdict", v.outcome.value),
                ("Started (UTC)", report.started_at.isoformat(timespec="seconds")),
                ("Finished (UTC)", finished),
                ("pah version", report.pah_version),
                ("Report schema", report.schema_version),
            ],
        ),
        "",
        "## Summary",
        "",
        f'Verdict for the claim "{report.claim}" over layers '
        f"{', '.join(map(str, report.layers))}: {v.outcome.value}. "
        f"{sum(report.counts.values())} checks: {_counts(report.counts)}.",
        "",
    ]
    findings = {f.check_id: f for s in report.sections for f in s.findings}
    for label, ids in (
        ("Stops", v.stops),
        ("Warnings", v.warnings),
        ("Not verified", v.incomplete),
    ):
        if ids:
            lines.append(f"{label}:")
            lines += [f"- `{cid}`: {findings[cid].message}" for cid in ids if cid in findings]
            lines.append("")
    if v.not_applicable:
        lines += [
            f"Not applicable to these inputs: {', '.join(f'`{c}`' for c in v.not_applicable)}.",
            "",
        ]
    lines += _inputs(report)
    lines += ["## Results by layer", ""]
    for sec in report.sections:
        lines += _section(sec)
    lines += _thresholds(report)
    if report.figures:
        lines += ["## Figures", "", *_figures(report.figures)]
    if report.render_errors:
        lines += ["Render errors:", *[f"- {e}" for e in report.render_errors], ""]
    lines += _provenance(report)
    lines += ["## Limitations", "", *[f"- {x}" for x in report.limitations], ""]
    lines += ["## Files", ""]
    lines += _table(
        ["Path", "Kind", "Bytes", "SHA-256"],
        ((a.path, a.kind.value, a.size_bytes, a.sha256[:16]) for a in report.artifacts),
    )
    return "\n".join(lines) + "\n"


def batch_markdown(report: BatchReport) -> str:
    finished = report.finished_at.isoformat(timespec="seconds") if report.finished_at else "n/a"
    ran = [t for t in report.targets if t.run_id]
    lines = [
        f"# Batch assurance report: {report.name}",
        "",
        *_table(
            ["Field", "Value"],
            [
                ("Batch", report.batch_id),
                ("Targets", len(report.targets)),
                ("Started (UTC)", report.started_at.isoformat(timespec="seconds")),
                ("Finished (UTC)", finished),
                ("pah version", report.pah_version),
                ("Report schema", report.schema_version),
            ],
        ),
        "",
        "## Summary",
        "",
        f"{len(ran)} of {len(report.targets)} targets ran. Verdicts: "
        + ", ".join(f"{n} {k}" for k, n in sorted(report.verdict_counts.items()))
        + ".",
        "",
    ]
    lines += _table(
        ["Target", "Task", "Verdict", "Pass", "Warn", "Stop", "Skip", "Report"],
        (
            (
                t.name, t.task or "", t.verdict or f"not run: {t.error}",
                t.counts.get("pass", 0), t.counts.get("warn", 0), t.counts.get("stop", 0),
                t.counts.get("skip", 0), f"[report]({t.report_path})" if t.report_path else "",
            )
            for t in report.targets
        ),
    )  # fmt: skip
    lines.append("")
    flagged = [c for c in report.check_summary if c.targets_stop or c.targets_warn]
    lines += ["## Checks that stopped or warned", ""]
    if flagged:
        lines += _table(
            ["Check", "Layer", "Stop", "Warn", "Targets with stop", "Targets with warn"],
            (
                (c.check_id, c.layer, c.counts["stop"], c.counts["warn"],
                 ", ".join(c.targets_stop), ", ".join(c.targets_warn))
                for c in flagged
            ),
        )  # fmt: skip
    else:
        lines.append("No check stopped or warned on any target.")
    lines.append("")
    lines += ["## Gate per check", ""]
    targets = [t.name for t in ran]
    lines += _table(
        ["Check", *targets],
        ((c, *(report.matrix.get(t, {}).get(c, "") for t in targets)) for c in report.checks),
    )
    lines.append("")
    if report.figures:
        lines += ["## Figures", "", *_figures(report.figures)]
    lines += ["## Limitations", "", *[f"- {x}" for x in report.limitations], ""]
    return "\n".join(lines) + "\n"
