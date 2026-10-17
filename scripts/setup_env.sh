#!/usr/bin/env bash
# Creates the Python environment (.venv) and the conda tool prefix.
# Usage: scripts/setup_env.sh [prefix_dir]   (default: repository root)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${1:-$ROOT}"
VENV="$PREFIX/.venv"
TOOLS="$PREFIX/.tools"

command -v uv >/dev/null || { echo "uv not found: https://docs.astral.sh/uv/" >&2; exit 1; }

echo "[setup] python venv: $VENV"
uv venv --python 3.12 "$VENV"
uv pip install --python "$VENV/bin/python" -e "$ROOT[all,dev]"

echo "[setup] micromamba: $TOOLS/bin/micromamba"
mkdir -p "$TOOLS/bin"
if [ ! -x "$TOOLS/bin/micromamba" ]; then
  curl -sSL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C "$TOOLS" bin/micromamba
fi
export MAMBA_ROOT_PREFIX="$TOOLS/mamba"
"$TOOLS/bin/micromamba" create -y -q -p "$TOOLS/conda-env" -f "$ROOT/environment/conda.yml"

echo "[setup] skills submodules"
git -C "$ROOT" submodule update --init --depth 1

echo "[setup] done. Run: $VENV/bin/pah doctor"
