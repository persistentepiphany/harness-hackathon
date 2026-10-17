"""Markdown reports with the structure of the HTML report: verdict, meta table, layers with key
figures, stats tables and checks, then provenance and files. Values only; no commentary.

The run report reads the `UiRunRecord` (pah.api.adapter) for everything the HTML shows, and the
`RunReport` for the file list and limitations, so the two formats cannot disagree.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from itertools import count
from typing import Any

from pah.report import fmt
from pah.report.model import BatchReport, FigureEntry, RunReport
from pah.report.view import Block, Card, Cell, controls_table, stats_blocks

GATE_ORDER = ("pass", "warn", "stop", "skip")
NA = "n/a"
OUTCOME_LABEL = {
    "supported": "Supported",
    "narrowed": "Narrowed",
    "refused": "Refused",
    "incomplete": "Incomplete",
}


def _cell(value: object) -> str:
    text = NA if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _table(header: Sequence[str], rows: Iterable[Sequence[object]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return lines


def _counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{counts.get(g, 0)} {g}" for g in GATE_ORDER)


def _code(value: object) -> str | None:
    return None if value is None or value == "" else f"`{value}`"


def _figures(figures: Sequence[FigureEntry], numbers: Iterable[int]) -> list[str]:
    lines: list[str] = []
    for f, n in zip(figures, numbers, strict=False):
        lines += [f"![{f.alt}]({f.path})", "", f"Fig. {n} · {f.caption}"]
        extras = []
        if f.data_path:
            extras.append(f"data [{f.data_path}]({f.data_path})")
        if f.session_path:
            extras.append(f"PyMOL session [{f.session_path}]({f.session_path})")
        if extras:
            lines.append(f"Files: {'; '.join(extras)}.")
        lines.append("")
    return lines


def _cell_text(c: Cell) -> str | None:
    if c.text is None:
        return None
    return f"{c.text} ({c.sub})" if c.sub else c.text


def _block(b: Block) -> list[str]:
    if isinstance(b, Card):
        return [
            f"#### {b.title}",
            "",
            *_table(["Field", "Value"], ((k, _cell_text(v)) for k, v in b.rows)),
            "",
        ]
    head = f"#### {b.title}" + (f" · {b.summary}" if b.summary else "")
    rows = [[_cell_text(c) for c in r.cells] for r in b.rows]
    if b.footer:
        rows.append([_cell_text(c) for c in b.footer.cells])
    lines = [head, "", *_table(list(b.columns), rows), ""]
    if b.caption:
        lines += [b.caption, ""]
    return lines


def _checks(checks: Sequence[Mapping[str, Any]]) -> list[str]:
    def evidence(c: Mapping[str, Any]) -> str | None:
        if c.get("result") == "pending":
            return None
        if c.get("skipReason") == "unknown_check":
            return "not implemented"
        ev = c.get("evidence") or c.get("message")
        reason = c.get("skipReason")
        return f"{ev} · {str(reason).replace('_', ' ')}" if reason else ev

    def ident(c: Mapping[str, Any]) -> str:
        ms = fmt.duration(c.get("ms"))
        return f"`{c['id']}`" + (f" · {ms}" if ms else "")

    return _table(
        ["Check", "Result", "Measured cmp threshold", "Evidence", "Id · time"],
        ((c["name"], c["result"], _code(fmt.compare(c)), evidence(c), ident(c)) for c in checks),
    )


def _layer(
    layer: Mapping[str, Any],
    stats: Mapping[str, Any],
    figures: Sequence[FigureEntry],
    numbers: Iterable[int],
) -> list[str]:
    i = layer["i"]
    lines = [f"## L{i} {layer['name']}", "", f"{layer.get('question', '')}", ""]
    if layer.get("status") == "not_run":
        return [*lines, "Status: not run.", ""]
    dur = fmt.duration(layer.get("durationMs"))
    lines += [
        f"Status: {layer.get('status')}. Checks: {fmt.counts_text(layer.get('counts', {}))}"
        + (f". Time: {dur}." if dur else "."),
        "",
    ]
    if layer.get("figures"):
        lines += ["#### Key figures", "", *_table(["Figure", "Value"], layer["figures"]), ""]
    for b in stats_blocks(stats, i):
        lines += _block(b)
    lines += _figures(figures, numbers)
    if layer.get("checks"):
        lines += ["#### Checks", "", *_checks(layer["checks"]), ""]
    return lines


def _meta(ui: Mapping[str, Any], report: RunReport) -> list[str]:
    inputs = ui.get("inputs") or {}
    tools = ", ".join(
        f"{t['name']}"
        + (f" {t['version']}" if t.get("version") else "")
        + (f" ({t['family']})" if t.get("family") else "")
        for t in ui.get("tools", [])
    )
    finished = report.finished_at.isoformat(timespec="seconds") if report.finished_at else None
    rows: list[tuple[str, object]] = [
        ("Task", f"{ui.get('taskName')} (`{report.task}`)"),
        ("Tools", tools or None),
        ("Target", _code(inputs.get("target"))),
        ("Partner", _code(inputs.get("partner"))),
        ("Ligand", _code(inputs.get("ligand"))),
        ("Reference", _code(inputs.get("reference"))),
        ("pH", fmt.number(inputs.get("ph"))),
        ("Seeds", fmt.number(inputs.get("seeds"))),
        ("Layers run", ", ".join(map(str, report.layers))),
        ("Run", f"`{report.run_id}`"),
        ("Created", fmt.when(ui.get("createdAt"))),
        ("Finished", fmt.when(finished)),
        ("pah version", report.pah_version),
        ("Report schema", report.schema_version),
    ]
    if not inputs.get("partner"):
        rows = [r for r in rows if r[0] != "Partner"]
    return [*_table(["Field", "Value"], rows), ""]


def _layers_table(ui: Mapping[str, Any]) -> list[str]:
    from pah.api.adapter import worst

    def row(layer: Mapping[str, Any]) -> list[object]:
        c = layer.get("counts") or {}
        run = layer.get("status") != "not_run"
        result = worst(x["result"] for x in layer.get("checks", [])) if run else None
        return [
            f"L{layer['i']} {layer['name']}",
            str(layer.get("status")).replace("_", " "),
            result,
            *(c.get(g) if run else None for g in GATE_ORDER),
            fmt.duration(layer.get("durationMs")),
        ]

    header = ["Layer", "Status", "Result", *GATE_ORDER, "Time"]
    return [*_table(header, (row(x) for x in ui.get("layers", []))), ""]


def _provenance(ui: Mapping[str, Any], report: RunReport) -> list[str]:
    sources = ui.get("sources") or []
    cached = sum(1 for s in sources if s.get("cached") is True)
    network = sum(1 for s in sources if s.get("cached") is False)
    lines = [
        "## Provenance",
        "",
        f"{len(sources)} objects · {cached} cached · {network} network.",
        "",
    ]
    used = {p.sha256: p.used_by for p in report.provenance}
    lines += _table(
        ["Source", "Accession", "Release", "SHA-256", "Retrieved", "Bytes", "Cache", "Used by"],
        (
            (
                s.get("source"), s.get("accession"), s.get("release"),
                _code(fmt.sha12(s.get("sha256"))),
                fmt.when(s.get("retrievedAt")), s.get("sizeBytes"),
                {True: "hit", False: "miss"}.get(bool(s["cached"])) if "cached" in s else None,
                ", ".join(used.get(str(s.get("sha256")), ())) or None,
            )
            for s in sources
        ),
    )  # fmt: skip
    lines.append("")
    if report.graph:
        lines += [
            "Provenance graph: " + ", ".join(f"[{k}]({v})" for k, v in report.graph.items()) + ".",
            "",
        ]
    return lines


def _thresholds(ui: Mapping[str, Any]) -> list[str]:
    rows = [
        (f"`{c['id']}`", t["name"], f"{t['comparator']} {fmt.number(t['value'])}", t["origin"],
         t["evidenceLevel"])
        for layer in ui.get("layers", [])
        for c in layer.get("checks", [])
        for t in c.get("thresholds") or []
    ]  # fmt: skip
    if not rows:
        return []
    return [
        "## Thresholds",
        "",
        *_table(["Check", "Threshold", "Value", "Origin", "Evidence level"], rows),
        "",
    ]


def _renders(report: RunReport) -> list[str]:
    renders = [f for f in report.figures if f.kind == "render"]
    if not renders:
        return []
    lines = ["## Structures", "", f"{len(renders)} PyMOL renders.", ""]
    for f in renders:
        session = f" PyMOL session: [{f.session_path}]({f.session_path})." if f.session_path else ""
        lines += [f"![{f.alt}]({f.path})", "", f"{f.caption}{session}", ""]
    return lines


def run_markdown(report: RunReport, ui: Mapping[str, Any]) -> str:
    v = ui.get("verdict") or {}
    outcome = str(v.get("outcome", "incomplete"))
    numbers = count(1)
    plots = [f for f in report.figures if f.kind != "render"]
    stats = ui.get("stats") or {}
    lines = [
        f"# Run report · {report.task_title}",
        "",
        f"Prediction assurance · run `{report.run_id}` · {fmt.when(ui.get('createdAt')) or NA}",
        "",
        f'**{OUTCOME_LABEL.get(outcome, outcome)}** for the claim "{report.claim}".',
        "",
        v.get("statement", ""),
        "",
    ]
    for label, key in (("Stops", "stops"), ("Warnings", "warnings")):
        if v.get(key):
            lines += [f"{label}: {', '.join(f'`{c}`' for c in v[key])}.", ""]
    if v.get("incomplete"):
        lines += [f"Not verified: {len(v['incomplete'])} checks.", ""]
    lines += _meta(ui, report)
    lines += ["## Layers", "", *_layers_table(ui)]
    top = [f for f in plots if f.layer is None]
    if top:
        lines += ["## Figures", "", *_figures(top, numbers)]
    lines += _renders(report)
    for layer in ui.get("layers", []):
        lines += _layer(layer, stats, [f for f in plots if f.layer == layer["i"]], numbers)
    controls = controls_table(ui.get("controls") or [])
    if controls:
        lines += ["## Controls", "", *_block(controls)[2:]]
    if report.render_errors:
        lines += ["Render and figure errors:", "", *[f"- {e}" for e in report.render_errors], ""]
    lines += _provenance(ui, report)
    lines += _thresholds(ui)
    if report.tool_versions:
        versions = ", ".join(f"{k} {v}" for k, v in sorted(report.tool_versions.items()))
        lines += [f"Tool versions: {versions}.", ""]
    lines += ["## Limitations", "", *[f"- {x}" for x in report.limitations], ""]
    lines += ["## Files", ""]
    lines += _table(
        ["Path", "Kind", "Bytes", "SHA-256"],
        ((a.path, a.kind.value, a.size_bytes, f"`{a.sha256[:12]}`") for a in report.artifacts),
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
        lines += ["## Figures", "", *_figures(report.figures, count(1))]
    lines += ["## Limitations", "", *[f"- {x}" for x in report.limitations], ""]
    return "\n".join(lines) + "\n"
