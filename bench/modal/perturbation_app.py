"""Boltz-2 and DiffDock-L for the perturbation benchmark on Modal GPUs.

    modal run bench/modal/perturbation_app.py::probe                 # images and GPU
    modal run bench/modal/perturbation_app.py::predict_all --run-id <id>

Images come from configs/runtimes.yaml through pah.runtimes, the same stock routes `pah runtimes`
uses: Boltz-2 2.2.1 from its pip pin, DiffDock-L from the digest-pinned rbgcsail/diffdock image.
Weights are cached in the `pah-weights` volume. Every system runs in its own container, so wall
time is set by the slowest prediction. Outputs come back as tarballs and are unpacked into
bench/runs/<id>/predictions/<system>/<executor>/ with modal.json recording image ids, GPU, seeds,
commands and durations.
"""

from __future__ import annotations

import io
import json
import shlex
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any

import modal

SYSTEM_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
GPU = "A100"

if modal.is_local():
    # Image recipes are resolved from configs/runtimes.yaml on the machine that launches the app;
    # containers receive the values they need as environment variables.
    REPO = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(REPO / "src"))
    from pah.runtimes.images import native_steps
    from pah.runtimes.registry import load_runtimes

    _reg = load_runtimes(REPO / "configs")
    _boltz, _dd = _reg.get("boltz2"), _reg.get("diffdock")
    _base, _steps = native_steps(_reg, _boltz)
    assert _boltz.native is not None and _dd.native is not None and _dd.native.image is not None
    BENCH_ENV = {
        "BENCH_BOLTZ_VERSION": str(_boltz.native.version),
        "BENCH_BOLTZ_PIP": " ".join(_boltz.native.pip),
        "BENCH_DD_VERSION": str(_dd.native.version),
        "BENCH_DD_REF": str(_dd.native.image.pull).removeprefix("docker.io/"),
        "BENCH_DD_DIR": str(_dd.native.image.workdir or "/home/appuser/DiffDock"),
    }
else:
    import os

    REPO = Path("/root")
    _base, _steps = "unused", ["true"]
    BENCH_ENV = {k: v for k, v in os.environ.items() if k.startswith("BENCH_")}

DD_REF = BENCH_ENV.get("BENCH_DD_REF", "unused")
DD_DIR = BENCH_ENV.get("BENCH_DD_DIR", "/home/appuser/DiffDock")
MICROMAMBA = "/home/appuser/bin/micromamba"
boltz_image = (
    modal.Image.from_registry(_base, add_python="3.11")
    .run_commands(*_steps)
    .env({"PATH": "/opt/executor/bin:" + SYSTEM_PATH, "BOLTZ_CACHE": "/weights/boltz", **BENCH_ENV})
)
diffdock_image = modal.Image.from_registry(DD_REF, add_python="3.11").env(
    {"TORCH_HOME": "/weights/torch", "HOME": "/weights/home", **BENCH_ENV}
)

weights = modal.Volume.from_name("pah-weights", create_if_missing=True)
app = modal.App("pah-perturbation-bench")


def _run(argv: list[str], cwd: str | None = None) -> dict[str, Any]:
    print("+", shlex.join(argv), flush=True)
    t0 = time.time()
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    tail = (proc.stdout + proc.stderr)[-4000:]
    print(tail, flush=True)
    return {
        "argv": argv,
        "rc": proc.returncode,
        "seconds": round(time.time() - t0, 1),
        "tail": tail,
    }


def _tar(root: Path) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for p in sorted(root.rglob("*")):
            if p.is_file() and "processed" not in p.parts:
                tf.add(p, arcname=str(p.relative_to(root)))
    return buf.getvalue()


def _env() -> dict[str, str]:
    import os

    return {k: os.environ.get(k, "") for k in ("MODAL_IMAGE_ID", "MODAL_TASK_ID", "MODAL_REGION")}


def _gpu() -> str:
    proc = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


@app.function(image=boltz_image, gpu=GPU, timeout=3600, volumes={"/weights": weights})
def boltz_predict(system: str, yaml_text: str, seeds: list[int]) -> dict[str, Any]:
    import yaml

    work = Path("/tmp/boltz") / system
    work.mkdir(parents=True, exist_ok=True)
    doc = yaml.safe_load(yaml_text)
    runs = []
    msa: Path | None = None
    for seed in seeds:
        inp = work / f"{system}.yaml"
        if msa is not None:
            for entry in doc["sequences"]:
                if "protein" in entry:
                    entry["protein"]["msa"] = str(msa)
        inp.write_text(yaml.safe_dump(doc, sort_keys=False))
        out = work / f"seed_{seed}"
        argv = [
            "boltz",
            "predict",
            str(inp),
            "--out_dir",
            str(out),
            "--model",
            "boltz2",
            "--cache",
            "/weights/boltz",
            "--seed",
            str(seed),
            "--diffusion_samples",
            "1",
            "--write_full_pae",
            "--output_format",
            "mmcif",
            "--override",
        ]
        if msa is None:
            argv.append("--use_msa_server")
        runs.append({"seed": seed, **_run(argv)})
        weights.commit()
        if msa is None:
            found = sorted(out.glob("boltz_results_*/msa/*.csv"))
            msa = found[0] if found else None
        (work / f"seed_{seed}" / "input.yaml").write_text(inp.read_text())
    return {
        "system": system,
        "executor": "boltz2",
        "version": BENCH_ENV.get("BENCH_BOLTZ_VERSION"),
        "runs": runs,
        "gpu": _gpu(),
        "env": _env(),
        "tar": _tar(work),
    }


