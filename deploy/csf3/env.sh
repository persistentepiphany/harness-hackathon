#!/usr/bin/env bash
# Source on CSF3 (login or compute node): `source deploy/csf3/env.sh`
# Module names are unverified here; confirm with `module avail`.
export PAH_ROOT="${PAH_ROOT:-$HOME/scratch/pah}"
export PAH_REPO="${PAH_REPO:-$HOME/harness-hackathon}"
export PAH_CONFIG_DIR="$PAH_REPO/configs"
module load tools/apptainer 2>/dev/null || echo "[env] apptainer module not loaded"
export PATH="$PAH_ROOT/.venv/bin:$PAH_ROOT/.tools/conda-env/bin:$PATH"
mkdir -p "$PAH_ROOT"/{cache,runs,images}
