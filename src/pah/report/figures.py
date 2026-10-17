"""Figures following the scientific-visualization skill: Okabe-Ito colours, hatching and text
labels so gates read without colour, constrained layout, SVG and PNG, data saved as CSV."""

from __future__ import annotations

import csv
from collections.abc import Callable, Mapping, Sequence
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


# ---- figures from UiRunRecord.stats -------------------------------------------------------

OKABE_ITO = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000")
UI_GATE = {"pass": "#3B8A58", "fail": "#C4513B", "unknown": "#EFEFEB"}
INK, MUTED, LINE = "#1A1A18", "#8B8B85", "#E6E6E1"

StatsFigure = Callable[[Mapping[str, Any], Path, Path], FigureEntry | None]
STATS_FIGURES: list[tuple[str, StatsFigure]] = []


def stats_figure(block: str) -> Callable[[StatsFigure], StatsFigure]:
    """Registers a figure that is drawn only when `stats[block]` exists."""

    def deco(fn: StatsFigure) -> StatsFigure:
        STATS_FIGURES.append((block, fn))
        return fn

    return deco


def stats_figures(
    stats: Mapping[str, Any], out_dir: Path, rel_to: Path
) -> tuple[list[FigureEntry], list[str]]:
    """Every registered figure whose stats block is present; errors are returned, not raised."""
    entries: list[FigureEntry] = []
    errors: list[str] = []
    for block, fn in STATS_FIGURES:
        if not stats.get(block):
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            entry = fn(stats, out_dir, rel_to)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"figure {fn.__name__}: {type(exc).__name__}: {exc}")
            continue
        if entry is not None:
            entries.append(entry)
    return entries, errors


def _rows(value: object) -> list[Mapping[str, Any]]:
    return [v for v in value if isinstance(v, Mapping)] if isinstance(value, list) else []


def _is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _clean(ax: Any) -> None:
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)


def _entry(
    fid: str, svg: Path, data: Path, rel_to: Path, caption: str, alt: str, layer: int
) -> FigureEntry:
    return FigureEntry(
        id=fid,
        kind="figure",
        path=str(svg.relative_to(rel_to)),
        caption=caption,
        alt=alt,
        data_path=str(data.relative_to(rel_to)),
        layer=layer,
    )


@stats_figure("seeds")
def seed_spread(stats: Mapping[str, Any], out_dir: Path, rel_to: Path) -> FigureEntry | None:
    import statistics

    rows = [r for r in _rows(stats.get("seeds")) if _is_num(r.get("rmsdToMedoid"))]
    if not rows:
        return None
    plt = _plt()
    labels = [str(r.get("pose") or f"seed {r.get('seed')}") for r in rows]
    xs = [float(r["rmsdToMedoid"]) for r in rows]
    clusters = [r.get("cluster") for r in rows]
    order = list(dict.fromkeys(clusters))
    data = out_dir / "seed_spread.csv"
    _write_csv(
        data,
        ["pose", "seed", "cluster", "rmsd_to_medoid_A", "confidence"],
        [
            [lab, r.get("seed"), r.get("cluster"), r.get("rmsdToMedoid"), r.get("confidence")]
            for lab, r in zip(labels, rows, strict=True)
        ],
    )
    med = statistics.median(xs)
    fig, ax = plt.subplots(figsize=(89 / 25.4 * 1.6, 0.32 * len(rows) + 1.2), layout="constrained")
    for ci, cluster in enumerate(order):
        idx = [i for i, c in enumerate(clusters) if c == cluster]
        ax.scatter(
            [xs[i] for i in idx], idx, s=36, color=OKABE_ITO[ci % len(OKABE_ITO)],
            edgecolor="white", linewidth=0.8, zorder=3, label=f"cluster {cluster}",
        )  # fmt: skip
    ax.axvline(med, color=MUTED, linestyle="--", linewidth=0.8, zorder=2)
    ax.text(med, -0.8, f"median {med:.2f} Å", ha="center", va="bottom", fontsize=7, color=MUTED)
    ax.set_yticks(range(len(rows)), labels, fontsize=7)
    ax.set_ylim(len(rows) - 0.5, -1.2)
    ax.set_xlim(left=-0.04 * max(max(xs), 1.0))
    ax.set_xlabel("RMSD to medoid (Å)")
    ax.grid(axis="x", color=LINE, linewidth=0.5)
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    _clean(ax)
    svg, _ = _save(fig, out_dir / "seed_spread")
    plt.close(fig)
    return _entry(
        "seed_spread",
        svg,
        data,
        rel_to,
        f"RMSD to the medoid for {len(rows)} poses, coloured by cluster ({len(order)} clusters). "
        f"Dashed line: median {med:.2f} Å; range {min(xs):.2f} to {max(xs):.2f} Å.",
        "Dot plot of RMSD to the medoid per pose, coloured by cluster, with a dashed median line.",
        5,
    )


