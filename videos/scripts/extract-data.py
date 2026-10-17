"""Copy the values film B shows out of the harness's own records into src/videos/demo-b/data/.

    python3 scripts/extract-data.py

Sources (all checked into the repository or produced by `pah serve`):
- web/tests/fixtures/live/ui-record-vina.json  UI record of run ui-vina (AutoDock Vina 1.2.7 on 3PTB)
- web/tests/fixtures/live/log-vina.json        its log lines (GET /ui/jobs/ui-vina/log?format=json)
- web/tests/fixtures/live/jobs.json            the Jobs list entries (ui-vina and ui-faulty)
- web/tests/fixtures/live/tools.json           the executor register (docking parameter labels, defaults)
- web/tests/fixtures/live/ui-record-faulty.json the run listed under ui-vina on the Jobs page
- web/lib/mock/data.ts                         prototype demo agent task (copied by hand into agent.json)

The film never computes a number: every value on screen comes from these files.
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIVE = ROOT / "web/tests/fixtures/live"
OUT = pathlib.Path(__file__).resolve().parents[1] / "src/videos/demo-b/data"


def main() -> None:
    record = json.loads((LIVE / "ui-record-vina.json").read_text())
    log = json.loads((LIVE / "log-vina.json").read_text())
    jobs = json.loads((LIVE / "jobs.json").read_text())
    job = next(j for j in jobs if j["id"] == "ui-vina")
    register = json.loads((LIVE / "tools.json").read_text())
    vina = next(t for t in register if t["id"] == "vina")
    reported = {p["key"]: p for p in record["docking"]["params"]}
    # ExecutorList rows: the record's value, else the register default marked as such (selectors/run.ts dockingParams)
    docking = []
    for p in vina["dockingParams"]:
        got = reported.get(p["key"])
        value = got["value"] if got else p.get("default")
        if value is not None:
            docking.append({"label": p["label"], "value": value, "unit": p.get("unit"), "isDefault": got is None})
    others = [
        {
            "id": j["id"],
            "name": j["name"],
            "tools": j["tools"],
            "verdict": j["verdict"],
            "elapsedMs": j["elapsedMs"],
            "layers": j["layers"],
        }
        for j in jobs
        if j["id"] in ("ui-faulty",)
    ]
    faulty = json.loads((LIVE / "ui-record-faulty.json").read_text())

    layers = []
    for layer in record["layers"]:
        layers.append(
            {
                "i": layer["i"],
                "key": layer["key"],
                "name": layer["name"],
                "question": layer["question"],
                "durationMs": layer.get("durationMs"),
                "counts": layer["counts"],
                "summary": layer.get("summary", []),
                "checks": [
                    {
                        k: c.get(k)
                        for k in ("id", "name", "tool", "gate", "result", "evidence", "ms", "threshold", "skipReason", "measurements", "thresholds")
                    }
                    for c in layer["checks"]
                ],
            }
        )

    # Run lines only (the report stage that follows writes renders for minutes; the film stops at run end).
    run_lines = []
    for line in log:
        run_lines.append({k: line.get(k) for k in ("seq", "t", "layer", "kind", "result", "plain", "text")})
        if line["kind"] == "run" and line["text"].startswith("run  end"):
            break

    out = {
        "_source": "web/tests/fixtures/live/ui-record-vina.json, log-vina.json, jobs.json (run ui-vina, 2026-10-17)",
        "id": record["id"],
        "harnessRunId": record["record"]["runId"],
        "createdAt": record["createdAt"],
        "task": record["task"],
        "taskName": record["taskName"],
        "claim": record["claim"],
        "inputs": record["inputs"],
        "tools": [{k: t.get(k) for k in ("id", "name", "version", "family", "ranBy")} for t in record["tools"]],
        "sources": [{k: s.get(k) for k in ("source", "sourceId", "accession", "release", "sha256", "url")} for s in record["sources"]],
        "layers": layers,
        "verdict": record["verdict"],
        "controls": record["controls"],
        "stats": {k: record["stats"].get(k) for k in ("seeds", "pairwise", "posebusters", "pose", "site", "interactions")},
        "toolVersions": record["record"]["toolVersions"],
        "pahVersion": record["record"]["pahVersion"],
        "startedAt": record["record"]["startedAt"],
        "finishedAt": record["record"]["finishedAt"],
        "job": job,
        "docking": docking,
        "otherJob": {
            "id": faulty["id"],
            "name": others[0]["name"] if others else "",
            "taskName": faulty["taskName"],
            "tools": [f"{t['name']} {t['version']}" for t in faulty["tools"]],
            "inputs": faulty["inputs"],
            "claim": faulty["claim"],
            "verdict": faulty["verdict"]["outcome"],
            "elapsedMs": others[0]["elapsedMs"] if others else None,
            "layers": [{"i": l["i"], "name": l["name"], "counts": l["counts"]} for l in faulty["layers"]],
        },
        "log": run_lines,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "run.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"run.json: {len(layers)} layers, {len(run_lines)} log lines")


if __name__ == "__main__":
    main()
