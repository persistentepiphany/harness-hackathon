#!/usr/bin/env bash
# Copy one built version to the deliverable names: publish.sh <version>
set -euo pipefail
V="$1"
A=/home/user/harness-hackathon/out/videos/a2
D=$A/work/$V
M=/home/user/harness-hackathon/media/videos
cp "$D/demo-a2.mp4" "$A/demo-a2.mp4"
[ -f "$D/demo-a2.webm" ] && cp "$D/demo-a2.webm" "$A/demo-a2.webm"
cp "$D/demo-a2.srt" "$A/demo-a2.srt"
cp "$D/mix.wav" "$A/mix.wav"
mkdir -p "$M"
cp "$D/demo-a2.mp4" "$M/demo-a2.mp4"
cp "$D/demo-a2.srt" "$M/demo-a2.srt"
ls -la "$A" "$M"