@stats_figure("posebusters")
def posebusters_grid(stats: Mapping[str, Any], out_dir: Path, rel_to: Path) -> FigureEntry | None:
    from matplotlib.patches import Rectangle

    tests = _rows(stats.get("posebusters"))
    if not tests:
        return None
    names = [str(t.get("test")) for t in tests]
    poses = [r for r in _rows(stats.get("physics")) if "pbFailed" in r or "pbPassed" in r]
    failed_by_pose = [(str(p.get("pose")), p) for p in poses]
    for _, p in failed_by_pose:
        names += [str(x) for x in p.get("pbFailed") or [] if str(x) not in names]
    columns: list[tuple[str, dict[str, str]]] = []
    for pose, p in failed_by_pose:
        failed = {str(x) for x in p.get("pbFailed") or []}
        known = "pbFailed" in p
        states = {n: "fail" if n in failed else "pass" if known else "unknown" for n in names}
        columns.append((pose, states))
    if not columns:
        single = {str(t.get("test")): "pass" if t.get("pass") else "fail" for t in tests}
        columns = [("tests", single)]
    plt = _plt()
    data = out_dir / "posebusters_grid.csv"
    _write_csv(
        data,
        ["test", *(c for c, _ in columns)],
        [[n, *(col.get(n, "unknown") for _, col in columns)] for n in names],
    )
    fig, ax = plt.subplots(
        figsize=(max(3.2, 0.55 * len(columns) + 2.6), 0.2 * len(names) + 1.3), layout="constrained"
    )
    mark = {"pass": "", "fail": "x", "unknown": "?"}
    for xi, (_, col) in enumerate(columns):
        for yi, n in enumerate(names):
            state = col.get(n, "unknown")
            ax.add_patch(
                Rectangle(
                    (xi + 0.06, yi + 0.06), 0.88, 0.88, facecolor=UI_GATE[state],
                    edgecolor="white", linewidth=0.6,
                )
            )  # fmt: skip
            color = INK if state == "unknown" else "white"
            ax.text(xi + 0.5, yi + 0.5, mark[state], ha="center", va="center", fontsize=6,
                    color=color)  # fmt: skip
    ax.set_xlim(0, len(columns))
    ax.set_ylim(len(names), 0)
    ax.set_xticks(
        [i + 0.5 for i in range(len(columns))], [c for c, _ in columns], rotation=45, ha="right",
        fontsize=6,
    )  # fmt: skip
    ax.set_yticks([i + 0.5 for i in range(len(names))], names, fontsize=6)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    svg, _ = _save(fig, out_dir / "posebusters_grid")
    plt.close(fig)
    fails = sum(1 for _, col in columns for v in col.values() if v == "fail")
    return _entry(
        "posebusters_grid",
        svg,
        data,
        rel_to,
        f"PoseBusters tests ({len(names)}) by pose ({len(columns)}). Failed cells marked x: "
        f"{fails} of {len(names) * len(columns)}.",
        "Grid of PoseBusters tests (rows) by poses (columns); failed cells red with an x.",
        4,
    )


def _heatmap(
    ax: Any, values: list[list[float | None]], labels: list[list[str]], cmap: Any, vmax: float
) -> Any:
    import numpy as np

    grid = np.array([[np.nan if v is None else v for v in row] for row in values], dtype=float)
    im = ax.imshow(grid, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
    for yi, row in enumerate(labels):
        for xi, lab in enumerate(row):
            if lab:
                v = grid[yi, xi]
                dark = not np.isnan(v) and v > vmax * 0.6
                color = "white" if dark else INK
                ax.text(xi, yi, lab, ha="center", va="center", fontsize=7, color=color)
    return im


def _seq_cmap(name: str, start: str, end: str) -> Any:
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(name, [start, end]).with_extremes(bad="#F7F7F4")


def _bare(ax: Any) -> None:
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)


@stats_figure("interactions")
def interactions(stats: Mapping[str, Any], out_dir: Path, rel_to: Path) -> FigureEntry | None:
    rows = _rows(stats.get("interactions"))
    if not rows:
        return None
    residues = list(dict.fromkeys(str(r.get("residue")) for r in rows))
    types = list(dict.fromkeys(str(r.get("type")) for r in rows))
    cell = {(str(r.get("residue")), str(r.get("type"))): r for r in rows}
    values: list[list[float | None]] = []
    labels: list[list[str]] = []
    for res in residues:
        vrow: list[float | None] = []
        lrow: list[str] = []
        for t in types:
            r = cell.get((res, t))
            n = r.get("poses") if r else None
            vrow.append(float(n) if isinstance(n, (int, float)) and _is_num(n) else None)
            of = r.get("of") if r else None
            lrow.append("" if n is None else f"{n}/{of}" if of is not None else str(n))
        values.append(vrow)
        labels.append(lrow)
    data = out_dir / "interactions.csv"
    _write_csv(
        data,
        ["residue", "type", "poses", "of", "distance_A"],
        [[r.get("residue"), r.get("type"), r.get("poses"), r.get("of"), r.get("distance")]
         for r in rows],
    )  # fmt: skip
    plt = _plt()
    vmax = max([float(r["of"]) for r in rows if _is_num(r.get("of"))] or [1.0])
    fig, ax = plt.subplots(
        figsize=(0.75 * len(types) + 2.4, 0.32 * len(residues) + 1.2), layout="constrained"
    )
    im = _heatmap(ax, values, labels, _seq_cmap("pah_int", "#FBF7EE", "#0072B2"), vmax)
    ax.set_xticks(range(len(types)), types, rotation=30, ha="right", fontsize=7)
    ax.set_yticks(range(len(residues)), residues, fontsize=7)
    _bare(ax)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Poses with the interaction")
    svg, _ = _save(fig, out_dir / "interactions")
    plt.close(fig)
    return _entry(
        "interactions",
        svg,
        data,
        rel_to,
        f"Interactions by residue ({len(residues)}) and type ({len(types)}); cell label: poses "
        "with the interaction over poses assessed.",
        "Heatmap of residues (rows) by interaction type (columns), shaded by pose count.",
        4,
    )


