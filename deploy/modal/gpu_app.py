"""GPU executors for web UI runs on Modal: one app per executor, `pah-gpu-<executor>`.

    PAH_GPU_EXECUTOR=boltz2 modal deploy deploy/modal/gpu_app.py   # one app
    python deploy/modal/gpu_app.py --deploy boltz2,diffdock         # several, one app each
    python deploy/modal/gpu_app.py --deploy all                     # every modal route
    python deploy/modal/gpu_app.py --plan                           # route per executor

The image comes from configs/runtimes.yaml. When the executor has an optimisation kit and the kit
checkout exists (`pah runtimes kits fetch` puts it in .tools/accel), the image is the kit's own
Dockerfile and the run tries the kit mode from configs/accel.yaml first. A kit that does not engage
(exit code `not_active_exit_code`) is rerun as stock in the same image (kit mode `off`), and the
reason is returned as `routeNote`. Executors without a kit, or deployed without the checkout, run
the stock route (pip venv, binary or upstream image) and say why in `routeNote`.

Functions in each app:
    predict(run_id, request)        runs the executor; returns the execution record
    setup()                         fills the weights directory on `pah-weights`
    probe()                         GPU, route and tool entry point, without a prediction
    list_outputs(run_id)            files written for a run: [{path, bytes, sha256}]
    read_batch(items)               byte ranges of those files, small enough to return inline

`request` is built by pah.webui.execute from the run manifest:
    {"files": {name: text}, "params": {placeholder: value}, "seeds": [int], "name": str}
Values in `params` that name a key of `files` become the path of that file in the work directory.
Outputs land on the `pah-predictions` volume at /<run_id>/<executor>/ in the layout the harness
parser reads (rules in configs/dispatch.yaml `collect`), with execution.json beside them. Progress
goes to the Modal Dict `pah-gpu-progress` under "<run_id>/<executor>" as it changes.

Requires MODAL_TOKEN_ID and MODAL_TOKEN_SECRET (or ~/.modal.toml).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import modal

SYSTEM_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
OUT_ROOT = Path("/out")
WEIGHTS_ROOT = Path("/weights")
WORK_ROOT = Path("/tmp/pah-gpu")
ENV_PREFIX = "PAH_GPU_"


# --------------------------------------------------------------------------- definition (local)


def _definition(executor: str) -> dict[str, Any]:
    """Everything the container needs, resolved from configs/ on the machine that deploys."""
    import yaml

    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "src"))
    from pah.runtimes.registry import load_accel, load_runtimes

    reg = load_runtimes(repo / "configs")
    accel = load_accel(repo / "configs")
    dispatch = yaml.safe_load((repo / "configs" / "dispatch.yaml").read_text())
    spec = dict(dispatch["executors"][executor])
    rt = reg.get(executor)
    kits = repo / ".tools" / "accel"
    route, note = "stock", None
    if rt.accel is not None:
        dockerfile = kits / reg.kit_defaults.dockerfile.format(kit=rt.accel.kit)
        if dockerfile.is_file():
            route = "kit"
        else:
            note = (
                f"kit {rt.accel.kit} not available in this deployment "
                f"({dockerfile.relative_to(repo)} missing; run `pah runtimes kits fetch` first)"
            )
    else:
        note = rt.accel_note or f"no optimisation kit is published for {executor}"
    if route == "stock" and rt.native is None:
        raise SystemExit(f"{executor}: no stock route and no kit image ({rt.native_note})")
    defaults = {**rt.defaults, **dict(spec.get("params") or {})}
    d: dict[str, Any] = {
        "executor": executor,
        "tool": rt.tool,
        "route": route,
        "route_note": note,
        "gpu": spec.get("gpu", "A100"),
        "timeout_s": int(spec.get("timeout_s", 3600)),
        "weights": str(WEIGHTS_ROOT / rt.weights_dir),
        "defaults": defaults,
        "extra": spec.get("extra") or {},
        "collect": spec.get("collect") or {},
        "kit_seeds": spec.get("kit_seeds", "per_call"),
        "commands": spec.get("commands") or {},
        "not_active_rc": accel.not_active_exit_code,
        "mode": accel.mode,
        "cards": [r.model_dump() for r in accel.cards.by_name],
        "progress_dict": dispatch["modal"]["progress_dict"],
        "outputs_volume": dispatch["modal"]["outputs_volume"],
        "weights_volume": dispatch["modal"]["weights_volume"],
        "app": dispatch["modal"]["app_prefix"] + executor.replace("_", "-"),
        "kits_dir": str(kits),
    }
    if rt.native is not None:
        n = rt.native
        d["stock"] = {
            "version": n.version,
            "command": list(n.command),
            "env": dict(n.env),
            "fetch_weights": list(n.fetch_weights) if n.fetch_weights else None,
            "workdir": n.image.workdir if n.image else None,
            "kind": n.kind,
        }
        if n.kind == "image" and n.image is not None and n.image.pull:
            d["stock"]["pull"] = n.image.pull.removeprefix("docker.io/")
        elif n.kind in ("pip", "binary") or (n.image is not None and n.image.recipe is not None):
            from pah.runtimes.images import native_steps

            base, steps = native_steps(reg, rt)
            d["stock"]["base"], d["stock"]["steps"] = base, steps
            d["stock"]["python"] = n.python or "3.11"
    if rt.accel is not None:
        a = rt.accel
        kit_dir = reg.kit_defaults.dir_in_image.format(kit=a.kit)
        d["kit"] = {
            "kit": a.kit,
            "stock": a.stock,
            "dir": kit_dir,
            "dockerfile": reg.kit_defaults.dockerfile.format(kit=a.kit),
            "command": list(a.command),
            "env": dict(a.env),
            "install_weights": list(a.install_weights or reg.kit_defaults.install_weights),
            "configs": list(a.configs),
        }
    return d


def _env(d: dict[str, Any]) -> dict[str, str]:
    # base64: Dockerfile ENV lines cannot carry arbitrary quotes
    container = {k: v for k, v in d.items() if k != "kits_dir"}
    blob = base64.b64encode(json.dumps(container).encode()).decode()
    return {f"{ENV_PREFIX}DEF": blob, "PYTHONUNBUFFERED": "1"}


def _jitcache_placeholder(kits: Path, kit: str) -> None:
    """An empty compile-cache tar, so the kit Dockerfile's optional `COPY _jitcache/<kit>-*-jit.tar`
    matches a file: Modal's builder refuses a COPY glob that matches nothing (Docker accepts it)."""
    import tarfile

    target = kits / "_jitcache" / f"{kit}-pah-empty-jit.tar"
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(target, "w"):
            pass


