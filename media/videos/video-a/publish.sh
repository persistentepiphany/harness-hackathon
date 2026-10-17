#!/usr/bin/env bash
# Copy one built version to the deliverable names: publish.sh <version>
set -euo pipefail
V="$1"
A=/home/user/harness-hackathon/out/videos/a
D=$A/work/$V
M=/home/user/harness-hackathon/media/videos
cp "$D/demo-a.mp4" "$A/demo-a.mp4"
cp "$D/demo-a.webm" "$A/demo-a.webm"
cp "$D/demo-a.srt" "$A/demo-a.srt"
cp "$D/mix.wav" "$A/mix.wav"
mkdir -p "$M"
cp "$D/demo-a.mp4" "$M/demo-a.mp4"
cp "$D/demo-a.srt" "$M/demo-a.srt"
ls -la "$A" "$M"
