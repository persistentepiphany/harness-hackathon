"""The one figure behind the finding: sabotaged poses caught, with and without the harness.

    python bench/analysis/finding_figure.py --out <dir> [--runs <id> ...]

One cell per sabotaged Boltz-2 prediction (target by run). The top row is the agent judging on the
model's confidence score, the bottom row the same agent judging on the harness fact file. Colour
carries the verdict and so does the glyph, so the figure reads without colour. Writes PNG, SVG and
the plotted rows as CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# Excludes ftse: its reference is a homodimer and its values predate the superposition fix.
SOUND = {"cdk2": "CDK2", "mek1": "MEK1", "glc": "glucose DH"}
CAUGHT, MISSED = "#3B8A58", "#C4513B"
INK, MUTED = "#1A1A18", "#55554F"


def collect(runs: list[Path]) -> list[dict[str, str]]:
    rows = []
    for n, run in enumerate(runs, 1):
        with (run / "results" / "truth.csv").open() as fh:
            tr = {(r["system"], r["executor"]): r for r in csv.DictReader(fh)}
        for key, label in SOUND.items():
            r = tr[(f"{key}_pert", "boltz2")]
            f = json.loads((run / "facts" / f"{key}_pert_boltz2.json").read_text())
            rows.append(
                {
                    "run": str(n),
                    "run_id": run.name,
                    "target": label,
                    "contacts_recovered": str(f["key_interactions_recovered"]),
                    "contacts_reference": str(f["key_interactions_reference"]),
                    "score_only": r["arm_A"],
                    "fact_file": r["arm_B"],
                }
            )
    return rows


def draw(rows: list[dict[str, str]], out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "svg.fonttype": "none"})
    n = len(rows)
    fig, ax = plt.subplots(figsize=(1.05 * n + 2.6, 3.0), layout="constrained")
    for i, row in enumerate(rows):
        for j, arm in enumerate(("score_only", "fact_file")):
            caught = row[arm] == "invalid"
            ax.add_patch(
                plt.Rectangle(
                    (i + 0.06, 1 - j + 0.06),
                    0.88,
                    0.88,
                    facecolor=CAUGHT if caught else MISSED,
                    edgecolor="none",
                )
            )
            ax.text(
                i + 0.5,
                1 - j + 0.5,
                "caught" if caught else "missed",
                ha="center",
                va="center",
                color="white",
                fontsize=10,
                fontweight="bold",
            )
    ax.set_xticks([i + 0.5 for i in range(n)])
    ax.set_xticklabels([f"{r['target']}\nrun {r['run']}" for r in rows], fontsize=10)
    ax.set_yticks([1.5, 0.5])
    ax.set_yticklabels(["confidence score\nonly", "harness\nfact file"], fontsize=11)
    ax.set_xlim(0, n)
    ax.set_ylim(0, 2)
    ax.tick_params(length=0)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)
    miss = sum(1 for r in rows if r["score_only"] != "invalid")
    got = sum(1 for r in rows if r["fact_file"] == "invalid")
    ax.set_title(
        f"Sabotaged poses: {n - miss} of {n} caught on confidence, {got} of {n} with the harness",
        fontsize=12,
        color=INK,
        pad=12,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=200, metadata={"Software": None})
    with plt.rc_context({"svg.hashsalt": out.name}):
        fig.savefig(out.with_suffix(".svg"), metadata={"Date": None})
    plt.close(fig)
    with out.with_suffix(".csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    args = ap.parse_args()
    runs = [REPO / "bench" / "runs" / r for r in args.runs]
    rows = collect(runs)
    draw(rows, Path(args.out) / "flip")
    print(f"{len(rows)} sabotaged predictions -> {args.out}/flip.png")


if __name__ == "__main__":
    main()
