#!/bin/bash --login
# Runs one executor on a CSF3 GPU node through Apptainer. The kit is used when it can engage on
# the allocated card, otherwise stock runs and runtime_record.json says why.
#
#   sbatch deploy/csf3/executor.sbatch boltz2 $PAH_ROOT/runs/b2-001 --param input=$PWD/x.yaml
#   sbatch deploy/csf3/executor.sbatch chai1 $PAH_ROOT/runs/c1-001 --param input=$PWD/x.fasta --mode exact
#
# Images and weights must exist first (login node): deploy/csf3/prepare_executor.sh <executor>.
# Partition and GPU request syntax are unverified here; confirm with `sinfo -s` and override with
# `sbatch -p <partition> --gres=gpu:<n>`.
#SBATCH --job-name=pah-exec
#SBATCH --partition=gpu_l40s
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
#SBATCH --output=pah-exec-%j.out

set -euo pipefail
[ $# -ge 2 ] || { echo "usage: $0 <executor> <out_dir> [pah runtimes run options]" >&2; exit 2; }
source "${PAH_REPO:-$HOME/harness-hackathon}/deploy/csf3/env.sh"
executor="$1"; out="$2"; shift 2
export MODEL_OPT_JIT_ROOT="${MODEL_OPT_JIT_ROOT:-$PAH_ROOT/jit}"
mkdir -p "$MODEL_OPT_JIT_ROOT"
nvidia-smi --query-gpu=index,name,compute_cap,memory.total,driver_version --format=csv,noheader || true
pah runtimes run "$executor" --profile csf3 --out "$out" "$@"
