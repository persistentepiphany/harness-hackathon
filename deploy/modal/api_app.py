"""Serves the harness HTTP API from one Modal container, with runs and cache on Volumes.

    modal deploy deploy/modal/api_app.py      # https://<workspace>--pah-api.<region>.modal.run
    python deploy/modal/api_app.py            # same, then prints the endpoint URL
    python deploy/modal/api_app.py --url      # prints the URL of the deployed endpoint

The app serves `pah.webui.settings:create_app_from_env` (`pah.interfaces.api:create_app` with the
`/ui` routes and CORS) for the `modal` profile. Runs started with `POST /runs` or `POST /ui/runs`
execute on threads in the same container, so live tails and background runs share
one process: `max_containers=1` with concurrent inputs. The `pah-runs` and `pah-cache` Volumes are
mounted at the profile's `runs_dir` and `cache_dir`, reloaded at container start and committed
after every write the service reports (`pah.webui.persistence`) and every `commit_interval_s`.

Settings come from the `modal.api` block of configs/profiles/modal.yaml. Environment read when the
app is defined (local side):

    PAH_CORS_ORIGINS  comma-separated origins; `*` matches any run of characters except `/`
                      (default: localhost:3000, https://*.vercel.app and the pah-web endpoint,
                      https://*--pah-web.modal.run or https://*--pah-web.*.modal.run)

Requires MODAL_TOKEN_ID and MODAL_TOKEN_SECRET (or ~/.modal.toml). Behind an HTTPS proxy the
client needs `python-socks` (`pip install 'modal[api-proxy-support]'`).
"""

from __future__ import annotations

import argparse
import atexit
import importlib
import os
import threading
import time
import tomllib
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

import modal
import yaml

REMOTE_REPO = "/root/harness"
# Inside the container this file is mounted at /root/api_app.py; the checkout is at REMOTE_REPO.
REPO = Path(__file__).resolve().parents[2] if modal.is_local() else Path(REMOTE_REPO)
PROFILE = "modal"
EXTRAS = ("checks", "report", "api")
# Compilers for the sdist-only checks (freesasa, DockQ); GL and X libraries that PyMOL and RDKit
# load even when they render off screen.
APT_PACKAGES = ("build-essential", "libgl1", "libglib2.0-0", "libxrender1", "libxext6", "curl")
IGNORE = [
    ".venv",
    ".tools",
    "runs",
    "cache",
    ".git",
    "third_party",
    "node_modules",
    # Modal's matcher applies a bare name at the top level only: nested copies need **/
    "**/node_modules",
    "out",
    "videos",
    "media",
    "bench",
    ".claude",
    ".playwright*",
    "**/.env*",
    "web",
    "deploy/modal/urls.json",
    "**/__pycache__",
    "**/.pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
]
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://*.vercel.app",
    "https://*--pah-web.modal.run",
    "https://*--pah-web.*.modal.run",
)
CORS_ORIGINS = os.environ.get("PAH_CORS_ORIGINS") or ",".join(DEFAULT_CORS_ORIGINS)
PERSISTENCE_HOOKS = ("pah.webui.persistence", "pah.service.persistence")


def _profile() -> dict[str, Any]:
    data = yaml.safe_load((REPO / "configs" / "profiles" / f"{PROFILE}.yaml").read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"configs/profiles/{PROFILE}.yaml: expected a mapping")
    return data


def _pip_requirements() -> list[str]:
    meta = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]
    reqs = list(meta["dependencies"])
    for extra in EXTRAS:
        reqs += meta["optional-dependencies"][extra]
    return reqs


class VolumeCommitter:
    """Commits Volumes shortly after a write is reported and every `interval_s` seconds.

    `request()` is what the persistence hook calls; it only sets a flag, so a write never waits
    on the network. A failed commit is printed and retried on the next cycle.
    """

    def __init__(
        self, volumes: Mapping[Any, Any], interval_s: float, min_gap_s: float = 1.0
    ) -> None:
        self._volumes = dict(volumes)
        self._interval_s = interval_s
        self._min_gap_s = min_gap_s
        self._dirty = threading.Event()
        self._lock = threading.Lock()
        self.commits = 0

    def request(self) -> None:
        self._dirty.set()

    def commit(self) -> None:
        with self._lock:
            for path, volume in self._volumes.items():
                try:
                    volume.commit()
                except Exception as exc:  # retried on the next cycle
                    print(f"pah-api: commit {path} failed: {type(exc).__name__}: {exc}", flush=True)
            self.commits += 1

    def reload(self) -> None:
        for path, volume in self._volumes.items():
            try:
                volume.reload()
            except Exception as exc:  # the mounted state at start is still usable
                print(f"pah-api: reload {path} failed: {type(exc).__name__}: {exc}", flush=True)

    def run_forever(self) -> None:
        while True:
            self._dirty.wait(self._interval_s)
            self._dirty.clear()
            self.commit()
            time.sleep(self._min_gap_s)

    def start(self) -> None:
        threading.Thread(target=self.run_forever, name="pah-volume-commit", daemon=True).start()
        atexit.register(self.commit)


