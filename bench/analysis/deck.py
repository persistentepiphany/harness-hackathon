"""Slide deck for one benchmark run, built with .claude/skills/presentation-skill.

    python bench/analysis/deck.py --run-id <id> [--system cdk2] [--executor boltz2]

Writes <run>/deck/outline.json from results/stats.json, the fact files and the renders, then runs
the skill's `present.py finalize` (build, render, QA) to <run>/results/deck.pptx. Every number on a
slide is read from the run's files; speaker notes hold the longer explanation (human-pace: at most
about 30 words of body text per slide).
"""

from __future__ import annotations

import argparse
import json
import subprocess
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
    wt = json.loads((run / "facts" / f"{system}_wt_{executor}.json").read_text())
    pert = json.loads((run / "facts" / f"{system}_pert_{executor}.json").read_text())
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
            "title": f"One perturbed prediction, two views ({m_pert['protein'].split(' (')[0]}, "
            f"{EXEC[executor]})",
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
                "title": "The ligand stays in a pocket whose contacts are gone",
                "figures": panels,
                "figure_layout": "panel-grid",
                "caption": "PyMOL renders of the medoid poses, same view per panel.",
            }
        )
    slides += [
        {
            "type": "content",
            "role": "table",
            "variant": "table",
            "title": "Confusion counts, pooled over both executors",
            "table": {
                "headers": [
                    "Arm",
                    "Valid kept",
                    "Valid rejected",
                    "Invalid kept",
                    "Invalid rejected",
                ],
                "rows": [
                    [
                        "Score only",
                        str(allb["A"]["tp"]),
                        str(allb["A"]["fn"]),
                        str(allb["A"]["fp"]),
                        str(allb["A"]["tn"]),
                    ],
                    [
                        "Fact file",
                        str(allb["B"]["tp"]),
                        str(allb["B"]["fn"]),
                        str(allb["B"]["fp"]),
                        str(allb["B"]["tn"]),
                    ],
                ],
            },
            "caption": f"{allb['n']} predictions ({allb['n_valid']} valid, {allb['n_invalid']} "
            "invalid); majority verdict over three repeats.",
        },
        {
            "type": "content",
            "role": "evidence",
            "variant": "image-sidebar",
            "image_sidebar_mode": "analysis-rail",
            "title": "Balanced accuracy with 95% intervals",
            "assets": {"hero_image": str(figs / "balanced_accuracy.png")},
            "sidebar_sections": [
                {
                    "title": "Pooled",
                    "body": f"Score only {_ba(allb['A'])}; fact file {_ba(allb['B'])}",
                },
                {
                    "title": "McNemar",
                    "body": f"Exact p {allb['mcnemar']['p_exact']} "
                    f"({allb['mcnemar']['b_right_a_wrong']} for, "
                    f"{allb['mcnemar']['a_right_b_wrong']} against)",
                },
            ],
            "caption": "Bootstrap over predictions; dashed line at 0.5.",
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
            "role": "evidence",
            "variant": "scientific-figure",
            "title": "Decision per prediction",
            "figures": [{"path": str(figs / "decisions.png"), "label": "A"}],
            "figure_layout": "panel-grid",
            "caption": "B2 Boltz-2, DD DiffDock-L. V valid, I invalid.",
            "notes": f"Score only kept {allb['A']['fp']} of {allb['n_invalid']} invalid "
            f"predictions; the fact file arm kept {allb['B']['tp']} of {allb['n_valid']} valid.",
        },
        {
            "type": "content",
            "role": "comparison",
            "variant": "comparison-2col",
            "title": "What this run does and does not establish",
            "left": {
                "title": "Measured",
                "bullets": [
                    f"{stats['n_predictions']} predictions of 4 systems, 2 executors",
                    "Every prompt and response recorded",
                    "Ground truth fixed before any decision",
                ],
            },
            "right": {
                "title": "Not established",
                "bullets": [
                    "A statistical difference between arms",
                    "Binding loss beyond the source studies",
                    "Effect of prompt length alone",
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--system", default="cdk2")
    ap.add_argument("--executor", default="boltz2")
    args = ap.parse_args()
    run = REPO / "bench" / "runs" / args.run_id
    deck = run / "deck"
    deck.mkdir(parents=True, exist_ok=True)
    (deck / "outline.json").write_text(
        json.dumps(outline(run, args.system, args.executor), indent=2)
    )
    cmd = [
        "python3",
        str(SKILL / "scripts" / "python_runtime.py"),
        str(SKILL / "scripts" / "present.py"),
        "finalize",
        "--outline",
        str(deck / "outline.json"),
        "--output",
        str(run / "results" / "deck.pptx"),
        "--qa-dir",
        str(deck / "qa"),
    ]
    proc = subprocess.run(cmd, cwd=SKILL, capture_output=True, text=True)
    print(proc.stdout[-3000:], proc.stderr[-2000:])


if __name__ == "__main__":
    main()
