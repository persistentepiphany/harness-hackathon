"""Run the harness on every prediction and write one fact file per prediction.

    python bench/checks/run_checks.py --run-id <id> [--no-report]

For each system and primary executor this writes a manifest (task ligand_pose, layers 2 to 5,
the other executor as secondary so cross-executor agreement is measured), runs the harness, and
reduces the run record to `facts/<system>_<executor>.json` holding only what the agent may see:
confidence, PoseBusters, interactions against the deposited complex, strain, buried polars,
hydrophobic complementarity, ensemble spread and cross-executor agreement. The RMSD of the pose
to the deposited ligand is written separately to `truth/` and never enters a fact file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
EXECUTORS = ("boltz2", "diffdock")
LAYERS = (2, 3, 4, 5)


def manifest(run: Path, system: str, primary: str, seeds: list[int]) -> dict[str, Any]:
    meta = json.loads((run / "prep" / system / "meta.json").read_text())
    preds = []
    for executor in (primary, *[e for e in EXECUTORS if e != primary]):
        out = run / "predictions" / system / executor
        if not out.is_dir():
            continue
        entry: dict[str, Any] = {
            "executor": executor,
            "path": str(out),
            "ligand": "ligand",
            "role": "primary" if executor == primary else "secondary",
            "seeds": seeds,
        }
        if executor == "diffdock":
            entry["receptor"] = str(run / "prep" / system / "rec.pdb")
        preds.append(entry)
    return {
        "task": "ligand_pose",
        "claim": f"Predicted pose of {meta['ligand_code']} in {meta['protein']} is valid",
        "ph": 7.4,
        "proteins": [{"id": "protein", "sequence": meta["sequence"]}],
        "ligands": [{"id": "ligand", "smiles": meta["ligand_smiles"]}],
        "receptor": {"pdb_id": meta["pdb"], "chains": [meta["chain"]]},
        "reference": {
            "pdb_id": meta["pdb"],
            "ligand": meta["ligand_code"],
            "chain": meta["chain"],
        },
        "model": {
            "executor": primary,
            "version": "2.2.1" if primary == "boltz2" else "v1.1.3",
            "checkpoint": "boltz2_conf.ckpt" if primary == "boltz2" else "diffdock-l",
            "database_snapshot": "colabfold_msa_server" if primary == "boltz2" else None,
            "seeds": seeds,
        },
        "predictions": preds,
    }


def _f(record: Any, check: str) -> Any:
    return next((f for f in record.findings if f.check_id == check), None)


def _m(finding: Any) -> dict[str, Any]:
    return {m.name: m.value for m in finding.measurements} if finding else {}


def fact_file(record: Any, primary: str, n_seeds: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """(facts the agent may read, ground-truth measurements kept apart)."""
    conf = _f(record, "l5.confidence.local")
    rep = conf.evidence.get("representative") if conf else None
    rows = {r["pose"]: r for r in (conf.evidence.get("poses", []) if conf else [])}
    rr = rows.get(rep, {})
    if primary == "boltz2":
        confidence = {
            "ligand_iptm": rr.get("ligand_iptm"),
            "pocket_plddt": rr.get("pocket_plddt"),
            "confidence_score": rr.get("confidence_score"),
        }
    else:
        confidence = {"diffdock_confidence": rr.get("diffdock_confidence")}
    pb = _f(record, "l4.posebusters")
    fp = _f(record, "l4.interactions.fingerprint")
    kb = _f(record, "l4.interactions.known_binders")
    tor = _f(record, "l4.torsion_strain")
    unsat = _f(record, "l4.interactions.unsatisfied_polars")
    hyd = _f(record, "l4.interactions.hydrophobic")
    cl = _f(record, "l5.sampling.clusters")
    ag = _f(record, "l5.agreement.cross_family")
    rep_inter = fp.evidence.get("per_pose", {}).get(rep, []) if fp else []
    cross = [
        c
        for c in (ag.evidence.get("comparisons", []) if ag else [])
        if c.get("weight") != "decisive"
    ]
    crystal = [
        c
        for c in (ag.evidence.get("comparisons", []) if ag else [])
        if c.get("weight") == "decisive" and c.get("method") == primary
    ]
    clm = _m(cl)
    facts = {
        "executor": primary,
        "representative_pose": rep,
        "confidence": confidence,
        "posebusters": {
            "passed": _m(pb).get("passed"),
            "total": _m(pb).get("total"),
            "failed": next(
                (r["failed"] for r in pb.evidence.get("poses", []) if r["pose"] == rep), []
            )
            if pb
            else None,
        },
        "interactions": sorted({f"{r['type']} {r['residue']}" for r in rep_inter}),
        "interactions_reference": sorted(
            {
                f"{r['type']} {r['residue']}"
                for r in (kb.evidence.get("reference_interactions", []) if kb else [])
            }
        ),
        "key_interactions_recovered": _m(kb).get("reproduced"),
        "key_interactions_reference": _m(kb).get("key_interactions"),
        "torsion_strain_kcal": _m(tor).get("strain_kcal"),
        "unlikely_torsions": _m(tor).get("unlikely_torsions"),
        "buried_unsatisfied_polars": _m(unsat).get("unsatisfied"),
        "buried_charged_unsatisfied": _m(unsat).get("buried_charged"),
        "hydrophobic_complementarity": _m(hyd).get("complementarity"),
        "n_seeds": n_seeds,
        "ensemble_poses": clm.get("poses"),
        "ensemble_spread_A": clm.get("pairwise_rmsd_median_A"),
        "medoid_cluster_fraction": round(clm["largest_cluster"] / clm["poses"], 3)
        if clm.get("poses")
        else None,
        "cross_tool_rmsd_A": cross[0]["value"] if cross else None,
        "harness_gates": {
            f.check_id: f.gate.value for f in record.findings if int(f.layer) in (4, 5)
        },
    }
    truth = {
        "rmsd_to_deposited_A": crystal[0]["value"] if crystal else None,
        "representative_pose": rep,
    }
    return facts, truth


def main() -> None:
    from pah.config import load_profile
    from pah.core.events import JsonlSink
    from pah.service import RunOptions, run_manifest

    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--no-report", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=1, help="parallel harness runs (subprocesses)")
    args = ap.parse_args()
    if args.jobs > 1:
        return _parallel(args)
    run = REPO / "bench" / "runs" / args.run_id
    cfg = yaml.safe_load((REPO / "bench/config/targets.yaml").read_text())
    seeds = list(cfg["seeds"])
    profile = load_profile("local")
    (run / "facts").mkdir(parents=True, exist_ok=True)
    (run / "truth").mkdir(parents=True, exist_ok=True)
    (run / "harness").mkdir(parents=True, exist_ok=True)
    systems = sorted(p.name for p in (run / "prep").iterdir() if (p / "meta.json").is_file())
    for system in systems:
        for primary in EXECUTORS:
            name = f"{system}_{primary}"
            if args.only and name not in args.only.split(","):
                continue
            if not (run / "predictions" / system / primary).is_dir():
                print(f"{name}: no predictions, skipped", flush=True)
                continue
            mdir = run / "harness" / name
            mdir.mkdir(parents=True, exist_ok=True)
            data = manifest(run, system, primary, seeds)
            (mdir / "manifest.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
            options = RunOptions(layers=LAYERS, halt=False, report=not args.no_report)
            result = run_manifest(
                mdir / "manifest.yaml",
                profile,
                options,
                [JsonlSink(mdir / "console.jsonl")],
                run_dir=mdir / "run",
            )
            facts, truth = fact_file(result.record, primary, len(seeds))
            facts["system"] = system
            truth["system"] = system
            truth["verdict"] = (
                result.record.verdict.outcome.value if result.record.verdict else None
            )
            (run / "facts" / f"{name}.json").write_text(json.dumps(facts, indent=2))
            (run / "truth" / f"{name}.json").write_text(json.dumps(truth, indent=2))
            print(
                f"{name}: verdict={truth['verdict']} rmsd={truth['rmsd_to_deposited_A']} "
                f"pb={facts['posebusters']['passed']}/{facts['posebusters']['total']} "
                f"recovered={facts['key_interactions_recovered']}/"
                f"{facts['key_interactions_reference']}",
                flush=True,
            )


def _parallel(args: argparse.Namespace) -> None:
    """One subprocess per prediction, `--jobs` at a time; output lines are passed through."""
    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    run = REPO / "bench" / "runs" / args.run_id
    names = [
        f"{p.name}_{e}"
        for p in sorted((run / "prep").iterdir())
        if (p / "meta.json").is_file()
        for e in EXECUTORS
        if (run / "predictions" / p.name / e).is_dir()
    ]
    if args.only:
        names = [n for n in names if n in args.only.split(",")]

    def one(name: str) -> str:
        cmd = [sys.executable, __file__, "--run-id", args.run_id, "--only", name]
        if args.no_report:
            cmd.append("--no-report")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        line = (proc.stdout.strip().splitlines() or [f"{name}: no output"])[-1]
        if proc.returncode:
            line += f" (exit {proc.returncode}: {proc.stderr.strip().splitlines()[-1:]})"
        print(line, flush=True)
        return line

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(one, names))


if __name__ == "__main__":
    main()