def register_persist_hook(callback: Callable[[], object]) -> str | None:
    """Registers `callback` with the first persistence module that exists; its name or None."""
    for name in PERSISTENCE_HOOKS:
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        module.on_persist(callback)
        return name
    return None


PROFILE_DATA = _profile()
MODAL = PROFILE_DATA["modal"]
API = MODAL["api"]

# Conda-only tools from environment/conda.yml (OpenMM, PDBFixer, openmmforcefields and OpenFF for
# l4.minimisation_drift; cctbx MolProbity, reduce and probe for l4.molprobity; fpocket, Java, APBS)
# live in their own prefix, as locally (.tools/conda-env) and on CSF3. Checks find it through
# PAH_CONDA_PREFIX, which matches `conda_prefix` in configs/profiles/modal.yaml. The MolProbity
# reference data is installed by `pah fetch --only molprobity_data`; --strict fails the build when
# that asset fails, so a missing tool cannot pass silently.
CONDA_PREFIX = "/opt/conda"
CONDA_SPEC = "/tmp/pah-conda.yml"
MICROMAMBA_URL = "https://micro.mamba.pm/api/micromamba/linux-64/2.9.0"
MAMBA = "MAMBA_ROOT_PREFIX=/opt/mamba micromamba"
CONDA_APT = ("bzip2", "git")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(*APT_PACKAGES, *CONDA_APT)
    .add_local_file(REPO / "environment" / "conda.yml", CONDA_SPEC, copy=True)
    .run_commands(
        f"curl -fsSL {MICROMAMBA_URL} | tar -xj -C /usr/local bin/micromamba",
        f"{MAMBA} create -y -p {CONDA_PREFIX} -f {CONDA_SPEC}",
        f"{MAMBA} clean -a -y || true",  # cache cleanup only; its failure must not fail the image
    )
    .uv_pip_install(*_pip_requirements())
    .add_local_dir(REPO, REMOTE_REPO, copy=True, ignore=IGNORE)
    .run_commands(
        f"python -m pip install --no-cache-dir --no-deps -e {REMOTE_REPO}",
        f"cd {REMOTE_REPO} && PAH_CONFIG_DIR={REMOTE_REPO}/configs PAH_CONDA_PREFIX={CONDA_PREFIX} "
        f"pah fetch --profile {PROFILE} --only molprobity_data --strict",
    )
    .workdir(REMOTE_REPO)
    .env(
        {
            "PAH_CONFIG_DIR": f"{REMOTE_REPO}/configs",
            "PAH_PROFILE": PROFILE,
            "PAH_CONDA_PREFIX": CONDA_PREFIX,
            "MPLBACKEND": "Agg",
            "PYTHONUNBUFFERED": "1",
        }
    )
)

runs = modal.Volume.from_name(MODAL["volume_runs"], create_if_missing=True)
cache = modal.Volume.from_name(MODAL["volume_cache"], create_if_missing=True)
VOLUMES: dict[str | PurePosixPath, modal.Volume | modal.CloudBucketMount] = {
    PROFILE_DATA["runs_dir"]: runs,
    PROFILE_DATA["cache_dir"]: cache,
}

app = modal.App(API["app_name"], image=image)


@app.function(
    volumes=VOLUMES,
    cpu=float(API["cpu"]),
    memory=int(API["memory_mb"]),
    timeout=int(API["timeout_s"]),
    min_containers=0,
    max_containers=1,
    scaledown_window=int(API["scaledown_window_s"]),
    env={"PAH_CORS_ORIGINS": CORS_ORIGINS},
)
@modal.concurrent(max_inputs=int(API["max_inputs"]))
@modal.asgi_app(label=API["label"])
def api() -> Any:
    from pah.webui.settings import cors_config, cors_origins, create_app_from_env

    started = time.monotonic()
    committer = VolumeCommitter(VOLUMES, float(API["commit_interval_s"]))
    committer.reload()
    hook = register_persist_hook(committer.request)
    committer.start()
    # Profile from PAH_PROFILE, CORS from PAH_CORS_ORIGINS (one CORSMiddleware, `*` as regex).
    web_app = create_app_from_env()
    origins, origin_regex = cors_config(cors_origins())
    print(
        f"pah-api: profile={os.environ.get('PAH_PROFILE')} "
        f"persist_hook={hook or 'none (periodic commits only)'} "
        f"commit_interval_s={API['commit_interval_s']} cors={list(origins)} "
        f"regex={origin_regex} startup_s={time.monotonic() - started:.2f}",
        flush=True,
    )
    return web_app


def deployed_url() -> str:
    url = modal.Function.from_name(API["app_name"], "api").get_web_url()
    if not url:
        raise SystemExit(f"{API['app_name']}: no web URL; deploy the app first")
    return str(url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy pah-api to Modal and print its URL.")
    parser.add_argument("--url", action="store_true", help="only print the deployed URL")
    if not parser.parse_args().url:
        with modal.enable_output():
            app.deploy()
    print(deployed_url())