@app.function(image=diffdock_image, gpu=GPU, timeout=3600, volumes={"/weights": weights})
def diffdock_predict(
    system: str, receptor_pdb: bytes, smiles: str, replicates: list[int], samples: int
) -> dict[str, Any]:
    Path("/weights/torch").mkdir(parents=True, exist_ok=True)
    Path("/weights/home").mkdir(parents=True, exist_ok=True)
    work = Path("/tmp/diffdock") / system
    work.mkdir(parents=True, exist_ok=True)
    rec = work / "rec.pdb"
    rec.write_bytes(receptor_pdb)
    runs = []
    for rep in replicates:
        out = work / f"seed_{rep}"
        argv = [
            MICROMAMBA,
            "run",
            "-n",
            "diffdock",
            "python",
            "-m",
            "inference",
            "--config",
            "default_inference_args.yaml",
            "--protein_path",
            str(rec),
            "--ligand_description",
            smiles,
            "--complex_name",
            system,
            "--out_dir",
            str(out),
            "--samples_per_complex",
            str(samples),
        ]
        runs.append({"replicate": rep, **_run(argv, cwd=DD_DIR)})
        weights.commit()
    return {
        "system": system,
        "executor": "diffdock",
        "version": BENCH_ENV.get("BENCH_DD_VERSION"),
        "image": DD_REF,
        "runs": runs,
        "gpu": _gpu(),
        "env": _env(),
        "tar": _tar(work),
    }


@app.function(image=diffdock_image, gpu=GPU, timeout=900, volumes={"/weights": weights})
def probe_diffdock() -> dict[str, Any]:
    return {
        "which": _run(
            [
                "bash",
                "-lc",
                "which micromamba; micromamba env list; ls "
                + DD_DIR
                + "; ls "
                + DD_DIR
                + "/workdir || true",
            ]
        ),
        "gpu": _gpu(),
    }


@app.function(image=boltz_image, gpu=GPU, timeout=900, volumes={"/weights": weights})
def probe_boltz() -> dict[str, Any]:
    return {"boltz": _run(["boltz", "--help"]), "gpu": _gpu()}


@app.local_entrypoint()
def probe() -> None:
    for fn in (probe_boltz, probe_diffdock):
        res = fn.remote()
        print(json.dumps(res, indent=2)[:3000])


@app.local_entrypoint()
def predict_all(run_id: str, only: str = "") -> None:
    import yaml

    run = REPO / "bench" / "runs" / run_id
    prep = run / "prep"
    cfg = yaml.safe_load((REPO / "bench/config/targets.yaml").read_text())
    seeds = list(cfg["seeds"])
    systems = sorted(p.parent.name for p in prep.glob("*/boltz.yaml"))
    if only:
        systems = [s for s in systems if s in only.split(",")]
    handles = []
    for s in systems:
        d = prep / s
        handles.append(boltz_predict.spawn(s, (d / "boltz.yaml").read_text(), seeds))
        handles.append(
            diffdock_predict.spawn(
                s,
                (d / "rec.pdb").read_bytes(),
                (d / "ligand.smi").read_text().strip(),
                seeds,
                int(cfg["diffdock_samples"]),
            )
        )
    record: list[dict[str, Any]] = []
    for h in handles:
        try:
            res = h.get()
        except Exception as exc:  # one failed container never loses the others
            record.append({"error": f"{type(exc).__name__}: {exc}"})
            print("failed:", exc, flush=True)
            continue
        dest = run / "predictions" / res["system"] / res["executor"]
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(res.pop("tar")), mode="r:gz") as tf:
            tf.extractall(dest, filter="data")
        (dest / "modal.json").write_text(json.dumps(res, indent=2))
        record.append(
            {k: v for k, v in res.items() if k != "runs"}
            | {"rc": [r["rc"] for r in res["runs"]], "seconds": [r["seconds"] for r in res["runs"]]}
        )
        print("done", res["system"], res["executor"], [r["rc"] for r in res["runs"]], flush=True)
    (run / "predictions").mkdir(parents=True, exist_ok=True)
    (run / "predictions" / "modal.json").write_text(
        json.dumps(
            {
                "gpu": GPU,
                "boltz_image": "pip " + BENCH_ENV.get("BENCH_BOLTZ_PIP", ""),
                "diffdock_image": DD_REF,
                "seeds": seeds,
                "jobs": record,
            },
            indent=2,
        )
    )