def _image(d: dict[str, Any]) -> modal.Image:
    env = _env(d)
    if d["route"] == "kit":
        kit = d["kit"]
        _jitcache_placeholder(Path(d["kits_dir"]), kit["kit"])
        return modal.Image.from_dockerfile(
            str(Path(d["kits_dir"]) / kit["dockerfile"]), context_dir=d["kits_dir"]
        ).env(env)
    stock = d["stock"]
    if "pull" in stock:
        workdir = stock.get("workdir") or "/"
        home_bin = str(Path(workdir).parent / "bin")  # micromamba in the DiffDock image
        return modal.Image.from_registry(stock["pull"], add_python="3.11").env(
            {**env, "PATH": f"{home_bin}:{SYSTEM_PATH}"}
        )
    return (
        modal.Image.from_registry(stock["base"], add_python=stock.get("python", "3.11"))
        # Triton compiles kernels at first use (cuEquivariance in Boltz), which needs a C toolchain.
        .apt_install("build-essential")
        .run_commands(*stock["steps"])
        .env({**env, "PATH": "/opt/executor/bin:" + SYSTEM_PATH})
    )


if modal.is_local():
    EXECUTOR = os.environ.get(f"{ENV_PREFIX}EXECUTOR", "boltz2")
    DEF = _definition(EXECUTOR)
    image = _image(DEF)
    io_image = modal.Image.debian_slim(python_version="3.12").env(_env(DEF))
else:
    DEF = json.loads(base64.b64decode(os.environ.get(f"{ENV_PREFIX}DEF", "")) or b"{}")
    EXECUTOR = str(DEF.get("executor", "unknown"))
    image = io_image = modal.Image.debian_slim()

