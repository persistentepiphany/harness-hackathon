"""Runs `pah doctor --profile modal` inside a Modal container.

    modal run deploy/modal/doctor_app.py

Requires MODAL_TOKEN_ID and MODAL_TOKEN_SECRET (or ~/.modal.toml). The image installs the
same extras as pyproject.toml and the same conda tools as environment/conda.yml.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import modal

REPO = Path(__file__).resolve().parents[2]
REMOTE_REPO = "/root/harness"
EXTRAS = ("checks", "report", "mcp", "api", "modal")
IGNORE = [".venv", ".tools", "runs", "cache", ".git", "third_party/skills/*/.git", "**/__pycache__"]


def _pip_requirements() -> list[str]:
    meta = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]
    reqs = list(meta["dependencies"])
    for extra in EXTRAS:
        reqs += meta["optional-dependencies"][extra]
    return reqs


image = (
    modal.Image.micromamba(python_version="3.12")
    .apt_install("git", "curl")
    .micromamba_install(spec_file=str(REPO / "environment" / "conda.yml"))
    .uv_pip_install(*_pip_requirements())
    .add_local_dir(REPO, REMOTE_REPO, copy=True, ignore=IGNORE)
    .run_commands(f"pip install --no-deps -e {REMOTE_REPO}")
    .env({"PAH_CONFIG_DIR": f"{REMOTE_REPO}/configs"})
)

app = modal.App("pah-doctor", image=image)


@app.function(timeout=900, cpu=2.0, memory=4096)
def doctor() -> str:
    out = "/tmp/pah-doctor"
    proc = subprocess.Popen(
        ["pah", "doctor", "--profile", "modal", "--out", out],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=REMOTE_REPO,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="", flush=True)
    proc.wait()
    return Path(out, "doctor_report.json").read_text()


@app.local_entrypoint()
def main() -> None:
    report = json.loads(doctor.remote())
    target = REPO / "runs" / report["run_id"]
    target.mkdir(parents=True, exist_ok=True)
    (target / "doctor_report.json").write_text(json.dumps(report, indent=2))
    print(f"report: {target / 'doctor_report.json'}", file=sys.stderr)
