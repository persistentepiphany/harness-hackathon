"""Slide deck for one benchmark run, built with .claude/skills/presentation-skill.

    python bench/analysis/deck.py --run-id <id> [--system cdk2] [--executor boltz2]
    python bench/analysis/deck.py --run-id <id> --review <run>/deck/visual_judgment.json

Writes <run>/deck/outline.json from results/stats.json, the fact files and the renders, then runs
the skill's `present.py finalize` (build, render, QA) to <run>/results/deck.pptx. Every number on a
slide is read from the run's files; speaker notes hold the longer explanation (human-pace: at most
about 30 words of body text per slide).

The skill requires a visual review of the rendered slides. After inspecting deck/qa/renders, write
the judgment as visual_judgment_v1 JSON and pass it with --review: it is bound to the deck and
render hashes (deck/visual_review_receipt.json) and a strict QA pass requires it.
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
EXEC = {"boltz2": "Boltz-2", "diffdock": "DiffDock-L"}


def _v(x: Any) -> str:
    if x is None:
        return "n/a"
    return f"{x:.3g}" if isinstance(x, float) else str(x)


def _ba(block: dict[str, Any]) -> str:
    ci = block.get("ci95")
    ba = block.get("balanced_accuracy")
    return f"{_v(ba)} ({ci[0]} to {ci[1]})" if ci else _v(ba)


def _render(run: Path, name: str, rep: str) -> Path | None:
    stem = rep.replace("/", "_")
    hits = sorted((run / "harness" / name / "run" / "renders").glob(f"{stem}_pocket.png"))
    return hits[0] if hits else None


def outline(run: Path, system: str, executor: str) -> dict[str, Any]:
    stats = json.loads((run / "results" / "stats.json").read_text())
    metas = {
        p.parent.name: json.loads(p.read_text()) for p in sorted((run / "prep").glob("*/meta.json"))
    }
    facts = {p.stem: json.loads(p.read_text()) for p in sorted((run / "facts").glob("*.json"))}
    with (run / "results" / "truth.csv").open() as fh:
        tr = {(r["system"], r["executor"]): r for r in csv.DictReader(fh)}
    wt = facts[f"{system}_wt_{executor}"]
    pert = facts[f"{system}_pert_{executor}"]
    allb, figs = stats["arms"]["all"], run / "results" / "figures"
    rows = []
    for m in metas.values():
        if m["state"] != "pert":
            continue
        kind = m["perturbation"]["kind"]
        what = (
            f"{len(m['mutations'])} contacts to Gly"
            if kind == "pocket_to_gly"
            else f"{len(m['methylated_oxygens'])} hydroxyls methylated"
        )
        rows.append([m["protein"].split(" (")[0], m["pdb"], m["ligand_code"], what])

    def arm_rows(f: dict[str, Any]) -> list[str]:
        pb = f["posebusters"]
        return [
            f"PoseBusters {_v(pb['passed'])} of {_v(pb['total'])}",
            f"Deposited interactions recovered {_v(f['key_interactions_recovered'])} of "
            f"{_v(f['key_interactions_reference'])}",
            f"Buried unsatisfied polars {_v(f['buried_unsatisfied_polars'])}",
            f"Ensemble spread {_v(f['ensemble_spread_A'])} Å; cross-executor "
            f"{_v(f['cross_tool_rmsd_A'])} Å",
        ]

    conf = ", ".join(f"{k} {_v(v)}" for k, v in pert["confidence"].items() if v is not None)
    conf_wt = ", ".join(f"{k} {_v(v)}" for k, v in wt["confidence"].items() if v is not None)
    panels = []
    for state, f in (("wt", wt), ("pert", pert)):
        png = _render(run, f"{system}_{state}_{executor}", f["representative_pose"])
        if png is not None:
            panels.append(
                {
                    "path": str(png),
                    "label": "A" if state == "wt" else "B",
                    "title": "wild type" if state == "wt" else "perturbed",
                    "caption": f"{EXEC[executor]} medoid pose",
                }
            )
    m_pert = metas[f"{system}_pert"]
    slides: list[dict[str, Any]] = [
        {
            "type": "title",
            "role": "title",
            "title": "Does the fact file help reject invalid poses?",
            "subtitle": f"Perturbation benchmark, run {run.name}",
            "notes": "Same agent, same predictions, two kinds of evidence: the model confidence "
            "score alone, or the harness fact file.",
        },
        {
            "type": "content",
            "role": "table",
            "variant": "table",
            "title": "Four systems, each wild type and perturbed",
            "subtitle": "Perturbed systems are invalid by construction",
            "table": {"headers": ["System", "Entry", "Ligand", "Perturbation"], "rows": rows},
            "notes": "Each system is predicted by Boltz-2 and DiffDock-L with three seeds. A "
            "wild-type prediction is valid when its medoid lies within 2 Å of the deposited "
            "ligand.",
        },
        {
            "type": "content",
            "role": "comparison",
            "variant": "comparison-2col",
            "title": "One perturbed prediction, two views",
            "subtitle": f"{m_pert['protein'].split(' (')[0]}, {EXEC[executor]}, "
            + (
                f"{len(m_pert['mutations'])} contacts to glycine"
                if m_pert["mutations"]
                else f"{len(m_pert['methylated_oxygens'])} hydroxyls methylated"
            ),
            "left": {
                "title": "Score only",
                "bullets": [f"Confidence: {conf}", f"Wild type: {conf_wt}"],
            },
            "right": {"title": "Harness fact file", "bullets": arm_rows(pert)},
            "notes": f"{len(m_pert['mutations'])} contact residues were cut to glycine. The "
            "confidence the model reports and the fact file for the same prediction.",
        },
    ]
    if panels:
        slides.append(
            {
                "type": "content",
                "role": "evidence",
                "variant": "scientific-figure",
                "title": "Medoid poses, wild type and perturbed",
                "subtitle": f"{m_pert['protein'].split(' (')[0]}, {EXEC[executor]}",
                "figures": panels,
                "figure_layout": "panel-grid",
                "caption": "Each panel oriented on its ligand; grey: residues ≤ 5 Å.",
            }
        )
    # Named cases lead: what the perturbation did to each system's pose, by name.
    case_rows = []
    for name, m in ((n, v) for n, v in metas.items() if v["state"] == "pert"):
        sysn = name.removesuffix("_pert")
        f = {(s, e): facts[f"{sysn}_{s}_{e}"] for s in ("wt", "pert") for e in EXEC}
        ref = _v(f[("wt", "boltz2")]["key_interactions_reference"])
        rec = "key_interactions_recovered"
        case_rows.append(
            [
                m["protein"].split(" (")[0],
                f"{_v(f[('wt', 'boltz2')][rec])} / {_v(f[('wt', 'diffdock')][rec])} of {ref}",
                f"{_v(f[('pert', 'boltz2')][rec])} / {_v(f[('pert', 'diffdock')][rec])} of {ref}",
                " / ".join(
                    _v(tr[(f"{sysn}_pert", e)]["rmsd_A"] or None) for e in ("boltz2", "diffdock")
                ),
            ]
        )
    slides += [
        {
            "type": "content",
            "role": "table",
            "variant": "table",
            "title": "What the perturbation did, by system",
            "subtitle": "Deposited contacts the medoid reproduces, wild type against perturbed",
            "table": {
                "headers": [
                    "System",
                    "Wild type contacts",
                    "Perturbed contacts",
                    "Perturbed medoid (Å)",
                ],
                "rows": case_rows,
            },
            "caption": "Each cell Boltz-2 / DiffDock-L. Medoid RMSD is to the deposited ligand; "
            "n/a where the perturbation modifies the ligand.",
            "notes": "Contact recovery is the signal that separates the states. Confidence and "
            "PoseBusters stay clean on the perturbed poses.",
        },
        {
            "type": "content",
            "role": "evidence",
            "variant": "scientific-figure",
            "title": "Decision per prediction",
            "figures": [
                {
                    "path": str(figs / "decisions.png"),
                    "title": "Ground truth and majority verdict per prediction",
                }
            ],
            "figure_layout": "panel-grid",
            "caption": "B2 Boltz-2, DD DiffDock-L. V valid, I invalid.",
            "notes": f"Score only kept {allb['A']['fp']} of {allb['n_invalid']} invalid "
            f"predictions; the fact file arm kept {allb['B']['tp']} of {allb['n_valid']} valid.",
        },
        {
            "type": "content",
            "role": "evidence",
            "variant": "image-sidebar",
            "image_sidebar_mode": "analysis-rail",
            "title": "Aggregate over this run",
            "assets": {"hero_image": str(figs / "balanced_accuracy.png")},
            "sidebar_sections": [
                {"title": "Score only, pooled", "body": _ba(allb["A"])},
                {"title": "Fact file, pooled", "body": _ba(allb["B"])},
                {
                    "title": "McNemar exact p",
                    "body": f"{allb['mcnemar']['p_exact']}; discordant "
                    f"{allb['mcnemar']['b_right_a_wrong']} and "
                    f"{allb['mcnemar']['a_right_b_wrong']}",
                },
            ],
            "caption": f"{allb['n']} predictions; intervals are wide at this size. Invalid kept: "
            f"score only {allb['A']['fp']} of {allb['n_invalid']}, fact file {allb['B']['fp']} "
            f"of {allb['n_invalid']}. Dashed line at 0.5.",
            "notes": "Boltz-2: score only "
            + _ba(stats["arms"]["boltz2"]["A"])
            + ", fact file "
            + _ba(stats["arms"]["boltz2"]["B"])
            + ". DiffDock-L: score only "
            + _ba(stats["arms"]["diffdock"]["A"])
            + ", fact file "
            + _ba(stats["arms"]["diffdock"]["B"])
            + ".",
        },
        {
            "type": "content",
            "role": "comparison",
            "variant": "comparison-2col",
            "title": "What this run does and does not establish",
            "left": {
                "title": "Measured",
                "bullets": [
                    f"{stats['n_predictions']} predictions, 2 executors",
                    "Every prompt and response logged",
                    "Ground truth fixed in advance",
                ],
            },
            "right": {
                "title": "Not established",
                "bullets": [
                    "A significant difference",
                    "Loss of binding (assumed)",
                    "Effect of prompt length",
                ],
            },
            "notes": "Eight systems per executor support a demonstration, not a statistical "
            "claim. A length-matched control arm was not run.",
        },
    ]
    for slide in slides:
        if slide["type"] == "content":
            slide.setdefault("sources", ["S1"])
            slide.setdefault("footer", f"S1: bench/runs/{run.name} (stats.json, facts, renders)")
    return {
        "title": "Perturbation benchmark",
        "deck_style": {
            "style_preset": "lab-report",
            "composition_grammar": "scientific-evidence-plate",
            "style_seed": "pah-perturbation-bench",
            "header_variant": "auto",
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
    print(proc.stdout[-3000:], proc.stderr[-2000:])
    return proc


def bind_review(run: Path, review: Path) -> None:
    """Bind a visual judgment of the rendered slides to the built deck and require it in a strict
    QA pass. The deck is not rebuilt: a rebuild changes its hash and voids the receipt."""

    deck, pptx = run / "deck", run / "results" / "deck.pptx"
    receipt = deck / "visual_review_receipt.json"
    if _skill(
        "visual_review_receipt.py", "create", "--input", str(pptx),
        "--renders-dir", str(deck / "qa" / "renders"), "--review", str(review),
        "--output", str(receipt),
    ).returncode:  # fmt: skip
        sys.exit("visual review receipt not created")
    gate = _skill(
        "qa_gate.py", "--input", str(pptx), "--outline", str(deck / "outline.json"),
        "--outdir", str(deck / "qa_bound"), "--style-preset", "lab-report", "--strict-geometry",
        "--fail-on-geometry-warnings", "--fail-on-whitespace-warnings", "--run-visual-review",
        "--fail-on-visual-review-warnings", "--fail-on-design-warnings", "--accessibility",
        "--strict-accessibility", "--accessibility-min-body-pt", "16",
        "--accessibility-min-support-pt", "13", "--accessibility-min-metadata-pt", "9",
        "--visual-review-receipt", str(receipt), "--require-bound-visual-review",
    )  # fmt: skip
    if gate.returncode:
        sys.exit(f"strict QA with the bound visual review failed; see {deck / 'qa_bound'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--system", default="cdk2")
    ap.add_argument("--executor", default="boltz2")
    ap.add_argument(
        "--review",
        type=Path,
        help="visual_judgment_v1 JSON written after inspecting deck/qa/renders; binds it to the "
        "existing deck instead of building",
    )
    args = ap.parse_args()
    run = REPO / "bench" / "runs" / args.run_id
    if args.review:
        bind_review(run, args.review.resolve())
        return
    deck = run / "deck"
    deck.mkdir(parents=True, exist_ok=True)
    (deck / "outline.json").write_text(
        json.dumps(outline(run, args.system, args.executor), indent=2)
    )
    proc = _skill(
        "present.py", "finalize", "--outline", str(deck / "outline.json"),
        "--output", str(run / "results" / "deck.pptx"), "--qa-dir", str(deck / "qa"),
    )  # fmt: skip
    if proc.returncode:
        sys.exit(f"presentation-skill finalize failed ({proc.returncode}); see {deck / 'qa'}")
    print(f"deck built; inspect {deck / 'qa' / 'renders'} and bind the review with --review")


if __name__ == "__main__":
    main()
