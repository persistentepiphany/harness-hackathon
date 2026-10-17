"""Both agent arms against GLM through the Z.AI endpoint (OpenAI-compatible).

    python bench/agent/decide.py --run-id <id> [--model glm-4.6] [--repeats 3]

Arm A sees the confidence score only; arm B sees the harness fact file. Prompts are the runbook's
templates, filled from facts/*.json; neither arm is told whether a system is perturbed or given
the deposited structure. Calls run in a shuffled order (seeded, recorded) at temperature 0, three
repeats per decision. Every prompt and response is written verbatim to agent/calls.jsonl and the
parsed decisions to results/decisions.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

REPO = Path(__file__).resolve().parents[2]


def run_config(run: Path) -> dict[str, Any]:
    """The run's own copy of the design when it has one (bench/run_pipeline.py writes it),
    otherwise bench/config/targets.yaml."""

    own = run / "config" / "targets.yaml"
    return dict(
        yaml.safe_load((own if own.is_file() else REPO / "bench/config/targets.yaml").read_text())
    )


SYSTEM_PROMPT = """You are assessing whether a predicted protein-ligand pose should be
trusted as evidence that this ligand binds this protein in this
orientation.

Answer with JSON only:
{"verdict": "valid" | "invalid", "confidence": 0.0-1.0, "reason": "<one sentence>"}

"valid" means the pose is credible evidence of binding.
"invalid" means it is not, whether because the pose is implausible or
because the evidence does not support the claim.

Do not hedge. Choose one verdict."""

ARM_A = """System: {system_id}
Executor: {executor}
Confidence score: {confidence}

(For Boltz-2 this is the ligand ipTM and the pocket pLDDT.
 For DiffDock-L this is the model confidence of the top-ranked pose.)"""

ARM_B = """System: {system_id}
Executor: {executor}
Confidence score: {confidence}

Physical validity (PoseBusters): {posebusters_summary}
Failed checks: {posebusters_failed}

Interaction fingerprint of the predicted pose: {interactions}
Interaction fingerprint seen in deposited complexes of this pocket: {interactions_reference}
Interactions recovered: {n_recovered} of {n_reference}

Ligand torsional strain: {torsion_strain_kcal} kcal/mol
Buried polar atoms without a hydrogen-bond partner: {buried_unsatisfied_polars}
Hydrophobic complementarity: {hydrophobic_complementarity}

Ensemble over {n_seeds} seeds:
  pairwise RMSD spread: {ensemble_spread_A}
  medoid cluster holds {medoid_cluster_fraction} of samples

Cross-executor agreement: {cross_tool_rmsd}

Notes:
- Confidence scores from these models have been shown to remain high for
  physically implausible poses, so confidence alone does not establish validity.