weights = modal.Volume.from_name(DEF["weights_volume"], create_if_missing=True)
outputs = modal.Volume.from_name(DEF["outputs_volume"], create_if_missing=True)
progress = modal.Dict.from_name(DEF["progress_dict"], create_if_missing=True)
app = modal.App(DEF["app"])


# --------------------------------------------------------------------------- container side


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _gpu_name() -> str:
    proc = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""


def _card(gpu: str) -> str | None:
    for rule in DEF.get("cards", []):
        if rule["contains"] in gpu and rule["config"] in DEF.get("kit", {}).get("configs", []):
            return str(rule["config"])
    return None


def _fill(template: list[str], values: dict[str, Any]) -> list[str]:
    return [str(part).format(**values) for part in template]


class Job:
    """One predict call: work and output directories, progress and the execution record."""

    def __init__(self, run_id: str, request: dict[str, Any]) -> None:
        self.run_id = run_id
        self.request = request
        self.key = f"{run_id}/{EXECUTOR}"
        self.work = WORK_ROOT / run_id / EXECUTOR
        self.out = OUT_ROOT / run_id / EXECUTOR
        if self.out.exists():
            shutil.rmtree(self.out)
        self.work.mkdir(parents=True, exist_ok=True)
        self.out.mkdir(parents=True, exist_ok=True)
        self.seeds = [int(s) for s in request.get("seeds") or [0]]
        self.t0 = time.time()
        self.gpu = _gpu_name()
        self.state: dict[str, Any] = {
            "executor": EXECUTOR,
            "tool": DEF.get("tool"),
            "phase": "building",
            "route": DEF["route"],
            "routeNote": DEF.get("route_note"),
            "gpu": self.gpu or None,
            "requestedGpu": DEF.get("gpu"),
            "startedAt": _now(),
            "elapsedMs": 0,
            "seeds": [{"seed": s, "phase": "queued", "ms": None} for s in self.seeds],
            "message": "container started",
            "modal": {
                k: os.environ.get(k) for k in ("MODAL_IMAGE_ID", "MODAL_TASK_ID", "MODAL_REGION")
            },
        }
        self.runs: list[dict[str, Any]] = []
        self.lock = threading.Lock()
        self.push()

    def push(self, **changes: Any) -> None:
        with self.lock:
            self.state.update(changes)
            self.state["elapsedMs"] = int((time.time() - self.t0) * 1000)
            snapshot = json.loads(json.dumps(self.state))
        try:
            progress[self.key] = snapshot
        except Exception as exc:  # progress is best effort; the record is the return value
            print(f"progress write failed: {type(exc).__name__}: {exc}", flush=True)

    def seed_phase(self, seed: int, phase: str, ms: int | None = None) -> None:
        with self.lock:
            for row in self.state["seeds"]:
                if row["seed"] == seed:
                    row["phase"] = phase
                    if ms is not None:
                        row["ms"] = ms
        self.push()

    def run(
        self, argv: list[str], *, env: dict[str, str], cwd: str | None, seed: Any
    ) -> dict[str, Any]:
        print("+", shlex.join(argv), flush=True)
        t0 = time.time()
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            env={**os.environ, **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert proc.stdout is not None
        lines: list[str] = []
        for line in proc.stdout:
            print(line, end="", flush=True)
            lines.append(line)
            if len(lines) > 400:
                del lines[:200]
        rc = proc.wait()
        tail = "".join(lines)[-6000:]
        row = {
            "seed": seed,
            "argv": argv,
            "rc": rc,
            "seconds": round(time.time() - t0, 1),
            "tail": tail,
        }
        self.runs.append(row)
        return row

    def finish(
        self, status: str, message: str, files: list[dict[str, Any]], error: str | None
    ) -> dict[str, Any]:
        phase = "done" if status == "done" else "failed"
        self.push(phase=phase, message=message)
        record = {
            **self.state,
            "status": status,
            "error": error,
            "runId": self.run_id,
            "finishedAt": _now(),
            "runs": self.runs,
            "files": files,
            "version": DEF.get("stock", {}).get("version") if DEF.get("stock") else None,
            "kit": DEF.get("kit", {}).get("kit") if DEF.get("kit") else None,
            "kitStock": DEF.get("kit", {}).get("stock") if DEF.get("kit") else None,
        }
        (self.out / "execution.json").write_text(json.dumps(record, indent=2))
        outputs.commit()
        try:
            weights.commit()
        except Exception as exc:  # compile caches and downloads are kept when the commit works
            print(f"weights commit failed: {exc}", flush=True)
        # The full record (commands, exit codes, output tails, file digests) is execution.json;
        # the return value stays small so it never needs a blob transfer.
        return {k: v for k, v in record.items() if k not in ("runs", "files")} | {
            "files": len(files),
            "record": "execution.json",
        }


def _write_inputs(job: Job) -> dict[str, Any]:
    inputs = job.work / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    files = job.request.get("files") or {}
    for name, text in files.items():
        (inputs / name).write_text(text)
    values: dict[str, Any] = {**DEF.get("defaults", {}), **(job.request.get("params") or {})}
    for key, value in list(values.items()):
        if isinstance(value, str) and value in files:
            values[key] = str(inputs / value)
    values.setdefault("name", job.request.get("name", "complex"))
    values["weights"] = DEF["weights"]
    return values


def _collect(job: Job, mode: str, src: Path, seed: int, values: dict[str, Any]) -> int:
    """Copies the files matched by the `collect` rules for `mode` into the output layout."""
    count = 0
    for rule in DEF.get("collect", {}).get(mode, []):
        pattern = str(rule["from"]).format(**{**values, "seed": seed})
        dest = job.out / str(rule["to"]).format(**{**values, "seed": seed})
        for path in sorted(src.glob(pattern)):
            if not path.is_file() or "processed" in path.relative_to(src).parts:
                continue
            rename = rule.get("rename")
            name = str(rename).format(**{**values, "seed": seed}) if rename else path.name
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            count += 1
    return count


def _setup_weights(job: Job | None, mode: str) -> dict[str, Any] | None:
    """Kit weight install or stock fetch, once per weights directory and route."""
    wdir = Path(DEF["weights"])
    marker = wdir / f".pah-setup-{mode}"
    if marker.exists():
        return None
    wdir.mkdir(parents=True, exist_ok=True)
    values = {"weights": str(wdir), "kit_dir": DEF.get("kit", {}).get("dir", "")}
    argv = None
    if mode == "kit" and DEF.get("kit"):
        argv = _fill(DEF["kit"]["install_weights"], values)
        env = {k: v.format(**values) for k, v in DEF["kit"]["env"].items()}
        cwd = DEF["kit"]["dir"]
    elif DEF.get("stock") and DEF["stock"].get("fetch_weights"):
        argv = _fill(DEF["stock"]["fetch_weights"], values)
        env = {k: v.format(**values) for k, v in DEF["stock"]["env"].items()}
        cwd = DEF["stock"].get("workdir")
    if argv is None:
        return None
    if job is not None:
        job.push(message=f"weights: {shlex.join(argv)}")
    t0 = time.time()
    proc = subprocess.run(argv, env={**os.environ, **env}, cwd=cwd, capture_output=True, text=True)
    tail = (proc.stdout + proc.stderr)[-4000:]
    print(tail, flush=True)
    if proc.returncode == 0:
        marker.write_text(_now())
        weights.commit()
    return {
        "argv": argv,
        "rc": proc.returncode,
        "seconds": round(time.time() - t0, 1),
        "tail": tail,
    }


def _not_active_reason(tail: str) -> str:
    for line in tail.splitlines():
        if "NOT ACTIVE" in line:
            return line.strip()[:400]
    return tail.strip().splitlines()[-1][:400] if tail.strip() else "no output"


def _attempt(job: Job, mode: str, values: dict[str, Any]) -> tuple[bool, str]:
    """Runs every seed in one route mode (kit | off | stock). Returns (all seeds ok, last tail)."""
    if mode == "stock":
        stock = DEF["stock"]
        template = list(DEF.get("commands", {}).get("stock") or stock["command"])
        env_t, cwd = stock["env"], stock.get("workdir")
    else:
        kit = DEF["kit"]
        template = list(DEF.get("commands", {}).get(mode) or kit["command"])
        env_t, cwd = kit["env"], kit["dir"]
    extra = [str(x) for x in DEF.get("extra", {}).get(mode, [])]
    base = {
        **values,
        "kit_dir": DEF.get("kit", {}).get("dir", ""),
        "card": _card(job.gpu) or "",
        "mode": DEF["mode"] if mode == "kit" else "off",
    }
    env = {k: str(v).format(**base) for k, v in env_t.items()}
    if mode != "stock":
        env.setdefault("MODEL_OPT_JIT_ROOT", str(WEIGHTS_ROOT / "jit" / DEF["kit"]["kit"]))
    joined = mode == "kit" and DEF.get("kit_seeds") == "joined"
    groups = [job.seeds] if joined else [[s] for s in job.seeds]
    ok, tail = True, ""
    for group in groups:
        label = ",".join(map(str, group))
        out_dir = job.work / mode / f"seed_{label.replace(',', '_')}"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filled = {**base, "seed": label, "out_dir": str(out_dir)}
        argv = _fill(template, filled) + extra
        for s in group:
            job.seed_phase(s, "running")
        job.push(phase="running", message=f"{mode}: seed {label}")
        row = job.run(argv, env=env, cwd=cwd, seed=group if joined else group[0])
        tail = row["tail"]
        if row["rc"] == DEF["not_active_rc"] and mode == "kit":
            return False, tail
        for s in group:
            n = _collect(job, mode, out_dir, s, filled)
            good = row["rc"] == 0 and n > 0
            ms = int(row["seconds"] * 1000 / len(group))
            job.seed_phase(s, "done" if good else "failed", ms)
            ok = ok and good
    return ok, tail


def _probe_entry(mode: str) -> dict[str, Any]:
    if mode == "kit":
        cmd = [
            "bash",
            f"{DEF['kit']['dir']}/run.sh",
            "check",
            "--config",
            _card(_gpu_name()) or "",
            "--mode",
            DEF["mode"],
        ]
        cwd = DEF["kit"]["dir"]
        env = {k: v.format(weights=DEF["weights"]) for k, v in DEF["kit"]["env"].items()}
    else:
        tool = DEF["stock"]["command"][0]
        cmd = ["sh", "-c", f"command -v {shlex.quote(tool)} || ls {shlex.quote(tool)}"]
        cwd, env = DEF["stock"].get("workdir"), {}
    proc = subprocess.run(cmd, cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True)
    return {"argv": cmd, "rc": proc.returncode, "tail": (proc.stdout + proc.stderr)[-3000:]}


@app.function(
    image=image,
    gpu=DEF["gpu"],
    timeout=int(DEF["timeout_s"]),
    volumes={str(WEIGHTS_ROOT): weights, str(OUT_ROOT): outputs},
    # GPU time is billed while idle; one minute keeps a container for the next seed group only
    scaledown_window=60,
)
def predict(run_id: str, request: dict[str, Any]) -> dict[str, Any]:
    job = Job(run_id, request)
    try:
        values = _write_inputs(job)
        modes = ["kit", "off"] if DEF["route"] == "kit" else ["stock"]
        if DEF["route"] == "kit" and not _card(job.gpu):
            job.push(
                route="stock",
                routeNote=f"kit {DEF['kit']['kit']} has no card config for GPU {job.gpu!r}; "
                "ran stock (kit mode off) in the kit image",
            )
            modes = ["off"]
        setup = _setup_weights(job, "kit" if modes[0] in ("kit", "off") else "stock")
        if setup is not None:
            job.runs.append({"seed": None, **setup, "step": "weights"})
        ok, tail = False, ""
        for mode in modes:
            ok, tail = _attempt(job, mode, values)
            if mode == "kit" and not ok and job.runs and job.runs[-1]["rc"] == DEF["not_active_rc"]:
                job.push(
                    route="stock",
                    routeNote=f"kit {DEF['kit']['kit']} did not engage "
                    f"({_not_active_reason(tail)}); ran stock (kit mode off) in the kit image",
                )
                for row in job.state["seeds"]:
                    row["phase"] = "queued"
                continue
            if mode == "kit":
                job.push(route="kit", routeNote=f"kit {DEF['kit']['kit']} mode {DEF['mode']}")
            break
        files = _listing(job.out)
        if ok:
            return job.finish("done", f"{len(files)} files written", files, None)
        return job.finish("failed", "prediction failed", files, _not_active_reason(tail))
    except Exception as exc:  # the record says what failed; the caller turns it into an event
        return job.finish("failed", "error", _listing(job.out), f"{type(exc).__name__}: {exc}")


@app.function(
    image=image,
    timeout=int(DEF["timeout_s"]),
    volumes={str(WEIGHTS_ROOT): weights},
)
def setup() -> dict[str, Any]:
    mode = "kit" if DEF["route"] == "kit" else "stock"
    res = _setup_weights(None, mode)
    return res or {"rc": 0, "note": "weights already set up or nothing to fetch"}


@app.function(image=image, gpu=DEF["gpu"], timeout=900, volumes={str(WEIGHTS_ROOT): weights})
def probe() -> dict[str, Any]:
    gpu = _gpu_name()
    mode = "kit" if DEF["route"] == "kit" else "stock"
    return {
        "executor": EXECUTOR,
        "route": DEF["route"],
        "routeNote": DEF.get("route_note"),
        "gpu": gpu,
        "card": _card(gpu),
        "entry": _probe_entry(mode),
        "modal": {k: os.environ.get(k) for k in ("MODAL_IMAGE_ID", "MODAL_REGION")},
    }


def _listing(root: Path) -> list[dict[str, Any]]:
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rows.append(
                {
                    "path": p.relative_to(root).as_posix(),
                    "bytes": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                }
            )
    return rows


@app.function(image=io_image, timeout=600, volumes={str(OUT_ROOT): outputs})
def list_outputs(run_id: str) -> list[dict[str, Any]]:
    outputs.reload()
    return _listing(OUT_ROOT / run_id / EXECUTOR)


@app.function(image=io_image, timeout=600, volumes={str(OUT_ROOT): outputs})
def read_batch(run_id: str, items: list[tuple[str, int, int]]) -> list[bytes]:
    """Byte ranges (relative path, start, length) of files under /<run_id>/<executor>/."""
    outputs.reload()
    root = (OUT_ROOT / run_id / EXECUTOR).resolve()
    out: list[bytes] = []
    for rel, start, length in items:
        path = (root / rel).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"{rel}: outside the run's outputs")
        with path.open("rb") as fh:
            fh.seek(start)
            out.append(fh.read(length))
    return out


