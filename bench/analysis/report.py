"""Write manifest.json and report.md for one benchmark run from its recorded files only.

    python bench/analysis/report.py --run-id <id>

Every number comes from results/stats.json, results/truth.csv, results/decisions.csv, facts/,
prep/*/meta.json and predictions/modal_*.json. The text follows the harness report rules (values,
thresholds with origin, no commentary) and is checked with `pah lint`.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
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


EXEC = {"boltz2": "Boltz-2", "diffdock": "DiffDock-L"}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def manifest(run: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    modal: dict[str, Any] = {}
    for p in sorted((run / "predictions").glob("modal_*.json")):
        modal[p.stem.removeprefix("modal_")] = json.loads(p.read_text())
    images, gpus = {}, set()
    for p in sorted((run / "predictions").glob("*/*/modal.json")):
        job = json.loads(p.read_text())
        images[job["executor"]] = job.get("env", {}).get("MODAL_IMAGE_ID") or job.get("image")
        gpus.add(job.get("gpu", ""))
    settings = run / "agent" / "settings.json"
    agent = json.loads(settings.read_text()) if settings.is_file() else {}
    return {
        "run_id": run.name,
        "git_commit": _git("rev-parse", "--short", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "modal_images": images,
        "gpus": sorted(g for g in gpus if g),
        "model_versions": {
            "boltz2": "2.2.1",
            "diffdock": "v1.1.3 (rbgcsail/diffdock image)",
            "agent": agent.get("model", cfg["agent"]["model"]),
        },
        "seeds": cfg["seeds"],
        "diffdock_samples": cfg["diffdock_samples"],
        "sources": json.loads((run / "prep" / "sources.json").read_text()),
        "modal_jobs": modal,
        "agent": {k: v for k, v in agent.items() if k != "system_prompt"},
    }


def _fmt(x: Any) -> str:
    if x is None or x == "":
        return "n/a"
    if isinstance(x, float):
        return f"{x:.3g}"
    return str(x)


def _ci(block: dict[str, Any]) -> str:
    ci = block.get("ci95")
    return (
        f"{_fmt(block['balanced_accuracy'])} ({ci[0]} to {ci[1]})"
        if ci
        else _fmt(block["balanced_accuracy"])
    )


def report(run: Path, cfg: dict[str, Any], man: dict[str, Any]) -> str:
    stats = json.loads((run / "results" / "stats.json").read_text())
    with (run / "results" / "truth.csv").open() as fh:
        truth = list(csv.DictReader(fh))
    metas = {
        p.parent.name: json.loads(p.read_text()) for p in sorted((run / "prep").glob("*/meta.json"))
    }
    facts = {p.stem: json.loads(p.read_text()) for p in sorted((run / "facts").glob("*.json"))}
    allb = stats["arms"]["all"]
    out: list[str] = []
    w = out.append
    w(f"# Perturbation benchmark, run {run.name}")
    w("")
    w("## Summary")
    w("")
    w(
        "| Scope | Predictions | Score only, balanced accuracy (95% CI) | Fact file, balanced "
        "accuracy (95% CI) | McNemar exact p |"
    )
    w("| --- | --- | --- | --- | --- |")
    for scope, label in (("all", "pooled"), ("boltz2", "Boltz-2"), ("diffdock", "DiffDock-L")):
        b = stats["arms"][scope]
        w(
            f"| {label} | {b['n']} ({b['n_valid']} valid, {b['n_invalid']} invalid) "
            f"| {_ci(b['A'])} | {_ci(b['B'])} | {b['mcnemar']['p_exact']} |"
        )
    w("")
    w(
        f"Decisions are the majority over {man['agent'].get('repeats', cfg['agent']['repeats'])} "
        f"repeats at temperature 0 ({man['model_versions']['agent']}). Agreement across repeats: "
        f"score only {stats['repeat_agreement']['A']}, fact file {stats['repeat_agreement']['B']}. "
        f"Failed agent calls: {stats['call_errors']}. Predictions without ground truth: "
        f"{stats['n_unlabelled']}."
    )
    w("")
    w("## Design")
    w("")
    w(
        "Ground truth by construction: a perturbed system is invalid; a wild-type system is "
        f"valid when the representative pose lies within {stats['cutoff_A']} Å "
        "(symmetry-aware heavy-atom RMSD, spyrmsd) of the deposited ligand. The representative "
        "pose is the medoid of the largest cluster at 2.0 Å over the "
        f"{len(cfg['seeds'])} seeds (harness l5.sampling.clusters). "
        "The RMSD to the deposited ligand is never part of a fact file."
    )
    w("")
    w("| System | Entry | Ligand | Perturbation | Mutated positions |")
    w("| --- | --- | --- | --- | --- |")
    for m in metas.values():
        if m["state"] != "pert":
            continue
        kind = m["perturbation"]["kind"]
        detail = (
            f"{len(m['mutations'])} contacts within {m['contacts_within_A']} Å to glycine"
            if kind == "pocket_to_gly"
            else f"{len(m['methylated_oxygens'])} ring hydroxyls methylated (O2, O3, O4)"
        )
        muts = ", ".join(x["residue"] for x in m["mutations"]) or "none (ligand modified)"
        w(
            f"| {m['protein']} | {m['pdb']} chain {m['chain']} | {m['ligand_code']} | {detail} | "
            f"{muts} |"
        )
    w("")
    w("## Results per prediction")
    w("")
    w("| Prediction | RMSD to deposited ligand (Å) | Truth | Score only | Fact file |")
    w("| --- | --- | --- | --- | --- |")
    for r in truth:
        w(
            f"| {r['system']} · {EXEC[r['executor']]} | {_fmt(r['rmsd_A'])} | {_fmt(r['truth'])} | "
            f"{_fmt(r['arm_A'])} ({r['arm_A_votes']}) | {_fmt(r['arm_B'])} ({r['arm_B_votes']}) |"
        )
    w("")
    w("## Fact file values")
    w("")
    w(
        "| Prediction | Confidence | PoseBusters | Deposited interactions recovered "
        "| Strain (kcal/mol) | Buried unsatisfied polars | Hydrophobic complementarity "
        "| Ensemble spread (Å) | Medoid cluster fraction | Cross-executor RMSD (Å) |"
    )
    w("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for f in facts.values():
        conf = ", ".join(f"{k} {_fmt(v)}" for k, v in f["confidence"].items() if v is not None)
        pb = f["posebusters"]
        w(
            f"| {f['system']} · {EXEC[f['executor']]} | {conf or 'n/a'} | {_fmt(pb['passed'])}/"
            f"{_fmt(pb['total'])} | {_fmt(f['key_interactions_recovered'])}/"
            f"{_fmt(f['key_interactions_reference'])} | {_fmt(f['torsion_strain_kcal'])} | "
            f"{_fmt(f['buried_unsatisfied_polars'])} | {_fmt(f['hydrophobic_complementarity'])} | "
            f"{_fmt(f['ensemble_spread_A'])} | {_fmt(f['medoid_cluster_fraction'])} | "
            f"{_fmt(f['cross_tool_rmsd_A'])} |"
        )
    w("")
    w("## Figures")
    w("")
    for stem, cap in (
        (
            "balanced_accuracy",
            "Balanced accuracy per arm and executor with 95% "
            "bootstrap intervals over predictions; dashed line at 0.5.",
        ),
        ("confusion", f"Confusion matrices, pooled over {allb['n']} predictions."),
        ("decisions", "Ground truth and majority decision per prediction."),
    ):
        w(f"![{cap}](results/figures/{stem}.png)")
        w("")
        w(f"{cap} Data: `results/figures/{stem}.csv`.")
        w("")
    w("## Run record")
    w("")
    w(f"- Commit {man['git_commit']} on {man['branch']}.")
    w(f"- GPUs: {', '.join(man['gpus']) or 'n/a'} on Modal; images {man['modal_images']}.")
    w(
        f"- Executors: Boltz-2 {man['model_versions']['boltz2']}, DiffDock-L "
        f"{man['model_versions']['diffdock']}; seeds {man['seeds']}; DiffDock samples per run "
        f"{man['diffdock_samples']}. DiffDock has no seed option; its seeds label replicate runs."
    )
    w(
        f"- Agent: {man['model_versions']['agent']} through {cfg['agent']['base_url']}; "
        "every prompt and response in `agent/calls.jsonl`."
    )
    w(
        "- Sources: "
        + ", ".join(
            f"{k} sha256 {v['sha256'][:12]}"
            for k, v in man["sources"].items()
            if k.endswith(".cif")
        )
        + "."
    )
    w(
        "- Harness runs per prediction: `harness/<system>_<executor>/run/` "
        "(record, report, renders)."
    )
    w("")
    w("## Limitations")
    w("")
    w(
        "- Eight systems per executor support a demonstration, not a statistical claim; the "
        "intervals above are the measure of that."
    )
    w(
        "- Perturbed systems are negatives by construction, which assumes the perturbation "
        "abolishes binding; the assumption is inherited from the source studies."
    )
    w(
        "- The arms differ in prompt length as well as content; a length-matched control arm was "
        "not run."
    )
    w("- Wild-type ground truth uses the deposited ligand position as the reference pose.")
    w(
        "- The runbook names the glucose ligand GLC; entry 2VWH holds BGC, which was used. The "
        "8X61 FtsE chain A has 7 contacts within 3.5 Å that are not already glycine; the runbook "
        "cites 12 from the source study."
    )
    w("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    run = REPO / "bench" / "runs" / args.run_id
    cfg = run_config(run)
    man = manifest(run, cfg)
    (run / "manifest.json").write_text(json.dumps(man, indent=2))
    text = report(run, cfg, man)
    (run / "report.md").write_text(text)
    lint = subprocess.run(
        [str(REPO / ".venv/bin/pah"), "lint", str(run / "report.md")],
        capture_output=True,
        text=True,
    )
    print(lint.stdout.strip())
    print(run / "report.md")


if __name__ == "__main__":
    main()
