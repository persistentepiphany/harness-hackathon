"""Score both agent arms against ground truth by construction.

    python bench/analysis/score.py --run-id <id>

Ground truth: a perturbed system is invalid; a wild-type system is valid when the representative
pose lies within 2 Å of the deposited ligand (truth/*.json, never shown to the agent). Each arm's
decision per prediction is the majority verdict over repeats. Outputs in results/: truth.csv,
confusion.csv, stats.json (balanced accuracy with 95 percent bootstrap intervals over systems,
exact McNemar on paired decisions, agreement across repeats) and figures/ (PNG, SVG, CSV).
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from math import comb
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]


def run_config(run: Path) -> dict[str, Any]:
    """The run's own copy of the design when it has one (bench/run_pipeline.py writes it),
    otherwise bench/config/targets.yaml."""

    own = run / "config" / "targets.yaml"
    return dict(
        yaml.safe_load((own if own.is_file() else REPO / "bench/config/targets.yaml").read_text())
    )


OKABE = {"A": "#8B8B85", "B": "#B07E2C", "valid": "#3B8A58", "invalid": "#C4513B"}
EXEC = {"boltz2": "Boltz-2", "diffdock": "DiffDock-L"}


def truth_table(run: Path, cutoff: float) -> dict[tuple[str, str], dict[str, Any]]:
    out = {}
    for p in sorted((run / "truth").glob("*.json")):
        t = json.loads(p.read_text())
        system = t["system"]
        executor = p.stem.removeprefix(system + "_")
        state = system.rsplit("_", 1)[1]
        rmsd = t.get("rmsd_to_deposited_A")
        if state == "pert":
            label, basis = "invalid", "perturbed (by construction)"
        elif rmsd is None:
            label, basis = None, "RMSD to deposited ligand not computed"
        else:
            label = "valid" if rmsd <= cutoff else "invalid"
            basis = f"wild type, RMSD {rmsd} Å {'<=' if label == 'valid' else '>'} {cutoff} Å"
        out[(system, executor)] = {
            "system": system,
            "executor": executor,
            "state": state,
            "rmsd_A": rmsd,
            "truth": label,
            "basis": basis,
        }
    return out


def majority(rows: list[dict[str, str]]) -> str | None:
    votes = Counter(r["verdict"] for r in rows if r["verdict"])
    if not votes:
        return None
    (top, n), *rest = votes.most_common()
    return None if rest and rest[0][1] == n else top


def balanced_accuracy(pairs: list[tuple[str, str]]) -> float | None:
    pos = [p == t for p, t in pairs if t == "valid"]
    neg = [p == t for p, t in pairs if t == "invalid"]
    if not pos or not neg:
        return None
    return (sum(pos) / len(pos) + sum(neg) / len(neg)) / 2


def bootstrap(pairs: list[tuple[str, str]], n: int = 10000, seed: int = 7) -> list[float] | None:
    import numpy as np

    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, len(pairs), len(pairs))
        v = balanced_accuracy([pairs[i] for i in idx])
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)]


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p from the discordant counts b (A right, B wrong), c (B right)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n
    return round(min(1.0, p), 4)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    run = REPO / "bench" / "runs" / args.run_id
    cfg = run_config(run)
    truth = truth_table(run, float(cfg["ground_truth_rmsd_A"]))
    res = run / "results"
    with (res / "decisions.csv").open() as fh:
        decisions = list(csv.DictReader(fh))
    by: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for d in decisions:
        by[(d["system"], d["executor"], d["arm"])].append(d)
    table = []
    for (system, executor), t in sorted(truth.items()):
        row = dict(t)
        for arm in ("A", "B"):
            reps = by.get((system, executor, arm), [])
            row[f"arm_{arm}"] = majority(reps)
            row[f"arm_{arm}_votes"] = ",".join(r["verdict"] or "error" for r in reps)
            row[f"arm_{arm}_agreement"] = (
                round(max(Counter(r["verdict"] for r in reps).values()) / len(reps), 3)
                if reps
                else None
            )
        table.append(row)
    with (res / "truth.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    stats: dict[str, Any] = {
        "run_id": args.run_id,
        "cutoff_A": cfg["ground_truth_rmsd_A"],
        "n_predictions": len(table),
        "n_unlabelled": sum(1 for r in table if r["truth"] is None),
        "arms": {},
    }
    confusion_rows = []
    for scope in ("all", "boltz2", "diffdock"):
        rows = [r for r in table if r["truth"] and (scope == "all" or r["executor"] == scope)]
        block: dict[str, Any] = {
            "n": len(rows),
            "n_valid": sum(r["truth"] == "valid" for r in rows),
            "n_invalid": sum(r["truth"] == "invalid" for r in rows),
        }
        for arm in ("A", "B"):
            pairs = [(r[f"arm_{arm}"] or "none", r["truth"]) for r in rows]
            tp = sum(p == "valid" and t == "valid" for p, t in pairs)
            fn = sum(p != "valid" and t == "valid" for p, t in pairs)
            tn = sum(p == "invalid" and t == "invalid" for p, t in pairs)
            fp = sum(p != "invalid" and t == "invalid" for p, t in pairs)
            ba = balanced_accuracy(pairs)
            block[arm] = {
                "tp": tp,
                "fn": fn,
                "tn": tn,
                "fp": fp,
                "accuracy": round((tp + tn) / len(pairs), 3) if pairs else None,
                "balanced_accuracy": round(ba, 3) if ba is not None else None,
                "ci95": bootstrap(pairs),
            }
            confusion_rows.append(
                {"scope": scope, "arm": arm, "tp": tp, "fn": fn, "tn": tn, "fp": fp}
            )
        b = sum((r["arm_A"] == r["truth"]) and (r["arm_B"] != r["truth"]) for r in rows)
        c = sum((r["arm_A"] != r["truth"]) and (r["arm_B"] == r["truth"]) for r in rows)
        block["mcnemar"] = {
            "a_right_b_wrong": b,
            "b_right_a_wrong": c,
            "p_exact": mcnemar_exact(b, c),
        }
        stats["arms"][scope] = block
    stats["repeat_agreement"] = {
        arm: round(sum(r[f"arm_{arm}_agreement"] or 0 for r in table) / len(table), 3)
        for arm in ("A", "B")
    }
    stats["call_errors"] = sum(1 for d in decisions if d["error"])
    (res / "stats.json").write_text(json.dumps(stats, indent=2))
    with (res / "confusion.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(confusion_rows[0]))
        w.writeheader()
        w.writerows(confusion_rows)
    figures(res, table, stats)
    print(json.dumps(stats["arms"]["all"], indent=2))


def figures(res: Path, table: list[dict[str, Any]], stats: dict[str, Any]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    out = res / "figures"
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )

    # 1. balanced accuracy with intervals, per executor and arm
    fig, ax = plt.subplots(figsize=(4.6, 2.8), layout="constrained")
    scopes = ["boltz2", "diffdock", "all"]
    rows = []
    for i, scope in enumerate(scopes):
        for j, arm in enumerate(("A", "B")):
            blk = stats["arms"][scope][arm]
            ba, ci = blk["balanced_accuracy"], blk["ci95"]
            x = i + (j - 0.5) * 0.36
            if ba is not None:
                ax.bar(
                    x,
                    ba,
                    0.34,
                    color=OKABE[arm],
                    label=("score only" if arm == "A" else "harness fact file") if i == 0 else None,
                )
                if ci:
                    ax.errorbar(
                        x, ba, yerr=[[ba - ci[0]], [ci[1] - ba]], color="#1A1A18", capsize=3, lw=1
                    )
                ax.text(x, 0.02, f"{ba:.2f}", ha="center", va="bottom", fontsize=8, color="white")
            rows.append(
                {
                    "scope": scope,
                    "arm": arm,
                    "balanced_accuracy": ba,
                    "ci_low": ci[0] if ci else None,
                    "ci_high": ci[1] if ci else None,
                }
            )
    ax.axhline(0.5, color="#8B8B85", lw=0.8, ls="--")
    ax.set_xticks(range(3), ["Boltz-2", "DiffDock-L", "pooled"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("balanced accuracy")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _save(fig, out / "balanced_accuracy", rows)

    # 2. decision grid: columns = predictions, rows = truth, arm A, arm B (landscape for slides)
    short = {"boltz2": "B2", "diffdock": "DD"}
    labels = [f"{r['system'].replace('_', ' ')} {short[r['executor']]}" for r in table]
    cols = ["truth", "arm_A", "arm_B"]
    code = {"valid": 1, "invalid": 0, None: 0.5, "none": 0.5}
    grid = [[code.get(r[c], 0.5) for r in table] for c in cols]
    fig, ax = plt.subplots(figsize=(0.55 * len(table) + 1.4, 2.9), layout="constrained")
    cmap = ListedColormap([OKABE["invalid"], "#E6E6E1", OKABE["valid"]])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for j, r in enumerate(table):
        for i, c in enumerate(cols):
            ax.text(
                j,
                i,
                {"valid": "V", "invalid": "I"}.get(r[c] or "", "?"),
                ha="center",
                va="center",
                color="white",
                fontsize=9,
            )
    ax.set_yticks(range(3), ["ground truth", "score only", "fact file"])
    ax.set_xticks(range(len(labels)), labels, fontsize=9, rotation=55, ha="right")
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    rows_csv = [
        {"prediction": lab.replace("\n", " "), **{c: r[c] for c in cols}}
        for lab, r in zip(labels, table, strict=True)
    ]
    _save(fig, out / "decisions", rows_csv)

    # 3. confusion matrices
    fig, axes = plt.subplots(1, 2, figsize=(5.2, 2.5), layout="constrained")
    crow = []
    for ax, arm in zip(axes, ("A", "B"), strict=True):
        blk = stats["arms"]["all"][arm]
        m = [[blk["tp"], blk["fn"]], [blk["fp"], blk["tn"]]]
        ax.imshow([[1, 0], [0, 1]], cmap=ListedColormap(["#F3F3EF", "#F6EEDC"]), vmin=0, vmax=1)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, str(m[i][j]), ha="center", va="center", fontsize=12)
        ax.set_xticks([0, 1], ["called valid", "called invalid"])
        ax.set_yticks([0, 1], ["truly valid", "truly invalid"])
        ax.set_title("score only" if arm == "A" else "harness fact file", fontsize=9)
        ax.tick_params(length=0)
        crow.append(
            {"arm": arm, "tp": blk["tp"], "fn": blk["fn"], "fp": blk["fp"], "tn": blk["tn"]}
        )
    _save(fig, out / "confusion", crow)


def _save(fig: Any, stem: Path, rows: list[dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    # Fixed metadata and element ids, so a rerun on the same data writes the same bytes.
    fig.savefig(stem.with_suffix(".png"), dpi=200, metadata={"Software": None})
    with plt.rc_context({"svg.hashsalt": stem.name}):
        fig.savefig(stem.with_suffix(".svg"), metadata={"Date": None})
    plt.close(fig)
    if rows:
        with stem.with_suffix(".csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