@stats_figure("agreement")
def agreement(stats: Mapping[str, Any], out_dir: Path, rel_to: Path) -> FigureEntry | None:
    rows = _rows(stats.get("agreement"))
    if not rows:
        return None
    methods = [str(r.get("method")) for r in rows]
    others = list(dict.fromkeys(str(c.get("vs")) for r in rows for c in _rows(r.get("cells"))))
    units = sorted(
        {str(c.get("unit")) for r in rows for c in _rows(r.get("cells")) if c.get("unit")}
    )
    values: list[list[float | None]] = []
    labels: list[list[str]] = []
    csv_rows: list[list[object]] = []
    for r in rows:
        cells = {str(c.get("vs")): c for c in _rows(r.get("cells"))}
        vrow: list[float | None] = []
        lrow: list[str] = []
        for o in others:
            c = cells.get(o)
            v = c.get("value") if c else None
            ok = _is_num(v) and o != r.get("method")
            vrow.append(float(v) if ok and isinstance(v, (int, float)) else None)
            lrow.append(f"{v:g}" if ok else "")
            if c:
                csv_rows.append([r.get("method"), o, v, c.get("unit"), c.get("weight")])
        values.append(vrow)
        labels.append(lrow)
    data = out_dir / "agreement.csv"
    _write_csv(data, ["method", "vs", "value", "unit", "weight"], csv_rows)
    nums = [v for row in values for v in row if v is not None]
    unit = ", ".join(units)
    plt = _plt()
    fig, ax = plt.subplots(
        figsize=(0.9 * len(others) + 2.6, 0.5 * len(methods) + 1.3), layout="constrained"
    )
    cmap = _seq_cmap("pah_agree", "#FBF7EE", "#8E6420")
    im = _heatmap(ax, values, labels, cmap, max(nums or [1.0]))
    ax.set_xticks(range(len(others)), others, fontsize=7)
    ax.set_yticks(range(len(methods)), methods, fontsize=7)
    _bare(ax)
    fig.colorbar(im, ax=ax, shrink=0.8, label=f"Difference ({unit})" if unit else "Difference")
    svg, _ = _save(fig, out_dir / "agreement")
    plt.close(fig)
    rng = ""
    if nums:
        rng = f"; range {min(nums):g} to {max(nums):g}" + (f" {unit}" if unit else "")
    return _entry(
        "agreement",
        svg,
        data,
        rel_to,
        f"Agreement between {len(methods)} methods and {len(others)} comparators{rng}.",
        "Matrix of methods (rows) against comparators (columns), shaded by the difference.",
        5,
    )


@stats_figure("pae")
def pae(stats: Mapping[str, Any], out_dir: Path, rel_to: Path) -> FigureEntry | None:
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap

    ref = stats.get("pae")
    if not isinstance(ref, Mapping) or not ref.get("path"):
        return None
    path = Path(str(ref["path"]))
    matrix = np.load(path if path.is_absolute() else rel_to / path)
    if matrix.ndim != 2:
        raise ValueError(f"PAE matrix must be 2D, got shape {matrix.shape}")
    data = out_dir / "pae.csv"
    np.savetxt(data, matrix, delimiter=",", fmt="%.3f")
    plt = _plt()
    cmap = LinearSegmentedColormap.from_list("pah_pae", ["#2F6B4F", "#B9D7C3", "#F6F6F3"])
    vmax = max(30.0, float(np.nanmax(matrix)))
    fig, ax = plt.subplots(figsize=(3.4, 3.0), layout="constrained")
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=vmax)
    ax.set_xlabel("Scored token")
    ax.set_ylabel("Aligned token")
    fig.colorbar(im, ax=ax, shrink=0.85, label="Expected position error (Å)")
    svg, _ = _save(fig, out_dir / "pae")
    plt.close(fig)
    pose = ref.get("pose")
    lo, hi, mean = (float(f(matrix)) for f in (np.nanmin, np.nanmax, np.nanmean))
    return _entry(
        "pae",
        svg,
        data,
        rel_to,
        f"Predicted aligned error{f' for pose {pose}' if pose else ''}, {matrix.shape[0]} by "
        f"{matrix.shape[1]} tokens; values {lo:.1f} to {hi:.1f} Å, mean {mean:.1f} Å.",
        "Heatmap of predicted aligned error between tokens, green low to pale high.",
        5,
    )
