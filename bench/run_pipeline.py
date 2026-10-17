"""Run the whole perturbation benchmark once and record its scores.

    python bench/run_pipeline.py --seeds 4,5,6            # a new run with its own seeds
    python bench/run_pipeline.py --run-id <id> --from checks   # resume an existing run

Writes the run's design to runs/<id>/config/targets.yaml (targets.yaml with the given seeds), then
runs prep, Modal predictions, harness checks, agent decisions, scoring, the report, the deck and
the video, and appends one row per scope to bench/scores.csv. A failing stage stops the run and is
recorded in runs/<id>/pipeline.json; nothing is scored from a partial run.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
PY = str(REPO / ".venv" / "bin" / "python")
MODAL = str(REPO / ".venv" / "bin" / "modal")
STAGES = ("prep", "predict", "checks", "agent", "score", "report", "deck", "video")


def commands(run_id: str, run: Path) -> dict[str, list[list[str]]]:
    app = "bench/modal/perturbation_app.py"
    return {
        "prep": [
            [
                PY,
                "bench/prep/fetch_and_perturb.py",
                "--config",
                str(run / "config" / "targets.yaml"),
                "--out",
                str(run / "prep"),
            ]
        ],
        "predict": [
            [MODAL, "run", f"{app}::predict_all", "--run-id", run_id],
            [MODAL, "run", f"{app}::fetch_all", "--run-id", run_id],
        ],
        "checks": [[PY, "bench/checks/run_checks.py", "--run-id", run_id, "--jobs", "3"]],
        "agent": [[PY, "bench/agent/decide.py", "--run-id", run_id]],
        "score": [[PY, "bench/analysis/score.py", "--run-id", run_id]],
        "report": [[PY, "bench/analysis/report.py", "--run-id", run_id]],
        "deck": [[PY, "bench/analysis/deck.py", "--run-id", run_id]],
        "video": [[PY, "bench/analysis/render_frames.py", "--run-id", run_id]],
    }


def record_scores(run: Path) -> None:
    stats = json.loads((run / "results" / "stats.json").read_text())
    cfg = yaml.safe_load((run / "config" / "targets.yaml").read_text())
    path = REPO / "bench" / "scores.csv"
    new = not path.is_file()
    with path.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(
                [
                    "run_id",
                    "recorded",
                    "seeds",
                    "scope",
                    "n",
                    "score_only_ba",
                    "score_only_ci",
                    "fact_file_ba",
                    "fact_file_ci",
                    "mcnemar_p",
                    "agent_model",
                    "repeat_agreement_a",
                    "repeat_agreement_b",
                ]
            )
        for scope, block in stats["arms"].items():
            w.writerow(
                [
                    run.name,
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    " ".join(map(str, cfg["seeds"])),
                    scope,
                    block["n"],
                    block["A"]["balanced_accuracy"],
                    block["A"]["ci95"],
                    block["B"]["balanced_accuracy"],
                    block["B"]["ci95"],
                    block["mcnemar"]["p_exact"],
                    cfg["agent"]["model"],
                    stats["repeat_agreement"]["A"],
                    stats["repeat_agreement"]["B"],
                ]
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--from", dest="start", default="prep", choices=STAGES)
    ap.add_argument("--to", dest="stop", default="video", choices=STAGES)
    args = ap.parse_args()
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()
    run_id = args.run_id or f"{datetime.now(UTC):%Y-%m-%dT%H%MZ}-{commit}"
    run = REPO / "bench" / "runs" / run_id
    (run / "config").mkdir(parents=True, exist_ok=True)
    own = run / "config" / "targets.yaml"
    if not own.is_file():
        cfg = yaml.safe_load((REPO / "bench" / "config" / "targets.yaml").read_text())
        if args.seeds:
            cfg["seeds"] = [int(s) for s in args.seeds.split(",")]
        own.write_text(yaml.safe_dump(cfg, sort_keys=False))
    env = dict(os.environ)
    env.setdefault("MODAL_TOKEN_ID", env.get("MODAL_API_TOKEN_ID", ""))
    env.setdefault("MODAL_TOKEN_SECRET", env.get("MODAL_API_TOKEN_SECRET", ""))
    log_path = run / "pipeline.json"
    log = (
        json.loads(log_path.read_text()) if log_path.is_file() else {"run_id": run_id, "stages": []}
    )
    stages = STAGES[STAGES.index(args.start) : STAGES.index(args.stop) + 1]
    for stage in stages:
        for cmd in commands(run_id, run)[stage]:
            t0 = time.time()
            print(f"[{stage}] {' '.join(cmd)}", flush=True)
            proc = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
            (run / "logs").mkdir(exist_ok=True)
            (run / "logs" / f"{stage}.log").open("a").write(proc.stdout + proc.stderr)
            entry = {
                "stage": stage,
                "cmd": cmd[1:],
                "rc": proc.returncode,
                "seconds": round(time.time() - t0, 1),
            }
            log["stages"].append(entry)
            log_path.write_text(json.dumps(log, indent=2))
            print(f"[{stage}] exit {proc.returncode} in {entry['seconds']} s", flush=True)
            if proc.returncode:
                sys.exit(f"{stage} failed; see {run / 'logs' / (stage + '.log')}")
        if stage == "score":
            record_scores(run)
    print(run)


if __name__ == "__main__":
    main()
