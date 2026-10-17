"""Figures following the scientific-visualization skill: Okabe-Ito colours, hatching and text
labels so gates read without colour, constrained layout, SVG and PNG, data saved as CSV."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pah.core.engine import LAYER_NAMES, RunRecord
from pah.core.models import Layer
from pah.report.model import BatchReport, FigureEntry

GATES = ("pass", "warn", "stop", "skip")
COLOURS = {"pass": "#009E73", "warn": "#E69F00", "stop": "#D55E00", "skip": "#BBBBBB"}
HATCH = {"pass": "", "warn": "//", "stop": "xx", "skip": ".."}
LETTER = {"pass": "P", "warn": "W", "stop": "S", "skip": "-"}
NOT_RUN = "#FFFFFF"


def _plt() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 8, "svg.fonttype": "none", "axes.spines.top": False})
    return plt


def _save(fig, stem: Path) -> tuple[Path, Path]:  # type: ignore[no-untyped-def]
    svg, png = stem.with_suffix(".svg"), stem.with_suffix(".png")
    fig.savefig(svg)
    fig.savefig(png, dpi=200)
    return svg, png


def _write_csv(path: Path, header: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def gates_by_layer(record: RunRecord, out_dir: Path, rel_to: Path) -> FigureEntry:
    plt = _plt()
    out_dir.mkdir(parents=True, exist_ok=True)
    labels, rows = [], []
    for layer in record.layers:
        fs = [f for f in record.findings if int(f.layer) == layer]
        counts = [sum(1 for f in fs if f.gate.value == g) for g in GATES]
        labels.append(f"L{layer} {LAYER_NAMES.get(Layer(layer), '')}")
        rows.append(counts)
    data = out_dir / "gates_by_layer.csv"
    _write_csv(data, ["layer", *GATES], [[lab, *r] for lab, r in zip(labels, rows, strict=True)])
    fig, ax = plt.subplots(figsize=(89 / 25.4 * 1.6, 0.5 * len(labels) + 1.1), layout="constrained")
    left = [0] * len(labels)
    for gi, gate in enumerate(GATES):
        widths = [r[gi] for r in rows]
        bars = ax.barh(
            labels, widths, left=left, color=COLOURS[gate], hatch=HATCH[gate],
            edgecolor="#333333", linewidth=0.5, label=gate,
        )  # fmt: skip
        for bar, w in zip(bars, widths, strict=True):
            if w:
                ax.text(
                    bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height() / 2,
                    f"{LETTER[gate]}{w}", ha="center", va="center", fontsize=7,
                )  # fmt: skip
        left = [a + b for a, b in zip(left, widths, strict=True)]
    ax.invert_yaxis()
    ax.set_xlabel("Checks (count)")
    ax.legend(ncols=4, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False)
    svg, _ = _save(fig, out_dir / "gates_by_layer")
    plt.close(fig)
    total = ", ".join(f"{g} {sum(r[i] for r in rows)}" for i, g in enumerate(GATES))
    return FigureEntry(
        id="gates_by_layer",
        kind="figure",
        path=str(svg.relative_to(rel_to)),
        caption=f"Check outcomes per layer for run {record.run_id}. Totals: {total}.",
        alt="Horizontal stacked bars per layer, split into pass, warn, stop and skip counts.",
        data_path=str(data.relative_to(rel_to)),
    )


def gate_matrix(report: BatchReport, out_dir: Path, rel_to: Path) -> FigureEntry:
    plt = _plt()
    from matplotlib.patches import Rectangle

    out_dir.mkdir(parents=True, exist_ok=True)
    targets = [t.name for t in report.targets if t.run_id]
    checks = list(report.checks)
    data = out_dir / "gate_matrix.csv"
    _write_csv(
        data,
        ["target", *checks],
        [[t, *(report.matrix.get(t, {}).get(c, "") for c in checks)] for t in targets],
    )
    fig, ax = plt.subplots(
        figsize=(max(4.0, 0.42 * len(checks) + 2.2), max(2.0, 0.34 * len(targets) + 2.4)),
        layout="constrained",
    )
    for yi, t in enumerate(targets):
        for xi, c in enumerate(checks):
            gate = report.matrix.get(t, {}).get(c)
            ax.add_patch(
                Rectangle(
                    (xi, yi), 1, 1,
                    facecolor=COLOURS.get(gate or "", NOT_RUN), hatch=HATCH.get(gate or "", ""),
                    edgecolor="#333333", linewidth=0.4,
                )
            )  # fmt: skip
            ax.text(
                xi + 0.5, yi + 0.5, LETTER.get(gate or "", ""), ha="center", va="center", fontsize=7
            )
    ax.set_xlim(0, len(checks))
    ax.set_ylim(len(targets), 0)
    ax.set_xticks(
        [i + 0.5 for i in range(len(checks))], checks, rotation=60, ha="right", fontsize=6
    )
    ax.set_yticks([i + 0.5 for i in range(len(targets))], targets)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    svg, _ = _save(fig, out_dir / "gate_matrix")
    plt.close(fig)
    return FigureEntry(
        id="gate_matrix",
        kind="figure",
        path=str(svg.relative_to(rel_to)),
        caption=(
            f"Gate per check and target for batch {report.batch_id}. P pass, W warn, S stop, "
            "- skip; blank cells were not part of that target's task."
        ),
        alt="Grid of targets (rows) by checks (columns); cells coloured and lettered by gate.",
        data_path=str(data.relative_to(rel_to)),
    )


def verdict_counts(report: BatchReport, out_dir: Path, rel_to: Path) -> FigureEntry:
    plt = _plt()
    out_dir.mkdir(parents=True, exist_ok=True)
    order = ["pass", "pass_with_warnings", "stop", "incomplete", "not_run"]
    colours = {
        "pass": COLOURS["pass"], "pass_with_warnings": COLOURS["warn"], "stop": COLOURS["stop"],
        "incomplete": "#56B4E9", "not_run": "#BBBBBB",
    }  # fmt: skip
    values = [report.verdict_counts.get(k, 0) for k in order]
    data = out_dir / "verdict_counts.csv"
    _write_csv(data, ["verdict", "targets"], list(zip(order, values, strict=True)))
    fig, ax = plt.subplots(figsize=(89 / 25.4 * 1.4, 2.4), layout="constrained")
    bars = ax.bar(
        order, values, color=[colours[k] for k in order], edgecolor="#333333", linewidth=0.5
    )
    for bar, v in zip(bars, values, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, v, str(v), ha="center", va="bottom", fontsize=7)
    ax.set_ylabel("Targets (count)")
    ax.tick_params(axis="x", labelsize=7)
    svg, _ = _save(fig, out_dir / "verdict_counts")
    plt.close(fig)
    return FigureEntry(
        id="verdict_counts",
        kind="figure",
        path=str(svg.relative_to(rel_to)),
        caption=f"Verdicts across {sum(values)} targets in batch {report.batch_id}.",
        alt="Bar chart of target counts per verdict.",
        data_path=str(data.relative_to(rel_to)),
    )
