#!/bin/bash --login
# Runs `pah doctor` on a CSF3 compute node. Compare with a login-node run to see
# which sources compute nodes can reach directly.
#   login node:   source deploy/csf3/env.sh && pah doctor --profile csf3
#   compute node: sbatch deploy/csf3/doctor.sbatch
# Partition name is unverified here; confirm with `sinfo -s`.
#SBATCH --job-name=pah-doctor
#SBATCH --partition=serial
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:15:00
#SBATCH --output=pah-doctor-%j.out

set -euo pipefail
source "${PAH_REPO:-$HOME/harness-hackathon}/deploy/csf3/env.sh"
pah doctor --profile csf3 --out "$PAH_ROOT/runs/doctor-compute-${SLURM_JOB_ID}"
