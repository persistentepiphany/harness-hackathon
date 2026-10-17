#!/usr/bin/env bash
# Sets up the harness on the end user's host: Python venv, conda tool prefix, skill
# submodules, then `pah fetch` for binaries and datasets that PyPI and conda do not carry.
# Each step runs on its own. A failed step is reported and the remaining steps still run.
#
# Usage: scripts/setup_env.sh [prefix_dir] [profile]
#   prefix_dir  where .venv and .tools are created (default: repository root)
#   profile     profile passed to `pah fetch` (default: local)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${1:-$ROOT}"
PROFILE="${2:-local}"
VENV="$PREFIX/.venv"
TOOLS="$PREFIX/.tools"
FAILED=()

step() {
  local name="$1"
  shift
  echo "[setup] $name"
  if "$@"; then
    echo "[setup] $name: ok"
  else
    echo "[setup] $name: failed (exit $?)" >&2
    FAILED+=("$name")
  fi
}

python_env() {
  command -v uv >/dev/null || { echo "uv not found: https://docs.astral.sh/uv/" >&2; return 1; }
  uv venv --python 3.12 "$VENV" && uv pip install --python "$VENV/bin/python" -e "$ROOT[all,dev]"
}

conda_env() {
  mkdir -p "$TOOLS/bin"
  if [ ! -x "$TOOLS/bin/micromamba" ]; then
    curl -fsSL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C "$TOOLS" bin/micromamba || return 1
  fi
  MAMBA_ROOT_PREFIX="$TOOLS/mamba" "$TOOLS/bin/micromamba" create -y -q \
    -p "$TOOLS/conda-env" -f "$ROOT/environment/conda.yml"
}

skills() {
  git -C "$ROOT" submodule update --init --depth 1
}

externals() {
  [ -x "$VENV/bin/pah" ] || { echo "pah not installed; skipping fetch" >&2; return 1; }
  "$VENV/bin/pah" fetch --profile "$PROFILE"
}

step "python venv ($VENV)" python_env
step "conda tools ($TOOLS/conda-env)" conda_env
step "skill submodules" skills
step "external assets (pah fetch)" externals

if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "[setup] completed with failures: ${FAILED[*]}" >&2
  echo "[setup] run '$VENV/bin/pah doctor' to see what is available" >&2
  exit 1
fi
echo "[setup] done. Run: $VENV/bin/pah doctor"
