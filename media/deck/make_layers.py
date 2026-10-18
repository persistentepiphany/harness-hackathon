"""Render the six-layer diagram for the Dock Harness deck."""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

out = Path(sys.argv[1])
layers = [
    ("L0", "provenance", "inputs"),
    ("L1", "input\nintegrity", "inputs"),
    ("L2", "input\nadequacy", "inputs"),
    ("L3", "applicability", "model"),
    ("L4", "output\nvalidity", "outputs"),
    ("L5", "output\nsupport", "outputs"),
]
fill = {"inputs": "#DCE6F0", "model": "#E8E2F0", "outputs": "#DDEBDF"}
edge = {"inputs": "#3A5F85", "model": "#5E4A85", "outputs": "#3B7046"}

fig, ax = plt.subplots(figsize=(13.0, 5.6), dpi=200)
ax.set_xlim(0, 13)
ax.set_ylim(0.95, 5.6)
ax.axis("off")

w, h, gap, x0, y0 = 1.85, 2.0, 0.27, 0.3, 3.0
for i, (lid, name, group) in enumerate(layers):
    x = x0 + i * (w + gap)
    ax.add_patch(
        FancyBboxPatch(
            (x, y0),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            fc=fill[group],
            ec=edge[group],
            lw=2,
        )
    )
    ax.text(
        x + w / 2,
        y0 + h - 0.45,
        lid,
        ha="center",
        va="center",
        fontsize=26,
        fontweight="bold",
        color=edge[group],
    )
    ax.text(
        x + w / 2,
        y0 + 0.75,
        name,
        ha="center",
        va="center",
        fontsize=15.5,
        color="#1F2328",
        linespacing=1.1,
    )
    if i < len(layers) - 1:
        ax.add_patch(
            FancyArrowPatch(
                (x + w + 0.02, y0 + h / 2),
                (x + w + gap - 0.02, y0 + h / 2),
                arrowstyle="-|>",
                mutation_scale=16,
                color="#57606A",
                lw=1.6,
            )
        )

# group brackets
for label, i0, i1, group in (
    ("inputs", 0, 2, "inputs"),
    ("model", 3, 3, "model"),
    ("outputs", 4, 5, "outputs"),
):
    xa = x0 + i0 * (w + gap)
    xb = x0 + i1 * (w + gap) + w
    ax.plot([xa, xb], [y0 + h + 0.22, y0 + h + 0.22], color=edge[group], lw=2.5)
    ax.text(
        (xa + xb) / 2,
        y0 + h + 0.42,
        label,
        ha="center",
        va="bottom",
        fontsize=15,
        color=edge[group],
    )

# outcome row
ax.text(0.3, 1.55, "each check returns", ha="left", va="center", fontsize=17, color="#1F2328")
chips = [("pass", "#2E7D4F"), ("warn", "#B7791F"), ("stop", "#B23A2E"), ("skip", "#6E7781")]
cx = 3.25
for label, col in chips:
    ax.add_patch(
        FancyBboxPatch(
            (cx, 1.15), 1.25, 0.8, boxstyle="round,pad=0.02,rounding_size=0.3", fc=col, ec=col
        )
    )
    ax.text(
        cx + 0.625,
        1.55,
        label,
        ha="center",
        va="center",
        fontsize=18,
        color="white",
        fontweight="bold",
    )
    cx += 1.45
ax.text(
    cx + 0.15,
    1.55,
    "+ evidence\n+ threshold with origin",
    ha="left",
    va="center",
    fontsize=17,
    color="#1F2328",
    linespacing=1.3,
)

fig.savefig(out, bbox_inches="tight", pad_inches=0.1, facecolor="white")
