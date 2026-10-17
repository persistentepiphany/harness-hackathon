#!/bin/bash --login
# Slurm array over a manifest: line N holds the arguments of task N for `pah runtimes run`.
#
#   manifest.txt:
#     boltz2 /scratch/.../runs/b2-0001 --param input=/scratch/.../in/0001.yaml
#     boltz2 /scratch/.../runs/b2-0002 --param input=/scratch/.../in/0002.yaml
#   sbatch --array=1-$(wc -l < manifest.txt)%16 deploy/csf3/executor_array.sbatch manifest.txt
#
# Partition and GPU request syntax are unverified here; confirm with `sinfo -s`.
#SBATCH --job-name=pah-exec-array
#SBATCH --partition=gpu_l40s
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
#SBATCH --output=pah-exec-%A_%a.out

set -euo pipefail
manifest="${1:?usage: $0 <manifest>}"
line="$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$manifest")"
[ -n "$line" ] || { echo "no line ${SLURM_ARRAY_TASK_ID} in $manifest" >&2; exit 2; }
source "${PAH_REPO:-$HOME/harness-hackathon}/deploy/csf3/env.sh"
export MODEL_OPT_JIT_ROOT="${MODEL_OPT_JIT_ROOT:-$PAH_ROOT/jit}"
mkdir -p "$MODEL_OPT_JIT_ROOT"
read -r -a args <<< "$line"
executor="${args[0]}"; out="${args[1]}"
pah runtimes run "$executor" --profile csf3 --out "$out" "${args[@]:2}"