# --------------------------------------------------------------------------- deploy helpers (local)


def _modal_executors() -> list[str]:
    import yaml

    repo = Path(__file__).resolve().parents[2]
    data = yaml.safe_load((repo / "configs" / "dispatch.yaml").read_text())
    return [k for k, v in data["executors"].items() if v.get("route") == "modal"]


def _deploy(names: list[str], runner: Callable[[list[str], dict[str, str]], int]) -> dict[str, int]:
    """Deploys each executor as its own app; one failed build never stops the others."""
    results: dict[str, int] = {}
    for name in names:
        env = {**os.environ, f"{ENV_PREFIX}EXECUTOR": name}
        rc = runner([sys.executable, "-m", "modal", "deploy", __file__], env)
        results[name] = rc
        print(f"{name}: deploy exit {rc}", flush=True)
    return results


def _plan(names: list[str]) -> list[dict[str, Any]]:
    rows = []
    for name in names:
        d = _definition(name)
        rows.append(
            {
                "executor": name,
                "app": d["app"],
                "route": d["route"],
                "routeNote": d["route_note"],
                "gpu": d["gpu"],
            }
        )
    return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Deploy the pah GPU executor apps to Modal.")
    parser.add_argument("--deploy", default="", help="comma-separated executors, or all")
    parser.add_argument("--plan", action="store_true", help="print the route per executor")
    args = parser.parse_args()
    chosen = _modal_executors() if args.deploy in ("", "all") else args.deploy.split(",")
    if args.plan:
        print(json.dumps(_plan(chosen), indent=2))
    else:
        res = _deploy(chosen, lambda argv, env: subprocess.call(argv, env=env))
        print(json.dumps(res, indent=2))
        sys.exit(0 if all(rc == 0 for rc in res.values()) else 1)
