"""Runs one executor on a Modal GPU, in its kit image by default.

    pah runtimes kits fetch                                   # kit images build from this checkout
    PAH_EXECUTOR=boltz2 modal run deploy/modal/executors_app.py --param input=inputs/x.yaml
    PAH_EXECUTOR=boltz2 modal run deploy/modal/executors_app.py::fetch_weights

Environment (read when the app is defined, so one deployment serves one executor):

    PAH_EXECUTOR      executor id from configs/runtimes.yaml (default boltz2)
    PAH_MODAL_GPU     Modal GPU type (default H100; the kits ship card configs for A100, H100, H200)
    PAH_MODAL_IMAGE   kit (default when the executor has a kit) or native

The kit image also serves stock as mode `off`, so `--accel stock` and the automatic fallback run
in the same pinned stack. Weights live in the `pah-weights` volume and run outputs in `pah-runs`.
Local files passed as `--param key=path` are uploaded and the parameter is rewritten to the
remote path. Requires MODAL_TOKEN_ID and MODAL_TOKEN_SECRET (or ~/.modal.toml).
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import uuid
from pathlib import Path

import modal

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pah.runtimes.images import native_image_ref, native_steps  # noqa: E402
from pah.runtimes.registry import load_runtimes  # noqa: E402

REMOTE_REPO = "/root/harness"
PAH = "/opt/pah/bin/pah"
SYSTEM_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
IGNORE = [".venv", ".tools", "runs", "cache", ".git", "third_party", "**/__pycache__"]

EXECUTOR = os.environ.get("PAH_EXECUTOR", "boltz2")
GPU = os.environ.get("PAH_MODAL_GPU", "H100")
REG = load_runtimes(REPO / "configs")
RT = REG.get(EXECUTOR)
ROUTE = os.environ.get("PAH_MODAL_IMAGE", "kit" if RT.accel else "native")


def _base_image() -> modal.Image:
    if ROUTE == "kit":
        if RT.accel is None:
            raise SystemExit(f"{EXECUTOR}: no kit; set PAH_MODAL_IMAGE=native")
        kits = REPO / ".tools" / "accel"
        dockerfile = kits / REG.kit_defaults.dockerfile.format(kit=RT.accel.kit)
        if not dockerfile.is_file():
            raise SystemExit(f"{dockerfile} missing: run `pah runtimes kits fetch` first")
        return modal.Image.from_dockerfile(str(dockerfile), context_dir=str(kits))
    native = RT.native
    if native is None:
        raise SystemExit(f"{EXECUTOR}: {RT.native_note}")
    if native.image is not None and native.image.pull:
        return modal.Image.from_registry(native.image.pull.removeprefix("docker.io/"))
    if native.image is not None and native.image.build is not None:
        src = REPO / ".tools" / "images" / "src" / EXECUTOR
        if not src.is_dir():
            b = native.image.build
            raise SystemExit(f"clone {b.git} at {b.ref} into {src} first")
        return modal.Image.from_dockerfile(
            str(src / native.image.build.dockerfile), context_dir=str(src)
        )
    base, steps = native_steps(REG, RT)
    return (
        modal.Image.from_registry(base, add_python="3.12")
        .run_commands(*steps)
        .env({"PATH": "/opt/executor/bin:" + SYSTEM_PATH})
    )


# The harness gets its own venv so the executor's pinned stack is left as built.
image = (
    _base_image()
    .add_local_dir(REPO, REMOTE_REPO, copy=True, ignore=IGNORE)
    .run_commands(
        "python3 -m pip install --no-cache-dir --target /opt/uvpkg uv==0.9.5",
        "/opt/uvpkg/bin/uv venv --python 3.12 /opt/pah",
        f"/opt/uvpkg/bin/uv pip install --python /opt/pah/bin/python -e {REMOTE_REPO}",
    )
    .env({"PAH_CONFIG_DIR": f"{REMOTE_REPO}/configs"})
)

weights = modal.Volume.from_name("pah-weights", create_if_missing=True)
runs = modal.Volume.from_name("pah-runs", create_if_missing=True)
app = modal.App(f"pah-{EXECUTOR.replace('_', '-')}", image=image)
VOLUMES: dict[str | os.PathLike[str], modal.Volume] = {"/weights": weights, "/runs": runs}


def _stream(argv: list[str]) -> int:
    print("+", shlex.join(argv), flush=True)
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="", flush=True)
    return proc.wait()


@app.function(gpu=GPU, timeout=4 * 3600, volumes=VOLUMES)
def run(
    params: dict[str, str],
    uploads: dict[str, tuple[str, bytes]],
    extra: list[str],
    accel: str | None,
    mode: str | None,
    name: str,
) -> dict[str, object]:
    out = Path("/runs") / name
    inputs = out / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    for key, (filename, data) in uploads.items():
        target = inputs / filename
        target.write_bytes(data)
        params[key] = str(target)
    argv = [PAH, "runtimes", "run", EXECUTOR, "--profile", "modal", "--out", str(out)]
    for key, value in params.items():
        argv += ["--param", f"{key}={value}"]
    if accel:
        argv += ["--accel", accel]
    if mode:
        argv += ["--mode", mode]
    if extra:
        argv += ["--", *extra]
    rc = _stream(argv)
    runs.commit()
    record = out / "runtime_record.json"
    return {"exit_code": rc, "record": json.loads(record.read_text()) if record.exists() else None}


@app.function(timeout=3 * 3600, volumes=VOLUMES)
def fetch_weights() -> int:
    rc = _stream([PAH, "runtimes", "weights", EXECUTOR, "--profile", "modal"])
    weights.commit()
    return rc


@app.local_entrypoint()
def main(
    param: str = "",
    extra: str = "",
    accel: str = "",
    mode: str = "",
) -> None:
    """--param 'input=a.yaml,seed=1' --extra '--recycling_steps 3' --accel kit --mode exact"""
    params: dict[str, str] = {}
    uploads: dict[str, tuple[str, bytes]] = {}
    for item in filter(None, param.split(",")):
        key, _, value = item.partition("=")
        path = Path(value).expanduser()
        if path.is_file():
            uploads[key] = (path.name, path.read_bytes())
        else:
            params[key] = value
    name = f"{EXECUTOR}-{uuid.uuid4().hex[:8]}"
    result = run.remote(params, uploads, shlex.split(extra), accel or None, mode or None, name)
    target = REPO / "runs" / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "runtime_record.json").write_text(json.dumps(result["record"], indent=2))
    print(f"exit {result['exit_code']}; record: {target / 'runtime_record.json'}", file=sys.stderr)
    print(f"outputs: modal volume get pah-runs {name} {target}", file=sys.stderr)


if __name__ == "__main__":
    print(
        f"image for {EXECUTOR}: route={ROUTE} ref={native_image_ref(RT) if RT.native else RT.accel}"
    )
