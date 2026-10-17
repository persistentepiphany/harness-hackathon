#!/usr/bin/env bash
# Prepares one executor on the CSF3 login node: kits checkout, stock image, weights.
#   deploy/csf3/prepare_executor.sh boltz2
#
# Kit images are converted from a Docker image (the kits' apptainer.def reads the local Docker
# daemon), and CSF3 has no Docker. Build them on any Docker host and copy the .sif over:
#   docker host:  pah runtimes kits fetch && pah runtimes build boltz2 --target apptainer
#                 scp .tools/images/boltz2-kit.sif csf3:~/scratch/pah/images/
# Stock images build here without Docker (`apptainer build --fakeroot` from a rendered
# definition, or `docker://` pulls), and the weights are fetched here because compute nodes may
# have no outbound network.
set -euo pipefail
executor="${1:?usage: $0 <executor>}"
source "${PAH_REPO:-$HOME/harness-hackathon}/deploy/csf3/env.sh"
mkdir -p "$PAH_ROOT/images" "$PAH_ROOT/weights"

pah runtimes kits fetch --profile csf3
if ! pah runtimes build "$executor" --route native --target apptainer --profile csf3; then
  echo "[prepare] no stock image for $executor here (kit image only, or upstream needs Docker)" >&2
fi
pah runtimes weights "$executor" --profile csf3 || echo "[prepare] weights: see message above" >&2
pah runtimes hardware --profile csf3
