#!/usr/bin/env bash
# Record one take: record.sh <version> [warm] [press|page]
# Fills record.tpl.js and runs it with playwright-cli run-code in session "va2".
set -euo pipefail
V="$1"; WARM="${2:-false}"; TYPEMODE="${3:-press}"
A=/home/user/harness-hackathon/out/videos/a2
W=$A/work
D=$W/$V
mkdir -p "$D"
/home/user/harness-hackathon/.venv/bin/python - "$W" "$D" "$WARM" "$TYPEMODE" <<'PY'
import json, sys, pathlib
w, d, warm, mode = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3], sys.argv[4]
src = (w / "record.tpl.js").read_text()
caps = json.loads((w / "captions.json").read_text())
src = (src.replace("__BASE__", "http://127.0.0.1:3302")
          .replace("__OUT__", str(d / "raw.webm"))
          .replace("__ASSETS__", str(w / "assets") + "/")
          .replace("__WARM__", "true" if warm == "warm" else "false")
          .replace("__TYPEMODE__", mode)
          .replace("__CAPTIONS__", json.dumps(caps, ensure_ascii=False)))
(d / "record.js").write_text(src)
PY
cd /home/user/harness-hackathon
# fresh browser per take, so no overlay or state from an earlier take survives
npx --no-install playwright-cli -s=va2 close >/dev/null 2>&1 || true
npx --no-install playwright-cli -s=va2 open --config=out/videos/a2/work/cli.config.json about:blank >/dev/null 2>&1
npx --no-install playwright-cli -s=va2 run-code --filename="$D/record.js" > "$D/run.log" 2>&1 || true
/home/user/harness-hackathon/.venv/bin/python - "$D" <<'PY'
import json, sys, pathlib
d = pathlib.Path(sys.argv[1])
lines = (d / "run.log").read_text().splitlines()
try:
    i = lines.index("### Result")
except ValueError:
    print("no result; see", d / "run.log"); print("\n".join(lines[:40])); sys.exit(1)
res = json.loads(json.loads(lines[i + 1]))
(d / "events.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
print("events:", len(res["ev"] or []), "captions:", len(res["caps"]), "job:", res.get("myId"), "error:", res.get("error"))
PY
ffprobe -v error -show_entries format=duration -of csv=p=0 "$D/raw.webm"