- A pose recovering none of the interactions observed in deposited complexes
  of the same pocket warrants scrutiny even when its geometry is sound."""

EXECUTOR_NAMES = {"boltz2": "Boltz-2", "diffdock": "DiffDock-L"}


def _v(x: Any) -> str:
    if x is None:
        return "not computed"
    if isinstance(x, float):
        return f"{x:.3g}"
    if isinstance(x, list):
        return ", ".join(map(str, x)) if x else "none"
    return str(x)


def _unit(x: Any, unit: str) -> str:
    return "not computed" if x is None else f"{_v(x)} {unit}"


def _fraction(facts: dict[str, Any]) -> str:
    frac, n = facts.get("medoid_cluster_fraction"), facts.get("ensemble_poses")
    if frac is None or not n:
        return "not computed"
    return f"{frac:.2f} ({round(frac * n)} of {n})"


def blind_id(system: str) -> str:
    """The system name without its state suffix, so the prompt does not reveal the perturbation."""
    return system.rsplit("_", 1)[0]


def confidence_text(facts: dict[str, Any]) -> str:
    c = facts["confidence"]
    if facts["executor"] == "boltz2":
        return f"ligand ipTM {_v(c.get('ligand_iptm'))}, pocket pLDDT {_v(c.get('pocket_plddt'))}"
    return f"{_v(c.get('diffdock_confidence'))}"


def prompt(arm: str, facts: dict[str, Any]) -> str:
    base = {
        "system_id": blind_id(facts["system"]),
        "executor": EXECUTOR_NAMES[facts["executor"]],
        "confidence": confidence_text(facts),
    }
    if arm == "A":
        return ARM_A.format(**base)
    pb = facts["posebusters"]
    return ARM_B.format(
        **base,
        posebusters_summary=f"{_v(pb.get('passed'))} of {_v(pb.get('total'))} tests pass",
        posebusters_failed=_v(pb.get("failed")),
        interactions=_v(facts["interactions"]),
        interactions_reference=_v(facts["interactions_reference"]),
        n_recovered=_v(facts["key_interactions_recovered"]),
        n_reference=_v(facts["key_interactions_reference"]),
        torsion_strain_kcal=_v(facts["torsion_strain_kcal"]),
        buried_unsatisfied_polars=_v(facts["buried_unsatisfied_polars"]),
        hydrophobic_complementarity=_v(facts["hydrophobic_complementarity"]),
        n_seeds=_v(facts["n_seeds"]),
        ensemble_spread_A=_unit(facts["ensemble_spread_A"], "A"),
        medoid_cluster_fraction=_fraction(facts),
        cross_tool_rmsd=_unit(facts["cross_tool_rmsd_A"], "A RMSD between the executors' medoids"),
    )


def call(client: httpx.Client, base_url: str, model: str, user: str) -> dict[str, Any]:
    body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    for attempt in range(8):
        r = client.post(
            f"{base_url}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {os.environ['ZAI_API_KEY']}"},
        )
        if r.status_code == 200:
            return {"request": body, "response": r.json(), "attempts": attempt + 1}
        # 429 is the endpoint's request rate limit: wait longer each time, up to a minute.
        time.sleep(min(60, 5 * 2**attempt) if r.status_code == 429 else 2 ** (attempt + 1))
    return {"request": body, "error": f"HTTP {r.status_code}: {r.text[:500]}"}


def parse(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    data = json.loads(text[start : end + 1])
    verdict = str(data.get("verdict", "")).lower()
    if verdict not in ("valid", "invalid"):
        raise ValueError(f"verdict {verdict!r}")
    return {"verdict": verdict, "confidence": data.get("confidence"), "reason": data.get("reason")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--repeats", type=int, default=None)
    ap.add_argument("--order-seed", type=int, default=20261017)
    ap.add_argument("--workers", type=int, default=4, help="concurrent calls")
    args = ap.parse_args()
    cfg = run_config(REPO / "bench" / "runs" / args.run_id)["agent"]
    model = args.model or cfg["model"]
    repeats = args.repeats or int(cfg["repeats"])
    run = REPO / "bench" / "runs" / args.run_id
    facts = {p.stem: json.loads(p.read_text()) for p in sorted((run / "facts").glob("*.json"))}
    jobs = [(name, arm, rep) for name in facts for arm in ("A", "B") for rep in range(repeats)]
    random.Random(args.order_seed).shuffle(jobs)
    (run / "agent").mkdir(parents=True, exist_ok=True)
    (run / "results").mkdir(parents=True, exist_ok=True)
    import threading
    from concurrent.futures import ThreadPoolExecutor

    rows: list[dict[str, Any]] = []
    lock = threading.Lock()
    done = [0]

    def one(client: httpx.Client, log: Any, i: int, name: str, arm: str, rep: int) -> None:
        f = facts[name]
        res = call(client, cfg["base_url"], model, prompt(arm, f))
        entry = {
            "i": i,
            "name": name,
            "system": f["system"],
            "executor": f["executor"],
            "arm": arm,
            "repeat": rep,
            **res,
        }
        row = {
            "system": f["system"],
            "executor": f["executor"],
            "arm": arm,
            "repeat": rep,
            "verdict": "",
            "confidence": "",
            "reason": "",
            "error": "",
        }
        try:
            row.update(parse(res["response"]["choices"][0]["message"]["content"]))
        except Exception as exc:  # recorded per call; the run continues
            row["error"] = res.get("error") or f"{type(exc).__name__}: {exc}"
        entry["parsed"] = row
        with lock:
            log.write(json.dumps(entry) + "\n")
            log.flush()
            rows.append(row)
            done[0] += 1
            print(
                f"{done[0]}/{len(jobs)} {name} arm {arm} r{rep}: {row['verdict'] or row['error']}",
                flush=True,
            )

    # Calls are submitted in the shuffled order; with several workers they complete out of order,
    # and each log entry keeps its submission index `i`.
    with (
        httpx.Client(timeout=300) as client,
        (run / "agent" / "calls.jsonl").open("w") as log,
        ThreadPoolExecutor(max_workers=args.workers) as pool,
    ):
        for fut in [pool.submit(one, client, log, i, *job) for i, job in enumerate(jobs)]:
            fut.result()
    with (run / "results" / "decisions.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["system"], r["executor"], r["arm"], r["repeat"])))
    (run / "agent" / "settings.json").write_text(
        json.dumps(
            {
                "model": model,
                "base_url": cfg["base_url"],
                "temperature": 0,
                "repeats": repeats,
                "order_seed": args.order_seed,
                "workers": args.workers,
                "calls": len(jobs),
                "system_prompt": SYSTEM_PROMPT,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
