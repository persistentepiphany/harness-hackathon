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
    # cuEquivariance kernels compile at first use (triton), which needs a C toolchain.
    .apt_install("build-essential")
    .run_commands(*_steps)
    .env({"PATH": "/opt/executor/bin:" + SYSTEM_PATH, "BOLTZ_CACHE": "/weights/boltz", **BENCH_ENV})
)
diffdock_image = modal.Image.from_registry(DD_REF, add_python="3.11").env(
    {"TORCH_HOME": "/weights/torch", "HOME": "/weights/home", **BENCH_ENV}
)

weights = modal.Volume.from_name("pah-weights", create_if_missing=True)
results = modal.Volume.from_name("pah-bench-results", create_if_missing=True)
CHUNK = 1 << 18  # results come back in pieces small enough to travel inline over the API
app = modal.App("pah-perturbation-bench")


def run_config(run: Path) -> dict[str, Any]:
    """The run's own copy of the design when it has one (bench/run_pipeline.py writes it),
    otherwise bench/config/targets.yaml."""
    import yaml

    own = run / "config" / "targets.yaml"
    return dict(
        yaml.safe_load((own if own.is_file() else REPO / "bench/config/targets.yaml").read_text())
    )


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


def _tar(root: Path, name: str) -> dict[str, Any]:
    """Packs a work directory into the results volume; returns its volume path and size."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for p in sorted(root.rglob("*")):
            if p.is_file() and "processed" not in p.parts:
                tf.add(p, arcname=str(p.relative_to(root)))
    data = buf.getvalue()
    dest = Path("/results") / f"{name}.tar.gz"
    dest.write_bytes(data)
    results.commit()
    return {"path": str(dest), "bytes": len(data)}


def _finish(meta: dict[str, Any], work: Path) -> dict[str, Any]:
    """Writes the tarball and the job metadata to the results volume. The local side reads both
    from the volume, so a lost return value loses nothing."""
    name = f"{meta['system']}_{meta['executor']}"
    meta["tar"] = _tar(work, name)
    Path(f"/results/{name}.json").write_text(json.dumps(meta, indent=2))
    results.commit()
    return {"system": meta["system"], "executor": meta["executor"], "tar": meta["tar"]}


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


@app.function(
    image=boltz_image, gpu=GPU, timeout=3600, volumes={"/weights": weights, "/results": results}
)
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
    meta = {
        "system": system,
        "executor": "boltz2",
        "version": BENCH_ENV.get("BENCH_BOLTZ_VERSION"),
        "runs": runs,
        "gpu": _gpu(),
        "env": _env(),
    }
    return _finish(meta, work)


@app.function(
    image=diffdock_image, gpu=GPU, timeout=3600, volumes={"/weights": weights, "/results": results}
)
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
    meta = {
        "system": system,
        "executor": "diffdock",
        "version": BENCH_ENV.get("BENCH_DD_VERSION"),
        "image": DD_REF,
        "runs": runs,
        "gpu": _gpu(),
        "env": _env(),
    }
    return _finish(meta, work)


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


@app.function(timeout=600, volumes={"/results": results})
def read_chunk(path: str, start: int) -> bytes:
    results.reload()
    with Path(path).open("rb") as fh:
        fh.seek(start)
        return fh.read(CHUNK)


def _download(info: dict[str, Any]) -> bytes:
    parts = [read_chunk.remote(info["path"], start) for start in range(0, info["bytes"], CHUNK)]
    data = b"".join(parts)
    if len(data) != info["bytes"]:
        raise RuntimeError(f"{info['path']}: got {len(data)} of {info['bytes']} bytes")
    return data


def fetch(run: Path, systems: list[str], executors: str) -> list[dict[str, Any]]:
    """Downloads each job's metadata and tarball from the results volume and unpacks it."""
    record: list[dict[str, Any]] = []
    for system in systems:
        for executor in executors.split(","):
            name = f"{system}_{executor}"
            try:
                try:
                    meta = json.loads(_download_path(f"/results/{name}.json"))
                except Exception:  # jobs from before metadata was written to the volume
                    path = f"/results/{name}.tar.gz"
                    meta = {
                        "system": system,
                        "executor": executor,
                        "runs": [],
                        "tar": {"path": path, "bytes": file_size.remote(path)},
                        "note": "job metadata not on the volume; commands and exit codes "
                        "are in the launcher log",
                    }
                data = _download(meta["tar"])
            except Exception as exc:  # one missing job never loses the others
                record.append(
                    {
                        "system": system,
                        "executor": executor,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                print("failed:", name, exc, flush=True)
                continue
            dest = run / "predictions" / system / executor
            dest.mkdir(parents=True, exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                tf.extractall(dest, filter="data")
            (dest / "modal.json").write_text(json.dumps(meta, indent=2))
            rcs = [r["rc"] for r in meta["runs"]]
            record.append(
                {k: v for k, v in meta.items() if k != "runs"}
                | {"rc": rcs, "seconds": [r["seconds"] for r in meta["runs"]]}
            )
            print("done", system, executor, rcs, flush=True)
    return record


@app.function(timeout=600, volumes={"/results": results})
def file_size(path: str) -> int:
    results.reload()
    return Path(path).stat().st_size


def _download_path(path: str) -> bytes:
    return _download({"path": path, "bytes": file_size.remote(path)})


@app.local_entrypoint()
def fetch_all(run_id: str, executors: str = "boltz2,diffdock") -> None:
    run = REPO / "bench" / "runs" / run_id
    systems = sorted(p.parent.name for p in (run / "prep").glob("*/boltz.yaml"))
    record = fetch(run, systems, executors)
    (run / "predictions" / f"fetch_{executors.replace(',', '_')}.json").write_text(
        json.dumps(record, indent=2)
    )


@app.local_entrypoint()
def probe() -> None:
    for fn in (probe_boltz, probe_diffdock):
        res = fn.remote()
        print(json.dumps(res, indent=2)[:3000])


@app.local_entrypoint()
def predict_all(run_id: str, only: str = "", executors: str = "boltz2,diffdock") -> None:

    run = REPO / "bench" / "runs" / run_id
    prep = run / "prep"
    cfg = run_config(run)
    seeds = list(cfg["seeds"])
    systems = sorted(p.parent.name for p in prep.glob("*/boltz.yaml"))
    if only:
        systems = [s for s in systems if s in only.split(",")]
    handles = []
    for s in systems:
        d = prep / s
        if "boltz2" in executors:
            handles.append(boltz_predict.spawn(s, (d / "boltz.yaml").read_text(), seeds))
        if "diffdock" in executors:
            handles.append(
                diffdock_predict.spawn(
                    s,
                    (d / "rec.pdb").read_bytes(),
                    (d / "ligand.smi").read_text().strip(),
                    seeds,
                    int(cfg["diffdock_samples"]),
                )
            )
    for h in handles:
        try:
            h.get()
        except Exception as exc:  # the volume copy is read below either way
            print("return value not received:", type(exc).__name__, exc, flush=True)
    record = fetch(run, systems, executors)
    (run / "predictions").mkdir(parents=True, exist_ok=True)
    (run / "predictions" / f"modal_{executors.replace(',', '_')}.json").write_text(
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
