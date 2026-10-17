"""Print a take's notes, captions and main events in seconds from the start."""

import json
import sys
from pathlib import Path

d = json.loads(Path(sys.argv[1]).read_text())
t0 = d["pageT0"]
rows = [(t, "NOTE " + k + (" " + str(v)[:80] if v else "")) for t, k, v in d["notes"]]
rows += [(t, "CAP  " + x) for t, x in d["caps"]]
rows += [
    (t, "EV   " + k + " " + json.dumps(v)[:90])
    for t, k, v in (d["ev"] or [])
    if k in ("route", "pointerdown", "status")
]
for t, s in sorted(rows):
    print(f"{(t - t0) / 1000:7.2f}  {s[:140]}")
print("error:", d.get("error"))
