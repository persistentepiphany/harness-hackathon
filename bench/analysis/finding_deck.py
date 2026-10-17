"""The focused deck: what the harness caught that the confidence score did not.

    python bench/analysis/finding_deck.py --runs <id> <id> <id>
    python bench/analysis/finding_deck.py --runs ... --review bench/finding/visual_judgment.json

Six slides, built from the recorded runs: the question, the sabotage, one named target seen twice,
the flip, the values, and what it costs. Every number is read from facts/ and results/truth.csv.
Text is kept short on purpose; the longer wording lives in the speaker notes.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / ".claude" / "skills" / "presentation-skill"
OUT = REPO / "bench" / "finding"
# FtsE is left out: its reference is a homodimer and its values predate the superposition fix.
SOUND = {"cdk2": "CDK2", "mek1": "MEK1", "glc": "glucose DH"}
ENTRY = {"cdk2": "1B38, ATP", "mek1": "7XLP, FZC", "glc": "2VWH, glucose"}


def gather(runs: list[Path]) -> dict[str, Any]:
    per: dict[str, list[dict[str, Any]]] = {k: [] for k in SOUND}
    for run in runs:
        with (run / "results" / "truth.csv").open() as fh:
            tr = {(r["system"], r["executor"]): r for r in csv.DictReader(fh)}
        for key in SOUND:
            row: dict[str, Any] = {"run": run.name}
            for state in ("wt", "pert"):
                f = json.loads((run / "facts" / f"{key}_{state}_boltz2.json").read_text())
                r = tr[(f"{key}_{state}", "boltz2")]
                conf = f["confidence"]
                row[state] = {
                    "recovered": f["key_interactions_recovered"],
                    "reference": f["key_interactions_reference"],
                    "iptm": conf.get("ligand_iptm"),
                    "plddt": conf.get("pocket_plddt"),
                    "pb_passed": f["posebusters"]["passed"],
                    "pb_total": f["posebusters"]["total"],
                    "strain": f["torsion_strain_kcal"],
                    "polars": f["buried_unsatisfied_polars"],
                    "spread": f["ensemble_spread_A"],
                    "cross": f["cross_tool_rmsd_A"],
                    "pose": f["representative_pose"],
                    "score_only": r["arm_A"],
                    "fact_file": r["arm_B"],
                    "truth": r["truth"],
                }
            per[key].append(row)
    sab = [(k, r) for k, rows in per.items() for r in rows]
    return {
        "per": per,
        "n": len(sab),
        "missed": sum(1 for _, r in sab if r["pert"]["score_only"] != "invalid"),
        "caught": sum(1 for _, r in sab if r["pert"]["fact_file"] == "invalid"),
        "runs": [r.name for r in runs],
    }


def _panels(system: str) -> list[dict[str, Any]]:
    out = []
    for state, title in (("wt", "as deposited"), ("pert", "pocket cut away")):
        png = OUT / "panels" / f"{system}_{state}.png"
        if png.is_file():
            out.append({"path": str(png), "title": title})
    return out


def _v(x: Any) -> str:
    return "n/a" if x is None else (f"{x:g}" if isinstance(x, float) else str(x))


def _structure_slide(system: str, first: dict[str, Any], mut: dict[str, int]) -> dict[str, Any]:
    """One named target, seen twice through one camera, with its measured values."""
    wt, pert = first[system]["wt"], first[system]["pert"]
    pdb = ENTRY[system].split(",")[0]
    return {
        "type": "content",
        "role": "evidence",
        "variant": "scientific-figure",
        "title": f"{SOUND[system]}: the ligand stays, the contacts go",
        "subtitle": f"{pdb} chain A, Boltz-2 medoid {wt['pose']}, {mut.get(system, 0)} contacts "
        "cut to glycine",
        "figures": _panels(system),
        "figure_layout": "panel-grid",
        "caption": f"Contacts {wt['recovered']} of {wt['reference']} then "
        f"{pert['recovered']} of {pert['reference']}; ipTM {_v(wt['iptm'])} then "
        f"{_v(pert['iptm'])}.",
        "notes": "One camera, proteins superposed; red marks the residues cut to glycine. "
        f"Confidence barely moves ({_v(wt['iptm'])} to {_v(pert['iptm'])}) and "
        f"PoseBusters still passes {pert['pb_passed']} of {pert['pb_total']}. The interactions "
        "are what collapse, and that is what the fact file reports.",
    }


def outline(d: dict[str, Any], mut: dict[str, int]) -> dict[str, Any]:
    n, caught, missed = d["n"], d["caught"], d["missed"]
    first = {k: v[0] for k, v in d["per"].items()}
    src = d["runs"][0]  # the values on the two tables all come from one run
    conf_rows = [
        [
            SOUND[k],
            f"{_v(first[k]['wt']['iptm'])} / {_v(first[k]['pert']['iptm'])}",
            f"{_v(first[k]['wt']['plddt'])} / {_v(first[k]['pert']['plddt'])}",
            f"{first[k]['wt']['pb_passed']}/{first[k]['wt']['pb_total']} / "
            f"{first[k]['pert']['pb_passed']}/{first[k]['pert']['pb_total']}",
        ]
        for k in SOUND
    ]
    harness_rows = [
        [
            SOUND[k],
            f"{first[k]['wt']['recovered']} of {first[k]['wt']['reference']} / "
            f"{first[k]['pert']['recovered']} of {first[k]['pert']['reference']}",
            f"{_v(first[k]['wt']['cross'])} / {_v(first[k]['pert']['cross'])}",
            f"{_v(first[k]['wt']['strain'])} / {_v(first[k]['pert']['strain'])}",
        ]
        for k in SOUND
    ]
    slides: list[dict[str, Any]] = [
        {
            "type": "title",
            "role": "title",
            "title": "Confidence missed every sabotaged pose",
            "subtitle": f"The harness caught all {caught} of {n}",
            "notes": "Same predictions, same agent, two kinds of evidence: the model's own "
            "confidence score, or the harness fact file.",
        },
        {
            "type": "content",
            "role": "table",
            "variant": "table",
            "title": "Three targets, each predicted twice",
            "table": {
                "headers": ["Target", "Entry and ligand", "Sabotage", "Medoid pose"],
                "rows": [
                    [
                        SOUND[k],
                        ENTRY[k],
                        f"{mut.get(k, 0)} contacts to glycine"
                        if k != "glc"
                        else f"{mut.get(k, 0)} hydroxyls methylated",
                        first[k]["pert"]["pose"],
                    ]
                    for k in SOUND
                ],
            },
            "caption": "Boltz-2 2.2.1 on A100, three seeds per prediction, three independent "
            "runs. A sabotaged system cannot bind as deposited, so every sabotaged pose should "
            "be rejected.",
        },
        _structure_slide("cdk2", first, mut),
        _structure_slide("mek1", first, mut),
        {
            "type": "content",
            "role": "table",
            "variant": "table",
            "title": "What the confidence score sees",
            "subtitle": f"As deposited / sabotaged, run {src}",
            "table": {
                "headers": ["Target", "Ligand ipTM", "Pocket pLDDT", "PoseBusters"],
                "rows": conf_rows,
            },
            "caption": "Confidence stays high after the pocket is cut away, and for glucose "
            "dehydrogenase the pocket pLDDT rises. PoseBusters passes almost everywhere.",
            "notes": "This is the whole problem. Nothing in these columns tells the agent the "
            "pocket is gone.",
        },
        {
            "type": "content",
            "role": "table",
            "variant": "table",
            "title": "What the harness sees",
            "subtitle": f"As deposited / sabotaged, run {src}",
            "table": {
                "headers": [
                    "Target",
                    "Deposited contacts recovered",
                    "Cross-executor RMSD (A)",
                    "Strain (kcal/mol)",
                ],
                "rows": harness_rows,
            },
            "caption": "Contact recovery falls on every target. Cross-executor RMSD rises on "
            "CDK2 and MEK1 and falls on glucose dehydrogenase, where both tools were already "
            "far apart.",
        },
        {
            "type": "content",
            "role": "evidence",
            "variant": "scientific-figure",
            "title": "Every sabotaged pose, both ways of judging",
            "figures": [{"path": str(OUT / "flip.png")}],
            "figure_layout": "panel-grid",
            "caption": f"{n} sabotaged predictions: 3 targets by 3 runs.",
            "notes": f"Confidence missed {missed} of {n}; the fact file caught {caught}.",
        },
        {
            "type": "content",
            "role": "comparison",
            "variant": "comparison-2col",
            "title": "What it buys and what it costs",
            "left": {
                "title": "Buys",
                "bullets": [
                    f"{caught} of {n} sabotaged poses rejected",
                    "Same answer in three runs",
                    "A reason recorded per decision",
                ],
            },
            "right": {
                "title": "Costs",
                "bullets": [
                    "Good poses rejected too",
                    "CDK2 as deposited, all runs",
                    "Mostly high strain estimates",
                ],
            },
            "notes": "A fourth target, FtsE, is held back: its reference is a homodimer and its "
            "values predate a superposition fix.",
        },
    ]
    for sl in slides:
        if sl["type"] == "content":
            sl.setdefault("sources", ["S1"])
            sl.setdefault("footer", f"S1: bench/runs ({', '.join(d['runs'])})")
    return {
        "title": "What the harness caught",
        "deck_style": {
            "style_preset": "lab-report",
            "composition_grammar": "scientific-evidence-plate",
            "style_seed": "pah-finding",
            "footer_mode": "source-line",
            "footer_page_numbers": True,
            "readability_contract": {
                "min_title_pt": 28,
                "min_body_pt": 16,
                "min_support_pt": 13,
                "min_caption_pt": 9,
                "min_footer_pt": 9,
                "min_metadata_pt": 9,
                "max_title_lines": 2,
            },
        },
        "slides": slides,
    }


def _skill(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = ["python3", str(SKILL / "scripts" / "python_runtime.py"), str(SKILL / "scripts" / script)]
    proc = subprocess.run([*cmd, *args], cwd=SKILL, capture_output=True, text=True)
    print(proc.stdout[-2500:], proc.stderr[-1500:])
    return proc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--review", type=Path)
    args = ap.parse_args()
    runs = [REPO / "bench" / "runs" / r for r in args.runs]
    pptx = OUT / "finding.pptx"
    if args.review:
        receipt = OUT / "visual_review_receipt.json"
        if _skill(
            "visual_review_receipt.py", "create", "--input", str(pptx),
            "--renders-dir", str(OUT / "qa" / "renders"), "--review", str(args.review.resolve()),
            "--output", str(receipt),
        ).returncode:  # fmt: skip
            sys.exit("receipt not created")
        if _skill(
            "qa_gate.py", "--input", str(pptx), "--outline", str(OUT / "outline.json"),
            "--outdir", str(OUT / "qa_bound"), "--style-preset", "lab-report", "--strict-geometry",
            "--fail-on-geometry-warnings", "--fail-on-whitespace-warnings", "--run-visual-review",
            "--fail-on-visual-review-warnings", "--fail-on-design-warnings", "--accessibility",
            "--strict-accessibility", "--visual-review-receipt", str(receipt),
            "--require-bound-visual-review",
        ).returncode:  # fmt: skip
            sys.exit("strict QA with the bound review failed")
        return
    mut = {}
    for key in SOUND:
        meta = json.loads((runs[0] / "prep" / f"{key}_pert" / "meta.json").read_text())
        mut[key] = len(meta["mutations"]) or len(meta["methylated_oxygens"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "outline.json").write_text(json.dumps(outline(gather(runs), mut), indent=2))
    proc = _skill(
        "present.py", "finalize", "--outline", str(OUT / "outline.json"),
        "--output", str(pptx), "--qa-dir", str(OUT / "qa"),
    )  # fmt: skip
    if proc.returncode:
        sys.exit(f"finalize failed; see {OUT / 'qa'}")
    print(f"built {pptx}; inspect {OUT / 'qa' / 'renders'} then bind with --review")


if __name__ == "__main__":
    main()
